from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.tech_login, name='tech_login'),
    path('logout/', views.tech_logout, name='tech_logout'),
    path('dashboard/', views.tech_dashboard, name='tech_dashboard'),
    path('job/<int:job_id>/', views.tech_job_detail, name='tech_job_detail'),
]
