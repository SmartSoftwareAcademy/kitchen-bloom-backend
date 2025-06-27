"""
Django settings for Kitchen Bloom POS + KDS system.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/topics/settings/
"""

import os
from pathlib import Path
from datetime import timedelta
import sys
import logging
from .jazzmin import JAZZMIN_SETTINGS
from corsheaders.defaults import default_headers
import dj_database_url
from urllib.parse import urlparse
import logging

logger = logging.getLogger(__name__)


# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Add apps directory to Python path
sys.path.insert(0, os.path.join(BASE_DIR, '..', 'apps'))

# Custom Unicode-safe console handler
class UnicodeSafeStreamHandler(logging.StreamHandler):
    """A StreamHandler that safely handles Unicode characters on Windows."""
    
    def emit(self, record):
        try:
            msg = self.format(record)
            stream = self.stream
            
            # For Windows console, handle Unicode properly
            if hasattr(stream, 'buffer'):
                # Use the underlying buffer for binary writing
                stream.buffer.write(msg.encode('utf-8'))
                stream.buffer.flush()
            else:
                # Fallback to regular write
                stream.write(msg)
                stream.flush()
        except UnicodeEncodeError:
            # If Unicode encoding fails, try to encode with error handling
            try:
                msg = self.format(record)
                stream = self.stream
                if hasattr(stream, 'buffer'):
                    stream.buffer.write(msg.encode('utf-8', errors='replace'))
                    stream.buffer.flush()
                else:
                    stream.write(msg.encode('utf-8', errors='replace').decode('utf-8'))
                    stream.flush()
            except Exception:
                self.handleError(record)
        except Exception:
            self.handleError(record)

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'django-insecure-*s6=s+r=n$jh-kgwr@0#5_$z$#m45s2*nog5x3s8ef=36y$mi7')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get('DJANGO_DEBUG', 'True') == 'True'

# ALLOWED_HOSTS = os.environ.get('DJANGO_ALLOWED_HOSTS', '*').split(',')
ALLOWED_HOSTS = ['*']

#jazzmin modals not working fix
X_FRAME_OPTIONS = 'SAMEORIGIN'


# Application definition

INSTALLED_APPS = [
    # Django Channels must come before django.contrib.staticfiles
    'daphne',
    'channels',
    
    # Jazzmin must come before django.contrib.admin
    'jazzmin',
    # Django built-in apps
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    
    # Third-party apps
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'drf_spectacular',
    'phonenumber_field',
    'health_check',
    'health_check.db',
    'health_check.cache',
    'health_check.storage',
    'django_filters',
    'crum',  # For tracking current request user in middleware
    'mfa',
    
    # Local apps
    'apps.accounts',
    'apps.accounting',
    'apps.branches',
    'apps.base',
    'apps.crm',
    'apps.employees',
    'apps.inventory',
    'apps.kds',
    'apps.loyalty',
    'apps.payroll',
    'apps.tables',
    'apps.reporting',
    'apps.sales',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',  # Must be after SessionMiddleware
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'crum.CurrentRequestUserMiddleware',
    'apps.base.middleware.SeedDefaultConfigsMiddleware',
]

# MFA settings
MFA_UNALLOWED_METHODS=() 
# Methods that shouldn't be allowed for the user MFA_LOGIN_CALLBACK=""
#  A function that should be called by username to login the user in session MFA_RECHECK=True 
# Allow random rechecking of the user MFA_RECHECK_MIN=10 
# Minimum interval in seconds MFA_RECHECK_MAX=30 
# Maximum in seconds MFA_QUICKLOGIN=True 
# Allow quick login for returning users by provide only their 2FA
TOKEN_ISSUER_NAME="Kitchen Bloom" #TOTP Issuer name
U2F_APPID="https://localhost" #URL For U2 FIDO_SERVER_ID=u"localehost" 
# Server rp id for FIDO2, it the full domain of your project FIDO_SERVER_NAME=u"PROJECT_NAME" FIDO_LOGIN_URL=BASE_URL
FIDO_SERVER_ID=u"localhost" # Server rp id for FIDO2, it the full domain of your project FIDO_SERVER_NAME=u"PROJECT_NAME" FIDO_LOGIN_URL=BASE_URL
MFA_ENABLED = True
MFA_SMS_PROVIDER = 'africastalking'
MFA_SMS_PROVIDER_API_KEY = os.environ.get('MFA_SMS_PROVIDER_API_KEY')
MFA_SMS_PROVIDER_USERNAME = os.environ.get('MFA_SMS_PROVIDER_USERNAME')

