from django.contrib import admin
from .models import OTP


@admin.register(OTP)
class OTPAdmin(admin.ModelAdmin):
    list_display = ('user', 'code', 'created_at', 'expires_at', 'is_used')
    search_fields = ('user__username', 'user__email', 'code')
