from email.policy import default
import uuid
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager, Permission
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from phonenumber_field.modelfields import PhoneNumberField

from apps.base.models import BaseNameDescriptionModel, TimestampedModel, UserMixin


class UserManager(BaseUserManager):
    """Custom user model manager where email is the unique identifier."""
    
    def create_user(self, email, password=None, **extra_fields):
        """Create and save a user with the given email and password."""
        if not email:
            raise ValueError(_('The Email must be set'))
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        """Create and save a SuperUser with the given email and password."""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError(_('Superuser must have is_staff=True.'))
        if extra_fields.get('is_superuser') is not True:
            raise ValueError(_('Superuser must have is_superuser=True.'))
        return self.create_user(email, password, **extra_fields)


class Role(BaseNameDescriptionModel):
    """Role model for user permissions."""
    ADMIN = 'admin'
    MANAGER = 'manager'
    CASHIER = 'cashier'
    KITCHEN_STAFF = 'kitchen_staff'
    WAITER = 'waiter'
    ACCOUNTANT = 'accountant'
    
    ROLE_CHOICES = [
        (ADMIN, _('Administrator')),
        (MANAGER, _('Manager')),
        (CASHIER, _('Cashier')),
        (KITCHEN_STAFF, _('Kitchen Staff')),
        (WAITER, _('Waiter')),
        (ACCOUNTANT, _('Accountant')),
    ]
    
    name = models.CharField(_('name'), max_length=50, choices=ROLE_CHOICES, unique=True)
    description = models.TextField(_('description'), blank=True, null=True)
    base_salary=models.DecimalField(max_digits=14,decimal_places=4,default=10000)
    max_salary=models.DecimalField(max_digits=14,decimal_places=4,default=250000)
    permissions = models.ManyToManyField(
        'auth.Permission',
        verbose_name=_('permissions'),
        blank=True,
        related_name='role_permissions'
    )
    
    class Meta:
        verbose_name = _('role')
        verbose_name_plural = _('roles')
    
    def __str__(self):
        return self.get_name_display()


