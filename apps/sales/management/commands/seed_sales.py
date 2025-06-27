import random
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models.signals import post_save, post_delete
from faker import Faker
from apps.branches.models import Branch, Company
from apps.crm.models import Customer
from apps.inventory.models import Product
from apps.sales.models import Order, OrderItem, Payment
from apps.tables.models import Table
from apps.inventory.models import MenuItem, Menu
from apps.accounting.models import Revenue, RevenueCategory, RevenueAccount
from apps.sales.services.accounting import create_revenue_for_order
from django.db import models
from apps.accounts.models import Role
from django.contrib.auth import get_user_model

User = get_user_model()

def get_or_create_branch():
    company = Company.objects.get_or_create(
        name='Kitchen Bloom',
        defaults={
            'code': 'MB001',
            'address': '123 Main St',
            'city': 'Nairobi',
            'country': 'Kenya',
            'phone': '+254700000000',
            'email': 'main@company.com',
        }
    )
    branch, _ = Branch.objects.get_or_create(
        name='Main Branch',
        defaults={
            'code': 'MB001',
            'address': '123 Main St',
            'city': 'Nairobi',
            'country': 'Kenya',
            'phone': '+254700000000',
            'email': 'main@branch.com',
        }
    )
    return branch

def get_or_create_customer():
    customer, _ = Customer.objects.get_or_create(
        customer_code='CUST0001',
        defaults={
            'customer_type': 'individual',
            'address_line1': '456 Customer Rd',
            'city': 'Nairobi',
            'country': 'Kenya',
            'alternate_phone': '+254700000001',
        }
    )
    return customer

def get_or_create_products(branch, count=5):
    products = list(Product.objects.all()[:count])
    if len(products) < count:
        for i in range(count - len(products)):
            p, _ = Product.objects.get_or_create(
                name=f'Product {i+1}',
                defaults={
                    'sku': f'SKU{i+1:04d}',
                    'unit_of_measure_id': 1,  # Adjust as needed
                    'cost_price': Decimal('100.00'),
                    'selling_price': Decimal('150.00'),
                    'is_active': True
                }
            )
            p.branches.add(branch)
            products.append(p)
    return products

def get_or_create_menu_items(branch, count=5):
    menu = Menu.objects.filter(branch=branch, is_active=True).first()
    if not menu:
        menu = Menu.objects.create(
            name='Main Menu',
            branch=branch,
            is_active=True,
            is_default=True
        )
    menu_items = list(MenuItem.objects.filter(menu=menu, is_available=True)[:count])
    if len(menu_items) < count:
        for i in range(count - len(menu_items)):
            mi, _ = MenuItem.objects.get_or_create(
                menu=menu,
                name=f'Menu Item {i+1}',
                defaults={
                    'selling_price': Decimal('200.00'),
                    'cost_price': Decimal('120.00'),
                    'is_available': True
                }
            )
            menu_items.append(mi)
    return menu_items

