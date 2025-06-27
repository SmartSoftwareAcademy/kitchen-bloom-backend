from django.core.management.base import BaseCommand
from django.db import transaction
from apps.inventory.models import Product, BranchStock
from apps.branches.models import Branch
from decimal import Decimal


class Command(BaseCommand):
    help = 'Set up initial inventory stock for existing products'

    def add_arguments(self, parser):
        parser.add_argument(
            '--initial-stock',
            type=float,
            default=10.0,
            help='Initial stock level for products (default: 10.0)'
        )
        parser.add_argument(
            '--reorder-level',
            type=float,
            default=5.0,
            help='Reorder level for products (default: 5.0)'
        )
        parser.add_argument(
            '--branch-id',
            type=int,
            help='Specific branch ID to set up stock for (optional)'
        )
        parser.add_argument(
            '--product-id',
            type=int,
            help='Specific product ID to set up stock for (optional)'
        )

    def handle(self, *args, **options):
        initial_stock = Decimal(str(options['initial_stock']))
        reorder_level = Decimal(str(options['reorder_level']))
        branch_id = options.get('branch_id')
        product_id = options.get('product_id')

        # Get branches
        if branch_id:
            branches = Branch.objects.filter(id=branch_id, is_active=True)
            if not branches.exists():
                self.stdout.write(
                    self.style.ERROR(f'Branch with ID {branch_id} not found or not active')
                )
                return
        else:
            branches = Branch.objects.filter(is_active=True)

        # Get products
        if product_id:
            products = Product.objects.filter(id=product_id, is_active=True)
            if not products.exists():
                self.stdout.write(
                    self.style.ERROR(f'Product with ID {product_id} not found or not active')
                )
                return
        else:
            products = Product.objects.filter(is_active=True)

        self.stdout.write(
            self.style.SUCCESS(
                f'Setting up inventory stock for {products.count()} products across {branches.count()} branches'
            )
        )

        created_count = 0
        updated_count = 0

        with transaction.atomic():
            for branch in branches:
                for product in products:
                    branch_stock, created = BranchStock.objects.get_or_create(
                        product=product,
                        branch=branch,
                        defaults={
                            'current_stock': initial_stock,
                            'reorder_level': reorder_level,
                            'cost_price': product.cost_price,
                            'selling_price': product.selling_price,
                            'is_active': True
                        }
                    )

                    if created:
                        created_count += 1
                        self.stdout.write(
                            f'Created stock for {product.name} at {branch.name}: {initial_stock} units'
                        )
                    else:
                        # Update existing stock if it's zero
                        if branch_stock.current_stock == 0:
                            branch_stock.current_stock = initial_stock
                            branch_stock.reorder_level = reorder_level
                            branch_stock.save()
                            updated_count += 1
                            self.stdout.write(
                                f'Updated stock for {product.name} at {branch.name}: {initial_stock} units'
                            )

        self.stdout.write(
            self.style.SUCCESS(
                f'Inventory setup completed! Created: {created_count}, Updated: {updated_count}'
            )
        ) 