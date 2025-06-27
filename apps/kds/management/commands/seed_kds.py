import random
from django.core.management.base import BaseCommand
from faker import Faker
from apps.kds.models import KDSStation, KDSItem
from apps.branches.models import Branch
from apps.sales.models import Order, OrderItem
from apps.inventory.models import Product
from django.contrib.auth import get_user_model

User = get_user_model()

class Command(BaseCommand):
    help = 'Seed demo KDS stations and items for development/testing.'

    def add_arguments(self, parser):
        parser.add_argument('--stations', type=int, default=3, help='Number of KDS stations to create')
        parser.add_argument('--items', type=int, default=10, help='Number of KDS items per station')

    def handle(self, *args, **options):
        fake = Faker()
        station_count = options['stations']
        items_per_station = options['items']

        branch = Branch.objects.first()
        if not branch:
            self.stdout.write(self.style.ERROR('No branch found. Please seed branches first.'))
            return

        # Create KDS stations
        station_types = ['hot_kitchen', 'cold_kitchen', 'prep', 'beverage']
        stations = []
        for i in range(station_count):
            station, _ = KDSStation.objects.get_or_create(
                branch=branch,
                name=f"KDS Station {i+1}",
                defaults={
                    'station_type': random.choice(station_types),
                    'description': fake.sentence(),
                    'is_active': True,
                    'metadata': {'screen_size': random.choice(['15\"', '21\"', '27\"'])}
                }
            )
            stations.append(station)
            self.stdout.write(self.style.SUCCESS(f'Created station: {station.name}'))

        # Get or create a user for created_by
        user = User.objects.filter(is_active=True).first()

        # Get or create a product for order items
        product = Product.objects.first()
        if not product:
            self.stdout.write(self.style.ERROR('No product found. Please seed products first.'))
            return

        # Create KDS items (and OrderItems) for each station
        for station in stations:
            for j in range(items_per_station):
                # Create a fake order
                order, _ = Order.objects.get_or_create(
                    branch=branch,
                    status=random.choice([
                        Order.Status.CONFIRMED,
                        Order.Status.PROCESSING,
                        Order.Status.READY
                    ]),
                    order_type=Order.OrderType.DINE_IN,
                    defaults={
                        'service_type': Order.ServiceType.REGULAR,
                        'notes': fake.sentence(),
                    }
                )
                # Create a fake order item (signal will create KDSItem)
                order_item = OrderItem.objects.create(
                    order=order,
                    product=product,
                    item_type=OrderItem.ItemType.PRODUCT,
                    quantity=random.randint(1, 5),
                    unit_price=product.selling_price,
                    status=OrderItem.Status.PREPARING,
                    kitchen_status=OrderItem.Status.PREPARING,
                    notes=fake.sentence(),
                    kitchen_notes=fake.sentence(),
                )
                self.stdout.write(self.style.SUCCESS(
                    f'Created OrderItem: {order_item.id} (Order: {order.order_number})'
                ))

        self.stdout.write(self.style.SUCCESS(
            f'Successfully seeded {station_count} KDS stations and {station_count * items_per_station} KDS items.'
        ))