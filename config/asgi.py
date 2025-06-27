"""
ASGI config for core project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/asgi/
"""
import os
from django.core.asgi import get_asgi_application
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

if settings.DEBUG:
    application = get_asgi_application()
else:
    from channels.routing import ProtocolTypeRouter
    application = ProtocolTypeRouter({
        "http": get_asgi_application(),
        # Disable websockets if not used
    })