class Command(BaseCommand):
    help = 'Seed sales data with completed orders and revenue.'

    def add_arguments(self, parser):
        parser.add_argument('--orders', type=int, default=20, help='Number of orders to create (default: 20)')

    def handle(self, *args, **options):
        # Clear all relevant sales data
        self.stdout.write(self.style.WARNING('Clearing existing sales data...'))
        from apps.sales.models import OrderItem, Payment, Order
        OrderItem.objects.all().delete()
        Payment.objects.all().delete()
        Order.objects.all().delete()
        self.stdout.write(self.style.SUCCESS('Sales data cleared.'))
        # Find a user who is a waiter, accountant, or superuser
        user = User.objects.filter(
            models.Q(role__name=Role.WAITER) |
            models.Q(role__name=Role.ACCOUNTANT) |
            models.Q(is_superuser=True)
        ).first()
        if not user:
            self.stdout.write(self.style.ERROR('No suitable user (waiter, accountant, or superuser) found.'))
            return

        fake = Faker()
        order_count = max(options['orders'], 20)
        branch = get_or_create_branch()
        customer = get_or_create_customer()
        products = get_or_create_products(branch, count=5)
        menu_items = get_or_create_menu_items(branch, count=5)

        # Get or create revenue account and category
        revenue_account, _ = RevenueAccount.objects.get_or_create(
            code='SALES',
            defaults={
                'name': 'Sales Revenue',
                'account_type': 'sales',
                'description': 'Revenue from sales',
                'is_active': True
            }
        )
        revenue_category, _ = RevenueCategory.objects.get_or_create(
            name='Sales',
            defaults={
                'description': 'Sales revenue',
                'is_active': True,
                'default_account': revenue_account
            }
        )
        if not revenue_category.default_account:
            revenue_category.default_account = revenue_account
            revenue_category.save()

        self.stdout.write(self.style.SUCCESS('Seeding sales data...'))
        for i in range(order_count):
            order_number = f'ORD{i+1:05d}'
            subtotal = Decimal('0.00')
            tax_amount = Decimal('0.00')
            discount_amount = Decimal('0.00')
            total_amount = Decimal('0.00')
            order = Order.objects.create(
                order_number=order_number,
                branch=branch,
                order_type=random.choice([c[0] for c in Order.OrderType.choices]),
                status='completed',
                delivery_address=fake.address(),
                subtotal=Decimal('0.00'),
                tax_amount=Decimal('0.00'),
                discount_amount=Decimal('0.00'),
                total_amount=Decimal('0.00'),
                payment_status='paid',
                payment_method=random.choice([c[0] for c in Order.PaymentMethod.choices]),
                notes=fake.sentence(),
                created_by=user,
                last_modified_by=user,
            )
            order._skip_ws = True
            order.save()
            order.customers.add(customer)
            tables = Table.objects.filter(branch=branch)
            if tables.exists():
                table = random.choice(list(tables))
                order.tables.add(table)
            # Add order items: mix of product and menu_item
            item_count = random.randint(2, 5)
            order_items = []
            for idx in range(item_count):
                if idx % 2 == 0 and products:
                    product = random.choice(products)
                    quantity = Decimal(random.randint(1, 5))
                    unit_price = product.selling_price
                    item_type = 'product'
                    menu_item = None
                else:
                    menu_item = random.choice(menu_items)
                    quantity = Decimal(random.randint(1, 5))
                    unit_price = menu_item.selling_price
                    item_type = 'menu_item'
                    product = None
                item_subtotal = quantity * unit_price
                item_tax = item_subtotal * Decimal('0.16')
                item_discount = Decimal('0.00')
                item_total = item_subtotal + item_tax - item_discount
                subtotal += item_subtotal
                tax_amount += item_tax
                discount_amount += item_discount
                total_amount += item_total
                order_item = OrderItem(
                    order=order,
                    item_type=item_type,
                    product=product if item_type == 'product' else None,
                    menu_item=menu_item if item_type == 'menu_item' else None,
                    quantity=quantity,
                    unit_price=unit_price,
                    discount_amount=item_discount,
                    tax_amount=item_tax,
                    subtotal=item_subtotal,
                    total=item_total,
                    notes=fake.sentence(),
                    kitchen_notes=fake.sentence(),
                )
                order_item._skip_ws = True
                order_items.append(order_item)
            OrderItem.objects.bulk_create(order_items)
            order.subtotal = subtotal
            order.tax_amount = tax_amount
            order.discount_amount = discount_amount
            order.total_amount = total_amount
            order._skip_ws = True
            order.save()
            # Add payment
            payment = Payment(
                order=order,
                amount=total_amount,
                method=random.choice([c[0] for c in Payment.PaymentMethod.choices]),
                status='completed',
                transaction_reference=fake.uuid4(),
                notes=fake.sentence(),
                created_by=user,
                last_modified_by=user,
            )
            payment._skip_ws = True
            payment.save(force_insert=True)
            # Create revenue for this order
            create_revenue_for_order(order, payment)
            self.stdout.write(self.style.SUCCESS(f'Created order {order.order_number} with {item_count} items, payment, and revenue.'))
        self.stdout.write(self.style.SUCCESS('Sales data seeding complete.'))

# NOTE: For further admin/serializer optimization, consider using select_related/prefetch_related in admin queryset and serializer to avoid N+1 queries when viewing order details. 