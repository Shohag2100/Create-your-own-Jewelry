from django.contrib import admin
from .models import ChatRoom, Message, ChatNotification


@admin.register(ChatRoom)
class ChatRoomAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'admin', 'created_at', 'updated_at', 'is_active']
    list_filter = ['created_at', 'is_active']
    search_fields = ['user__username', 'admin__username']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Chat Room Info', {
            'fields': ('user', 'admin', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ['id', 'chat_room', 'sender', 'message_type', 'created_at', 'is_read']
    list_filter = ['message_type', 'created_at', 'is_read']
    search_fields = ['sender__username', 'content', 'chat_room__user__username']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Message Info', {
            'fields': ('chat_room', 'sender', 'message_type', 'content')
        }),
        ('Attachments', {
            'fields': ('file', 'image'),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': ('is_read',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.select_related('chat_room', 'sender')


@admin.register(ChatNotification)
class ChatNotificationAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'chat_room', 'unread_count', 'created_at', 'updated_at']
    list_filter = ['created_at', 'updated_at']
    search_fields = ['user__username', 'chat_room__user__username']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Notification Info', {
            'fields': ('user', 'chat_room', 'unread_count')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

