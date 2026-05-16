from rest_framework import serializers
from .models import ChatRoom, Message, ChatNotification
from django.contrib.auth.models import User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']


class MessageSerializer(serializers.ModelSerializer):
    sender_username = serializers.CharField(source='sender.username', read_only=True)
    sender_id = serializers.IntegerField(source='sender.id', read_only=True)
    file_url = serializers.SerializerMethodField()
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = [
            'id', 'chat_room', 'sender', 'sender_id', 'sender_username',
            'message_type', 'content', 'file', 'file_url', 'image', 'image_url',
            'created_at', 'updated_at', 'is_read'
        ]
        read_only_fields = ['id', 'sender', 'created_at', 'updated_at', 'sender_username', 'sender_id']

    def get_file_url(self, obj):
        if obj.file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.file.url)
            return obj.file.url
        return None

    def get_image_url(self, obj):
        if obj.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.image.url)
            return obj.image.url
        return None


class ChatRoomSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    admin = UserSerializer(read_only=True)
    messages = MessageSerializer(many=True, read_only=True)
    unread_count = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()

    class Meta:
        model = ChatRoom
        fields = [
            'id', 'user', 'admin', 'created_at', 'updated_at',
            'is_active', 'messages', 'unread_count', 'last_message'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_unread_count(self, obj):
        try:
            notification = ChatNotification.objects.get(
                user=self.context['request'].user,
                chat_room=obj
            )
            return notification.unread_count
        except ChatNotification.DoesNotExist:
            return 0

    def get_last_message(self, obj):
        last_message = obj.messages.last()
        if last_message:
            return MessageSerializer(last_message, context=self.context).data
        return None


class ChatNotificationSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    chat_room = ChatRoomSerializer(read_only=True)

    class Meta:
        model = ChatNotification
        fields = ['id', 'user', 'chat_room', 'unread_count', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']
