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
    path('ops/customers/<int:customer_id>/save/', views.customer_save, name='customer_save_edit'),
    path('ops/customers/new/', views.ops_customer_form, name='ops_customer_new'),
    path('ops/customers/<int:customer_id>/edit/', views.ops_customer_form, name='ops_customer_edit'),
    path('ops/customers/<int:customer_id>/locations/save/', views.location_save, name='location_save'),
    path('ops/customers/<int:customer_id>/locations/<int:location_id>/save/', views.location_save, name='location_save_edit'),
    path('ops/locations/<int:location_id>/delete/', views.location_delete, name='location_delete'),
    path('ops/jobs/<int:job_id>/delete/', views.job_delete, name='job_delete'),
    path('ops/jobs/<int:job_id>/cancel/', views.job_cancel, name='job_cancel'),
    path('ops/customers/<int:customer_id>/delete/', views.customer_delete, name='customer_delete'),
    path('ops/customers/<int:customer_id>/set-active/', views.customer_set_active, name='customer_set_active'),
    path('ops/autoschedule/', views.ops_auto_schedule, name='ops_auto_schedule'),
    path('ops/import/', views.ops_import, name='ops_import'),
    path('ops/import/confirm/', views.ops_import_confirm, name='ops_import_confirm'),
    path('ops/import/template/', views.ops_download_template, name='ops_download_template'),

    # Admin
    path('admin/users/', views.admin_users, name='admin_users'),
    path('admin/users/new/', views.admin_user_form, name='admin_user_new'),
    path('admin/users/<int:user_id>/edit/', views.admin_user_form, name='admin_user_edit'),
    path('admin/smoketests/', views.admin_smoke_tests, name='admin_smoke_tests'),
    path('admin/processmining/', views.admin_process_mining, name='admin_process_mining'),
    path('admin/demo/', views.admin_demo, name='admin_demo'),
    path('admin/demo/reload/', views.admin_demo_reload, name='admin_demo_reload'),
    path('admin/demo/reload-jobs/', views.admin_demo_reload_jobs, name='admin_demo_reload_jobs'),
    path('admin/demo/reload-accounts/', views.admin_demo_reload_accounts, name='admin_demo_reload_accounts'),
    path('admin/demo/cleanup-orphan-jobs/', views.admin_demo_cleanup_orphan_jobs, name='admin_demo_cleanup_orphan_jobs'),

    # Customer portal
    path('customer/', views.customer_dashboard, name='customer_dashboard'),
    path('customer/request-test/', views.customer_request_test, name='customer_request_test'),
    path('customer/edit-profile/', views.customer_edit_profile, name='customer_edit_profile'),
    path('customer/locations/', views.customer_manage_locations, name='customer_manage_locations'),

    # Temporary seed endpoints
    path('seedusers/', views.seed_users, name='seed_users'),
    path('reseedcoords/', views.reseed_customer_coords, name='reseed_customer_coords'),
    path('seedhistory/', views.seed_history, name='seed_history'),
    path('reassignhistory/', views.reassign_history, name='reassign_history'),
    path('seedutilityfields/', views.seed_utility_fields, name='seed_utility_fields'),
    path('seedupcomingjobs/', views.seed_upcoming_jobs, name='seed_upcoming_jobs'),
    path('seedcustomerwebsites/', views.seed_customer_websites, name='seed_customer_websites'),
    path('geocodecustomers/', views.geocode_customers, name='geocode_customers'),
    path('seedcustomerportalusers/', views.seed_customer_portal_users, name='seed_customer_portal_users'),
]