# CORS settings
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOWED_ORIGINS = [
    'http://localhost:5173',
    'http://127.0.0.1:5173',
]

# Authentication backends
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
]

# JWT Settings
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
}

# REST Framework settings
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
}

# JWT Settings
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
}

# Spectacular API Schema
SPECTACULAR_SETTINGS = {
    'TITLE': 'Kitchen Bloom POS + KDS API',
    'DESCRIPTION': 'API documentation for Kitchen Bloom POS and KDS system',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
}

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': ['templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# Default primary key field type
# https://docs.djangoproject.com/en/4.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Enable channels layer for development
os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"

# Database
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases
db_url = os.getenv('DATABASE_URL', 'postgresql://postgres:ZlaOXwlvqjDUqlBcOpXIkODrLPiLrEVb@nozomi.proxy.rlwy.net:23252/railway')
logger.info(f"Using DATABASE_URL: {db_url}")
#print(os.environ['DATABASE_URL'])
DATABASES = {
    'default': dj_database_url.config(
        default=db_url, 
        conn_max_age=600, 
        ssl_require=True
    )
}
# Fall back to individual settings
# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.postgresql',
#         'NAME': os.getenv('POSTGRES_DB', 'kitchen_bloom'),
#         'USER': os.getenv('POSTGRES_USER', 'postgres'),
#         'PASSWORD': os.getenv('POSTGRES_PASSWORD', 'postgres'),
#         'HOST': os.getenv('POSTGRES_HOST', 'localhost'),
#         'PORT': os.getenv('POSTGRES_PORT', '5432'),
#     }
# }
  
# Password validation
# https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Phone number settings
PHONENUMBER_DB_FORMAT = 'E164'
PHONENUMBER_DEFAULT_REGION = 'KE'  # Kenya
PHONENUMBER_DEFAULT_FORMAT = 'INTERNATIONAL'

# OTP settings
OTP_EXPIRY_MINUTES = 15
OTP_LENGTH = 6
OTP_MAX_ATTEMPTS = 3
OTP_RESEND_TIMEOUT = 60  # seconds

# Default currency
DEFAULT_CURRENCY = 'KES'
SUPPORTED_CURRENCIES = ['KES', 'USD']

