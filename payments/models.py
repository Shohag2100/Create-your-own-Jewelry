from django.db import models

class Payment(models.Model):
    stripe_payment_id = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    is_paid = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Payment {self.stripe_payment_id} - Paid: {self.is_paid}"


class Milestone(models.Model):
    TIER_CHOICES = [
        ('basic', 'Basic'),
        ('standard', 'Standard'),
        ('premium', 'Premium'),
    ]
    tier = models.CharField(max_length=20, choices=TIER_CHOICES)
    # position indicates milestone number within a tier (1,2,3)
    position = models.IntegerField(default=1)
    name = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.name} ({self.tier} #{self.position}) - ${self.amount}"

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['tier', 'position'], name='unique_tier_position')
        ]


class MilestonePayment(models.Model):
    milestone = models.ForeignKey(Milestone, on_delete=models.CASCADE, related_name='payments')
    stripe_session_id = models.CharField(max_length=255, blank=True, null=True)
    stripe_payment_intent = models.CharField(max_length=255, blank=True, null=True)
    # store the milestone position at time of payment (1,2,3)
    position = models.IntegerField(blank=True, null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    is_paid = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(blank=True, null=True)

    def __str__(self):
        return f"MilestonePayment {self.milestone.tier}#{self.position or '?'} - Paid: {self.is_paid}"