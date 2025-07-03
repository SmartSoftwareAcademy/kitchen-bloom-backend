import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction
from django.utils import timezone

from .models import Product, BranchStock, MenuItem, UnitOfMeasure, PurchaseOrder, InventoryTransaction, InventoryAdjustment
from apps.branches.models import Branch

logger = logging.getLogger(__name__)

@receiver(post_save, sender=Product)
def create_branch_stock_for_product(sender, instance, created, **kwargs):
    """Automatically create BranchStock entries when a product is created."""
    if created:
        branches = Branch.objects.filter(is_active=True)
        for branch in branches:
            # Try to find a soft-deleted BranchStock
            branch_stock = BranchStock.objects.filter(
                product=instance,
                branch=branch,
                deleted_at__isnull=False
            ).first()
            if branch_stock:
                # Restore the soft-deleted record
                branch_stock.deleted_at = None
                branch_stock.current_stock = 0
                branch_stock.reorder_level = 0
                branch_stock.cost_price = instance.cost_price
                branch_stock.selling_price = instance.selling_price
                branch_stock.is_active = True
                branch_stock.save()
            else:
                # Create if not exists (including not soft-deleted)
                BranchStock.objects.get_or_create(
                    product=instance,
                    branch=branch,
                    defaults={
                        'current_stock': 0,
                        'reorder_level': 0,
                        'cost_price': instance.cost_price,
                        'selling_price': instance.selling_price,
                        'is_active': True
                    }
                )

@receiver(post_save, sender=MenuItem)
def create_branch_stock_for_menu_item(sender, instance, created, **kwargs):
    """Automatically create BranchStock entries when a menu item is created."""
    if created:
        branch = instance.menu.branch
        # Create a product for the menu item if it doesn't exist
        product, product_created = Product.objects.get_or_create(
            name=instance.name,
            defaults={
                'SKU': f'MI-{instance.id}',
                'description': instance.description,
                'product_type': 'finished_product',
                'category': instance.category,
                'unit_of_measure': UnitOfMeasure.objects.filter(code='pcs').first(),
                'cost_price': instance.cost_price,
                'selling_price': instance.selling_price,
                'is_available_for_sale': True,
                'is_available_for_recipes': False,
                'is_active': True
            }
        )
        # Create BranchStock for the menu item's product
        BranchStock.objects.get_or_create(
            product=product,
            branch=branch,
            defaults={
                'current_stock': 0,
                'reorder_level': 0,
                'cost_price': instance.cost_price,
                'selling_price': instance.selling_price,
                'is_active': True
            }
        )

@receiver(post_save, sender=PurchaseOrder)
def create_inventory_transaction_for_purchase(sender, instance, created, **kwargs):
    """Create inventory transactions when purchase orders are received."""
    if instance.status == 'received' and not created:
        try:
            old_instance = PurchaseOrder.objects.get(pk=instance.pk)
            if old_instance.status != 'received':
                for item in instance.items.all():
                    branch_stock, created = BranchStock.objects.get_or_create(
                        product=item.product,
                        branch=instance.receiving_branch,
                        defaults={
                            'current_stock': 0,
                            'reorder_level': 0,
                            'is_active': True
                        }
                    )
                    branch_stock.current_stock += item.quantity
                    branch_stock.last_restocked = timezone.now()
                    branch_stock.save()
                    InventoryTransaction.objects.create(
                        product=item.product,
                        branch=instance.receiving_branch,
                        branch_stock=branch_stock,
                        transaction_type='purchase',
                        quantity=item.quantity,
                        reference=f'PO-{instance.id}',
                        notes=f'Purchase order {instance.id} received',
                        created_by=instance.created_by,
                        related_order=None
                    )
        except PurchaseOrder.DoesNotExist:
            pass

@receiver(post_save, sender=InventoryAdjustment)
def create_inventory_transaction_for_adjustment(sender, instance, created, **kwargs):
    """Create inventory transactions when adjustments are approved."""
    if instance.status == 'approved' and not created:
        try:
            old_instance = InventoryAdjustment.objects.get(pk=instance.pk)
            if old_instance.status != 'approved':
                adjustment_quantity = instance.quantity_after - instance.quantity_before
                branch_stock, created = BranchStock.objects.get_or_create(
                    product=instance.product,
                    branch=instance.branch,
                    defaults={
                        'current_stock': 0,
                        'reorder_level': 0,
                        'is_active': True
                    }
                )
                branch_stock.current_stock = instance.quantity_after
                branch_stock.save()
                InventoryTransaction.objects.create(
                    product=instance.product,
                    branch=instance.branch,
                    branch_stock=branch_stock,
                    transaction_type='adjustment',
                    quantity=adjustment_quantity,
                    reference=f'ADJ-{instance.id}',
                    notes=f'Adjustment: {instance.reason}',
                    created_by=instance.reviewed_by,
                    related_order=None
                )
        except InventoryAdjustment.DoesNotExist:
            pass