# Logging configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
        'detailed': {
            'format': '{levelname} {asctime} {name} {module} {funcName} {lineno} {message}',
            'style': '{',
        },
    },
    'filters': {
        'require_debug_true': {
            '()': 'django.utils.log.RequireDebugTrue',
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'filters': ['require_debug_true'],
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
            'stream': 'ext://sys.stdout'
        },
        'file': {
            'level': 'ERROR',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(BASE_DIR, 'logs/error.log'),
            'maxBytes': 1024 * 1024 * 5,  # 5 MB
            'backupCount': 5,
            'formatter': 'verbose',
            'encoding': 'utf-8',
        },
        'signals_file': {
            'level': 'DEBUG',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(BASE_DIR, 'logs/signals.log'),
            'maxBytes': 1024 * 1024 * 5,  # 5 MB
            'backupCount': 5,
            'formatter': 'detailed',
            'encoding': 'utf-8',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': True,
        },
        'apps': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG' if DEBUG else 'INFO',
            'propagate': True,
        },
        'apps.inventory.signals': {
            'handlers': ['console', 'signals_file'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'apps.sales.signals': {
            'handlers': ['console', 'signals_file'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}

# Create logs directory if it doesn't exist
os.makedirs(os.path.join(BASE_DIR, 'logs'), exist_ok=True)

# Custom user model
AUTH_USER_MODEL = 'accounts.User'

# Authentication URLs
LOGIN_URL = 'rest_framework:login'
LOGOUT_URL = 'rest_framework:logout'

# Internationalization
# https://docs.djangoproject.com/en/4.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'Africa/Nairobi'

USE_I18N = True

USE_L10N = True

USE_TZ = True

# Supported languages
LANGUAGES = [
    ('en', 'English'),
    ('sw', 'Swahili'),
]

LOCALE_PATHS = [
    os.path.join(BASE_DIR, 'locale'),
]

# CORS settings
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_ALL_ORIGINS = True  # For development only! Use CORS_ALLOWED_ORIGINS in production.

# Explicitly allowed origins for CORS
CORS_ALLOWED_ORIGINS = [
    "http://127.0.0.1:5173",
    "http://localhost:5173",
]

CORS_ALLOW_HEADERS = list(default_headers) + [
    'authorization',
    'x-branch-id',
]

# CSRF settings
CSRF_TRUSTED_ORIGINS = [
    'http://127.0.0.1:5173',
    'http://localhost:5173',
]
CSRF_COOKIE_HTTPONLY = False  # Allow JavaScript to read the CSRF cookie
CSRF_COOKIE_SAMESITE = 'Lax'  # Lax same-site policy is a good default
CSRF_USE_SESSIONS = False  # Use cookies for CSRF tokens (default)
CSRF_COOKIE_SECURE = False  # Set to True in production with HTTPS
CSRF_COOKIE_NAME = 'csrftoken'  # Default cookie name

# Session settings
SESSION_COOKIE_SECURE = False  # Set to True in production with HTTPS
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'

# For development - allow requests from any origin (remove in production)
CORS_ORIGIN_ALLOW_ALL = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/
STATIC_URL = '/static/'
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Media files (Uploads)
if DEBUG:
    MEDIA_URL = '/media/'
    MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
else:
    # settings.py
    CLOUDINARY_STORAGE = {
        'CLOUD_NAME': os.environ.get('CLOUDINARY_CLOUD_NAME', 'dvynnjixc'),
        'API_KEY': os.environ.get('CLOUDINARY_API_KEY', '153798342855752'),
        'API_SECRET': os.environ.get('CLOUDINARY_API_SECRET', 'QL2NLOUV3d0OkRLpMkuKnsCzwsE'),
    }
    MEDIA_URL = '/media/'
    DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'

# Channels ASGI application
ASGI_APPLICATION = 'config.routing.application'

# Channel layer configuration (using Redis)
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            "hosts": [('127.0.0.1', 6379)],
        },
    },
}

# Email settings (for OTP)
EMAIL_BACKEND = os.environ.get(
    'EMAIL_BACKEND',
    'django.core.mail.backends.console.EmailBackend'
)
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'codevertexitsolutions@gmail.com')
JAZZMIN_SETTINGS=JAZZMIN_SETTINGS

# REST Framework settings
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
}

# drf-spectacular settings for API documentation
SPECTACULAR_SETTINGS = {
    'TITLE': 'Kitchen Bloom POS + KDS API',
    'DESCRIPTION': 'API documentation for Kitchen Bloom POS and Kitchen Display System',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'COMPONENT_SPLIT_REQUEST': True,  # Split request/response schemas
    'SCHEMA_PATH_PREFIX': r'/api/',
    'SCHEMA_PATH_PREFIX_TRIM': True,
    'SERVERS': [
        {'url': 'http://localhost:8000', 'description': 'Local Development'},
        {'url': 'https://api.kitchenbloom.com', 'description': 'Production'},
    ],
    'TAGS': [
        {'name': 'auth', 'description': 'Authentication and user management'},
        {'name': 'accounting', 'description': 'Financial operations including gift cards'},
        {'name': 'crm', 'description': 'Customer relationship management'},
        {'name': 'inventory', 'description': 'Product and stock management'},
        {'name': 'sales', 'description': 'Sales and order processing'},
        {'name': 'kds', 'description': 'Kitchen Display System'},
    ],
    'SECURITY': [
        {
            'bearerAuth': [],
        },
    ],
}

# Swagger UI settings (for drf-yasg)
SWAGGER_SETTINGS = {
    'SECURITY_DEFINITIONS': {
        'Bearer': {
            'type': 'apiKey',
            'name': 'Authorization',
            'in': 'header'
        }
    },
    'USE_SESSION_AUTH': False,
    'JSON_EDITOR': True,
}

# Enable/disable KDS WebSocket updates (default: False for development)
KDS_WEBSOCKETS_ENABLED = os.environ.get('KDS_WEBSOCKETS_ENABLED', 'False') == 'True'


