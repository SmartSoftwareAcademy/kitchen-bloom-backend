import uuid

class MultiSerializerViewSetMixin(object):
    """
    Mixin to support multiple serializers for different actions in a ViewSet.
    
    Usage:
        class MyViewSet(MultiSerializerViewSetMixin, viewsets.ModelViewSet):
            serializer_class = DefaultSerializer
            serializer_action_classes = {
                'list': ListSerializer,
                'retrieve': DetailSerializer,
                'create': CreateSerializer,
                'update': UpdateSerializer,
            }
    """
    serializer_action_classes = {}

    def get_serializer_class(self):
        """
        Look for serializer class in self.serializer_action_classes, which
        should be a dict mapping action name (key) to serializer class (value).
        """
        try:
            return self.serializer_action_classes[self.action]
        except (KeyError, AttributeError):
            # Default to the regular get_serializer_class logic
            return super().get_serializer_class()


def generate_unique_barcode(prefix='PRD'):
    """
    Generate a unique barcode with the given prefix.
    Format: PREFIX-XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX (UUID v4)
    """
    return f"{prefix}-{str(uuid.uuid4())}"


class BarcodeMixin:
    """Mixin to handle barcode generation for models."""
    
    def generate_barcode(self, prefix='VAR'):
        """Generate a unique barcode for the variant with a different prefix."""
        return generate_unique_barcode(prefix)
    
    def save(self, *args, **kwargs):
        """Save the model instance, ensuring a unique barcode."""
        if not self.barcode:
            self.barcode = self.generate_barcode()
        super().save(*args, **kwargs)
