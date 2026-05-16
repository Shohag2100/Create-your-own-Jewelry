import stripe
from django.conf import settings
from django.shortcuts import render,  get_object_or_404, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import Payment, Milestone, MilestonePayment
from django.views.decorators.http import require_POST, require_GET
from django.urls import reverse
import json

stripe.api_key = settings.STRIPE_TEST_SECRET_KEY

def welcome(request):
    return render(request, "payments/welcome.html")


@csrf_exempt
def create_checkout_session(request):
    YOUR_DOMAIN = "http://10.10.20.61:8000"  # Replace with your domain in production
    
    # Create Stripe checkout session
    session = stripe.checkout.Session.create(
        payment_method_types=['card'],
        line_items=[{
            'price_data': {
                'currency': 'usd',
                'product_data': {
                    'name': 'Product or Service Name',  # Customize your product name here
                },
                'unit_amount': 500,  # Amount in cents (e.g., $5.00)
            },
            'quantity': 1,
        }],
        mode='payment',
        success_url=YOUR_DOMAIN + '/payment/success/',
        cancel_url=YOUR_DOMAIN + '/payment/cancel/',
    )
    
    # Create payment record in DB
    payment = Payment.objects.create(stripe_payment_id=session.id, amount=5.00)
    
    return redirect(session.url, code=303)  # Redirect the user to Stripe's hosted payment page


@require_GET
def milestones_list(request):
    # Return available milestones
    milestones = Milestone.objects.all().order_by('tier', 'position')
    data = [{'tier': m.tier, 'position': m.position, 'name': m.name, 'amount': float(m.amount)} for m in milestones]
    return JsonResponse({'milestones': data})


@csrf_exempt
@require_POST
def create_milestone_checkout(request):
    """Create a Stripe Checkout Session for a milestone tier.
    POST JSON body: { "tier": "basic" , "success_url": "...", "cancel_url": "..." }
    """
    try:
        data = json.loads(request.body.decode('utf-8'))
    except Exception:
        return JsonResponse({'detail': 'Invalid JSON'}, status=400)

    tier = data.get('tier')
    # Use explicit paths to avoid reverse name resolution issues
    success_url = data.get('success_url') or request.build_absolute_uri('/payment/success/')
    cancel_url = data.get('cancel_url') or request.build_absolute_uri('/payment/cancel/')

    if not tier:
        return JsonResponse({'detail': 'tier required'}, status=400)

    # Allow selecting a specific milestone position within the tier, or default to the first position
    position = data.get('position')
    try:
        if position is not None:
            position = int(position)
            milestone = Milestone.objects.get(tier=tier, position=position)
        else:
            milestone = Milestone.objects.filter(tier=tier).order_by('position').first()
            if milestone is None:
                return JsonResponse({'detail': 'Invalid tier or no milestones configured for this tier'}, status=400)
    except Milestone.DoesNotExist:
        return JsonResponse({'detail': 'Invalid tier/position'}, status=400)

    YOUR_DOMAIN = request.build_absolute_uri('/')[:-1]

    session = stripe.checkout.Session.create(
        payment_method_types=['card'],
        line_items=[{
            'price_data': {
                'currency': 'usd',
                'product_data': {
                    'name': milestone.name,
                },
                'unit_amount': int(milestone.amount * 100),
            },
            'quantity': 1,
        }],
        mode='payment',
        success_url=success_url + '?session_id={CHECKOUT_SESSION_ID}',
        cancel_url=cancel_url,
        metadata={'milestone_tier': milestone.tier}
    )

    mp = MilestonePayment.objects.create(
        milestone=milestone,
        stripe_session_id=session.id,
        amount=milestone.amount,
        position=milestone.position,
        metadata={'tier': milestone.tier, 'position': milestone.position}
    )

    return JsonResponse({'url': session.url, 'session_id': session.id})


@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    endpoint_secret = getattr(settings, 'STRIPE_WEBHOOK_SECRET', None)
    event = None

    try:
        if endpoint_secret:
            event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
        else:
            event = json.loads(payload)
    except Exception as e:
        return JsonResponse({'detail': 'Invalid payload'}, status=400)

    # Handle the checkout.session.completed event
    if event and event.get('type') == 'checkout.session.completed' or (hasattr(event, 'get') and event.get('type') == 'checkout.session.completed'):
        session = event['data']['object'] if isinstance(event, dict) else event.data.object
        session_id = session.get('id')
        try:
            mp = MilestonePayment.objects.get(stripe_session_id=session_id)
            mp.is_paid = True
            mp.stripe_payment_intent = session.get('payment_intent')
            mp.save()
        except MilestonePayment.DoesNotExist:
            pass

    return JsonResponse({'status': 'success'})


def success(request):
    return render(request, "payments/success.html")

@csrf_exempt
def cancel(request):
    return render(request, "payments/cancel.html")

def refund_payment(request, payment_id):
    payment = get_object_or_404(Payment, pk=payment_id)

    stripe.Refund.create(
    payment_intent='pi_realPaymentIntentIdHere',
    amount=500,
)

    return render(request, "payments/refund_done.html", {"payment": payment})


@require_GET
def milestone_status(request):
    """Return payment status for a given checkout session id.
    Query param: session_id (or id)
    Checks `MilestonePayment` first; if not found, attempts to retrieve the
    Stripe session and returns its payment status.
    """
    session_id = request.GET.get('session_id') or request.GET.get('id')
    if not session_id:
        return JsonResponse({'detail': 'session_id required'}, status=400)
    try:
        mp = MilestonePayment.objects.get(stripe_session_id=session_id)
        return JsonResponse({
            'found_in_db': True,
            'session_id': mp.stripe_session_id,
            'is_paid': mp.is_paid,
            'amount': float(mp.amount),
            'milestone_tier': mp.milestone.tier,
            'position': mp.position,
            'stripe_payment_intent': mp.stripe_payment_intent,
            'created_at': mp.created_at.isoformat(),
        })
    except MilestonePayment.DoesNotExist:
        # fallback: try to fetch session from Stripe
        try:
            session = stripe.checkout.Session.retrieve(session_id)
            return JsonResponse({
                'found_in_db': False,
                'session_id': session.id,
                'payment_status': getattr(session, 'payment_status', None),
                'payment_intent': getattr(session, 'payment_intent', None),
                'amount_total': getattr(session, 'amount_total', None),
                'currency': getattr(session, 'currency', None),
            })
        except Exception as e:
            return JsonResponse({'detail': 'not found', 'error': str(e)}, status=404)