from django.db import models
from django.db.models import Sum
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator
from django.utils.functional import cached_property
from django.db.models.signals import post_save
from django.dispatch import receiver
from apps.base.models import TimestampedModel, SoftDeleteModel
from apps.branches.models import Branch
from apps.crm.models import Customer
from apps.accounting.models import Revenue, RevenueAccount
from django.utils import timezone
from apps.accounting.utils import generate_number
from django.conf import settings
from apps.tables.models import Table
from decimal import Decimal, ROUND_HALF_UP
import json
from django.contrib.auth import get_user_model
from django.db import transaction, IntegrityError
import logging

logger = logging.getLogger(__name__)

User=get_user_model()

class Payment(TimestampedModel, SoftDeleteModel):
    """
    Represents a payment transaction for an order.
    Integrates with the accounting system for proper revenue tracking.
    """
    class Status(models.TextChoices):
        PENDING = 'pending', _('Pending')
        COMPLETED = 'completed', _('Completed')
        FAILED = 'failed', _('Failed')
        REFUNDED = 'refunded', _('Refunded')
        PARTIAL_REFUND = 'partial_refund', _('Partial Refund')
        
    class PaymentMethod(models.TextChoices):
        CASH = 'cash', _('Cash')
        CARD = 'card', _('Card')
        CHEQUE = 'cheque', _('Cheque')
        BANK_TRANSFER = 'bank_transfer', _('Bank Transfer')
        MPESA = 'mpesa', _('M-Pesa')
        PAYPAL = 'paypal', _('PayPal')
        ONLINE_PAYMENT = 'online_payment', _('Online Payment')
        LOYALTY_POINTS = 'loyalty_points', _('Loyalty Points')
        GIFT_CARD = 'gift_card', _('Gift Card')
        OTHER = 'other', _('Other')
        
    order = models.ForeignKey('Order', on_delete=models.PROTECT, related_name='payments', verbose_name=_('order'))
    amount = models.DecimalField(_('amount'), max_digits=10, decimal_places=2, validators=[MinValueValidator(0.01)])
    method = models.CharField(_('payment method'), max_length=20, choices=PaymentMethod.choices, default=PaymentMethod.CASH)
    status = models.CharField(_('status'), max_length=20, choices=Status.choices, default=Status.PENDING)
    transaction_reference = models.CharField(_('transaction reference'), max_length=100, blank=True, help_text=_('Transaction ID or reference from payment processor'))
    notes = models.TextField(_('notes'), blank=True, help_text=_('Additional notes about the payment'))
    accounting_entry = models.OneToOneField(Revenue, on_delete=models.PROTECT, related_name='payment', null=True, blank=True, verbose_name=_('accounting entry'))
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payments_created',
        verbose_name=_('created by')
    )
    last_modified_by=models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payments_modified',
        verbose_name=_('created by')
    )
    
    class Meta:
        verbose_name = _('payment')
        verbose_name_plural = _('payments')
        ordering = ['-created_at']
        
    def __str__(self):
        return f"Payment {self.id} for Order {self.order.order_number}"
    
    def save(self, *args, **kwargs):
        """Save payment and create accounting entry."""
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        if is_new and self.status == self.Status.COMPLETED:
            self._create_accounting_entry()
    
    def _create_accounting_entry(self):
        """Create accounting entry for this payment."""
        # Get or create revenue account based on payment method
        account, _ = RevenueAccount.objects.get_or_create(
            code=f'PAY-{self.method.upper()}',
            defaults={
                'name': f'{self.method.upper()} Payments',
                'account_type': 'sales',
                'description': f'Account for {self.method.upper()} payment method'
            }
        )
        # Get or create the 'Sales' revenue category
        from apps.accounting.models import RevenueCategory
        category, _ = RevenueCategory.objects.get_or_create(
            name='Sales',
            defaults={
                'description': 'Sales Revenue Category'
            }
        )
        # Determine the correct currency
        currency = getattr(self.order.branch, 'currency', None) or \
                  getattr(getattr(self.order.branch, 'company', None), 'currency', None) or \
                  getattr(settings, 'DEFAULT_CURRENCY', 'KES')
        # Quantize amount
        amount = Decimal(str(self.amount)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        # Map payment method to valid Revenue.PAYMENT_METHODS
        PAYMENT_METHOD_MAP = {
            'cash': 'cash',
            'cheque': 'cheque',
            'bank_transfer': 'bank_transfer',
            'card': 'other',
            'mpesa': 'other',
            'paypal': 'other',
            'online_payment': 'other',
            'loyalty_points': 'other',
            'gift_card': 'other',
            'other': 'other',
        }
        revenue_payment_method = PAYMENT_METHOD_MAP.get(self.method, 'other')
        # Use the first customer if available
        customer = self.order.customers.first() if self.order.customers.exists() else None
        # Set created_by and last_modified_by
        created_by = self.created_by
        # Create revenue entry
        revenue = Revenue.objects.create(
            revenue_number=generate_number('RE'),
            revenue_date=self.created_at.date(),
            amount=amount,
            currency=currency,
            description=f'Payment for Order {self.order.order_number}',
            revenue_type='sales',
            category=category,
            branch=self.order.branch,
            customer=customer,
            payment_method=revenue_payment_method,
            payment_reference=self.transaction_reference,
            status='paid',
            created_by=created_by,
            last_modified_by=created_by
        )
        # Link accounting entry to payment
        self.accounting_entry = revenue
        self.save()

class PaymentHistory(models.Model):
    """Tracks history of payment-related events."""
    class HistoryType(models.TextChoices):
        PAYMENT = 'payment', _('Payment')
        REFUND = 'refund', _('Refund')
        DISPUTE = 'dispute', _('Dispute')
        VERIFICATION = 'verification', _('Verification')
        STATUS_CHANGE = 'status_change', _('Status Change')
    
    payment = models.ForeignKey(Payment, on_delete=models.PROTECT, related_name='history')
    history_type = models.CharField(_('history type'), max_length=20, choices=HistoryType.choices)
    details = models.JSONField(_('details'), help_text=_('JSON object containing relevant details for the history record'))
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    
    class Meta:
        verbose_name = _('payment history')
        verbose_name_plural = _('payment history')
        ordering = ['-created_at']
        
    def __str__(self):
        return f"{self.get_history_type_display()} for Payment {self.payment_id}"

class Dispute(models.Model):
    """Represents a payment dispute."""
    class Status(models.TextChoices):
        PENDING = 'pending', _('Pending')
        RESOLVED = 'resolved', _('Resolved')
        ESCALATED = 'escalated', _('Escalated')
        CANCELLED = 'cancelled', _('Cancelled')

    payment = models.ForeignKey('Payment', on_delete=models.PROTECT, related_name='disputes')
    reason = models.TextField(_('reason'))
    evidence = models.TextField(_('evidence'), blank=True)
    status = models.CharField(_('status'), max_length=20, choices=Status.choices, default=Status.PENDING)
    reported_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='reported_disputes')
    resolved_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='resolved_disputes', null=True, blank=True)
    resolution_notes = models.TextField(_('resolution notes'), blank=True)
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)

    class Meta:
        verbose_name = _('dispute')
        verbose_name_plural = _('disputes')
        ordering = ['-created_at']

    def __str__(self):
        return f"Dispute {self.id} for Payment {self.payment_id}"

    def resolve(self, resolution_notes, resolved_by):
        """Resolve the dispute."""
        self.status = self.Status.RESOLVED
        self.resolution_notes = resolution_notes
        self.resolved_by = resolved_by
        self.save()

    def escalate(self):
        """Escalate the dispute."""
        self.status = self.Status.ESCALATED
        self.save()

    def cancel(self, reason):
        """Cancel the dispute."""
        self.status = self.Status.CANCELLED
        self.resolution_notes = reason
        self.save()

