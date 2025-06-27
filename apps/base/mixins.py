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
