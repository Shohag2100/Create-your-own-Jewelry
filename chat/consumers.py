import json
import os
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.core.files.base import ContentFile
from django.contrib.auth.models import User
from .models import ChatRoom, Message, ChatNotification
import base64


class ChatConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for real-time chat functionality"""

    async def connect(self):
        """Handle WebSocket connection"""
        self.room_id = self.scope['url_route']['kwargs']['room_id']
        self.user = self.scope['user']
        self.room_group_name = f'chat_{self.room_id}'

        # Verify user has access to this chat room
        has_access = await self.verify_chat_access()
        
        if not has_access:
            await self.close()
            return

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()
        
        # Notify others that user is online
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'user_status',
                'status': 'online',
                'username': self.user.username,
                'timestamp': str(self.get_current_time()),
            }
        )

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        # Notify others that user is offline
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'user_status',
                'status': 'offline',
                'username': self.user.username,
                'timestamp': str(self.get_current_time()),
            }
        )

        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        """Handle incoming WebSocket messages"""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')

            if message_type == 'chat_message':
                await self.handle_text_message(data)
            elif message_type == 'file_upload':
                await self.handle_file_upload(data)
            elif message_type == 'image_upload':
                await self.handle_image_upload(data)
            elif message_type == 'mark_read':
                await self.handle_mark_read(data)
            elif message_type == 'typing':
                await self.handle_typing_indicator(data)

        except json.JSONDecodeError:
            await self.send(json.dumps({
                'type': 'error',
                'message': 'Invalid JSON'
            }))
        except Exception as e:
            await self.send(json.dumps({
                'type': 'error',
                'message': str(e)
            }))

    async def handle_text_message(self, data):
        """Handle text chat messages"""
        content = data.get('message', '').strip()
        
        if not content:
            await self.send(json.dumps({
                'type': 'error',
                'message': 'Message cannot be empty'
            }))
            return

        # Save message to database
        message = await self.save_message('text', content)

        # Broadcast to room group
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': {
                    'id': message.id,
                    'sender': message.sender.username,
                    'sender_id': message.sender.id,
                    'content': message.content,
                    'message_type': message.message_type,
                    'created_at': message.created_at.isoformat(),
                    'timestamp': str(self.get_current_time()),
                }
            }
        )

    async def handle_file_upload(self, data):
        """Handle file uploads"""
        file_data = data.get('file')
        filename = data.get('filename', 'uploaded_file')

        if not file_data:
            await self.send(json.dumps({
                'type': 'error',
                'message': 'No file provided'
            }))
            return

        try:
            # Decode base64 file
            file_content = base64.b64decode(file_data.split(',')[1] if ',' in file_data else file_data)
            
            # Save message with file
            message = await self.save_file_message(filename, file_content)

            # Broadcast to room group
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'file_message',
                    'message': {
                        'id': message.id,
                        'sender': message.sender.username,
                        'sender_id': message.sender.id,
                        'filename': filename,
                        'file_url': message.file.url,
                        'message_type': message.message_type,
                        'created_at': message.created_at.isoformat(),
                        'timestamp': str(self.get_current_time()),
                    }
                }
            )
        except Exception as e:
            await self.send(json.dumps({
                'type': 'error',
                'message': f'File upload error: {str(e)}'
            }))

    async def handle_image_upload(self, data):
        """Handle image uploads"""
        image_data = data.get('image')
        filename = data.get('filename', 'uploaded_image.jpg')

        if not image_data:
            await self.send(json.dumps({
                'type': 'error',
                'message': 'No image provided'
            }))
            return

        try:
            # Decode base64 image
            image_content = base64.b64decode(image_data.split(',')[1] if ',' in image_data else image_data)
            
            # Save message with image
            message = await self.save_image_message(filename, image_content)

            # Broadcast to room group
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'image_message',
                    'message': {
                        'id': message.id,
                        'sender': message.sender.username,
                        'sender_id': message.sender.id,
                        'image_url': message.image.url,
                        'message_type': message.message_type,
                        'created_at': message.created_at.isoformat(),
                        'timestamp': str(self.get_current_time()),
                    }
                }
            )
        except Exception as e:
            await self.send(json.dumps({
                'type': 'error',
                'message': f'Image upload error: {str(e)}'
            }))

    async def handle_mark_read(self, data):
        """Handle marking messages as read"""
        message_id = data.get('message_id')
        if message_id:
            await self.mark_message_as_read(message_id)

    async def handle_typing_indicator(self, data):
        """Handle typing indicator"""
        is_typing = data.get('is_typing', False)
        
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'typing_indicator',
                'username': self.user.username,
                'is_typing': is_typing,
                'timestamp': str(self.get_current_time()),
            }
        )

    # Message handlers (called by group_send)
    async def chat_message(self, event):
        """Send text message to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'chat_message',
            'message': event['message']
        }))

    async def file_message(self, event):
        """Send file message to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'file_message',
            'message': event['message']
        }))

    async def image_message(self, event):
        """Send image message to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'image_message',
            'message': event['message']
        }))

    async def user_status(self, event):
        """Send user status to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'user_status',
            'status': event['status'],
            'username': event['username'],
            'timestamp': event['timestamp']
        }))

    async def typing_indicator(self, event):
        """Send typing indicator to WebSocket"""
        if event['username'] != self.user.username:  # Don't send to self
            await self.send(text_data=json.dumps({
                'type': 'typing_indicator',
                'username': event['username'],
                'is_typing': event['is_typing'],
                'timestamp': event['timestamp']
            }))

    # Database operations
    @database_sync_to_async
    def verify_chat_access(self):
        """Verify user has access to this chat room"""
        try:
            chat_room = ChatRoom.objects.get(id=self.room_id)
            return (self.user == chat_room.user or self.user == chat_room.admin or 
                    self.user.is_staff or self.user.is_superuser)
        except ChatRoom.DoesNotExist:
            return False

    @database_sync_to_async
    def save_message(self, message_type, content):
        """Save message to database"""
        chat_room = ChatRoom.objects.get(id=self.room_id)
        message = Message.objects.create(
            chat_room=chat_room,
            sender=self.user,
            message_type=message_type,
            content=content
        )
        return message

    @database_sync_to_async
    def save_file_message(self, filename, file_content):
        """Save file message to database"""
        chat_room = ChatRoom.objects.get(id=self.room_id)
        message = Message.objects.create(
            chat_room=chat_room,
            sender=self.user,
            message_type='file',
            content=f'Sent file: {filename}'
        )
        message.file.save(filename, ContentFile(file_content))
        return message

    @database_sync_to_async
    def save_image_message(self, filename, image_content):
        """Save image message to database"""
        chat_room = ChatRoom.objects.get(id=self.room_id)
        message = Message.objects.create(
            chat_room=chat_room,
            sender=self.user,
            message_type='image',
            content='Sent image'
        )
        message.image.save(filename, ContentFile(image_content))
        return message

    @database_sync_to_async
    def mark_message_as_read(self, message_id):
        """Mark message as read"""
        try:
            message = Message.objects.get(id=message_id)
            message.mark_as_read()
        except Message.DoesNotExist:
            pass

    @staticmethod
    def get_current_time():
        """Get current time"""
        from django.utils import timezone
        return timezone.now()
