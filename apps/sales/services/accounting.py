from decimal import Decimal, ROUND_HALF_UP
from django.utils import timezone
from apps.accounting.models import Revenue, RevenueCategory, RevenueAccount
from apps.accounting.utils import generate_number

def create_revenue_for_order(order, payment=None):
    """
    Create a Revenue record for a completed/paid order.
    If payment is provided, use its method/reference; otherwise, use order's payment info.
    """
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
    # Get or create the 'Sales' revenue category
    category, _ = RevenueCategory.objects.get_or_create(
        name='Sales',
        defaults={
            'description': 'Sales Revenue Category'
        }
    )
    if not category.default_account:
        category.default_account = revenue_account
        category.save()

    # Quantize amount
    amount = Decimal(str(order.total_amount)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
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
    if payment:
        revenue_payment_method = PAYMENT_METHOD_MAP.get(payment.method, 'other')
        payment_reference = payment.transaction_reference
    else:
        revenue_payment_method = PAYMENT_METHOD_MAP.get(order.payment_method, 'other')
        payment_reference = ''
    # Use the first customer if available
    customer = order.customers.first() if order.customers.exists() else None
    # Set created_by and last_modified_by
    created_by = getattr(order, 'created_by', None)
    # Create revenue entry
    revenue = Revenue.objects.create(
        revenue_number=generate_number('RE'),
        revenue_date=order.created_at.date() if hasattr(order, 'created_at') else timezone.now().date(),
        amount=amount,
        currency='KES',
        description=f'Revenue for Order {order.order_number}',
        revenue_type='sales',
        category=category,
        branch=order.branch,
        customer=customer,
        payment_method=revenue_payment_method,
        payment_reference=payment_reference,
        status='paid',
        created_by=created_by,
        last_modified_by=created_by
    )
    return revenue 