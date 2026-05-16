from django.urls import path
from . import views

urlpatterns = [
    path('gold-price/', views.get_gold_price, name='gold_price'),
]
