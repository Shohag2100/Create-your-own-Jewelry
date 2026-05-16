import json
import random
import jwt
import base64
import uuid
import os
from pathlib import Path
from datetime import datetime, timedelta
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from django.core.mail import send_mail
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from .models import OTP, Profile
from django.core.files.base import ContentFile
import logging

logger = logging.getLogger(__name__)


def _generate_otp():
    return f"{random.randint(0, 999999):06d}"


def _send_otp_email(email, code):
    subject = 'Your verification code'
    message = f'Your verification code is: {code}\nThis code expires in 10 minutes.'
    from_email = settings.EMAIL_FROM if hasattr(settings, 'EMAIL_FROM') else None
    send_mail(subject, message, from_email, [email], fail_silently=False)


def _create_jwt(user):
    payload = {
        'user_id': user.id,
        'email': user.email,
        'exp': datetime.utcnow() + timedelta(hours=1),
        'iat': datetime.utcnow(),
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')
    return token


def _decode_jwt(token):
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def _create_access_token(user):
    payload = {
        'user_id': user.id,
        'email': user.email,
        'exp': datetime.utcnow() + timedelta(hours=getattr(settings, 'JWT_EXPIRATION_HOURS', 1)),
        'iat': datetime.utcnow(),
        'type': 'access',
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')


def _create_refresh_token(user):
    payload = {
        'user_id': user.id,
        'email': user.email,
        'exp': datetime.utcnow() + timedelta(days=7),
        'iat': datetime.utcnow(),
        'type': 'refresh',
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')


def _create_tokens(user):
    access = _create_access_token(user)
    refresh = _create_refresh_token(user)
    return access, refresh


def _decode_and_validate(token, expected_type=None):
    payload = _decode_jwt(token)
    if not payload:
        return None
    if expected_type and payload.get('type') != expected_type:
        return None
    return payload


@csrf_exempt
def register(request):
    if request.method != 'POST':
        return JsonResponse({'detail': 'Method not allowed'}, status=405)
    # Support both JSON body and form-encoded POST data.
    content_type = request.META.get('CONTENT_TYPE', '')
    if 'application/json' in content_type:
        try:
            raw = request.body.decode('utf-8')
            if not raw:
                return JsonResponse({'detail': 'Empty request body'}, status=400)
            data = json.loads(raw)
        except json.JSONDecodeError:
            return JsonResponse({'detail': 'Invalid JSON body'}, status=400)
    else:
        # fallback to form data (e.g., application/x-www-form-urlencoded or multipart)
        data = request.POST.dict() if request.POST else {}
    full_name = data.get('full_name')
    email = data.get('email')
    password = data.get('password')
    confirm_password = data.get('confirm_password')

    if not full_name or not email or not password or not confirm_password:
        return JsonResponse({'detail': 'full_name, email, password and confirm_password are required'}, status=400)

    if password != confirm_password:
        return JsonResponse({'detail': 'Passwords do not match'}, status=400)

    existing = User.objects.filter(email=email).order_by('id')
    if existing.exists():
        # If the existing user's name matches the incoming name, treat as already-registered
        first = existing.first()
        parts = full_name.strip().split()
        first_name = parts[0]
        last_name = ' '.join(parts[1:]) if len(parts) > 1 else ''
        if first.first_name == first_name and first.last_name == last_name:
            return JsonResponse({'detail': 'User already registered'}, status=200)
        return JsonResponse({'detail': 'User with this email already exists'}, status=400)

    # Create a username from email local part and ensure uniqueness
    base_username = email.split('@')[0]
    username = base_username
    counter = 1
    while User.objects.filter(username=username).exists():
        username = f"{base_username}{counter}"
        counter += 1

    # Split full name into first and last name
    parts = full_name.strip().split()
    first_name = parts[0]
    last_name = ' '.join(parts[1:]) if len(parts) > 1 else ''

    user = User.objects.create_user(username=username, email=email, password=password)
    user.first_name = first_name
    user.last_name = last_name
    user.is_active = False
    user.save()

    code = _generate_otp()
    otp = OTP.objects.create(user=user, code=code)
    _send_otp_email(email, code)

    # Return OTP in response for testing (remove in production)
    return JsonResponse({'detail': 'User created, OTP sent to email', 'otp': code})


@csrf_exempt
def verify_otp(request):
    if request.method != 'POST':
        return JsonResponse({'detail': 'Method not allowed'}, status=405)

    data = json.loads(request.body.decode('utf-8'))
    email = data.get('email')
    code = data.get('otp')

    if not email or not code:
        return JsonResponse({'detail': 'email and otp required'}, status=400)

    # handle possible duplicate emails gracefully by selecting the first user
    users = User.objects.filter(email=email).order_by('id')
    if not users.exists():
        return JsonResponse({'detail': 'User not found'}, status=404)
    if users.count() > 1:
        logger.warning("verify_otp: multiple users found with email=%s, using first id=%s", email, users.first().id)
    user = users.first()
    otps = OTP.objects.filter(user=user, code=code, is_used=False).order_by('-created_at')
    if not otps.exists():
        return JsonResponse({'detail': 'Invalid code'}, status=400)

    otp = otps.first()
    if not otp.is_valid():
        return JsonResponse({'detail': 'Code expired or used'}, status=400)

    otp.is_used = True
    otp.save()
    user.is_active = True
    user.save()

    access, refresh = _create_tokens(user)
    return JsonResponse({'detail': 'verified', 'access_token': access, 'refresh_token': refresh})


@csrf_exempt
def resend_otp(request):
    if request.method != 'POST':
        return JsonResponse({'detail': 'Method not allowed'}, status=405)

    data = json.loads(request.body.decode('utf-8'))
    email = data.get('email')
    if not email:
        return JsonResponse({'detail': 'email required'}, status=400)

    users = User.objects.filter(email=email).order_by('id')
    if not users.exists():
        return JsonResponse({'detail': 'User not found'}, status=404)
    if users.count() > 1:
        logger.warning("resend_otp: multiple users found with email=%s, using first id=%s", email, users.first().id)
    user = users.first()
    if user.is_active:
        return JsonResponse({'detail': 'User already active'}, status=400)

    code = _generate_otp()
    otp = OTP.objects.create(user=user, code=code)
    _send_otp_email(email, code)
    # Return OTP in response for testing (remove in production)
    return JsonResponse({'detail': 'OTP resent', 'otp': code})


@csrf_exempt
def forgot_password(request):
    if request.method != 'POST':
        return JsonResponse({'detail': 'Method not allowed'}, status=405)
    try:
        data = json.loads(request.body.decode('utf-8'))
    except Exception:
        return JsonResponse({'detail': 'Invalid JSON'}, status=400)
    email = data.get('email')
    if not email:
        return JsonResponse({'detail': 'email required'}, status=400)

    users = User.objects.filter(email=email).order_by('id')
    if not users.exists():
        # Do not reveal whether email exists
        return JsonResponse({'detail': 'If an account exists, a reset code has been sent.'})
    user = users.first()
    # create OTP for password reset
    code = _generate_otp()
    otp = OTP.objects.create(user=user, code=code)
    try:
        _send_otp_email(email, code)
    except Exception:
        logger.exception('forgot_password: error sending email to %s', email)
    return JsonResponse({'detail': 'If an account exists, a reset code has been sent.'})


@csrf_exempt
def reset_password(request):
    if request.method != 'POST':
        return JsonResponse({'detail': 'Method not allowed'}, status=405)
    try:
        data = json.loads(request.body.decode('utf-8'))
    except Exception:
        return JsonResponse({'detail': 'Invalid JSON'}, status=400)
    email = data.get('email')
    code = data.get('otp')
    new_password = data.get('new_password')
    if not email or not code or not new_password:
        return JsonResponse({'detail': 'email, otp and new_password required'}, status=400)
    users = User.objects.filter(email=email).order_by('id')
    if not users.exists():
        return JsonResponse({'detail': 'Invalid code or email'}, status=400)
    user = users.first()
    otps = OTP.objects.filter(user=user, code=code, is_used=False).order_by('-created_at')
    if not otps.exists():
        return JsonResponse({'detail': 'Invalid code or email'}, status=400)
    otp = otps.first()
    if not otp.is_valid():
        return JsonResponse({'detail': 'Code expired or used'}, status=400)
    otp.is_used = True
    otp.save()
    user.set_password(new_password)
    user.save()
    return JsonResponse({'detail': 'Password reset successful'})


def _auth_required(view_func):
    def wrapper(request, *args, **kwargs):
        auth = request.META.get('HTTP_AUTHORIZATION')
        if not auth or not auth.startswith('Bearer '):
            return JsonResponse({'detail': 'Authentication credentials were not provided.'}, status=401)
        token = auth.split(' ', 1)[1]
        payload = _decode_and_validate(token, expected_type='access')
        if not payload:
            return JsonResponse({'detail': 'Invalid or expired token'}, status=401)
        request.user_id = payload.get('user_id')
        return view_func(request, *args, **kwargs)
    return wrapper


@csrf_exempt
@_auth_required
def change_password(request):
    """Authenticated endpoint to change current user's password.
    Expects JSON: {"current_password": "...", "new_password": "..."}
    """
    if request.method != 'POST':
        return JsonResponse({'detail': 'Method not allowed'}, status=405)
    try:
        data = json.loads(request.body.decode('utf-8'))
    except Exception:
        return JsonResponse({'detail': 'Invalid JSON'}, status=400)
    current = data.get('current_password')
    new_password = data.get('new_password')
    if not current or not new_password:
        return JsonResponse({'detail': 'current_password and new_password required'}, status=400)
    user = get_object_or_404(User, pk=request.user_id)
    if not user.check_password(current):
        return JsonResponse({'detail': 'Current password incorrect'}, status=403)
    user.set_password(new_password)
    user.save()
    return JsonResponse({'detail': 'Password changed successfully'})


@csrf_exempt
def login_view(request):
    if request.method != 'POST':
        return JsonResponse({'detail': 'Method not allowed'}, status=405)

    data = json.loads(request.body.decode('utf-8'))
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return JsonResponse({'detail': 'email and password required'}, status=400)

    # allow duplicate emails in DB but pick the first user and warn
    users = User.objects.filter(email=email).order_by('id')
    if not users.exists():
        return JsonResponse({'detail': 'Invalid credentials'}, status=400)
    if users.count() > 1:
        logger.warning("login_view: multiple users found with email=%s, using first id=%s", email, users.first().id)
    user = users.first()

    if not user.check_password(password):
        return JsonResponse({'detail': 'Invalid credentials'}, status=400)

    if not user.is_active:
        return JsonResponse({'detail': 'Account not verified'}, status=403)
    access, refresh = _create_tokens(user)

    # Build user profile info
    full_name = f"{user.first_name} {user.last_name}".strip()
    profile_picture = None
    try:
        profile = user.profile
        if profile.profile_picture:
            profile_picture = request.build_absolute_uri(profile.profile_picture.url)
    except Exception:
        profile_picture = None

    return JsonResponse({
        'access_token': access,
        'refresh_token': refresh,
        'user': {
            'full_name': full_name,
            'email': user.email,
            'profile_picture': profile_picture,
        }
    })


@csrf_exempt
def token_refresh(request):
    if request.method != 'POST':
        return JsonResponse({'detail': 'Method not allowed'}, status=405)

    data = json.loads(request.body.decode('utf-8'))
    refresh_token = data.get('refresh_token') or data.get('token')
    if not refresh_token:
        return JsonResponse({'detail': 'refresh_token required'}, status=400)

    payload = _decode_and_validate(refresh_token, expected_type='refresh')
    if not payload:
        return JsonResponse({'detail': 'Invalid token'}, status=400)

    user = get_object_or_404(User, pk=payload.get('user_id'))
    access, refresh = _create_tokens(user)
    return JsonResponse({'access_token': access, 'refresh_token': refresh})


@csrf_exempt
@_auth_required
def me(request):
    user = get_object_or_404(User, pk=request.user_id)
    logger.info("accounts.me called: method=%s, CONTENT_TYPE=%s, FILES_keys=%s", request.method, request.META.get('CONTENT_TYPE'), list(request.FILES.keys()))

    if request.method in ['POST', 'PUT', 'PATCH']:
        # Ensure profile exists
        profile, _ = Profile.objects.get_or_create(user=user)

        # Support JSON or multipart form (for image upload)
        content_type = request.META.get('CONTENT_TYPE', '')
        # Django doesn't automatically parse multipart for PATCH/PUT in standard views.
        # Force parsing so request.FILES is populated for PATCH requests.
        if request.method in ('PUT', 'PATCH') and content_type.startswith('multipart/') and not request.FILES:
            try:
                request._load_post_and_files()
            except Exception:
                pass
        if 'application/json' in content_type:
            try:
                data = json.loads(request.body.decode('utf-8'))
            except Exception:
                return JsonResponse({'detail': 'Invalid JSON'}, status=400)
            full_name = data.get('full_name')
            email = data.get('email')
            # Support base64 image in JSON as `profile_picture` (data URL or raw base64)
            if data.get('profile_picture'):
                b64 = data.get('profile_picture')
                try:
                    if b64.startswith('data:'):
                        # data:<mime>;base64,<data>
                        b64 = b64.split(',', 1)[1]
                    decoded = base64.b64decode(b64)
                    filename = f"{uuid.uuid4().hex}.jpg"
                    profile.profile_picture.save(filename, ContentFile(decoded), save=True)
                except Exception:
                    pass
            # update fields
            if full_name:
                parts = full_name.strip().split()
                user.first_name = parts[0]
                user.last_name = ' '.join(parts[1:]) if len(parts) > 1 else ''
            if email:
                user.email = email
            user.save()
        else:
            # multipart/form-data for file upload
            full_name = request.POST.get('full_name')
            email = request.POST.get('email')
            if full_name:
                parts = full_name.strip().split()
                user.first_name = parts[0]
                user.last_name = ' '.join(parts[1:]) if len(parts) > 1 else ''
            if email:
                user.email = email
            # handle file upload: check standard field names, then fallback to any file
            if request.FILES:
                uploaded_file = None
                for fname in ('profile_picture', 'profile', 'picture', 'avatar'):
                    if fname in request.FILES:
                        uploaded_file = request.FILES[fname]
                        break
                if uploaded_file is None:
                    uploaded_file = next(iter(request.FILES.values()))
                # assign and save
                profile.profile_picture = uploaded_file
                profile.save()
                logger.info("accounts.me: saved profile picture: %s -> %s", getattr(uploaded_file, 'name', None), profile.profile_picture.name)
            user.save()
            logger.info("accounts.me: user saved: id=%s name=%s %s", user.id, user.first_name, user.last_name)

    # Build response
    full_name = f"{user.first_name} {user.last_name}".strip()
    profile_picture = None
    try:
        profile = user.profile
        if profile.profile_picture:
            profile_picture = request.build_absolute_uri(profile.profile_picture.url)
    except Exception:
        profile_picture = None

    resp = {
        'id': user.id,
        'email': user.email,
        'full_name': full_name,
        'profile_picture': profile_picture,
    }

    return JsonResponse(resp)
