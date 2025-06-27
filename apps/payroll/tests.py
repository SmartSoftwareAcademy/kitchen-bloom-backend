import os
import tempfile
from datetime import date, timedelta
from decimal import Decimal
from django.conf import settings
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APIClient

from apps.employees.models import Department, Employee
from apps.payroll.models import (
    PayrollPeriod, SalaryStructure, PayrollItem, EmployeePayroll
)

User = get_user_model()


class PayrollModelTests(TestCase):
    """Test cases for payroll models."""

    def setUp(self):
        """Set up test data."""
        # Create test user
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User'
        )
        
        # Create department
        self.department = Department.objects.create(
            name='Test Department',
            code='TEST',
            description='Test Department Description'
        )
        
        # Create employee profile for the user
        self.employee = Employee.objects.create(
            user=self.user,
            employee_id='EMP001',
            date_of_birth=date(1990, 1, 1),
            gender='M',
            phone_number='+254712345678',
            id_number='12345678',
            department=self.department,
            hire_date=date.today() - timedelta(days=365),  # 1 year ago
            salary=50000.00,
            employment_type='FT',
            position='Test Position',
            created_by=None,  # Will be set after employee creation
            last_modified_by=None
        )
        
        # Now update department and employee with references
        self.department.created_by = self.employee
        self.department.last_modified_by = self.employee
        self.department.save()
        
        self.employee.created_by = self.employee
        self.employee.last_modified_by = self.employee
        self.employee.save()
        
        # Create salary structure
        self.salary_structure = SalaryStructure.objects.create(
            name='Test Salary Structure',
            description='Test Description',
            is_default=True,
            created_by=self.user.employee_profile,
            last_modified_by=self.user.employee_profile
        )
        
        # Create payroll items
        self.basic_salary = PayrollItem.objects.create(
            name='Basic Salary',
            description='Basic monthly salary',
            item_type='earning',
            is_percentage=False,
            is_tax_deductible=True,
            amount=Decimal('50000.00'),
            created_by=self.user.employee_profile,
            last_modified_by=self.user.employee_profile
        )
        
        self.bonus = PayrollItem.objects.create(
            name='Performance Bonus',
            description='Monthly performance bonus',
            item_type='earning',
            is_percentage=False,
            is_tax_deductible=True,
            amount=Decimal('10000.00'),
            created_by=self.user.employee_profile,
            last_modified_by=self.user.employee_profile
        )
        
        self.tax = PayrollItem.objects.create(
            name='PAYE',
            description='Pay As You Earn Tax',
            item_type='deduction',
            is_percentage=True,
            is_tax_deductible=False,
            amount=Decimal('15.00'),  # 15%
            created_by=self.user.employee_profile,
            last_modified_by=self.user.employee_profile
        )
        
        # Add items to salary structure
        self.salary_structure.items.add(self.basic_salary)
        self.salary_structure.items.add(self.bonus)
        self.salary_structure.items.add(self.tax)
        
        # Create payroll period
        today = timezone.now().date()
        self.payroll_period = PayrollPeriod.objects.create(
            start_date=today - timedelta(days=30),
            end_date=today - timedelta(days=1),
            status='draft',
            created_by=self.user.employee_profile,
            last_modified_by=self.user.employee_profile
        )
    
    def test_payroll_period_creation(self):
        """Test PayrollPeriod model creation."""
        period = self.payroll_period
        self.assertEqual(period.status, 'draft')
        self.assertTrue(period.start_date < period.end_date)
    
    def test_salary_structure_creation(self):
        """Test SalaryStructure model creation."""
        structure = self.salary_structure
        self.assertEqual(structure.name, 'Test Salary Structure')
        self.assertTrue(structure.is_default)
        self.assertEqual(structure.items.count(), 3)
    
    def test_payroll_item_creation(self):
        """Test PayrollItem model creation."""
        item = self.basic_salary
        self.assertEqual(item.name, 'Basic Salary')
        self.assertEqual(item.item_type, 'earning')
        self.assertTrue(item.is_tax_deductible)
    
    def test_employee_payroll_creation(self):
        """Test EmployeePayroll model creation and calculations."""
        # Create employee payroll
        payroll_data = {
            'employee': self.employee,
            'payroll_period': self.payroll_period,
            'salary_structure': self.salary_structure,
            'basic_salary': Decimal('50000.00'),
            'gross_pay': Decimal('60000.00'),  # 50k basic + 10k bonus
            'total_deductions': Decimal('9000.00'),  # 15% of 60k
            'net_pay': Decimal('51000.00'),  # 60k - 9k
            'status': 'draft',
            'payment_method': 'bank',
            'payment_reference': 'TEST123',
            'created_by': self.user.employee_profile,
            'last_modified_by': self.user.employee_profile
        }
        employee_payroll = EmployeePayroll.objects.create(**payroll_data)
        
        self.assertEqual(employee_payroll.employee, self.employee)
        self.assertEqual(employee_payroll.payroll_period, self.payroll_period)
        self.assertEqual(employee_payroll.gross_pay, Decimal('60000.00'))
        self.assertEqual(employee_payroll.total_deductions, Decimal('9000.00'))
        self.assertEqual(employee_payroll.net_pay, Decimal('51000.00'))
    
    def test_employee_payroll_calculate(self):
        """Test EmployeePayroll calculate_payroll method."""
        # Create employee payroll
        payroll_data = {
            'employee': self.employee,
            'payroll_period': self.payroll_period,
            'salary_structure': self.salary_structure,
            'basic_salary': Decimal('50000.00'),
            'status': 'draft',
            'created_by': self.user.employee_profile,
            'last_modified_by': self.user.employee_profile
        }
        employee_payroll = EmployeePayroll.objects.create(**payroll_data)
        
        # Calculate payroll
        employee_payroll.calculate_payroll()
        
        # Verify calculations
        self.assertEqual(employee_payroll.gross_pay, Decimal('60000.00'))  # 50k + 10k
        self.assertEqual(employee_payroll.total_deductions, Decimal('9000.00'))  # 15% of 60k
        self.assertEqual(employee_payroll.net_pay, Decimal('51000.00'))  # 60k - 9k
        self.assertEqual(employee_payroll.status, 'calculated')