class OrderItem(TimestampedModel, SoftDeleteModel):
    """
    Represents an item in an order.
    Each item is linked to a specific order and can be either a product or menu item.
    """
    class Status(models.TextChoices):
        PENDING = 'pending', _('Pending')
        PREPARING = 'preparing', _('Preparing')
        READY = 'ready', _('Ready')
        SERVED = 'served', _('Served')
        CANCELLED = 'cancelled', _('Cancelled')
    
    class ItemType(models.TextChoices):
        PRODUCT = 'product', _('Product')
        MENU_ITEM = 'menu_item', _('Menu Item')
        CUSTOM_ITEM = 'custom_item', _('Custom Item')
    
    # Relationships
    order = models.ForeignKey('Order',on_delete=models.CASCADE,related_name='items',verbose_name=_('order'))
    
    # Item can be either a product, menu item, or custom item
    item_type = models.CharField(_('item type'), max_length=20, choices=ItemType.choices, default=ItemType.PRODUCT,blank=True,null=True)
    product = models.ForeignKey('inventory.Product',on_delete=models.PROTECT,related_name='order_items',verbose_name=_('product'), null=True, blank=True)
    menu_item = models.ForeignKey('inventory.MenuItem',on_delete=models.PROTECT,related_name='order_items',verbose_name=_('menu item'), null=True, blank=True)
    
    # Item Details
    quantity = models.DecimalField(_('quantity'),max_digits=10,decimal_places=2,default=1,validators=[MinValueValidator(0.01)])
    unit_price = models.DecimalField(_('unit price'),max_digits=10,decimal_places=2,help_text=_('Price per unit at time of order'))
    status = models.CharField(_('status'),max_length=20,choices=Status.choices,default=Status.PENDING)
    
    # Notes and Special Requests
    notes = models.TextField(_('notes'),blank=True,help_text=_('Special instructions for this item'))
    
    # Preparation Details
    kitchen_notes = models.TextField(_('kitchen notes'),blank=True,help_text=_('Notes for kitchen staff'))
    kitchen_status = models.CharField(_('kitchen status'),max_length=20,choices=Status.choices,default=Status.PENDING,help_text=_('Status reported by kitchen'))
    
    # Financial Details
    discount_amount = models.DecimalField(_('discount amount'),max_digits=10,decimal_places=2,default=0,help_text=_('Discount applied to this item'))
    tax_amount = models.DecimalField(_('tax amount'),max_digits=10,decimal_places=2,default=0,help_text=_('Tax amount for this item'))
    
    # Calculated Fields
    subtotal = models.DecimalField(_('subtotal'),max_digits=10,decimal_places=2,default=0,help_text=_('Item subtotal before tax and discount'))
    total = models.DecimalField(_('total'),max_digits=10,decimal_places=2,default=0,help_text=_('Item total after tax and discount'))
    
    # Inventory tracking
    ingredients_consumed = models.JSONField(_('ingredients consumed'), default=list, blank=True, help_text=_('Ingredients consumed when this item was prepared'))
    inventory_updated = models.BooleanField(_('inventory updated'), default=False, help_text=_('Whether inventory has been updated for this item'))
    
    # Add new relationships
    assigned_customer = models.ForeignKey(Customer, null=True, blank=True, on_delete=models.SET_NULL, related_name='order_items')
    modifiers = models.TextField(_('modifiers'), blank=True, help_text=_('Customizations or modifications for this item'))
    
    # Custom item support
    is_custom = models.BooleanField(_('is custom item'), default=False, help_text=_('Whether this is a custom menu item'))
    custom_data = models.JSONField(_('custom data'), null=True, blank=True, help_text=_('Custom data for special menu items'))
    
    created_at = models.DateTimeField(_('created at'),default=timezone.now)
    updated_at = models.DateTimeField(_('updated at'),default=timezone.now)
    
    class Meta:
        verbose_name = _('order item')
        verbose_name_plural = _('order items')
        ordering = ['order', 'created_at']
        indexes = [
            models.Index(fields=['order']),
            models.Index(fields=['product']),
            models.Index(fields=['menu_item']),
            models.Index(fields=['status']),
            models.Index(fields=['kitchen_status']),
            models.Index(fields=['item_type']),
        ]
    
    def __str__(self):
        item_name = self.get_item_name()
        return f"{item_name} x {self.quantity} ({self.order.order_number})"
    
    def save(self, *args, update_totals=True, **kwargs):
        """Update calculated fields before saving."""
        # Only update totals if requested (default True)
        if update_totals:
            self._update_totals()
        super().save(*args, **kwargs)
    
    def _update_totals(self):
        """Calculate item totals including modifiers."""
        self.subtotal = self.quantity * self.unit_price
        # Add modifier costs (if modifiers is a JSON string with additional_cost fields)
        modifier_total = 0
        if self.modifiers:
            try:
                modifiers_data = json.loads(self.modifiers)
                if isinstance(modifiers_data, list):
                    modifier_total = sum(float(m.get('additional_cost', 0)) for m in modifiers_data if isinstance(m, dict))
            except Exception:
                modifier_total = 0
        self.subtotal += modifier_total
        # Calculate final total
        self.total = self.subtotal + self.tax_amount - self.discount_amount
    
    def get_item_name(self):
        """Get the name of the item based on its type."""
        if self.item_type == self.ItemType.PRODUCT and self.product:
            return self.product.name
        elif self.item_type == self.ItemType.MENU_ITEM and self.menu_item:
            return self.menu_item.name
        return "Unknown Item"
    
    def get_item_description(self):
        """Get the description of the item based on its type."""
        if self.item_type == self.ItemType.PRODUCT and self.product:
            return self.product.description
        elif self.item_type == self.ItemType.MENU_ITEM and self.menu_item:
            return self.menu_item.description
        return ""
    
    def get_item_image_url(self):
        """Get the image URL of the item based on its type."""
        if self.item_type == self.ItemType.PRODUCT and self.product:
            return self.product.get_image_url()
        elif self.item_type == self.ItemType.MENU_ITEM and self.menu_item:
            # Menu items can have images through their category or be linked to products
            return None
        return None
    
    def get_allergens(self):
        """Get allergens for the item."""
        if self.item_type == self.ItemType.PRODUCT and self.product:
            return self.product.allergens
        elif self.item_type == self.ItemType.MENU_ITEM and self.menu_item:
            return self.menu_item.allergens
        return []
    
    def get_allergy_warnings(self):
        """Get allergy warnings for the item."""
        allergens = self.get_allergens()
        if allergens:
            return f"Contains: {', '.join(allergens)}"
        return ""
    
    def get_modifier_notes(self):
        """Get notes from modifiers."""
        modifiers = self.modifiers.all()
        if modifiers:
            return ', '.join([f"{m.name}: {m.description}" for m in modifiers if m.description])
        return ""
    
    def consume_ingredients(self):
        """Consume ingredients when item is prepared."""
        import logging
        logger = logging.getLogger(__name__)
        
        logger.debug(f"consume_ingredients called for order item {self.id}")
        
        if self.inventory_updated:
            logger.debug(f"Order item {self.id} already has inventory updated, skipping")
            return  # Already updated
        
        branch = self.order.branch
        consumed_ingredients = []
        
        logger.debug(f"Processing order item {self.id} for branch: {branch.name}")
        logger.debug(f"Item type: {self.item_type}")
        
        if self.item_type == self.ItemType.MENU_ITEM and self.menu_item:
            logger.debug(f"Processing menu item: {self.menu_item.name}")
            # Consume recipe ingredients
            recipe = getattr(self.menu_item, 'recipe', None)
            if recipe:
                logger.debug(f"Recipe found with {recipe.ingredients.count()} ingredients")
                for recipe_ingredient in recipe.ingredients.all():
                    ingredient = recipe_ingredient.ingredient
                    logger.debug(f"Processing ingredient: {ingredient.name}")
                    
                    branch_stock = ingredient.get_stock_for_branch(branch)
                    if branch_stock:
                        logger.debug(f"Branch stock found: {branch_stock.current_stock} available")
                        quantity_needed = recipe_ingredient.quantity * self.quantity
                        logger.debug(f"Quantity needed: {quantity_needed} (recipe: {recipe_ingredient.quantity} * order: {self.quantity})")
                        
                        if branch_stock.current_stock >= quantity_needed:
                            old_stock = branch_stock.current_stock
                            branch_stock.current_stock -= quantity_needed
                            branch_stock.save()
                            logger.debug(f"Stock updated: {old_stock} -> {branch_stock.current_stock}")
                            
                            consumed_ingredients.append({
                                'ingredient_id': ingredient.id,
                                'ingredient_name': ingredient.name,
                                'quantity_consumed': quantity_needed,
                                'unit': recipe_ingredient.unit_of_measure.symbol
                            })
                            
                            # Create inventory transaction (negative quantity for sales)
                            from apps.inventory.models import InventoryTransaction
                            transaction = InventoryTransaction.objects.create(
                                product=ingredient,
                                branch=branch,
                                branch_stock=branch_stock,
                                transaction_type='sale',
                                quantity=-quantity_needed,  # Negative for sales
                                reference=f"Order {self.order.order_number}",
                                notes=f"Consumed for {self.menu_item.name}",
                                created_by=self.order.created_by,
                                related_order=self.order
                            )
                            logger.info(f"Created inventory transaction {transaction.id} for ingredient {ingredient.name}")
                        else:
                            logger.warning(f"Insufficient stock for {ingredient.name}: need {quantity_needed}, have {branch_stock.current_stock}")
                    else:
                        logger.warning(f"No branch stock found for ingredient {ingredient.name} at branch {branch.name}")
            else:
                logger.warning(f"No recipe found for menu item {self.menu_item.name}")
        
        elif self.item_type == self.ItemType.PRODUCT and self.product:
            logger.debug(f"Processing direct product: {self.product.name}")
            # Direct product consumption
            branch_stock = self.product.get_stock_for_branch(branch)
            if branch_stock and branch_stock.current_stock >= self.quantity:
                old_stock = branch_stock.current_stock
                branch_stock.current_stock -= self.quantity
                branch_stock.save()
                logger.debug(f"Stock updated: {old_stock} -> {branch_stock.current_stock}")
                
                consumed_ingredients.append({
                    'ingredient_id': self.product.id,
                    'ingredient_name': self.product.name,
                    'quantity_consumed': self.quantity,
                    'unit': self.product.unit_of_measure.symbol
                })
                
                # Create inventory transaction (negative quantity for sales)
                from apps.inventory.models import InventoryTransaction
                transaction = InventoryTransaction.objects.create(
                    product=self.product,
                    branch=branch,
                    branch_stock=branch_stock,
                    transaction_type='sale',
                    quantity=-self.quantity,  # Negative for sales
                    reference=f"Order {self.order.order_number}",
                    notes=f"Direct sale",
                    created_by=self.order.created_by,
                    related_order=self.order
                )
                logger.info(f"Created inventory transaction {transaction.id} for product {self.product.name}")
            else:
                if not branch_stock:
                    logger.warning(f"No branch stock found for product {self.product.name} at branch {branch.name}")
                else:
                    logger.warning(f"Insufficient stock for {self.product.name}: need {self.quantity}, have {branch_stock.current_stock}")
        
        logger.debug(f"Consumed ingredients: {consumed_ingredients}")
        self.ingredients_consumed = consumed_ingredients
        self.inventory_updated = True
        self.save(update_fields=['ingredients_consumed', 'inventory_updated'])
        logger.info(f"Order item {self.id} inventory consumption completed")
    
    @cached_property
    def is_ready(self):
        """Return True if the item is ready to be served."""
        return self.status in [self.Status.READY, self.Status.SERVED]

    @cached_property
    def is_cancelled(self):
        """Return True if the item is cancelled."""
        return self.status == self.Status.CANCELLED

    @cached_property
    def preparation_time(self):
        """Return the time taken for preparation."""
        if self.kitchen_status == self.Status.SERVED:
            return (self.modified - self.created).total_seconds()
        return None

