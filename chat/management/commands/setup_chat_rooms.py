from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from chat.models import ChatRoom


class Command(BaseCommand):
    help = 'Create chat rooms for users'

    def add_arguments(self, parser):
        parser.add_argument(
            '--user',
            type=int,
            help='Create chat room for specific user ID'
        )
        parser.add_argument(
            '--admin',
            type=int,
            help='Assign specific admin user ID'
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Create chat rooms for all users'
        )

    def handle(self, *args, **options):
        if options['all']:
            self.create_for_all_users()
        elif options['user']:
            self.create_for_user(options['user'], options.get('admin'))
        else:
            self.list_chat_rooms()

    def create_for_user(self, user_id, admin_id=None):
        """Create chat room for a specific user"""
        try:
            user = User.objects.get(id=user_id)
            admin = None
            
            if admin_id:
                admin = User.objects.get(id=admin_id)
            else:
                # Get first admin user
                admin = User.objects.filter(is_staff=True).first()
            
            chat_room, created = ChatRoom.objects.get_or_create(
                user=user,
                defaults={'admin': admin}
            )
            
            if created:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'✓ Created chat room for {user.username}'
                    )
                )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f'! Chat room already exists for {user.username}'
                    )
                )
        except User.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'✗ User with ID {user_id} not found')
            )

    def create_for_all_users(self):
        """Create chat rooms for all non-admin users"""
        users = User.objects.filter(is_staff=False)
        admin = User.objects.filter(is_staff=True).first()
        
        if not admin:
            self.stdout.write(
                self.style.ERROR('✗ No admin user found. Please create an admin user first.')
            )
            return
        
        count = 0
        for user in users:
            chat_room, created = ChatRoom.objects.get_or_create(
                user=user,
                defaults={'admin': admin}
            )
            if created:
                count += 1
        
        self.stdout.write(
            self.style.SUCCESS(
                f'✓ Created {count} chat rooms'
            )
        )

    def list_chat_rooms(self):
        """List all chat rooms"""
        chat_rooms = ChatRoom.objects.select_related('user', 'admin').all()
        
        if not chat_rooms:
            self.stdout.write(self.style.WARNING('No chat rooms found'))
            return
        
        self.stdout.write(self.style.SUCCESS('\n=== Chat Rooms ===\n'))
        
        for room in chat_rooms:
            user_display = room.user.username if room.user else 'N/A'
            admin_display = room.admin.username if room.admin else 'N/A'
            status = '✓ Active' if room.is_active else '✗ Inactive'
            
            self.stdout.write(
                f'ID: {room.id} | User: {user_display} | Admin: {admin_display} | {status}'
            )
            self.stdout.write(f'  Created: {room.created_at} | Updated: {room.updated_at}\n')
