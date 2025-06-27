import json
from datetime import datetime, timedelta
from django.urls import reverse
from django.utils import timezone
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase, APIClient

from apps.branches.models import Branch
from apps.employees.models import Employee
from .factories import (
    FloorPlanFactory, 
    TableCategoryFactory, 
    TableFactory, 
    TableReservationFactory,
    BranchFactory,
    EmployeeFactory
)
from ..models import FloorPlan, Table, TableCategory, TableReservation, TABLE_STATUS_CHOICES


class BaseTestCase(APITestCase):
    """Base test case with common setup"""
    
    def setUp(self):
        self.client = APIClient()
        
        # Create test data
        self.branch = BranchFactory()
        self.waiter = EmployeeFactory(branch=self.branch, role='waiter')
        self.category = TableCategoryFactory(branch=self.branch)
        self.floor_plan = FloorPlanFactory(branch=self.branch)
        
        # Create test tables
        self.table1 = TableFactory(
            branch=self.branch, 
            category=self.category,
            floor_plan=self.floor_plan,
            position_x=100,
            position_y=200,
            rotation=0
        )
        self.table2 = TableFactory(
            branch=self.branch,
            category=self.category,
            floor_plan=self.floor_plan,
            position_x=300,
            position_y=200,
            rotation=90
        )
        
        # Create a reservation
        self.reservation = TableReservationFactory(
            table=self.table1,
            branch=self.branch,
            customer_name="Test Customer",
            customer_phone="+1234567890",
            reservation_time=timezone.now(),
            party_size=4,
            status='confirmed'
        )
        
        # Login as admin for all tests
        self.admin = Employee.objects.create_superuser(
            email='admin@example.com',
            password='testpass123',
            branch=self.branch
        )
        self.client.force_authenticate(user=self.admin)


class FloorPlanTests(BaseTestCase):
    """Test floor plan endpoints"""
    
    def test_list_floor_plans(self):
        url = reverse('floor-plan-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_retrieve_floor_plan(self):
        url = reverse('floor-plan-detail', kwargs={'pk': self.floor_plan.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], self.floor_plan.name)
    
    def test_floor_plan_tables(self):
        url = reverse('floor-plan-tables', kwargs={'pk': self.floor_plan.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
    
    def test_update_floor_plan_layout(self):
        url = reverse('floor-plan-update-layout', kwargs={'pk': self.floor_plan.id})
        data = {
            'tables': [
                {'id': self.table1.id, 'position_x': 150, 'position_y': 250, 'rotation': 45},
                {'id': self.table2.id, 'position_x': 350, 'position_y': 250, 'rotation': 135}
            ]
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify updates
        self.table1.refresh_from_db()
        self.table2.refresh_from_db()
        self.assertEqual(self.table1.position_x, 150)
        self.assertEqual(self.table2.rotation, 135)


class TableCategoryTests(BaseTestCase):
    """Test table category endpoints"""
    
    def test_list_categories(self):
        url = reverse('table-category-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_category_tables(self):
        url = reverse('category-tables', kwargs={'pk': self.category.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
    
    def test_category_stats(self):
        url = reverse('category-stats', kwargs={'pk': self.category.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['table_count'], 2)


class TableTests(BaseTestCase):
    """Test table endpoints"""
    
    def test_list_tables(self):
        url = reverse('table-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)
    
    def test_retrieve_table(self):
        url = reverse('table-detail', kwargs={'pk': self.table1.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], self.table1.name)
    
    def test_table_reservations(self):
        url = reverse('table-reservations', kwargs={'pk': self.table1.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
    
    def test_current_reservation(self):
        # Create a current reservation
        current_reservation = TableReservationFactory(
            table=self.table1,
            branch=self.branch,
            customer_name="Current Customer",
            reservation_time=timezone.now() - timedelta(minutes=30),  # 30 minutes ago
            duration=60,  # 1 hour
            status='seated'
        )
        
        url = reverse('table-current-reservation', kwargs={'pk': self.table1.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['customer_name'], 'Current Customer')
    
    def test_update_table_status(self):
        url = reverse('table-update-status', kwargs={'pk': self.table1.id})
        data = {'status': 'occupied'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.table1.refresh_from_db()
        self.assertEqual(self.table1.status, 'occupied')
    
    def test_assign_waiter(self):
        url = reverse('table-assign-waiter', kwargs={'pk': self.table1.id})
        data = {'waiter_id': self.waiter.id}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.table1.refresh_from_db()
        self.assertEqual(self.table1.waiter.id, self.waiter.id)
    
    def test_clear_waiter(self):
        # First assign a waiter
        self.table1.waiter = self.waiter
        self.table1.save()
        
        url = reverse('table-clear-waiter', kwargs={'pk': self.table1.id})
        response = self.client.post(url, {})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.table1.refresh_from_db()
        self.assertIsNone(self.table1.waiter)
    
    def test_combine_tables(self):
        url = reverse('table-combine', kwargs={'pk': self.table1.id})
        data = {'table_ids': [self.table2.id]}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.table1.refresh_from_db()
        self.table2.refresh_from_db()
        
        self.assertTrue(self.table2 in self.table1.combined_tables.all())
        self.assertEqual(self.table2.status, 'combined')
    
    def test_split_tables(self):
        # First combine tables
        self.table1.combined_tables.add(self.table2)
        self.table2.status = 'combined'
        self.table2.save()
        
        url = reverse('table-split', kwargs={'pk': self.table1.id})
        response = self.client.post(url, {})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.table1.refresh_from_db()
        self.table2.refresh_from_db()
        
        self.assertEqual(self.table1.combined_tables.count(), 0)
        self.assertEqual(self.table2.status, 'available')


class TableReservationTests(BaseTestCase):
    """Test table reservation endpoints"""
    
    def test_list_reservations(self):
        url = reverse('table-reservation-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_upcoming_reservations(self):
        # Create an upcoming reservation
        future_time = timezone.now() + timedelta(hours=2)
        TableReservationFactory(
            table=self.table2,
            branch=self.branch,
            customer_name="Upcoming Customer",
            reservation_time=future_time,
            status='confirmed'
        )
        
        url = reverse('reservation-upcoming')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['customer_name'], 'Upcoming Customer')
    
    def test_current_reservations(self):
        # Create a current reservation
        current_reservation = TableReservationFactory(
            table=self.table2,
            branch=self.branch,
            customer_name="Current Customer",
            reservation_time=timezone.now() - timedelta(minutes=30),  # 30 minutes ago
            duration=60,  # 1 hour
            status='seated'
        )
        
        url = reverse('reservation-current')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['customer_name'], 'Current Customer')
    
    def test_reservation_table_info(self):
        url = reverse('reservation-table-info', kwargs={'pk': self.reservation.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['table_name'], self.table1.name)
    
    def test_update_reservation_status(self):
        url = reverse('reservation-update-status', kwargs={'pk': self.reservation.id})
        data = {'status': 'seated'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.reservation.refresh_from_db()
        self.assertEqual(self.reservation.status, 'seated')
        
        # Verify table status was updated
        self.table1.refresh_from_db()
        self.assertEqual(self.table1.status, 'occupied')
