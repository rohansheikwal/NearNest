from django.urls import path
from . import views

app_name = 'bookings'

urlpatterns = [
    path('request/<int:service_pk>/', views.request_service, name='request_service'),
    path('api/availability/<int:service_pk>/', views.service_availability_api, name='service_availability_api'),
    path('my-requests/', views.my_requests, name='my_requests'),
    path('request/<int:pk>/detail/', views.request_detail, name='request_detail'),
    path('request/<int:pk>/cancel/', views.cancel_request, name='cancel_request'),
    path('saved/', views.saved_services, name='saved_services'),
    path('saved/toggle/<int:service_pk>/', views.toggle_save_service, name='toggle_save'),
    path('saved/remove/<int:pk>/', views.remove_saved_service, name='remove_saved'),
]