class Order(TimestampedModel, SoftDeleteModel):
    """
    Represents a customer order in the system.
    Each order is associated with a specific branch.
    
    Key features:
    - Multi-channel order handling (dine-in, takeaway, delivery)
    - Real-time order status tracking
    - Payment processing and reconciliation
    - Customer loyalty integration
    - Branch-specific pricing and inventory
    """
    class Status(models.TextChoices):
        DRAFT = 'draft', _('Draft')
        CONFIRMED = 'confirmed', _('Confirmed')
        PROCESSING = 'processing', _('Processing')
        READY = 'ready', _('Ready')
        COMPLETED = 'completed', _('Completed')
        CANCELLED = 'cancelled', _('Cancelled')
        REFUNDED = 'refunded', _('Refunded')
        PARTIAL_REFUND = 'partial_refund', _('Partial Refund')
        
    class OrderType(models.TextChoices):
        DINE_IN = 'dine_in', _('Dine In')
        TAKEAWAY = 'takeaway', _('Takeaway')
        DELIVERY = 'delivery', _('Delivery')
        ONLINE = 'online', _('Online Order')
        BAR = 'bar', _('Bar Service')
        
    class ServiceType(models.TextChoices):
        REGULAR = 'regular', _('Regular Service')
        EXPRESS = 'express', _('Express Service')
        SELF_SERVICE = 'self_service', _('Self Service')
        TAKEAWAY = 'takeaway', _('Takeaway Service')
        BAR = 'bar', _('Bar Service')
        
    # Order Details
    order_type = models.CharField(_('order type'),max_length=20,choices=OrderType.choices,default=OrderType.DINE_IN)
    service_type = models.CharField(_('service type'),max_length=20,choices=ServiceType.choices,default=ServiceType.REGULAR)
    estimated_preparation_time = models.DurationField(_('estimated preparation time'), null=True, blank=True)
    actual_preparation_time = models.DurationField(_('actual preparation time'), null=True, blank=True)
    preparation_notes = models.TextField(_('preparation notes'), blank=True, help_text=_('Special preparation instructions'))
        
    class PaymentStatus(models.TextChoices):
        PENDING = 'pending', _('Pending')
        PAID = 'paid', _('Paid')
        PARTIALLY_PAID = 'partially_paid', _('Partially Paid')
        OVERPAID = 'overpaid', _('Overpaid')
        REFUNDED = 'refunded', _('Refunded')
        PARTIAL_REFUND = 'partial_refund', _('Partial Refund')
        FAILED = 'failed', _('Failed')
        
    class PaymentMethod(models.TextChoices):
        CASH = 'cash', _('Cash')
        CARD = 'card', _('Card')
        CHEQUE = 'cheque', _('Cheque')
        BANK_TRANSFER = 'bank_transfer', _('Bank Transfer')
        MPESA = 'mpesa', _('M-Pesa')
        PAYPAL = 'paypal', _('PayPal')
        OTHER = 'other', _('Other')
        ONLINE_PAYMENT = 'online_payment', _('Online Payment')
        LOYALTY_POINTS = 'loyalty_points', _('Loyalty Points')
        GIFT_CARD = 'gift_card', _('Gift Card')
    
    # Order Identification
    order_number = models.CharField(_('order number'),max_length=20,unique=True,editable=False,db_index=True)
    # Branch and Customer Information
    branch = models.ForeignKey(Branch,on_delete=models.PROTECT,related_name='orders',verbose_name=_('branch'))
    customers = models.ManyToManyField(Customer, related_name='orders', blank=True)
    # Add new relationships
    tables = models.ManyToManyField(Table, related_name='orders', blank=True)
    
    # Order Details
    status = models.CharField(_('status'),max_length=20,choices=Status.choices,default=Status.DRAFT)
    delivery_address = models.TextField(_('delivery address'),blank=True,help_text=_('Delivery address for takeaway/delivery orders'))
    # Financial Information
    subtotal = models.DecimalField(_('subtotal'),max_digits=10,decimal_places=2,default=0,help_text=_('Order subtotal before taxes and discounts'))
    tax_amount = models.DecimalField(_('tax amount'),max_digits=10,decimal_places=2,default=0,help_text=_('Total tax amount'))
    discount_amount = models.DecimalField(_('discount amount'),max_digits=10,decimal_places=2,default=0,help_text=_('Total discount amount'))
    total_amount = models.DecimalField(_('total amount'),max_digits=10,decimal_places=2,default=0,help_text=_('Final order total'))
    
    # Payment Information
    payment_status = models.CharField(_('payment status'),max_length=20,choices=[('pending', _('Pending')),
            ('paid', _('Paid')),
            ('partially_paid', _('Partially Paid')),
            ('overpaid', _('Overpaid')),
            ('refunded', _('Refunded'))
        ],
        default='pending'
    )
    payment_method = models.CharField(_('payment method'),max_length=20,choices=[('cash', _('Cash')),
            ('card', _('Card')),
            ('cheque', _('Cheque')),
            ('bank_transfer', _('Bank Transfer')),
            ('mpesa', _('M-Pesa')),
            ('paypal', _('PayPal')),
            ('other', _('Other'))
        ],
        blank=True
    )
    
    # Notes and Special Requests
    notes = models.TextField(_('notes'),blank=True,help_text=_('Special instructions or notes for the order'))
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True,null=True,related_name='order_created')
    last_modified_by = models.ForeignKey(User,on_delete=models.SET_NULL,null=True,blank=True,related_name='order_modified',verbose_name=_('Last Updated By'))

    class Meta:
        verbose_name = _('order')
        verbose_name_plural = _('orders')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['order_number']),
            models.Index(fields=['status']),
            models.Index(fields=['payment_status']),
            models.Index(fields=['created_at']),
            models.Index(fields=['branch']),
            models.Index(fields=['branch', 'created_at']),
        ]
        permissions = [
            ('split_order', 'Can split orders'),
            ('merge_orders', 'Can merge orders'),
        ]
    
    def __str__(self):
        return f"Order {self.order_number} ({self.get_status_display()})"
    
    def save(self, *args, **kwargs):
        """Save order and handle status changes."""
        is_new = self.pk is None
        old_status = None
        
        if not is_new:
            try:
                old_instance = Order.objects.get(pk=self.pk)
                old_status = old_instance.status
                if old_instance.order_number is None or old_instance.order_number == '':
                    self.order_number = self.generate_order_number()
            except Order.DoesNotExist:
                pass
        
        # Generate order number for new orders before first save
        if is_new and not self.order_number:
            self.order_number = self.generate_order_number()
        
        # Save the order first to get a primary key
        super().save(*args, **kwargs)
        
        # Calculate totals after saving (only if we have items)
        if not is_new and self.items.exists():
            self.calculate_totals()
            # Save again to update the calculated totals
            super().save(update_fields=['subtotal', 'tax_amount', 'discount_amount', 'total_amount'])
        
        # Update order items to served status when order is completed
        if not is_new and self.status == 'completed' and old_status != 'completed':
            self._update_order_items_to_served()
            
            # Directly consume ingredients for all items
            logger = logging.getLogger(__name__)
            logger.info(f"Order {self.order_number} completed, consuming ingredients for all items")
            
            for item in self.items.all():
                if item.status == 'served' and not item.inventory_updated:
                    try:
                        logger.info(f"Consuming ingredients for order item: {item.get_item_name()} (ID: {item.id})")
                        item.consume_ingredients()
                        logger.info(f"Successfully consumed ingredients for order item: {item.id}")
                    except Exception as e:
                        logger.error(f"Error consuming ingredients for order item {item.id}: {e}")
                        import traceback
                        logger.error(f"Traceback: {traceback.format_exc()}")
    
    def _update_order_items_to_served(self):
        """Update all order items to served status when order is completed."""
        with transaction.atomic():
            for item in self.items.all():
                if item.status not in ['cancelled', 'served']:
                    old_status = item.status
                    item.status = 'served'
                    item.save()
                    logger.info(f"Order item {item.id} status updated: {old_status} -> {item.status}")
                else:
                    logger.debug(f"Order item {item.id} already in final status: {item.status}")
    
    def generate_order_number(self):
        """Generate a unique order number."""
        prefix = f"{self.branch.code}-" if self.branch else "MB001-"
        today = timezone.now().strftime('%Y%m%d')
        # Find the last order for today and this branch
        last_order = Order.objects.filter(order_number__startswith=f"{prefix}{today}").order_by('-id').first()
        if last_order and last_order.order_number:
            try:
                last_seq = int(last_order.order_number.split('-')[-1])
            except Exception:
                last_seq = 0
        else:
            last_seq = 0
        return f"{prefix}{today}-{last_seq+1:04d}"
    
    def calculate_totals(self):
        """Calculate order totals efficiently."""
        items = self.items.all().only('subtotal', 'tax_amount', 'discount_amount')
        self.subtotal = sum(item.subtotal for item in items)
        self.tax_amount = sum(item.tax_amount for item in items)
        self.discount_amount = sum(item.discount_amount for item in items)
        self.total_amount = self.subtotal + self.tax_amount - self.discount_amount
    
    def add_item(self, product, quantity=1, unit_price=None, notes='', kitchen_notes=''):
        """Add an item to the order."""
        if not unit_price:
            unit_price = product.price
        item = OrderItem.objects.create(
            order=self,
            product=product,
            quantity=quantity,
            unit_price=unit_price,
            notes=notes,
            kitchen_notes=kitchen_notes
        )
        self.calculate_totals()
        self._skip_ws = True
        self.save()
        return item
    
    def update_item(self, item_id, **kwargs):
        """Update an existing order item."""
        item = self.items.get(id=item_id)
        for key, value in kwargs.items():
            setattr(item, key, value)
        item.save()
        self.calculate_totals()
        self._skip_ws = True
        self.save()
        return item
    
    def remove_item(self, item_id):
        """Remove an item from the order."""
        item = self.items.get(id=item_id)
        item.delete()
        self.calculate_totals()
        self._skip_ws = True
        self.save()
    
    def split_bill(self, split_items, new_customer=None):
        """Split the order into two orders."""
        new_order = Order.objects.create(
            branch=self.branch,
            customer=new_customer or self.customer,
            order_type=self.order_type,
            service_type=self.service_type,
            table=self.table if hasattr(self, 'table') else None,
            waiter=self.waiter if hasattr(self, 'waiter') else None,
            created_by=self.created_by
        )
        for item_id in split_items:
            item = self.items.get(id=item_id)
            item.order = new_order
            item.save()
        self.calculate_totals()
        new_order.calculate_totals()
        self._skip_ws = True
        new_order._skip_ws = True
        self.save()
        new_order.save()
        return new_order
    
    def apply_discount(self, amount, discount_type='fixed'):
        """Apply a discount to the order."""
        if discount_type == 'fixed':
            self.discount_amount = amount
        else:  # percentage
            self.discount_amount = (self.subtotal + self.tax_amount) * (amount / 100)
        self.calculate_totals()
        self._skip_ws = True
        self.save()
    
    def add_payment(self, amount, method, transaction_reference=None, notes='',user=None):
        """Add a payment to the order."""
        # Calculate total payments including this new payment
        existing_payments = self.payments.filter(status=Payment.Status.COMPLETED).aggregate(
            total=models.Sum('amount')
        )['total'] or 0
        total_with_new = existing_payments + amount
        
        # Determine payment status
        if total_with_new >= self.total_amount:
            payment_status = Payment.Status.COMPLETED
        else:
            payment_status = Payment.Status.PENDING
        
        return Payment.objects.create(
            order=self,
            created_by=user,
            last_modified_by=user,
            amount=amount,
            method=method,
            transaction_reference=transaction_reference,
            notes=notes,
            status=payment_status
        )
    
    def process_payment(self, amount, method,reference,notes,user):
        """Process payment for the order."""
        if amount < self.total_amount:
            raise ValueError(_('Insufficient payment amount'))
        
        # Create payment
        payment = self.add_payment(amount, method,reference,notes,user)
        
        # Update order status
        self.payment_status = self.PaymentStatus.PAID if amount >= self.total_amount else self.PaymentStatus.PARTIALLY_PAID
        self.payment_method = method
        self.created_by=user
        self.status=self.Status.COMPLETED
        self.last_modified_by=user
        self.save()
        
        # Update all order items to 'served' status to trigger inventory consumption
        for item in self.items.all():
            if item.status not in ['cancelled', 'served']:
                item.status = 'served'
                item.save()
        
        return payment
    
    def refund_payment(self, amount):
        """Refund a payment and create inventory transactions for returns if needed."""
        if amount > self.total_amount:
            raise ValueError("Refund amount cannot exceed order total")
        
        # Create refund payment
        refund_payment = Payment.objects.create(
            order=self,
            amount=amount,
            method=self.payment_method,
            status=Payment.Status.REFUNDED,
            transaction_reference=f"REFUND-{self.order_number}",
            notes=f"Refund for order {self.order_number}",
            created_by=self.last_modified_by
        )
        
        # Update order payment status
        if amount == self.total_amount:
            self.payment_status = 'refunded'
        else:
            self.payment_status = 'partial_refund'
        
        self.save()
        
        # Create inventory return transactions for all items
        self._create_return_transactions(amount)
        
        return refund_payment
    
    def _create_return_transactions(self, refund_amount):
        """Create inventory return transactions for order items."""
        from apps.inventory.models import InventoryTransaction
        
        # Calculate refund ratio
        refund_ratio = refund_amount / self.total_amount
        
        for item in self.items.all():
            # Calculate quantity to return based on refund ratio
            quantity_to_return = item.quantity * refund_ratio
            
            if quantity_to_return > 0:
                if item.item_type == item.ItemType.PRODUCT and item.product:
                    # Return direct product
                    branch_stock = item.product.get_stock_for_branch(self.branch)
                    if branch_stock:
                        InventoryTransaction.create_return_transaction(
                            product=item.product,
                            branch=self.branch,
                            quantity=quantity_to_return,
                            order=self,
                            created_by=self.last_modified_by,
                            notes=f"Return for order {self.order_number}"
                        )
                
                elif item.item_type == item.ItemType.MENU_ITEM and item.menu_item:
                    # Return recipe ingredients (reverse of consumption)
                    recipe = getattr(item.menu_item, 'recipe', None)
                    if recipe:
                        for recipe_ingredient in recipe.ingredients.all():
                            ingredient = recipe_ingredient.ingredient
                            branch_stock = ingredient.get_stock_for_branch(self.branch)
                            if branch_stock:
                                ingredient_quantity = recipe_ingredient.quantity * quantity_to_return
                                InventoryTransaction.create_return_transaction(
                                    product=ingredient,
                                    branch=self.branch,
                                    quantity=ingredient_quantity,
                                    order=self,
                                    created_by=self.last_modified_by,
                                    notes=f"Return ingredients for {item.menu_item.name} - Order {self.order_number}"
                                )
    
    def get_customer_history(self):
        """Get customer's order history with detailed statistics."""
        if not self.customer:
            return None
        
        # Get recent orders
        recent_orders = Order.objects.filter(
            customer=self.customer,
            branch=self.branch
        ).order_by('-created_at')[:5]
        
        # Calculate statistics
        total_orders = Order.objects.filter(
            customer=self.customer,
            branch=self.branch
        ).count()
        
        total_spent = Order.objects.filter(
            customer=self.customer,
            branch=self.branch
        ).aggregate(Sum('total_amount'))['total_amount__sum'] or 0
        
        average_order_value = total_spent / total_orders if total_orders else 0
        
        # Get customer's preferred payment method
        payment_stats = Order.objects.filter(
            customer=self.customer,
            branch=self.branch
        ).values('payment_method').annotate(count=models.Count('payment_method')).order_by('-count')[:1]
        
        preferred_payment = payment_stats[0]['payment_method'] if payment_stats else None
        
        return {
            'recent_orders': recent_orders,
            'total_orders': total_orders,
            'total_spent': total_spent,
            'average_order_value': average_order_value,
            'loyalty_points': self.customer.loyalty_points if self.customer else 0,
            'gift_cards': self.customer.active_gift_cards.all() if self.customer else None,
            'preferred_payment_method': preferred_payment,
            'customer_segment': self.customer.segment if self.customer else None,
            'communication_preference': self.customer.preferred_contact_method if self.customer else None
        }
    
    def get_preferred_items(self):
        """Get customer's preferred items with detailed statistics."""
        if not self.customer:
            return None
            
        # Get top items by count
        top_items = OrderItem.objects.filter(
            order__customer=self.customer,
            order__branch=self.branch
        ).values(
            'product__name',
            'product__category__name',
            'product__category__parent__name'
        ).annotate(
            count=models.Count('product'),
            total_spent=models.Sum('total'),
            average_spend=models.Avg('unit_price')
        ).order_by('-count')[:5]
        
        # Get last ordered items
        recent_items = OrderItem.objects.filter(
            order__customer=self.customer,
            order__branch=self.branch
        ).order_by('-order__created_at')[:5]
        
        # Get category preferences
        category_prefs = OrderItem.objects.filter(
            order__customer=self.customer,
            order__branch=self.branch
        ).values('product__category__name').annotate(count=models.Count('product__category__name')).order_by('-count')[:3]
        
        return {
            'top_items': top_items,
            'recent_items': recent_items,
            'total_items': OrderItem.objects.filter(
                order__customer=self.customer,
                order__branch=self.branch
            ).count(),
            'preferred_categories': category_prefs,
            'last_order_date': Order.objects.filter(
                customer=self.customer,
                branch=self.branch
            ).order_by('-created_at').first().created_at if Order.objects.filter(
                customer=self.customer,
                branch=self.branch
            ).exists() else None
        }
    
    def get_kitchen_display_data(self):
        """Get data formatted for kitchen display system."""
        items = []
        for item in self.items.all():
            item_data = {
                'order_number': self.order_number,
                'table_number': self.table.number if hasattr(self, 'table') else '',
                'item_name': item.product.name,
                'quantity': item.quantity,
                'status': item.get_status_display(),
                'prep_notes': item.kitchen_notes,
                'allergy_warnings': item.get_allergy_warnings(),
                'modifiers': item.get_modifier_notes(),
                'estimated_prep_time': self.estimated_preparation_time,
                'actual_prep_time': self.actual_preparation_time,
                'priority': self.priority,
                'created_at': item.created_at,
                'updated_at': item.updated_at
            }
            items.append(item_data)
        
        return {
            'order_number': self.order_number,
            'branch': self.branch.name,
            'table': self.table.number if hasattr(self, 'table') else '',
            'status': self.get_status_display(),
            'items': items,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }

    def complete_payment(self, user=None):
        """Complete the payment and trigger inventory consumption."""
        # Check if payment is sufficient
        total_payments = self.payments.filter(status=Payment.Status.COMPLETED).aggregate(
            total=models.Sum('amount')
        )['total'] or 0
        
        if total_payments < self.total_amount:
            raise ValueError(f"Insufficient payment. Required: {self.total_amount}, Received: {total_payments}")
        
        # Update order status
        self.payment_status = 'paid'
        self.status = 'completed'
        self.last_modified_by = user
        self.save()
        
        # Update all order items to 'served' status to trigger inventory consumption
        for item in self.items.all():
            if item.status not in ['cancelled', 'served']:
                item.status = 'served'
                item.save()
        
        return True
