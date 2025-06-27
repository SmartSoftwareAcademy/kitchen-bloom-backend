from django.urls import re_path
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from django.core.asgi import get_asgi_application

# Import WebSocket consumers
from apps.sales.routing import websocket_urlpatterns as sales_websocket_urls

# Combine all WebSocket URL patterns
websocket_urlpatterns = []
websocket_urlpatterns += sales_websocket_urls

# Define the application
application = ProtocolTypeRouter({
    'http': get_asgi_application(),
    'websocket': AuthMiddlewareStack(
        URLRouter(
            websocket_urlpatterns
        )
    ),
})