class PayrollManagementCommandsTests(TestCase):
    """Test cases for payroll management commands."""
    
    def setUp(self):
        """Set up test data."""
        # Create admin user
        self.admin = User.objects.create_superuser(
            email='admin@example.com',
            password='adminpass123',
            first_name='Admin',
            last_name='User'
        )
        
        # Create employee profile for admin
        self.employee = Employee.objects.create(
            user=self.admin,
            employee_id='ADMIN001',
            date_of_birth=date(1980, 1, 1),
            gender='M',
            phone_number='+254700000000',
            id_number='00000000',
            position='Administrator',
            employment_type='FT',
            hire_date=date(2020, 1, 1),
            created_by=None,  # Will be set after creation
            last_modified_by=None
        )
        
        # Now update employee with self-reference
        self.employee.created_by = self.employee
        self.employee.last_modified_by = self.employee
        self.employee.save()
    
    def test_generate_payroll_periods_command(self):
        """Test generate_payroll_periods management command."""
        # Call the command with test data
        call_command(
            'generate_payroll_periods',
            '--admin-email=admin@example.com',
            '--months=3'
        )
        
        # Verify periods were created
        self.assertEqual(PayrollPeriod.objects.count(), 3)
        
        # Verify periods are sequential
        periods = PayrollPeriod.objects.order_by('start_date')
        for i in range(1, len(periods)):
            self.assertEqual(
                periods[i].start_date,
                (periods[i-1].end_date + timedelta(days=1)).replace(day=1)
            )
    
    @override_settings(MEDIA_ROOT=tempfile.mkdtemp())
    def test_generate_payroll_reports_command(self):
        """Test generate_payroll_reports management command."""
        # Create test data
        today = timezone.now().date()
        period_data = {
            'start_date': today - timedelta(days=30),
            'end_date': today - timedelta(days=1),
            'status': 'draft',
            'created_by': self.admin.employee_profile,
            'last_modified_by': self.admin.employee_profile
        }
        period = PayrollPeriod.objects.create(**period_data)
        
        # Call the command
        output_dir = os.path.join(settings.MEDIA_ROOT, 'payroll_reports')
        call_command(
            'generate_payroll_reports',
            f'--period-id={period.id}',
            f'--output-dir={output_dir}',
            '--format=excel'
        )
        
        # Verify report was generated
        report_files = os.listdir(output_dir)
        self.assertTrue(any(str(period.id) in f for f in report_files))


class PayrollAPITests(TestCase):
    """Test cases for payroll API endpoints."""
    
    def setUp(self):
        """Set up test data."""
        # Create admin user
        self.admin = User.objects.create_superuser(
            email='admin@example.com',
            password='adminpass123',
            first_name='Admin',
            last_name='User'
        )
        
        # Create employee profile for admin
        self.employee = Employee.objects.create(
            user=self.admin,
            employee_id='ADMIN001',
            date_of_birth=date(1980, 1, 1),
            gender='M',
            phone_number='+254700000000',
            id_number='00000000',
            position='Administrator',
            employment_date=date(2020, 1, 1),
            created_by=self.admin.employee_profile,
            last_modified_by=self.admin.employee_profile
        )
        
        # Create test client
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)
        
        # Create test data
        self.payroll_period = PayrollPeriod.objects.create(
            start_date=date(2023, 1, 1),
            end_date=date(2023, 1, 31),
            status='draft',
            created_by=self.admin.employee_profile,
            last_modified_by=self.admin.employee_profile
        )
    
    def test_payroll_period_list(self):
        """Test listing payroll periods."""
        url = '/api/payroll/periods/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('results', response.data)
        self.assertIsInstance(response.data['results'], list)
    
    def test_create_employee_payroll(self):
        """Test creating an employee payroll record."""
        data = {
            'employee': self.employee.id,
            'payroll_period': self.payroll_period.id,
            'basic_salary': '50000.00',
            'status': 'draft'
        }
        
        response = self.client.post('/api/payroll/employee-payrolls/', data, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(EmployeePayroll.objects.count(), 1)
        self.assertEqual(EmployeePayroll.objects.get().employee, self.employee)
    
    def test_calculate_payroll(self):
        """Test calculating payroll for an employee."""
        # Create employee payroll
        payroll_data = {
            'employee': self.employee,
            'payroll_period': self.payroll_period,
            'basic_salary': Decimal('50000.00'),
            'status': 'draft',
            'created_by': self.admin.employee_profile,
            'last_modified_by': self.admin.employee_profile
        }
        payroll = EmployeePayroll.objects.create(**payroll_data)
        
        # Test calculate action
        response = self.client.post(
            f'/api/payroll/employee-payrolls/{payroll.id}/calculate/',
            format='json'
        )
        
        self.assertEqual(response.status_code, 200)
        payroll.refresh_from_db()
        self.assertEqual(payroll.status, 'calculated')
        self.assertIsNotNone(payroll.gross_pay)
        self.assertIsNotNone(payroll.total_deductions)
        self.assertIsNotNone(payroll.net_pay)
