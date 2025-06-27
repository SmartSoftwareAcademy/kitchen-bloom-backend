from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
import logging
from .models import Product, MenuItem, BranchStock, InventoryTransaction, PurchaseOrder, InventoryAdjustment, StockTransfer

# Set up logger
logger = logging.getLogger(__name__)


@receiver(post_save, sender=Product)
def create_branch_stock_for_product(sender, instance, created, **kwargs):
    """Automatically create BranchStock entries when a product is created."""
    if created:
        logger.info(f"Creating branch stock for new product: {instance.name} (ID: {instance.id})")
        
        # Get all active branches
        from apps.branches.models import Branch
        branches = Branch.objects.filter(is_active=True)
        
        logger.info(f"Found {branches.count()} active branches for stock creation")
        
        for branch in branches:
            branch_stock, created = BranchStock.objects.get_or_create(
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
            
            if created:
                logger.info(f"Created branch stock for {instance.name} at {branch.name}: {branch_stock.current_stock} units")
            else:
                logger.debug(f"Branch stock already exists for {instance.name} at {branch.name}")


@receiver(post_save, sender=MenuItem)
def create_branch_stock_for_menu_item(sender, instance, created, **kwargs):
    """Automatically create BranchStock entries when a menu item is created."""
    if created:
        logger.info(f"Creating branch stock for new menu item: {instance.name} (ID: {instance.id})")
        
        # Get the branch from the menu
        branch = instance.menu.branch
        
        # Create a product for the menu item if it doesn't exist
        from .models import UnitOfMeasure
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
        
        if product_created:
            logger.info(f"Created product for menu item: {product.name} (SKU: {product.SKU})")
        
        # Create BranchStock for the menu item's product
        branch_stock, created = BranchStock.objects.get_or_create(
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
        
        if created:
            logger.info(f"Created branch stock for menu item {instance.name} at {branch.name}: {branch_stock.current_stock} units")
        else:
            logger.debug(f"Branch stock already exists for menu item {instance.name} at {branch.name}")


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
                            'current_stock': 0,
                            'reorder_level': 0,
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
                        'current_stock': 0,
                        'reorder_level': 0,
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
                    defaults={'current_stock': 0, 'reorder_level': 0}
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
                    defaults={'current_stock': 0, 'reorder_level': 0}
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