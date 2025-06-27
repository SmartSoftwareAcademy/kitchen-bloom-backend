import random
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from faker import Faker
from apps.employees.models import Department, Employee
from apps.accounts.models import Role
from decimal import Decimal, ROUND_HALF_UP

User = get_user_model()

class Command(BaseCommand):
    help = 'Seed employee data for development and testing.'

    def add_arguments(self, parser):
        parser.add_argument('count', type=int, nargs='?', default=10,
                         help='Number of employees to create (default: 10)')

    def handle(self, *args, **options):
        fake = Faker()
        count = options['count']
        
        try:
            # Create departments if they don't exist
            departments = []
            dept_names = [
                'Kitchen', 'Service', 'Management', 'HR', 'Finance',
                'Marketing', 'IT', 'Operations', 'Procurement', 'Quality Control'
            ]
            
            for name in dept_names:
                dept, _ = Department.objects.get_or_create(
                    name=name,
                    defaults={
                        'code': name[:3].upper(),
                        'description': f'{name} Department',
                        'is_active': True
                    }
                )
                departments.append(dept)
            
            # Get or create roles using the predefined role constants
            roles = {}
            
            # Manager role
            manager_role, _ = Role.objects.get_or_create(
                name=Role.MANAGER,
                defaults={'description': 'Manager role with team oversight'}
            )
            roles['manager'] = manager_role
            
            # Cashier role
            cashier_role, _ = Role.objects.get_or_create(
                name=Role.CASHIER,
                defaults={'description': 'Handles payments and customer transactions'}
            )
            roles['cashier'] = cashier_role
            
            # Kitchen Staff role
            kitchen_staff_role, _ = Role.objects.get_or_create(
                name=Role.KITCHEN_STAFF,
                defaults={'description': 'Kitchen staff responsible for food preparation'}
            )
            roles['kitchen_staff'] = kitchen_staff_role
            
            # Waiter role
            waiter_role, _ = Role.objects.get_or_create(
                name=Role.WAITER,
                defaults={'description': 'Serves food and attends to customers'}
            )
            roles['waiter'] = waiter_role
            
            # Accountant role
            accountant_role, _ = Role.objects.get_or_create(
                name=Role.ACCOUNTANT,
                defaults={'description': 'Handles financial records and reporting'}
            )
            roles['accountant'] = accountant_role
            
            # Admin role (for system administrators)
            admin_role, _ = Role.objects.get_or_create(
                name=Role.ADMIN,
                defaults={'description': 'System administrator with full access'}
            )
            roles['admin'] = admin_role
            
            # Create management first (managers and admin)
            managers = []
            
            # Create admin user
            admin_user,_ = User.objects.get_or_create(
                email='admin@example.com',
                defaults={
                "first_name":"Admin",
                "last_name":"User",
                "password":"admin123",
                "is_active":True,
                "is_staff":True,
                "is_superuser":True,
                "role":roles['admin']
                }
            )
            
            # Create manager users (2 managers)
            for i in range(2):
                user,_ = User.objects.get_or_create(
                    email=f'manager{i+1}@example.com',
                    defaults={
                    "first_name":fake.first_name(),
                    "last_name":fake.last_name(),
                    "password":"password123",
                    "is_active":True,
                    "is_staff":True,
                    "role":roles['manager']
                    }
                )
                
                # Create manager with placeholder salary
                manager, created = Employee.objects.get_or_create(
                    user=user,
                    defaults={
                        "employee_id": f'MGR{100 + i}',
                        "salary": Decimal('0.00'),  # Placeholder
                        "date_of_birth": fake.date_of_birth(minimum_age=30, maximum_age=55),
                        "gender": random.choice(['M', 'F']),
                        "phone_number": fake.phone_number()[:20],
                        "department": random.choice(departments),
                        "hire_date": fake.date_between(start_date='-5y', end_date='-1y'),
                        "employment_type": "FT",
                        "is_active": True,
                    }
                )
                
                # Update salary separately
                if created:
                    cents = random.randint(150000, 300000)
                    manager.salary = Decimal(f'{cents // 100}.{cents % 100:02}')
                    manager.save()
                
                # Add address only if no primary address exists
                if not manager.addresses.filter(is_primary=True).exists():
                    manager.addresses.create(
                        address_line1=fake.street_address(),
                        city=fake.city(),
                        state=fake.state(),
                        postal_code=fake.postcode(),
                        country='Kenya',
                        is_primary=True
                    )
                
                managers.append(manager)
                self.stdout.write(self.style.SUCCESS(f'Created manager: {manager}'))
            
            # Create regular employees with different roles
            employee_roles = [
                roles['cashier'],
                roles['kitchen_staff'],
                roles['waiter'],
                roles['accountant']
            ]
            
            departments_by_role = {
                'cashier': ['Finance', 'Service'],
                'kitchen_staff': ['Kitchen'],
                'waiter': ['Service'],
                'accountant': ['Finance']
            }
            
            for i in range(count - 3):  # Subtract 3 for the managers and admin
                # Choose a random role for this employee
                role = random.choice(employee_roles)
                role_name = next((k for k, v in roles.items() if v == role), None)
                
                # Choose department based on role
                if role_name in departments_by_role:
                    dept_choices = [d for d in departments if d.name in departments_by_role[role_name]]
                    department = random.choice(dept_choices) if dept_choices else random.choice(departments)
                else:
                    department = random.choice(departments)
                
                # Create user
                user,_ = User.objects.get_or_create(
                    email=f'employee{i+1}@example.com',
                    defaults={
                    "first_name":fake.first_name(),
                    "last_name":fake.last_name(),
                    "password":"password123",
                    "is_active":True,
                    "is_staff":False,
                    "role":role
                    }
                )
                
                # Create employee with placeholder salary
                employee, created = Employee.objects.get_or_create(
                    user=user,
                    defaults={
                        "employee_id": f'EMP{1000 + i}',
                        "salary": Decimal('0.00'), # Placeholder
                        "date_of_birth": fake.date_of_birth(minimum_age=20, maximum_age=50),
                        "gender": random.choice(['M', 'F']),
                        "phone_number": fake.phone_number()[:20],
                        "department": department,
                        "hire_date": fake.date_between(start_date='-2y', end_date='-1m'),
                        "employment_type": random.choice(['FT', 'PT', 'TEMP']),
                        "supervisor": random.choice(managers) if managers and random.random() > 0.3 else None,
                        "is_active": random.random() > 0.1,
                    }
                )
                
                # Update salary separately
                if created:
                    cents = random.randint(50000, 200000)
                    employee.salary = Decimal(f'{cents // 100}.{cents % 100:02}')
                    employee.save()
                
                # Add address only if no primary address exists
                if not employee.addresses.filter(is_primary=True).exists():
                    employee.addresses.create(
                        address_line1=fake.street_address(),
                        city=fake.city(),
                        state=fake.state(),
                        postal_code=fake.postcode(),
                        country='Kenya',
                        is_primary=True
                    )
                
                # Add emergency contact for some employees
                if random.random() > 0.3:  # 70% chance
                    employee.emergency_contact_name = f'{fake.first_name()} {fake.last_name()}'
                    employee.emergency_contact_phone = fake.phone_number()[:20]
                    employee.emergency_contact_relation = random.choice(['Spouse', 'Parent', 'Sibling', 'Friend'])
                    employee.save()
                
                self.stdout.write(self.style.SUCCESS(f'Created employee: {employee}'))
            
            self.stdout.write(self.style.SUCCESS(f'Successfully created {count} employees'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error seeding employees: {str(e)}'))
