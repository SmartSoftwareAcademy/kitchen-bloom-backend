import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction

from .models import Product, BranchStock, MenuItem
from apps.branches.models import Branch

logger = logging.getLogger(__name__)

@receiver(post_save, sender=Product)
def create_branch_stock_for_product(sender, instance, created, **kwargs):
    """
    Automatically create BranchStock entries when a product is created.
    If initial_stock is provided in the raw_post_data, use those values.
    """
    if created:
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
    Creates or updates branch stock entries for the menu item.
    Each menu item can have its own stock levels per branch.
    """
    
    logger.info(f"Processing menu item: {instance.name} (ID: {instance.id}), created: {created}")
    
    # Skip if this is a raw save or if the menu item is being deleted
    if kwargs.get('raw', False) or kwargs.get('update_fields') == ('deleted',):
        return
    
    # Get all active branches
    branches = Branch.objects.filter(is_active=True)
    logger.info(f"Found {branches.count()} active branches for menu item: {instance.name}")
    
    with transaction.atomic():
        for branch in branches:
            # Use get_or_create to handle race conditions
            branch_stock, created = BranchStock.objects.get_or_create(
                menu_item=instance,
                branch=branch,
                defaults={
                    'current_stock': 0,  # Default to 0 stock for new menu items
                    'reorder_level': 0,  # Default reorder level
                    'selling_price': instance.selling_price,  # Default to menu item's selling price
                    'is_active': True
                }
            )
            
            if created:
                logger.info(f"Created branch stock for menu item {instance.name} at {branch.name}")
            else:
                # Update existing branch stock if needed
                update_fields = {}
                
                # Update selling price if it's different from the menu item's price
                if branch_stock.selling_price != instance.selling_price:
                    branch_stock.selling_price = instance.selling_price
                    update_fields['selling_price'] = instance.selling_price
                
                # Update is_active if needed
                if not branch_stock.is_active:
                    branch_stock.is_active = True
                    update_fields['is_active'] = True
                
                if update_fields:
                    branch_stock.save(update_fields=update_fields)
                    logger.info(f"Updated branch stock for menu item {instance.name} at {branch.name}")
    
    # If this menu item has a recipe, update the cost price based on ingredients
    if hasattr(instance, 'recipe') and instance.recipe:
        try:
            instance.update_cost_price()
            logger.info(f"Updated cost price for menu item {instance.name} to {instance.cost_price}")
        except Exception as e:
            logger.error(f"Error updating cost price for menu item {instance.name}: {str(e)}")
    
    logger.info(f"Finished processing menu item: {instance.name}")