from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'stations', views.KDSStationViewSet, basename='kds-station')
router.register(r'items', views.KDSItemViewSet, basename='kds-item')

urlpatterns = [
    path('', include(router.urls)),
    
    # Additional endpoints
    path('stations/<int:pk>/items/', views.KDSStationViewSet.as_view({'get': 'items'}), name='station-items'),
    path('items/active/', views.KDSItemViewSet.as_view({'get': 'active'}), name='kdsitem-active'),
    path('items/completed/', views.KDSItemViewSet.as_view({'get': 'completed'}), name='kdsitem-completed'),
    path('items/<int:pk>/update-status/', views.KDSItemViewSet.as_view({'post': 'update_status'}), name='kdsitem-update-status'),
]

app_name = 'kds'
