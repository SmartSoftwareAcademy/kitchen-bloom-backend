from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    ReportViewSet,
    ReportScheduleViewSet,
    ReportExecutionLogViewSet
)
from .viewsets import (
    StockReportViewSet,
    SalesReportViewSet,
    FinancialReportViewSet,
    DashboardReportViewSet,
)

router = DefaultRouter()
router.register(r'reports', ReportViewSet, basename='report')
router.register(r'report-schedules', ReportScheduleViewSet, basename='reportschedule')
router.register(r'report-executions', ReportExecutionLogViewSet, basename='reportexecution')
router.register(r'stock', StockReportViewSet, basename='stock-report')
router.register(r'sales', SalesReportViewSet, basename='sales-report')
router.register(r'financial', FinancialReportViewSet, basename='financial-report')
router.register(r'dashboard', DashboardReportViewSet, basename='dashboard-report')

app_name = 'reporting'

urlpatterns = [
    path('', include(router.urls)),
]
