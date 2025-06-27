#generate common units of measure like kg, g, ml, l, pcs, doz, pkt middleware

from django.utils.deprecation import MiddlewareMixin
from .models import UnitOfMeasure

class SeedDefaultConfigsMiddleware(MiddlewareMixin):
    def process_request(self, request):
        list_of_units = [
            {'name': 'Kilogram', 'code': 'kg', 'symbol': 'kg', 'is_fraction_allowed': True},
            {'name': 'Gram', 'code': 'g', 'symbol': 'g', 'is_fraction_allowed': True},
            {'name': 'Milligram', 'code': 'mg', 'symbol': 'mg', 'is_fraction_allowed': False},
            {'name': 'Liter', 'code': 'l', 'symbol': 'L', 'is_fraction_allowed': True},
            {'name': 'Milliliter', 'code': 'ml', 'symbol': 'mL', 'is_fraction_allowed': False},
            {'name': 'Piece', 'code': 'pcs', 'symbol': 'pcs', 'is_fraction_allowed': False},
            {'name': 'Dozen', 'code': 'doz', 'symbol': 'doz', 'is_fraction_allowed': False},
            {'name': 'Packet', 'code': 'pkt', 'symbol': 'pkt', 'is_fraction_allowed': False},
            {'name': 'Square Meter', 'code': 'sqm', 'symbol': 'm2', 'is_fraction_allowed': True},
            {'name':'Pieces','code':'pcs','symbol':'pcs','is_fraction_allowed':False}
        ]
        
        for unit in list_of_units:
            UnitOfMeasure.objects.get_or_create(
                code=unit['code'],
                defaults=unit
            )

