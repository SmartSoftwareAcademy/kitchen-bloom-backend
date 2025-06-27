from django.apps import AppConfig


class InventoryConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.inventory'
    label = 'inventory'

    def ready(self):
        # Import and connect signals when the app is ready
        import apps.inventory.signals
