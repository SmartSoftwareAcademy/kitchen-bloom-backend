import random
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from faker import Faker
from apps.crm.models import Customer, CustomerTag
from apps.loyalty.models import LoyaltyProgram
from apps.branches.models import Branch, Company

User = get_user_model()

class Command(BaseCommand):
    help = 'Seed customer data for development and testing.'

    def add_arguments(self, parser):
        parser.add_argument('count', type=int, nargs='?', default=10,
                         help='Number of customers to create (default: 10)')

    def handle(self, *args, **options):
        fake = Faker()
        count = options['count']
        
        # Get or create necessary related objects
        try:
            loyalty_program = LoyaltyProgram.objects.first()
            if not loyalty_program:
                loyalty_program = LoyaltyProgram.objects.create(
                    name='Standard Loyalty',
                    program_type='points',
                    status='active',
                    points_per_dollar=1.00,
                    minimum_points_for_reward=1000,
                    points_expiry_days=365,
                    description='Standard loyalty program for all customers'
                )
            company, _ = Company.objects.get_or_create(
                name='Kitchen Bloom',
                legal_name='Kitchen Bloom Limited',
                is_active=True
            )
                
            branch, _ = Branch.objects.get_or_create(
                company=company,
                name='Main Branch',
                defaults={
                    'code': 'MB001',
                    'is_active': True
                }
            )
                
            # Create some customer tags
            tags = []
            tag_names = ['VIP', 'Wholesale', 'Retail', 'Frequent', 'New']
            for name in tag_names:
                tag, _ = CustomerTag.objects.get_or_create(
                    name=name,
                    defaults={
                        'color': random.choice(CustomerTag.COLOR_CHOICES)[0],
                        'is_active': True
                    }
                )
                tags.append(tag)
                
            # Create customers
            for i in range(count):
                # Create user account for some customers
                if i % 3 != 0:  # Create user account for 2/3 of customers
                    user = User.objects.create_user(
                        email=fake.unique.email(),
                        first_name=fake.first_name(),
                        last_name=fake.last_name(),
                        password='password123',
                        is_active=True
                    )
                else:
                    user = None
                
                # Create customer data
                customer_data = {
                    'user': user,
                    'customer_code': f'CUST{fake.unique.random_number(digits=6)}',
                    'customer_type': random.choice([ct[0] for ct in Customer.CustomerType.choices]),
                    'gender': random.choice(['M', 'F', 'O', 'N']),  # M, F, O, or N (Prefer not to say)
                    'address_line1': fake.street_address(),
                    'city': fake.city(),
                    'state': fake.state(),
                    'postal_code': fake.postcode(),
                    'country': 'Kenya',
                    'company_name': fake.company() if random.random() > 0.7 else '',
                    'preferred_contact_method': random.choice([m[0] for m in Customer.CommunicationPreference.choices]),
                    'marketing_opt_in': random.choice([True, False]),
                    'loyalty_program': loyalty_program if random.random() > 0.7 else None,
                    'date_of_birth': fake.date_of_birth(minimum_age=18, maximum_age=90) if random.random() > 0.3 else None
                }
                
                # Add phone numbers - ensure guest customers have at least one phone number
                if user is None:  # Guest customer
                    customer_data['alternate_phone'] = fake.phone_number()[:20]
                elif random.random() > 0.3:  # 70% chance to add an alternate phone
                    customer_data['alternate_phone'] = fake.phone_number()[:20]
                
                # Only add tax_id for business/wholesale customers
                if customer_data['customer_type'] in [Customer.CustomerType.BUSINESS, Customer.CustomerType.WHOLESALER]:
                    customer_data['tax_id'] = f'TAX{fake.unique.random_number(digits=7)}'
                    customer_data['vat_number'] = f'VAT{fake.unique.random_number(digits=9)}'
                
                # Create the customer
                customer = Customer.objects.create(**customer_data)
                
                # Add some tags
                customer.tags.set(random.sample(tags, k=random.randint(0, min(3, len(tags)))))
                
                self.stdout.write(self.style.SUCCESS(f'Created customer: {customer}'))
                
            self.stdout.write(self.style.SUCCESS(f'Successfully created {count} customers'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error seeding customers: {str(e)}'))
