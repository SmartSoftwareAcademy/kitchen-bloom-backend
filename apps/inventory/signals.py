from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from django.db import transaction
import logging
from .models import Product, MenuItem, BranchStock, InventoryTransaction, PurchaseOrder, InventoryAdjustment, StockTransfer

# Set up logger
logger = logging.getLogger(__name__)


@receiver(post_save, sender=Product)
def create_branch_stock_for_product(sender, instance, created, **kwargs):
    """
    Automatically create BranchStock entries when a product is created.
    If initial_stock is provided in the raw_post_data, use those values.
    """
    if created:
        from django.db import transaction
        from apps.branches.models import Branch
        
        logger.info(f"Creating branch stock for new product: {instance.name} (ID: {instance.id})")
        
        # Get initial stock data if it exists
        initial_stock_data = getattr(instance, '_initial_stock_data', None)
        
        if initial_stock_data:
            # Process branches with initial stock data
            branch_ids = [int(branch_id) for branch_id in initial_stock_data.keys()]
            branches = Branch.objects.filter(id__in=branch_ids, is_active=True)
            logger.info(f"Processing initial stock for {branches.count()} branches")
            
            for branch in branches:
                branch_data = initial_stock_data.get(str(branch.id), {})
                BranchStock.objects.create(
                    product=instance,
                    branch=branch,
                    current_stock=branch_data.get('current_stock', 1),
                    reorder_level=branch_data.get('reorder_level', 1),
                    cost_price=instance.cost_price,
                    selling_price=instance.selling_price,
                    is_active=True
                )
                logger.info(f"Created branch stock for {instance.name} at {branch.name} with initial stock: {branch_data}")
        else:
            # Default behavior: create stock entries with 0 for all active branches
            branches = Branch.objects.filter(is_active=True)
            logger.info(f"Creating default (zero) stock for {branches.count()} branches")
            
            for branch in branches:
                BranchStock.objects.create(
                    product=instance,
                    branch=branch,
                    current_stock=1,
                    reorder_level=1,
                    cost_price=instance.cost_price,
                    selling_price=instance.selling_price,
                    is_active=True
                )
                logger.info(f"Created default branch stock for {instance.name} at {branch.name}")


@receiver(post_save, sender=MenuItem)
def create_branch_stock_for_menu_item(sender, instance, created, **kwargs):
    """
    Signal handler for MenuItem post_save.
    Menu items no longer create their own products or branch stock entries.
    They only reference existing products through recipe ingredients.
    """
    logger.info(f"Processing menu item: {instance.name} (ID: {instance.id}), created: {created}")
    
    # If there's an associated product (from a previous version), we'll clean it up
    if instance.product:
        logger.info(f"Menu item {instance.name} has an associated product (ID: {instance.product.id}). "
                   f"This is no longer needed and can be removed.")
        # We don't delete the product here to avoid data loss
        # You might want to run a data migration to clean this up
    
    # No need to create products or branch stock for menu items anymore
    logger.info("Skipping product and branch stock creation for menu item")
    return


