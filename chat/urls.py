from django.urls import path
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'chat'

# Create router for ViewSets
router = DefaultRouter()
router.register(r'chatrooms', views.ChatRoomViewSet, basename='chatroom')
router.register(r'messages', views.MessageViewSet, basename='message')

urlpatterns = [
    # Token endpoint
    path('api/token/', views.get_auth_token, name='get-token'),
    
    # API endpoints
    path('api/chatrooms/', views.ChatRoomViewSet.as_view({'get': 'list', 'post': 'create'}), name='chatroom-list'),
    path('api/chatrooms/<int:pk>/', views.ChatRoomViewSet.as_view({'get': 'retrieve'}), name='chatroom-detail'),
    path('api/messages/', views.MessageViewSet.as_view({'get': 'list', 'post': 'create'}), name='message-list'),
    path('api/messages/read/', views.mark_messages_as_read, name='mark-read'),
    path('api/unread-count/', views.get_unread_count, name='unread-count'),
    
    # HTML pages
    path('', views.chat_list, name='chat-list'),
    path('<int:room_id>/', views.chat_detail, name='chat-detail'),
] + router.urls
