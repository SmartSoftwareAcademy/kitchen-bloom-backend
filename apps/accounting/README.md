# Accounting App - Gift Cards

This module handles gift card functionality including creation, redemption, and management.

## Models

### GiftCard
- `code`: Unique identifier for the gift card (auto-generated)
- `initial_value`: Initial monetary value of the gift card
- `current_balance`: Current available balance
- `currency`: Currency code (KES, USD, etc.)
- `status`: One of: active, redeemed, expired, voided
- `issue_date`: When the card was issued
- `expiry_date`: When the card expires (optional)
- `issued_to`: Customer who owns the card (optional)
- `issued_by`: Staff user who issued the card
- `notes`: Any additional notes

### GiftCardRedemption
- `gift_card`: The gift card being redeemed
- `redemption_type`: Type of redemption (purchase, refund, void)
- `amount`: Amount being redeemed
- `order`: Related order (if applicable)
- `processed_by`: Staff user who processed the redemption
- `balance_after`: New balance after redemption
- `notes`: Any additional notes

## API Endpoints

### Gift Cards

#### List Gift Cards
- **URL**: `/api/accounting/gift-cards/`
- **Method**: `GET`
- **Query Params**:
  - `status`: Filter by status (active, redeemed, expired, voided)
  - `customer_id`: Filter by customer ID
  - `ordering`: Order by field (e.g., `-created_at` for newest first)
- **Permissions**: Staff users can see all, customers see only their own

#### Create Gift Card
- **URL**: `/api/accounting/gift-cards/`
- **Method**: `POST`
- **Data**:
  ```json
  {
    "initial_value": 1000.00,
    "currency": "KES",
    "expiry_date": "2025-12-31",
    "customer_id": 1,
    "notes": "Birthday gift"
  }
  ```
- **Permissions**: Staff only

#### Get Gift Card Details
- **URL**: `/api/accounting/gift-cards/{code}/`
- **Method**: `GET`
- **Permissions**: Staff or card owner

#### Redeem Gift Card
- **URL**: `/api/accounting/gift-cards/{code}/redeem/`
- **Method**: `POST`
- **Data**:
  ```json
  {
    "amount": 250.00,
    "order_id": 123,
    "notes": "Lunch order"
  }
  ```
- **Permissions**: Staff only

#### Void Gift Card
- **URL**: `/api/accounting/gift-cards/{code}/void/`
- **Method**: `POST`
- **Data**:
  ```json
  {
    "reason": "Lost card"
  }
  ```
- **Permissions**: Staff only

### Gift Card Redemptions

#### List Redemptions
- **URL**: `/api/accounting/redemptions/`
- **Method**: `GET`
- **Query Params**:
  - `gift_card`: Filter by gift card code
  - `redemption_type`: Filter by type (purchase, refund, void)
  - `ordering`: Order by field (e.g., `-created_at`)
- **Permissions**: Staff only

#### Get Redemption Details
- **URL**: `/api/accounting/redemptions/{id}/`
- **Method**: `GET`
- **Permissions**: Staff only

## Management Commands

### Generate Gift Cards
```bash
# Generate a single gift card
python manage.py generate_gift_cards --value 1000 --currency KES

# Generate 5 gift cards for a customer
python manage.py generate_gift_cards --count 5 --value 500 --currency KES --customer 1

# Generate gift cards with custom prefix and length
python manage.py generate_gift_cards --value 2000 --prefix CUST --length 10

# Generate gift cards that expire in 90 days
python manage.py generate_gift_cards --value 1500 --expires-in 90
```

### Update Gift Card Status
```bash
# Check for expired gift cards and mark them as expired
python manage.py update_gift_card_status --expire

# Check for gift cards expiring in the next 30 days
python manage.py update_gift_card_status --notify-days 30

# Dry run (show what would be changed without making changes)
python manage.py update_gift_card_status --expire --dry-run
```

## Usage Examples

### Issue a New Gift Card
```python
from apps.accounting.models import GiftCard
from django.contrib.auth import get_user_model
from apps.crm.models import Customer

# Get or create a customer
customer = Customer.objects.first()
user = get_user_model().objects.filter(is_staff=True).first()

# Create a new gift card
gift_card = GiftCard.objects.create(
    initial_value=5000.00,
    currency='KES',
    issued_to=customer,
    issued_by=user,
    notes="Customer loyalty reward"
)

print(f"Created gift card: {gift_card.code}")
```

### Redeem a Gift Card
```python
from apps.accounting.models import GiftCard

try:
    gift_card = GiftCard.objects.get(code="GC12345678")
    
    # Redeem 1000 from the card
    redemption = gift_card.redeem(
        amount=1000.00,
        redemption_type="purchase",
        order_id=123,
        processed_by=request.user,
        notes="Dinner order #123"
    )
    
    print(f"Redeemed {redemption.amount}. New balance: {gift_card.current_balance}")
    
except GiftCard.DoesNotExist:
    print("Gift card not found")
except ValueError as e:
    print(f"Error: {str(e)}")
```

## Permissions

- **Staff Users**: Can perform all operations
- **Customers**: Can only view their own gift cards and redemption history
- **Unauthenticated Users**: No access

## Testing

To test the gift card functionality, you can use the Django shell:

```bash
python manage.py shell
```

```python
from apps.accounting.models import GiftCard
from django.contrib.auth import get_user_model

# Get a staff user
User = get_user_model()
user = User.objects.filter(is_staff=True).first()

# Create a test gift card
gc = GiftCard.objects.create(
    initial_value=1000,
    currency='KES',
    issued_by=user,
    notes="Test card"
)

# Redeem some amount
redemption = gc.redeem(
    amount=250,
    redemption_type="purchase",
    processed_by=user,
    notes="Test redemption"
)

print(f"Gift Card: {gc.code}")
print(f"Initial Value: {gc.initial_value}")
print(f"Current Balance: {gc.current_balance}")
print(f"Redemption Amount: {redemption.amount}")
print(f"Balance After: {redemption.balance_after}")
```

## Notes

- Gift card codes are automatically generated in the format `[PREFIX][RANDOM_CHARS]`
- The default prefix is 'GC' and can be customized
- Gift cards can be set to expire after a certain date
- All redemptions are logged for audit purposes
- Gift cards can be voided but not deleted to maintain audit history
