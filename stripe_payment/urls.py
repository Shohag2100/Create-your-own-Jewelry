from django.contrib import admin
from django.urls import path, include
from payments import views as payment_views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', payment_views.welcome, name='welcome'),
    path('payment/', include(('payments.urls', 'payments'), namespace='payments')),
    path('accounts/', include('accounts.urls')),
    path('gold/', include('gold.urls')),
    path('chat/', include('chat.urls')),  # Chat app URLs
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)