from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class ChatRoom(models.Model):
    """Model to store chat room between user and admin"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='chat_room')
    admin = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='admin_chats')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f"Chat Room - {self.user.username}"


class Message(models.Model):
    """Model to store chat messages"""
    MESSAGE_TYPE_CHOICES = [
        ('text', 'Text'),
        ('file', 'File'),
        ('image', 'Image'),
    ]

    chat_room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    message_type = models.CharField(max_length=10, choices=MESSAGE_TYPE_CHOICES, default='text')
    content = models.TextField(blank=True)
    file = models.FileField(upload_to='chat_files/', null=True, blank=True)
    image = models.ImageField(upload_to='chat_images/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Message from {self.sender.username} in {self.chat_room}"

    def mark_as_read(self):
        self.is_read = True
        self.save()


class ChatNotification(models.Model):
    """Model to track unread message notifications"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chat_notifications')
    chat_room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE)
    unread_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['user', 'chat_room']

    def __str__(self):
        return f"Notification for {self.user.username} in {self.chat_room}"
