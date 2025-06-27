import random
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from faker import Faker
from apps.tables.models import TableCategory, Table, TableReservation, FloorPlan
from apps.branches.models import Branch
from apps.employees.models import Employee
from apps.accounts.models import User, Role
from decimal import Decimal, ROUND_DOWN

# Table status choices for seeding
TABLE_STATUS_CHOICES = [
    ('available', 'Available'),
    ('occupied', 'Occupied'),
    ('reserved', 'Reserved'),
    ('maintenance', 'Maintenance'),
    ('cleaning', 'Cleaning'),
]

# Table shape choices for seeding
TABLE_SHAPES = [
    ('rectangle', 'Rectangle'),
    ('circle', 'Circle'),
    ('square', 'Square'),
    ('oval', 'Oval'),
]

class Command(BaseCommand):
    help = 'Seed floor plans, table categories, tables, and reservations data for development and testing.'

    def add_arguments(self, parser):
        parser.add_argument('--floor-plans', type=int, default=2, help='Number of floor plans to create (default: 2)')
        parser.add_argument('--categories', type=int, default=3, help='Number of table categories to create (default: 3)')
        parser.add_argument('--tables', type=int, default=15, help='Number of tables to create (default: 15)')
        parser.add_argument('--reservations', type=int, default=30, help='Number of reservations to create (default: 30)')
        parser.add_argument('--waiters', type=int, default=5, help='Number of waiters to create (default: 5)')

    def handle(self, *args, **options):
        fake = Faker()
        floor_plan_count = options['floor_plans']
        category_count = options['categories']
        table_count = options['tables']
        reservation_count = options['reservations']
        waiter_count = options['waiters']
        
        self.stdout.write(self.style.SUCCESS('Starting to seed tables data...'))
        
        try:
            # Get or create a branch
            branch = Branch.objects.first()
            if not branch:
                self.stdout.write(self.style.NOTICE('Creating default branch...'))
                branch = Branch.objects.create(
                    name='Main Branch',
                    code='MB001',
                    is_active=True,
                    address='123 Restaurant St, Nairobi',
                    phone='+254700000000',
                    email='main@restaurant.com'
                )
            
            # Create admin user if not exists
            if not User.objects.filter(email='admin@example.com').exists():
                self.stdout.write(self.style.NOTICE('Creating admin user...'))
                User.objects.create_superuser(
                    email='admin@example.com',
                    password='admin123',
                    first_name='Admin',
                    last_name='User'
                )
            
            # Get or create the waiter role
            waiter_role, _ = Role.objects.get_or_create(
                name=Role.WAITER,
                defaults={'description': 'Waiter role'}
            )
            
            # Create waiters
            self.stdout.write(self.style.NOTICE(f'Creating {waiter_count} waiters...'))
            waiters = []
            for i in range(1, waiter_count + 1):
                user, _ = User.objects.get_or_create(
                    email=f'waiter{i}@example.com',
                    defaults={
                        'password': 'waiter123',
                        'first_name': f'Waiter{i}',
                        'last_name': 'Staff'
                    }
                )
                # Ensure salary is at least the base salary for the role, rounded to 2 decimal places
                base_salary = waiter_role.base_salary if hasattr(waiter_role, 'base_salary') else 10000
                salary = Decimal(base_salary).quantize(Decimal('0.01'), rounding=ROUND_DOWN)
                waiter, _ = Employee.objects.get_or_create(
                    user=user,
                    defaults={
                        'role': waiter_role,
                        'phone_number': f'+2547000000{i:02d}',
                        'hire_date': timezone.now() - timedelta(days=random.randint(30, 365)),
                        'is_active': True,
                        'employee_id': f'WTR{i:04d}',
                        'salary': salary,
                    }
                )
                # Add address if not present
                if not waiter.addresses.filter(is_primary=True).exists():
                    waiter.addresses.create(
                        address_line1=f'{i} Staff Quarters, Nairobi',
                        city='Nairobi',
                        country='Kenya',
                        is_primary=True
                    )
                waiters.append(waiter)
            
            # Create floor plans
            self.stdout.write(self.style.NOTICE(f'Creating {floor_plan_count} floor plans...'))
            floor_plans = []
            for i in range(1, floor_plan_count + 1):
                floor_plan, _ = FloorPlan.objects.get_or_create(
                    name=f'Floor {i}',
                    branch=branch,
                    defaults={
                        'width': 1000,
                        'height': 800,
                        'is_active': i == 1  # Only first floor active by default
                    }
                )
                floor_plans.append(floor_plan)
            
            # Create table categories
            self.stdout.write(self.style.NOTICE(f'Creating {category_count} table categories...'))
            categories = []
            category_names = ['Standard', 'Booth', 'Bar', 'VIP', 'Outdoor']
            colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEEAD']
            
            for i in range(min(category_count, len(category_names))):
                min_cap = 2 if i < 2 else (4 if i < 4 else 6)
                max_cap = min_cap * 2
                
                category, _ = TableCategory.objects.get_or_create(
                    name=category_names[i],
                    branch=branch,
                    defaults={
                        'capacity': (min_cap + max_cap) // 2,
                        'color': colors[i % len(colors)],
                        'is_default': (i == 0)
                    }
                )
                categories.append(category)
            
            # Create tables
            self.stdout.write(self.style.NOTICE(f'Creating {table_count} tables...'))
            tables = []
            tables_per_floor = table_count // len(floor_plans)
            
            for i in range(1, table_count + 1):
                floor_idx = (i - 1) // tables_per_floor
                floor_plan = floor_plans[min(floor_idx, len(floor_plans) - 1)]
                category = random.choice(categories)
                
                # Calculate position to distribute tables evenly
                tables_in_floor = tables_per_floor if floor_idx < len(floor_plans) - 1 else (table_count - (tables_per_floor * (len(floor_plans) - 1)))
                tables_per_row = int((tables_in_floor ** 0.5) + 1)
                
                row = ((i - 1) % tables_per_floor) // tables_per_row
                col = (i - 1) % tables_per_row
                
                # Add some random spacing
                pos_x = 100 + (col * 200) + random.randint(-20, 20)
                pos_y = 100 + (row * 200) + random.randint(-20, 20)
                width = random.randint(80, 120)
                height = random.randint(80, 120)
                
                table = Table.objects.create(
                    name=f'Table {i}',
                    number=f'{i}',
                    branch=branch,
                    category=category,
                    floor_plan=floor_plan,
                    status=random.choice([s[0] for s in TABLE_STATUS_CHOICES if s[0] != 'combined']),
                    location={"x": pos_x, "y": pos_y, "rotation": random.choice([0, 90, 180, 270])},
                    size={"width": width, "height": height},
                    capacity=category.capacity,
                    shape=random.choice([s[0] for s in TABLE_SHAPES])
                )
                
                # Randomly assign a waiter to some tables
                if random.random() > 0.7:  # 30% chance to have a waiter
                    table.waiter = random.choice(waiters)
                    table.save()
                
                tables.append(table)
            
            # Create some combined tables (10% of tables)
            self.stdout.write(self.style.NOTICE('Creating combined tables...'))
            combined_tables = random.sample(tables, max(1, table_count // 10))
            for i in range(0, len(combined_tables) - 1, 2):
                if i + 1 < len(combined_tables):
                    main_table = combined_tables[i]
                    sub_table = combined_tables[i + 1]
                    
                    main_table.combined_tables.add(sub_table)
                    sub_table.status = 'combined'
                    sub_table.save()
            
            # Create reservations
            self.stdout.write(self.style.NOTICE(f'Creating {reservation_count} reservations...'))
            status_weights = {
                'confirmed': 0.4,
                'seated': 0.3,
                'completed': 0.2,
                'cancelled': 0.1
            }
            
            for _ in range(reservation_count):
                table = random.choice(tables)
                status = random.choices(
                    list(status_weights.keys()),
                    weights=list(status_weights.values())
                )[0]
                
                # Create reservation time within the next 14 days
                days_ahead = random.randint(0, 14)
                reservation_time = timezone.now() + timedelta(days=days_ahead)
                expected_arrival_time = reservation_time + timedelta(minutes=15)
                
                # For past reservations, set to completed
                if days_ahead == 0:
                    status = 'completed'
                    reservation_time = timezone.now() - timedelta(days=random.randint(1, 30))
                    expected_arrival_time = reservation_time + timedelta(minutes=15)
                
                # For current reservations, set to seated
                if status == 'seated':
                    reservation_time = timezone.now() - timedelta(minutes=random.randint(10, 120))
                    expected_arrival_time = reservation_time + timedelta(minutes=15)
                
                TableReservation.objects.create(
                    table=table,
                    reservation_time=reservation_time,
                    expected_arrival_time=expected_arrival_time,
                    status=status,
                    covers=random.randint(1, table.capacity),
                    notes=fake.sentence() if random.random() > 0.7 else '',
                    source=random.choice(['in_house', 'website', 'phone', 'mobile_app', 'walk_in', 'other']),
                    metadata={},
                    customer=None  # You can add customer logic if needed
                )
            
            self.stdout.write(self.style.SUCCESS(f'Successfully seeded tables data with {len(tables)} tables and {reservation_count} reservations!'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error seeding tables data: {str(e)}'))
            raise e
