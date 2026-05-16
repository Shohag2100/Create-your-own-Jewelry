"""
Custom JWT Authentication for Django REST Framework
Handles JWT access tokens from the accounts login endpoint
"""

from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from django.conf import settings
from django.contrib.auth.models import User
import jwt


class JWTAuthentication(BaseAuthentication):
    """
    Custom authentication class for JWT tokens.
    Accepts Authorization header: Bearer <jwt_token>
    """
    
    keyword = 'Bearer'  # Authorization header format: Bearer <token>
    
    def authenticate(self, request):
        """
        Authenticate request using JWT token from Authorization header
        """
        # Get Authorization header
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        
        if not auth_header:
            return None
        
        try:
            auth_parts = auth_header.split()
        except (AttributeError, ValueError):
            raise AuthenticationFailed('Invalid Authorization header format.')
        
        if len(auth_parts) != 2:
            raise AuthenticationFailed('Invalid Authorization header format.')
        
        if auth_parts[0].lower() != self.keyword.lower():
            # Not a Bearer token, let other authenticators handle it
            return None
        
        token = auth_parts[1]
        
        return self.authenticate_credentials(token)
    
    def authenticate_credentials(self, key):
        """
        Validate JWT token and return user
        """
        try:
            # Decode JWT token
            payload = jwt.decode(key, settings.SECRET_KEY, algorithms=['HS256'])
        except jwt.ExpiredSignatureError:
            raise AuthenticationFailed('Token has expired.')
        except jwt.InvalidTokenError as e:
            raise AuthenticationFailed(f'Invalid token: {str(e)}')
        except Exception as e:
            raise AuthenticationFailed(f'Invalid token: {str(e)}')
        
        # Get user from token payload
        user_id = payload.get('user_id')
        if not user_id:
            raise AuthenticationFailed('Invalid token: user_id not found.')
        
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            raise AuthenticationFailed('User not found.')
        
        if not user.is_active:
            raise AuthenticationFailed('User is inactive.')
        
        return (user, key)
