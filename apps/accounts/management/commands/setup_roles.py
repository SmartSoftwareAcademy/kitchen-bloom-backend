"""
Management command to set up default roles and permissions.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import Permission, ContentType
from django.db import transaction

from apps.accounts.models import Role


class Command(BaseCommand):
    help = 'Set up default roles and permissions for the application'

    def handle(self, *args, **options):
        """Execute the management command."""
        self.stdout.write('Setting up default roles and permissions...')
        
        # Get all content types to assign view permissions
        content_types = ContentType.objects.all()
        
        # Define role permissions
        role_permissions = {
            Role.ADMIN: [
                'add', 'change', 'delete', 'view'
            ],
            Role.MANAGER: [
                'add', 'change', 'view'
            ],
            Role.CASHIER: [
                'view', 'add_order', 'process_payment'
            ],
            Role.KITCHEN_STAFF: [
                'view_order', 'update_order_status'
            ],
            Role.WAITER: [
                'view_menu', 'place_order', 'update_order_status', 'view_order'
            ],
            Role.ACCOUNTANT: [
                'view_reports', 'export_reports', 'view_financials'
            ]
        }
        
        with transaction.atomic():
            # Create or update roles
            for role_name, role_display in Role.ROLE_CHOICES:
                role, created = Role.objects.get_or_create(
                    name=role_name,
                    defaults={'description': f'{role_display} role'}
                )
                
                if created:
                    self.stdout.write(self.style.SUCCESS(f'Created role: {role_display}'))
                
                # Assign permissions to role
                permission_codenames = []
                
                if role_name in role_permissions:
                    for action in role_permissions[role_name]:
                        if action in ['add', 'change', 'delete', 'view']:
                            # Model-level permissions
                            for content_type in content_types:
                                codename = f'{action}_{content_type.model}'
                                permission_codenames.append(codename)
                        else:
                            # Custom permissions
                            permission_codenames.append(action)
                
                # Get or create permissions
                permissions = []
                for codename in permission_codenames:
                    # Try to find existing permission
                    permission = Permission.objects.filter(
                        codename=codename
                    ).first()
                    
                    if not permission:
                        # If permission doesn't exist, try to create it
                        try:
                            # This will only work for model permissions that exist in the DB
                            permission = Permission.objects.get(codename=codename)
                        except Permission.DoesNotExist:
                            # Skip if permission doesn't exist
                            self.stdout.write(
                                self.style.WARNING(f'Permission not found: {codename}')
                            )
                            continue
                    
                    permissions.append(permission)
                
                # Set permissions for the role
                role.permissions.set(permissions)
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Assigned {len(permissions)} permissions to {role_display} role'
                    )
                )
        
        self.stdout.write(self.style.SUCCESS('Successfully set up roles and permissions!'))
