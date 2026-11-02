from django.contrib import admin
from django.contrib.auth import views as auth
from django.urls import path
from console import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('health/', views.health),
    path('login/', auth.LoginView.as_view(template_name='login.html'), name='login'),
    path('logout/', auth.LogoutView.as_view(), name='logout'),
    path('admin/', admin.site.urls),
    path('plans/new/', views.edit_plan, name='plan-new'),
    path('plans/<int:pk>/', views.plan_detail, name='plan-detail'),
    path('plans/<int:pk>/edit/', views.edit_plan, name='plan-edit'),
    path('plans/<int:pk>/delete/', views.delete_plan, name='plan-delete'),
    path('plans/<int:pk>/action/', views.plan_action, name='plan-action'),
]
