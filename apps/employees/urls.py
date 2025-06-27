from django.urls import path, include
from rest_framework.routers import DefaultRouter

from . import views

# Create a router and register our viewsets with it.
router = DefaultRouter()
router.register(r'departments', views.DepartmentViewSet, basename='department')
router.register(r'employees', views.EmployeeViewSet, basename='employee')
router.register(r'attendance', views.AttendanceViewSet)
router.register(r'leave-types', views.LeaveTypeViewSet)
router.register(r'leave-balances', views.LeaveBalanceViewSet)
router.register(r'leave-requests', views.LeaveRequestViewSet)
router.register(r'leave-policies', views.LeavePolicyViewSet)
router.register(r'leave-reports', views.LeaveReportViewSet, basename='leave-reports')

# The API URLs are now determined automatically by the router.
urlpatterns = [
    path('', include(router.urls)),
    
    # Additional endpoints that don't fit the ViewSet pattern
    path('employees/<int:pk>/direct-reports/', 
         views.EmployeeViewSet.as_view({'get': 'direct_reports'}), 
         name='employee-direct-reports'),
    path('employees/<int:pk>/addresses/', 
         views.EmployeeViewSet.as_view({'get': 'list', 'post': 'create'}), 
         name='employee-addresses'),
    path('employees/<int:pk>/reporting-line/', 
         views.EmployeeViewSet.as_view({'get': 'reporting_line'}), 
         name='employee-reporting-line'),
]

app_name = 'employees'
