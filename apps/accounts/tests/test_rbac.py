"""
Tests for Role-Based Access Control (RBAC) functionality.
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission, Group
from django.contrib.contenttypes.models import ContentType

from rest_framework.test import APIClient
from rest_framework import status

from ..models import Role

User = get_user_model()


class RBACTests(TestCase):
    """Test cases for RBAC functionality."""
    
    def setUp(self):
        """Set up test data."""
        # Create test roles
        self.admin_role = Role.objects.create(
            name=Role.ADMIN,
            description='Administrator role with full access'
        )
        self.manager_role = Role.objects.create(
            name=Role.MANAGER,
            description='Manager role with limited admin access'
 )
        self.waiter_role = Role.objects.create(
            name=Role.WAITER,
            description='Waiter role for order management'
        )
        
        # Create test users
        self.admin_user = User.objects.create_superuser(
            email='admin@example.com',
            password='testpass123',
            first_name='Admin',
            last_name='User'
        )
        self.admin_user.role = self.admin_role
        self.admin_user.save()
        
        self.manager_user = User.objects.create_user(
            email='manager@example.com',
            password='testpass123',
            first_name='Manager',
            last_name='User',
            role=self.manager_role
        )
        
        self.waiter_user = User.objects.create_user(
            email='waiter@example.com',
            password='testpass123',
            first_name='Waiter',
            last_name='User',
            role=self.waiter_role
        )
        
        # Create some test permissions
        content_type = ContentType.objects.get_for_model(Role)
        self.view_permission = Permission.objects.create(
            codename='view_role',
            name='Can view role',
            content_type=content_type
        )
        self.add_permission = Permission.objects.create(
            codename='add_role',
            name='Can add role',
            content_type=content_type
        )
        self.change_permission = Permission.objects.create(
            codename='change_role',
            name='Can change role',
            content_type=content_type
        )
        self.delete_permission = Permission.objects.create(
            codename='delete_role',
            name='Can delete role',
            content_type=content_type
        )
        
        # Assign permissions to roles
        self.admin_role.permissions.add(
            self.view_permission,
            self.add_permission,
            self.change_permission,
            self.delete_permission
        )
        
        self.manager_role.permissions.add(
            self.view_permission,
            self.change_permission
        )
        
        self.waiter_role.permissions.add(
            self.view_permission
        )
        
        # Set up API client
        self.client = APIClient()
    
    def test_has_role_method(self):
        """Test the has_role method."""
        self.assertTrue(self.admin_user.has_role(Role.ADMIN))
        self.assertFalse(self.admin_user.has_role(Role.MANAGER))
        
        self.assertTrue(self.manager_user.has_role(Role.MANAGER))
        self.assertFalse(self.manager_user.has_role(Role.ADMIN))

    def test_has_any_role_method(self):
        """Test the has_any_role method."""
        self.assertTrue(
            self.admin_user.has_any_role(Role.ADMIN, Role.MANAGER)
        )
        self.assertTrue(
            self.manager_user.has_any_role(Role.MANAGER, Role.WAITER)
        )
        self.assertFalse(
            self.waiter_user.has_any_role(Role.ADMIN, Role.MANAGER)
        )
    
    def test_has_permission_method(self):
        """Test the has_permission method."""
        # Admin has all permissions
        self.assertTrue(self.admin_user.has_permission('view_role'))
        self.assertTrue(self.admin_user.has_permission('add_role'))
        self.assertTrue(self.admin_user.has_permission('change_role'))
        self.assertTrue(self.admin_user.has_permission('delete_role'))
        
        # Manager has view and change permissions
        self.assertTrue(self.manager_user.has_permission('view_role'))
        self.assertFalse(self.manager_user.has_permission('add_role'))
        self.assertTrue(self.manager_user.has_permission('change_role'))
        self.assertFalse(self.manager_user.has_permission('delete_role'))
        
        # Waiter only has view permission
        self.assertTrue(self.waiter_user.has_permission('view_role'))
        self.assertFalse(self.waiter_user.has_permission('add_role'))
        self.assertFalse(self.waiter_user.has_permission('change_role'))
        self.assertFalse(self.waiter_user.has_permission('delete_role'))
    
    def test_role_list_api_permissions(self):
        """Test role list API endpoint permissions."""
        url = '/api/accounts/roles/'
        
        # Unauthenticated user should get 401
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        
        # Waiter can view roles
        self.client.force_authenticate(user=self.waiter_user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 3)  # 3 roles in total
        
        # Manager can view roles
        self.client.force_authenticate(user=self.manager_user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Admin can view roles
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_role_create_api_permissions(self):
        ""Test role create API endpoint permissions."""
        url = '/api/accounts/roles/'
        data = {
            'name': 'test_role',
            'description': 'Test role',
            'permission_ids': [self.view_permission.id]
        }
        
        # Waiter cannot create roles
        self.client.force_authenticate(user=self.waiter_user)
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # Manager cannot create roles (only admin can)
        self.client.force_authenticate(user=self.manager_user)
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # Admin can create roles
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Role.objects.count(), 4)  # 3 initial + 1 new
        
    def test_role_update_api_permissions(self):
        ""Test role update API endpoint permissions."""
        # Create a test role to update
        role = Role.objects.create(
            name='test_role',
            description='Test role'
        )
        url = f'/api/accounts/roles/{role.id}/'
        data = {
            'name': 'updated_role',
            'description': 'Updated role',
            'permission_ids': [self.view_permission.id]
        }
        
        # Waiter cannot update roles
        self.client.force_authenticate(user=self.waiter_user)
        response = self.client.put(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # Manager can update roles
        self.client.force_authenticate(user=self.manager_user)
        response = self.client.put(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Admin can update roles
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.put(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify the role was updated
        role.refresh_from_db()
        self.assertEqual(role.name, 'updated_role')
        self.assertEqual(role.description, 'Updated role')
    
    def test_role_delete_api_permissions(self):
        ""Test role delete API endpoint permissions."""
        # Create a test role to delete
        role = Role.objects.create(
            name='test_role',
            description='Test role'
        )
        url = f'/api/accounts/roles/{role.id}/'
        
        # Waiter cannot delete roles
        self.client.force_authenticate(user=self.waiter_user)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # Manager cannot delete roles (only admin can)
        self.client.force_authenticate(user=self.manager_user)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # Admin can delete roles
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Role.objects.filter(id=role.id).count(), 0)
