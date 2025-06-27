from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    PayrollPeriodViewSet,
    PayrollItemViewSet,
    EmployeePayrollViewSet,
    CasualPaymentViewSet,
    WorkAssignmentViewSet,
    PayrollReportViewSet,
    DeductionCategoryViewSet
)

# Create router and register viewsets
router = DefaultRouter()
router.register(r'periods', PayrollPeriodViewSet, basename='payroll-period')
router.register(r'items', PayrollItemViewSet, basename='payroll-item')
router.register(r'employee-payrolls', EmployeePayrollViewSet, basename='employee-payroll')
router.register(r'work-assignments', WorkAssignmentViewSet, basename='work-assignment')
router.register(r'casual-payments', CasualPaymentViewSet, basename='casual-payment')
router.register(r'reports', PayrollReportViewSet, basename='payroll-report')
router.register(r'deduction-categories', DeductionCategoryViewSet, basename='deduction-category')

# Custom URLs for payroll period actions
period_actions = [
    path('periods/<int:pk>/calculate/', PayrollPeriodViewSet.as_view({'post': 'calculate_payroll'}),
         name='payroll-period-calculate'),
    path('periods/<int:pk>/close/', PayrollPeriodViewSet.as_view({'post': 'close_period'}),
         name='payroll-period-close'),
]

# Custom URLs for payroll item actions
item_actions = [
    path('items/bulk-update-tax-deductible/', PayrollItemViewSet.as_view({'post': 'bulk_update_tax_deductible'}),
         name='payroll-item-bulk-update'),
]

# Custom URLs for employee payroll actions
payroll_actions = [
    path('employee-payrolls/<int:pk>/calculate/', EmployeePayrollViewSet.as_view({'post': 'calculate'}),
         name='employee-payroll-calculate'),
    path('employee-payrolls/<int:pk>/mark-as-paid/', EmployeePayrollViewSet.as_view({'post': 'mark_as_paid'}),
         name='employee-payroll-mark-paid'),
    path('employee-payrolls/<int:pk>/cancel/', EmployeePayrollViewSet.as_view({'post': 'cancel'}),
         name='employee-payroll-cancel'),
    path('employee-payrolls/summary/', EmployeePayrollViewSet.as_view({'get': 'summary'}),
         name='employee-payroll-summary'),
]

# Custom URLs for casual payment actions
casual_payment_actions = [
    path('casual-payments/<int:pk>/approve/', CasualPaymentViewSet.as_view({'post': 'approve'}),
         name='casual-payment-approve'),
    path('casual-payments/<int:pk>/mark-as-paid/', CasualPaymentViewSet.as_view({'post': 'mark_as_paid'}),
         name='casual-payment-mark-paid'),
    path('casual-payments/<int:pk>/cancel/', CasualPaymentViewSet.as_view({'post': 'cancel'}),
         name='casual-payment-cancel'),
    path('casual-payments/summary/', CasualPaymentViewSet.as_view({'get': 'summary'}),
         name='casual-payment-summary'),
]

app_name = 'payroll'

urlpatterns = [
    # Include router URLs
    path('', include(router.urls)),
    
    # Include custom action URLs
    *period_actions,
    *item_actions,
    *payroll_actions,
    *casual_payment_actions,
]
