"""
Custom permission classes and utilities for role-based access control (RBAC).
"""
from rest_framework import permissions
from django.contrib.auth.models import Permission

def get_permission_codename(action, opts):
    """
    Return the codename for the permission for the specified action.
    """
    return f"{action}_{opts.model_name}"

class RolePermissionMixin:
    """
    Mixin that provides role-based permission checking.
    """
    def has_permission(self, user, permission_codename):
        """
        Check if user has the specified permission through their role.
        """
        if not user.is_authenticated:
            return False
            
        # Superusers have all permissions
        if user.is_superuser:
            return True
            
        # Check if the user's role has the permission
        if user.role and user.role.permissions.filter(codename=permission_codename).exists():
            return True
            
        # Check if user has the permission directly
        return user.has_perm(permission_codename)

class RolePermission(permissions.BasePermission, RolePermissionMixin):
    """
    Permission class that checks if the user's role has the required permission.
    """
    def has_permission(self, request, view):
        # Get the required permission from the view
        required_permission = getattr(view, 'required_permission', None)
        if not required_permission:
            return True  # No permission required
            
        return self.has_permission(request.user, required_permission)

class HasPermissionOrReadOnly(permissions.BasePermission, RolePermissionMixin):
    """
    Permission class that allows read-only access to all users,
    but requires specific permission for write operations.
    """
    def has_permission(self, request, view):
        # Read permissions are allowed to any request,
        # so we'll always allow GET, HEAD or OPTIONS requests.
        if request.method in permissions.SAFE_METHODS:
            return True
            
        # Get the required permission from the view
        required_permission = getattr(view, 'required_permission', None)
        if not required_permission:
            return True  # No permission required
            
        return self.has_permission(request.user, required_permission)

class IsAdminOrReadOnly(permissions.BasePermission):
    """
    Permission class that allows read-only access to all users,
    but requires admin role for write operations.
    """
    def has_permission(self, request, view):
        # Read permissions are allowed to any request,
        # so we'll always allow GET, HEAD or OPTIONS requests.
        if request.method in permissions.SAFE_METHODS:
            return True
            
        # Write permissions are only allowed to admin users
        return request.user and request.user.is_staff

def get_role_permissions(role):
    """
    Get all permissions assigned to a role.
    """
    if not role:
        return []
    return role.permissions.all()

def assign_permissions_to_role(role, permission_codenames):
    """
    Assign a list of permission codenames to a role.
    """
    if not role:
        return False
        
    permissions = Permission.objects.filter(codename__in=permission_codenames)
    role.permissions.set(permissions)
    return True

def get_user_permissions(user):
    """
    Get all permissions for a user, including those from their role.
    """
    if not user or not user.is_authenticated:
        return set()
        
    if user.is_superuser:
        # Superusers have all permissions
        return set(Permission.objects.values_list('codename', flat=True))
        
    permissions = set()
    
    # Get permissions from the user's role
    if user.role:
        role_permissions = user.role.permissions.values_list('codename', flat=True)
        permissions.update(role_permissions)
    
    # Get direct user permissions
    user_permissions = user.user_permissions.values_list('codename', flat=True)
    permissions.update(user_permissions)
    
    # Get permissions from user's groups
    group_permissions = Permission.objects.filter(
        group__user=user
    ).values_list('codename', flat=True)
    permissions.update(group_permissions)
    
    return permissions
