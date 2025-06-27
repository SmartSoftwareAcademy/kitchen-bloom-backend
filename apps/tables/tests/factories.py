import factory
import random
from datetime import datetime, timedelta
from django.utils import timezone

from apps.branches.tests.factories import BranchFactory
from apps.employees.tests.factories import EmployeeFactory
from apps.branches.models import Branch
from apps.employees.models import Employee
from ..models import FloorPlan, TableCategory, Table, TableReservation


class FloorPlanFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = FloorPlan
    
    name = factory.Sequence(lambda n: f'Floor Plan {n}')
    branch = factory.SubFactory(BranchFactory)
    width = 1000
    height = 800
    is_active = True


class TableCategoryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = TableCategory
    
    name = factory.Sequence(lambda n: f'Category {n}')
    branch = factory.SubFactory(BranchFactory)
    min_capacity = 2
    max_capacity = 6
    default_capacity = 4
    color = factory.Faker('hex_color')
    is_default = False


class TableFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Table
    
    name = factory.Sequence(lambda n: f'Table {n}')
    branch = factory.SubFactory(BranchFactory)
    category = factory.SubFactory(TableCategoryFactory, branch=factory.SelfAttribute('..branch'))
    floor_plan = factory.SubFactory(FloorPlanFactory, branch=factory.SelfAttribute('..branch'))
    status = 'available'
    position_x = factory.LazyFunction(lambda: random.randint(0, 800))
    position_y = factory.LazyFunction(lambda: random.randint(0, 600))
    rotation = factory.LazyFunction(lambda: random.choice([0, 90, 180, 270]))
    capacity = factory.SelfAttribute('category.default_capacity')
    min_capacity = factory.SelfAttribute('category.min_capacity')
    max_capacity = factory.SelfAttribute('category.max_capacity')
    shape = 'rectangle'
    width = 100
    height = 80
    is_active = True


class TableReservationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = TableReservation
    
    branch = factory.SubFactory(BranchFactory)
    table = factory.SubFactory(TableFactory, branch=factory.SelfAttribute('..branch'))
    customer_name = factory.Faker('name')
    customer_phone = factory.Sequence(lambda n: f'+12345678{n:03d}')
    customer_email = factory.Faker('email')
    reservation_time = factory.LazyFunction(timezone.now)
    duration = 60  # 1 hour
    party_size = factory.LazyAttribute(lambda o: random.randint(1, o.table.max_capacity))
    status = 'confirmed'
    notes = factory.Faker('sentence')
    
    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        # Ensure the table's branch matches the reservation's branch
        if 'branch' in kwargs and 'table' not in kwargs:
            kwargs['table'] = TableFactory(branch=kwargs['branch'])
        elif 'table' in kwargs and 'branch' not in kwargs:
            kwargs['branch'] = kwargs['table'].branch
        
        return super()._create(model_class, *args, **kwargs)


# Create a module-level instance of the factory for easy access
branch_factory = BranchFactory
employee_factory = EmployeeFactory
floor_plan_factory = FloorPlanFactory
table_category_factory = TableCategoryFactory
table_factory = TableFactory
table_reservation_factory = TableReservationFactory
