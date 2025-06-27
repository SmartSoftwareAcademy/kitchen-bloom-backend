from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    FloorPlanViewSet, 
    TableCategoryViewSet, 
    TableViewSet, 
    TableReservationViewSet
)

# Create router and register viewsets
router = DefaultRouter()
router.register(r'floor-plans', FloorPlanViewSet, basename='floor-plan')
router.register(r'table-categories', TableCategoryViewSet, basename='table-category')
router.register(r'tables', TableViewSet, basename='table')
router.register(r'table-reservations', TableReservationViewSet, basename='table-reservation')

# URL patterns
urlpatterns = [
    # API endpoints
    path('', include(router.urls)),
    
    # Floor plan endpoints
    path('floor-plans/<int:pk>/tables/', FloorPlanViewSet.as_view({'get': 'tables'}), name='floor-plan-tables'),
    path('floor-plans/<int:pk>/update-layout/', FloorPlanViewSet.as_view({'post': 'update_layout'}), name='floor-plan-update-layout'),
    
    # Table category endpoints
    path('table-categories/<int:pk>/tables/', TableCategoryViewSet.as_view({'get': 'tables'}), name='category-tables'),
    path('table-categories/<int:pk>/stats/', TableCategoryViewSet.as_view({'get': 'stats'}), name='category-stats'),
    
    # Table endpoints
    path('tables/<int:pk>/reservations/', TableViewSet.as_view({'get': 'reservations'}), name='table-reservations'),
    path('tables/<int:pk>/current-reservation/', TableViewSet.as_view({'get': 'current_reservation'}), name='table-current-reservation'),
    path('tables/<int:pk>/update-status/', TableViewSet.as_view({'post': 'update_status'}), name='table-update-status'),
    path('tables/<int:pk>/assign-waiter/', TableViewSet.as_view({'post': 'assign_waiter'}), name='table-assign-waiter'),
    path('tables/<int:pk>/clear-waiter/', TableViewSet.as_view({'post': 'clear_waiter'}), name='table-clear-waiter'),
    path('tables/<int:pk>/combine/', TableViewSet.as_view({'post': 'combine_tables'}), name='table-combine'),
    path('tables/<int:pk>/split/', TableViewSet.as_view({'post': 'split_tables'}), name='table-split'),
    
    # Table reservation endpoints
    path('table-reservations/upcoming/', TableReservationViewSet.as_view({'get': 'upcoming'}), name='reservation-upcoming'),
    path('table-reservations/current/', TableReservationViewSet.as_view({'get': 'current'}), name='reservation-current'),
    path('table-reservations/<int:pk>/table-info/', TableReservationViewSet.as_view({'get': 'table_info'}), name='reservation-table-info'),
    path('table-reservations/<int:pk>/update-status/', TableReservationViewSet.as_view({'post': 'update_status'}), name='reservation-update-status')
]
