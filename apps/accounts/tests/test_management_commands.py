"""
Tests for management commands in the accounts app.
"""
from io import StringIO
from django.test import TestCase, override_settings
from django.core.management import call_command
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission, ContentType

from ..models import Role

User = get_user_model()


class SetupRolesCommandTest(TestCase):
    """Tests for the setup_roles management command."""
    
    def setUp(self):
        """Set up test data."""
        self.content_type = ContentType.objects.create(
            app_label='auth',
            model='permission'
        )
        
        # Create some test permissions
        self.view_perm = Permission.objects.create(
            codename='view_permission',
            name='Can view permission',
            content_type=self.content_type
        )
        self.add_perm = Permission.objects.create(
            codename='add_permission',
            name='Can add permission',
            content_type=self.content_type
        )
        self.change_perm = Permission.objects.create(
            codename='change_permission',
            name='Can change permission',
            content_type=self.content_type
        )
        self.delete_perm = Permission.objects.create(
            codename='delete_permission',
            name='Can delete permission',
            content_type=self.content_type
        )
    
    def test_setup_roles_creates_roles(self):
        """Test that the command creates all default roles."""
        # Verify no roles exist initially
        self.assertEqual(Role.objects.count(), 0)
        
        # Call the command
        out = StringIO()
        call_command('setup_roles', stdout=out)
        
        # Verify roles were created
        self.assertEqual(Role.objects.count(), len(Role.ROLE_CHOICES))
        
        # Verify each role was created with the correct name and description
        for role_name, role_display in Role.ROLE_CHOICES:
            role = Role.objects.get(name=role_name)
            self.assertEqual(role.description, f'{role_display} role')
    
    def test_setup_roles_assigns_permissions(self):
        """Test that the command assigns permissions to roles."""
        # Call the command
        out = StringIO()
        call_command('setup_roles', stdout=out)
        
        # Get the admin role and verify it has all permissions
        admin_role = Role.objects.get(name=Role.ADMIN)
        self.assertTrue(admin_role.permissions.filter(codename='view_permission').exists())
        self.assertTrue(admin_role.permissions.filter(codename='add_permission').exists())
        self.assertTrue(admin_role.permissions.filter(codename='change_permission').exists())
        self.assertTrue(admin_role.permissions.filter(codename='delete_permission').exists())
        
        # Get the manager role and verify it has view, add, and change permissions
        manager_role = Role.objects.get(name=Role.MANAGER)
        self.assertTrue(manager_role.permissions.filter(codename='view_permission').exists())
        self.assertTrue(manager_role.permissions.filter(codename='add_permission').exists())
        self.assertTrue(manager_role.permissions.filter(codename='change_permission').exists())
        self.assertFalse(manager_role.permissions.filter(codename='delete_permission').exists())
        
        # Get the waiter role and verify it has view permission only
        waiter_role = Role.objects.get(name=Role.WAITER)
        self.assertTrue(waiter_role.permissions.filter(codename='view_permission').exists())
        self.assertFalse(waiter_role.permissions.filter(codename='add_permission').exists())
        self.assertFalse(waiter_role.permissions.filter(codename='change_permission').exists())
        self.assertFalse(waiter_role.permissions.filter(codename='delete_permission').exists())
    
    def test_setup_roles_idempotent(self):
        """Test that running the command multiple times doesn't create duplicate roles."""
        # Call the command twice
        out = StringIO()
        call_command('setup_roles', stdout=out)
        role_count = Role.objects.count()
        
        call_command('setup_roles', stdout=out)
        
        # Verify no duplicate roles were created
        self.assertEqual(Role.objects.count(), role_count)
    
    @override_settings(DEBUG=True)
    def test_setup_roles_debug_mode(self):
        """Test that the command works in debug mode."""
        out = StringIO()
        call_command('setup_roles', stdout=out)
        self.assertIn('Created role:', out.getvalue())
    
    def test_setup_roles_with_existing_roles(self):
        """Test that the command updates existing roles."""
        # Create a role that will be updated by the command
        existing_role = Role.objects.create(
            name=Role.ADMIN,
            description='Old description'
        )
        
        # Call the command
        out = StringIO()
        call_command('setup_roles', stdout=out)
        
        # Verify the role was updated
        existing_role.refresh_from_db()
        self.assertEqual(existing_role.description, 'Administrator role')
