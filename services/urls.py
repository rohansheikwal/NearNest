from django.urls import path
from . import views

app_name = 'services'

urlpatterns = [
    # Public
    path('', views.service_list, name='service_list'),
    path('<int:pk>/', views.service_detail, name='service_detail'),
    path('category/<slug:slug>/', views.category_view, name='category'),
    # Provider dashboard
    path('provider/dashboard/', views.provider_dashboard, name='provider_dashboard'),
    path('provider/create/', views.service_create, name='service_create'),
    path('provider/edit/<int:pk>/', views.service_edit, name='service_edit'),
    path('provider/delete/<int:pk>/', views.service_delete, name='service_delete'),
    path('provider/toggle/<int:pk>/', views.toggle_service_active, name='toggle_active'),
    path('provider/requests/', views.provider_requests, name='provider_requests'),
    path('provider/requests/<int:request_id>/update/', views.update_request_status, name='update_request_status'),
    path('provider/reviews/', views.provider_reviews, name='provider_reviews'),
]
