# payments/admin.py

from django.contrib import admin
from .models import Payment
from .models import Milestone, MilestonePayment

class PaymentAdmin(admin.ModelAdmin):
    list_display = ('stripe_payment_id', 'amount', 'is_paid', 'created_at')
    list_filter = ('is_paid', 'created_at')
    search_fields = ('stripe_payment_id',)

# Register the Payment model with the admin site
admin.site.register(Payment, PaymentAdmin)

@admin.register(Milestone)
class MilestoneAdmin(admin.ModelAdmin):
    list_display = ('tier', 'position', 'name', 'amount')

@admin.register(MilestonePayment)
class MilestonePaymentAdmin(admin.ModelAdmin):
    list_display = ('milestone', 'position', 'amount', 'is_paid', 'created_at')