class User(AbstractBaseUser, PermissionsMixin, TimestampedModel, UserMixin):
    """Custom user model that supports using email instead of username."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(_('email address'), unique=True, db_index=True)
    phone_number = PhoneNumberField(_('phone number'), blank=True, null=True, db_index=True)
    first_name = models.CharField(_('first name'), max_length=150, blank=False)
    last_name = models.CharField(_('last name'), max_length=150, blank=False)
    
    # Authentication fields
    is_staff = models.BooleanField(_('staff status'),default=False,help_text=_('Designates whether the user can log into this admin site.'))
    is_active = models.BooleanField(_('active'),default=True,help_text=_('Designates whether this user should be treated as active. Unselect this instead of deleting accounts.'))
    is_verified = models.BooleanField(_('verified'),default=True,help_text=_('Designates whether this user has verified their email address.'))
    
    # Timestamps
    date_joined = models.DateTimeField(_('date joined'), default=timezone.now)
    last_login = models.DateTimeField(_('last login'), auto_now=True)
    
    # Relationships
    role = models.ForeignKey('accounts.Role',on_delete=models.PROTECT,related_name='users',verbose_name=_('role'),null=True,blank=True)
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']
    
    objects = UserManager()
    
    class Meta:
        verbose_name = _('user')
        verbose_name_plural = _('users')
        indexes = [
            models.Index(fields=['last_login']),
            models.Index(fields=['email']),
        ]

    def __str__(self):
        return self.get_full_name() or self.email
    
    def get_full_name(self):
        """Return the first_name plus the last_name, with a space in between."""
        full_name = f'{self.first_name} {self.last_name}'.strip()
        return full_name if full_name else None
    
    def get_short_name(self):
        """Return the short name for the user."""
        return self.first_name or self.email.split('@')[0]
        
    def has_role(self, role_name):
        """Check if user has the specified role."""
        if not self.role:
            return False
        return self.role.name == role_name
        
    def has_any_role(self, *role_names):
        """Check if user has any of the specified roles."""
        if not self.role:
            return False
        return self.role.name in role_names
        
    def has_permission(self, permission_codename):
        """Check if user has the specified permission."""
        
        # Superusers have all permissions
        if self.is_superuser:
            return True
            
        # Check role permissions first
        if self.role and self.role.permissions.filter(codename=permission_codename).exists():
            return True
            
        # Check direct user permissions
        if self.user_permissions.filter(codename=permission_codename).exists():
            return True
            
        # Check group permissions
        return self.groups.filter(permissions__codename=permission_codename).exists()
        
    def get_all_permissions(self, obj=None):
        """
        Return a set of permission strings (app_label.codename) that the user has.
        For superusers, returns an empty set (but has_perm/has_module_perms will still return True).
        """
        if not hasattr(self, '_perm_cache'):
            from django.contrib.auth.models import Permission

            if self.is_anonymous or not self.is_active:
                self._perm_cache = set()
                return self._perm_cache

            # For superusers, we don't need to load all permissions
            if self.is_superuser:
                self._perm_cache = set()
                return self._perm_cache

            perms = set()

            # Get role permissions (if role exists)
            if self.role_id:  # Use ID to avoid fetching the full role
                perms.update(
                    Permission.objects.filter(role_permissions__id=self.role_id)
                    .values_list('content_type__app_label', 'codename')
                )

            # Get user permissions
            perms.update(
                self.user_permissions.values_list('content_type__app_label', 'codename')
            )

            # Get group permissions
            perms.update(
                Permission.objects.filter(group__user=self)
                .values_list('content_type__app_label', 'codename')
            )

            # Convert to "app_label.codename" format
            self._perm_cache = {f"{app_label}.{codename}" for app_label, codename in perms}

        return self._perm_cache

    def has_module_perms(self, app_label):
        """Check if user has any permissions for the given app."""
        if self.is_superuser:
            return True  # Superusers have all permissions

        # Check cached permissions
        perms = self.get_all_permissions()
        
        # Check if any permission starts with the app_label
        return any(p.startswith(f"{app_label}.") for p in perms)

    def has_perm(self, perm, obj=None):
        """Check if user has a specific permission."""
        if self.is_superuser:
            return True

        # First check the permission cache
        perms = self.get_all_permissions()
        if perm in perms:
            return True

        # If not in cache, do direct checks (more efficient than loading all permissions)
        try:
            app_label, codename = perm.split('.')
        except ValueError:
            return False

        # Check role permissions
        if self.role_id and self.role.permissions.filter(
            content_type__app_label=app_label,
            codename=codename
        ).exists():
            return True

        # Check user permissions
        if self.user_permissions.filter(
            content_type__app_label=app_label,
            codename=codename
        ).exists():
            return True

        # Check group permissions
        if Permission.objects.filter(
            group__user=self,
            content_type__app_label=app_label,
            codename=codename
        ).exists():
            return True

        return False
    
class OTP(TimestampedModel):
    """
    One-Time Password model for email/phone verification and password reset.
    
    Attributes:
        user: The user this OTP belongs to
        otp: The OTP code
        otp_type: Type of OTP (email verification, phone verification, etc.)
        is_used: Whether the OTP has been used
        expires_at: When the OTP expires
        verified_at: When the OTP was verified
        max_attempts: Maximum number of verification attempts
        attempts_remaining: Remaining verification attempts
    """
    EMAIL_VERIFICATION = 'email_verification'
    PHONE_VERIFICATION = 'phone_verification'
    PASSWORD_RESET = 'password_reset'
    LOGIN_VERIFICATION = 'login_verification'
    
    OTP_TYPE_CHOICES = [
        (EMAIL_VERIFICATION, _('Email Verification')),
        (PHONE_VERIFICATION, _('Phone Verification')),
        (PASSWORD_RESET, _('Password Reset')),
        (LOGIN_VERIFICATION, _('Login Verification')),
    ]
    
    user = models.ForeignKey('accounts.User',on_delete=models.CASCADE,related_name='otps',verbose_name=_('user'))
    otp = models.CharField(_('otp'), max_length=10, db_index=True)
    otp_type = models.CharField(_('otp type'), max_length=30, choices=OTP_TYPE_CHOICES, db_index=True)
    is_used = models.BooleanField(_('is used'), default=False, db_index=True)
    expires_at = models.DateTimeField(_('expires at'), db_index=True)
    verified_at = models.DateTimeField(_('verified at'), null=True, blank=True)
    max_attempts = models.PositiveSmallIntegerField(_('max attempts'), default=3)
    attempts_remaining = models.PositiveSmallIntegerField(_('attempts remaining'), default=3)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = _('OTP')
        verbose_name_plural = _('OTPs')
    
    def __str__(self):
        return f"{self.get_otp_type_display()} OTP for {self.user.email}"
    
    @property
    def is_expired(self):
        """Check if the OTP has expired."""
        return timezone.now() > self.expires_at
        
    @property
    def is_valid(self):
        """Check if the OTP is still valid (not used, not expired, and has attempts remaining)."""
        return not self.is_used and not self.is_expired and self.attempts_remaining > 0


class UserSession(TimestampedModel):
    """Track user sessions for security and analytics."""
    user = models.ForeignKey('accounts.User',on_delete=models.CASCADE,related_name='sessions',verbose_name=_('user'))
    session_key = models.CharField(_('session key'), max_length=40, db_index=True)
    user_agent = models.TextField(_('user agent'), blank=True, null=True)
    ip_address = models.GenericIPAddressField(_('ip address'), blank=True, null=True)
    last_activity = models.DateTimeField(_('last activity'), auto_now=True)
    is_active = models.BooleanField(_('is active'), default=True)
    
    class Meta:
        verbose_name = _('user session')
        verbose_name_plural = _('user sessions')
        ordering = ['-last_activity']
    
    def __str__(self):
        return f"{self.user.email} - {self.session_key}"
