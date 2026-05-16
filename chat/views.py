from rest_framework import viewsets, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.authtoken.models import Token
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.models import User
from django.db.models import Q
from .models import ChatRoom, Message, ChatNotification
from .serializers import ChatRoomSerializer, MessageSerializer, ChatNotificationSerializer
from django.core.paginator import Paginator


class ChatRoomViewSet(viewsets.ViewSet):
    """ViewSet for managing chat rooms"""
    permission_classes = [IsAuthenticated]

    def list(self, request):
        """Get all chat rooms for the current user"""
        # Get chat rooms where user is either the user or admin
        chat_rooms = ChatRoom.objects.filter(
            Q(user=request.user) | Q(admin=request.user)
        ).select_related('user', 'admin').prefetch_related('messages')

        serializer = ChatRoomSerializer(
            chat_rooms,
            many=True,
            context={'request': request}
        )
        return Response(serializer.data)

    def retrieve(self, request, pk=None):
        """Get a specific chat room with all messages"""
        chat_room = get_object_or_404(ChatRoom, id=pk)
        
        # Verify user has access
        if request.user != chat_room.user and request.user != chat_room.admin:
            return Response(
                {'detail': 'You do not have permission to view this chat room.'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Mark messages as read
        Message.objects.filter(
            chat_room=chat_room,
            is_read=False
        ).exclude(sender=request.user).update(is_read=True)

        serializer = ChatRoomSerializer(
            chat_room,
            context={'request': request}
        )
        return Response(serializer.data)

    def create(self, request):
        """Create a new chat room"""
        # Check if chat room already exists
        user_id = request.data.get('user_id')
        
        if not user_id:
            return Response(
                {'detail': 'user_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            target_user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response(
                {'detail': 'User not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        chat_room, created = ChatRoom.objects.get_or_create(
            user=target_user,
            defaults={'admin': request.user if request.user.is_staff else None}
        )

        serializer = ChatRoomSerializer(
            chat_room,
            context={'request': request}
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class MessageViewSet(viewsets.ViewSet):
    """ViewSet for managing messages"""
    permission_classes = [IsAuthenticated]

    def list(self, request):
        """Get messages for a specific chat room with pagination"""
        chat_room_id = request.query_params.get('chat_room_id')
        page = request.query_params.get('page', 1)
        page_size = request.query_params.get('page_size', 20)

        if not chat_room_id:
            return Response(
                {'detail': 'chat_room_id parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        chat_room = get_object_or_404(ChatRoom, id=chat_room_id)
        
        # Verify user has access
        if request.user != chat_room.user and request.user != chat_room.admin:
            return Response(
                {'detail': 'You do not have permission to view these messages.'},
                status=status.HTTP_403_FORBIDDEN
            )

        messages = Message.objects.filter(chat_room=chat_room).order_by('-created_at')
        
        # Pagination
        paginator = Paginator(messages, page_size)
        page_obj = paginator.get_page(page)

        serializer = MessageSerializer(
            page_obj.object_list,
            many=True,
            context={'request': request}
        )

        return Response({
            'count': paginator.count,
            'page': page,
            'page_size': page_size,
            'messages': serializer.data
        })

    def create(self, request):
        """Create a new message"""
        chat_room_id = request.data.get('chat_room_id')
        
        if not chat_room_id:
            return Response(
                {'detail': 'chat_room_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        chat_room = get_object_or_404(ChatRoom, id=chat_room_id)
        
        # Verify user has access
        if request.user != chat_room.user and request.user != chat_room.admin:
            return Response(
                {'detail': 'You do not have permission to send messages in this chat room.'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Determine message type
        content = request.data.get('content', '').strip()
        if 'file' in request.FILES:
            message = Message.objects.create(
                chat_room=chat_room,
                sender=request.user,
                message_type='file',
                content=content or f"Sent file: {request.FILES['file'].name}",
                file=request.FILES['file']
            )
        elif 'image' in request.FILES:
            message = Message.objects.create(
                chat_room=chat_room,
                sender=request.user,
                message_type='image',
                content=content or "Sent image",
                image=request.FILES['image']
            )
        else:
            if not content:
                return Response(
                    {'detail': 'Message content is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            message = Message.objects.create(
                chat_room=chat_room,
                sender=request.user,
                message_type='text',
                content=content
            )

        serializer = MessageSerializer(message, context={'request': request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_messages_as_read(request):
    """Mark all messages in a chat room as read"""
    chat_room_id = request.data.get('chat_room_id')
    
    if not chat_room_id:
        return Response(
            {'detail': 'chat_room_id is required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    chat_room = get_object_or_404(ChatRoom, id=chat_room_id)
    
    # Verify user has access
    if request.user != chat_room.user and request.user != chat_room.admin:
        return Response(
            {'detail': 'You do not have permission to update this chat room.'},
            status=status.HTTP_403_FORBIDDEN
        )

    # Mark messages as read
    Message.objects.filter(
        chat_room=chat_room,
        is_read=False
    ).exclude(sender=request.user).update(is_read=True)

    return Response({'status': 'Messages marked as read'})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_unread_count(request):
    """Get total unread message count"""
    unread_count = Message.objects.filter(
        chat_room__user=request.user,
        is_read=False
    ).exclude(sender=request.user).count()
    
    admin_unread = Message.objects.filter(
        chat_room__admin=request.user,
        is_read=False
    ).exclude(sender=request.user).count()

    return Response({
        'user_unread': unread_count,
        'admin_unread': admin_unread,
        'total_unread': unread_count + admin_unread
    })


def chat_list(request):
    """Render chat list page"""
    if not request.user.is_authenticated:
        return render(request, 'chat/login_required.html')

    context = {
        'user': request.user,
    }
    return render(request, 'chat/chat_list.html', context)


def chat_detail(request, room_id):
    """Render chat detail page"""
    if not request.user.is_authenticated:
        return render(request, 'chat/login_required.html')

    chat_room = get_object_or_404(ChatRoom, id=room_id)
    
    # Verify user has access
    if request.user != chat_room.user and request.user != chat_room.admin:
        return render(request, 'chat/permission_denied.html', status=403)

    context = {
        'chat_room': chat_room,
        'user': request.user,
    }
    return render(request, 'chat/chat_detail.html', context)


# Token Authentication Endpoints
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def get_auth_token(request):
    """Get authentication token for API requests"""
    user = request.user
    token, created = Token.objects.get_or_create(user=user)
    return Response({
        'token': token.key,
        'user_id': user.id,
        'username': user.username,
        'email': user.email
    })



