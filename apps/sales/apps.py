from django.apps import AppConfig


class SalesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.sales'
    label = 'sales'
    
    def ready(self):
        # Import and connect signals when the app is ready
        import apps.sales.signals
