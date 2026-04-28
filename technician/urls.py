from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.tech_login, name='tech_login'),
    path('customer/login/', views.customer_login, name='customer_login'),

    path('logout/', views.tech_logout, name='tech_logout'),

    # Technician
    path('dashboard/', views.tech_dashboard, name='tech_dashboard'),
    path('job/<int:job_id>/', views.tech_job_detail, name='tech_job_detail'),

    # Operations
    path('ops/', views.ops_dashboard, name='ops_dashboard'),
    path('ops/job/new/', views.ops_job_form, name='ops_job_new'),
    path('ops/job/<int:job_id>/edit/', views.ops_job_form, name='ops_job_edit'),
    path('ops/customers/save/', views.customer_save, name='customer_save'),
    path('ops/customers/<int:customer_id>/save/', views.customer_save, name='customer_edit'),

    # Admin
    path('admin/users/', views.admin_users, name='admin_users'),
    path('admin/users/new/', views.admin_user_form, name='admin_user_new'),
    path('admin/users/<int:user_id>/edit/', views.admin_user_form, name='admin_user_edit'),

    # Customer
    path('customer/', views.customer_dashboard, name='customer_dashboard'),
]