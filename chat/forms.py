from django import forms
from .models import Message, ChatRoom


class MessageForm(forms.ModelForm):
    """Form for creating chat messages"""
    
    class Meta:
        model = Message
        fields = ['content', 'file', 'image']
        widgets = {
            'content': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Type your message here...',
                'id': 'message-input'
            }),
            'file': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.doc,.docx,.xls,.xlsx,.txt,.csv'
            }),
            'image': forms.ImageField(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            })
        }


class ChatRoomForm(forms.ModelForm):
    """Form for creating/updating chat rooms"""
    
    class Meta:
        model = ChatRoom
        fields = ['is_active']
        widgets = {
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            })
        }
