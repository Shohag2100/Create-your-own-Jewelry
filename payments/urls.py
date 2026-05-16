from django.urls import path
from . import views

urlpatterns = [
    path('', views.create_checkout_session, name='pay'),
    path('success/', views.success, name='success'),
    path('cancel/', views.cancel, name='cancel'),
    path('refund/<int:payment_id>/', views.refund_payment, name='refund'),
    path('milestones/', views.milestones_list, name='milestones-list'),
    path('milestone/checkout/', views.create_milestone_checkout, name='milestone-checkout'),
    path('milestone/status/', views.milestone_status, name='milestone-status'),
    path('webhook/', views.stripe_webhook, name='stripe-webhook'),
]