@receiver(post_save, sender=PurchaseOrder)
def create_inventory_transaction_for_purchase(sender, instance, created, **kwargs):
    """Create inventory transactions when purchase orders are received."""
    if instance.status == 'received' and not created:
        logger.info(f"Processing received purchase order: PO-{instance.id}")
        
        # Get the previous status
        try:
            old_instance = PurchaseOrder.objects.get(pk=instance.pk)
            if old_instance.status != 'received':
                logger.info(f"Purchase order status changed from {old_instance.status} to received")
                
                # Create inventory transactions for all items
                for item in instance.items.all():
                    logger.info(f"Processing purchase item: {item.product.name} - {item.quantity} units")
                    
                    # Get or create branch stock
                    branch_stock, created = BranchStock.objects.get_or_create(
                        product=item.product,
                        branch=instance.receiving_branch,
                        defaults={
                            'current_stock': 1,
                            'reorder_level': 1,
                            'is_active': True
                        }
                    )
                    
                    old_stock = branch_stock.current_stock
                    
                    # Update stock level
                    branch_stock.current_stock += item.quantity
                    branch_stock.last_restocked = timezone.now()
                    branch_stock.save()
                    
                    logger.info(f"Updated stock for {item.product.name} at {instance.receiving_branch.name}: {old_stock} -> {branch_stock.current_stock}")
                    
                    # Create inventory transaction
                    transaction = InventoryTransaction.objects.create(
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
                    
                    logger.info(f"Created inventory transaction: {transaction.id} for purchase PO-{instance.id}")
                    
        except PurchaseOrder.DoesNotExist:
            logger.warning(f"Purchase order {instance.id} not found when processing received status")


@receiver(post_save, sender=InventoryAdjustment)
def create_inventory_transaction_for_adjustment(sender, instance, created, **kwargs):
    """Create inventory transactions when adjustments are approved."""
    if instance.status == 'approved' and not created:
        logger.info(f"Processing approved inventory adjustment: ADJ-{instance.id}")
        
        # Get the previous status
        try:
            old_instance = InventoryAdjustment.objects.get(pk=instance.pk)
            if old_instance.status != 'approved':
                logger.info(f"Adjustment status changed from {old_instance.status} to approved")
                
                # Calculate the adjustment quantity
                adjustment_quantity = instance.quantity_after - instance.quantity_before
                logger.info(f"Adjustment quantity: {adjustment_quantity} ({instance.quantity_before} -> {instance.quantity_after})")
                
                # Get or create branch stock
                branch_stock, created = BranchStock.objects.get_or_create(
                    product=instance.product,
                    branch=instance.branch,
                    defaults={
                        'current_stock': 1,
                        'reorder_level': 1,
                        'is_active': True
                    }
                )
                
                old_stock = branch_stock.current_stock
                
                # Update stock level
                branch_stock.current_stock = instance.quantity_after
                branch_stock.save()
                
                logger.info(f"Updated stock for {instance.product.name} at {instance.branch.name}: {old_stock} -> {branch_stock.current_stock}")
                
                # Create inventory transaction
                transaction = InventoryTransaction.objects.create(
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
                
                logger.info(f"Created inventory transaction: {transaction.id} for adjustment ADJ-{instance.id}")
                
        except InventoryAdjustment.DoesNotExist:
            logger.warning(f"Inventory adjustment {instance.id} not found when processing approved status")


@receiver(post_save, sender=StockTransfer)
def create_inventory_transaction_for_transfer(sender, instance, created, **kwargs):
    """Create inventory transactions when stock transfers are completed."""
    if instance.status == 'completed' and not created:
        logger.info(f"Processing completed stock transfer: Transfer-{instance.id}")
        
        # Get the previous status
        try:
            old_instance = StockTransfer.objects.get(pk=instance.pk)
            if old_instance.status != 'completed':
                logger.info(f"Transfer status changed from {old_instance.status} to completed")
                
                # Reduce stock from source branch
                source_stock, created = BranchStock.objects.get_or_create(
                    product=instance.product,
                    branch=instance.source_branch,
                    defaults={'current_stock': 1, 'reorder_level': 1}
                )
                
                old_source_stock = source_stock.current_stock
                source_stock.current_stock = max(0, source_stock.current_stock - instance.quantity)
                source_stock.save()
                
                logger.info(f"Reduced stock at source branch {instance.source_branch.name}: {old_source_stock} -> {source_stock.current_stock}")
                
                # Create inventory transaction for source branch (outgoing)
                source_transaction = InventoryTransaction.objects.create(
                    product=instance.product,
                    branch=instance.source_branch,
                    branch_stock=source_stock,
                    transaction_type='transfer',
                    quantity=-instance.quantity,
                    reference=f'Transfer {instance.id} - Outgoing',
                    notes=f'Stock transferred to {instance.target_branch.name}',
                    created_by=instance.created_by,
                    related_order=None
                )
                
                logger.info(f"Created outgoing transfer transaction: {source_transaction.id}")
                
                # Increase stock in target branch
                target_stock, created = BranchStock.objects.get_or_create(
                    product=instance.product,
                    branch=instance.target_branch,
                    defaults={'current_stock': 1, 'reorder_level': 1}
                )
                
                old_target_stock = target_stock.current_stock
                target_stock.current_stock += instance.quantity
                target_stock.save()
                
                logger.info(f"Increased stock at target branch {instance.target_branch.name}: {old_target_stock} -> {target_stock.current_stock}")
                
                # Create inventory transaction for target branch (incoming)
                target_transaction = InventoryTransaction.objects.create(
                    product=instance.product,
                    branch=instance.target_branch,
                    branch_stock=target_stock,
                    transaction_type='transfer',
                    quantity=instance.quantity,
                    reference=f'Transfer {instance.id} - Incoming',
                    notes=f'Stock received from {instance.source_branch.name}',
                    created_by=instance.created_by,
                    related_order=None
                )
                
                logger.info(f"Created incoming transfer transaction: {target_transaction.id}")
                
        except StockTransfer.DoesNotExist:
            logger.warning(f"Stock transfer {instance.id} not found when processing completed status")


@receiver(post_save, sender=InventoryTransaction)
def update_branch_stock_on_transaction(sender, instance, created, **kwargs):
    """Update branch stock when inventory transaction is created."""
    if created and instance.branch_stock:
        logger.info(f"Processing new inventory transaction: {instance.id} - {instance.transaction_type} - {instance.quantity}")
        
        old_stock = instance.branch_stock.current_stock
        
        # Update stock level based on transaction type
        if instance.transaction_type in ['purchase', 'return', 'production']:
            # Positive transactions increase stock
            instance.branch_stock.current_stock += instance.quantity
            logger.info(f"Positive transaction: {old_stock} + {instance.quantity} = {instance.branch_stock.current_stock}")
        elif instance.transaction_type in ['sale', 'waste']:
            # Negative transactions decrease stock
            instance.branch_stock.current_stock = max(0, instance.branch_stock.current_stock - abs(instance.quantity))
            logger.info(f"Negative transaction: {old_stock} - {abs(instance.quantity)} = {instance.branch_stock.current_stock}")
        elif instance.transaction_type == 'adjustment':
            # For adjustment, quantity represents the change
            instance.branch_stock.current_stock += instance.quantity
            logger.info(f"Adjustment transaction: {old_stock} + {instance.quantity} = {instance.branch_stock.current_stock}")
        elif instance.transaction_type == 'transfer':
            # Transfer transactions are handled separately in StockTransfer signal
            logger.debug(f"Transfer transaction handled separately: {instance.id}")
            pass
        
        # Update last_restocked for purchases
        if instance.transaction_type == 'purchase':
            instance.branch_stock.last_restocked = instance.created_at
            logger.debug(f"Updated last_restocked for purchase transaction: {instance.id}")
        
        instance.branch_stock.save()
        logger.info(f"Updated branch stock for {instance.product.name} at {instance.branch.name}: {old_stock} -> {instance.branch_stock.current_stock}") 