#function to genrate expense reference number
import random
from django.utils import timezone

def generate_number(prefix):
    date_str = timezone.now().strftime('%Y%m%d')
    # First revenue of the day
    return f'{prefix}{date_str}-{random.randint(1, 999999):03d}'
