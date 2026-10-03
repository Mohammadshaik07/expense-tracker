from django.urls import path
from . import views

urlpatterns = [
    # Auth
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # Dashboard
    path('dashboard/', views.dashboard, name='dashboard'),

    # Category CRUD
    path('categories/', views.category_list, name='category_list'),
    path('categories/create/', views.category_create, name='category_create'),
    path('categories/<int:pk>/edit/', views.category_edit, name='category_edit'),
    path('categories/<int:pk>/delete/', views.category_delete, name='category_delete'),

    # Budget Management
    path('budgets/', views.budget_list, name='budget_list'),
    path('budgets/create/', views.budget_create, name='budget_create'),
    path('budgets/<int:pk>/edit/', views.budget_edit, name='budget_edit'),
    path('budgets/<int:pk>/delete/', views.budget_delete, name='budget_delete'),

    # Expense CRUD & CSV Tools
    path('expenses/', views.expense_list, name='expense_list'),
    path('expenses/create/', views.expense_create, name='expense_create'),
    path('expenses/export/csv/', views.export_expenses_csv, name='export_expenses_csv'),
    path('expenses/import/csv/', views.import_expenses_csv, name='import_expenses_csv'),
    path('expenses/template/csv/', views.download_csv_template, name='download_csv_template'),
    path('expenses/<int:pk>/edit/', views.expense_edit, name='expense_edit'),
    path('expenses/<int:pk>/delete/', views.expense_delete, name='expense_delete'),

    # Income Management (Cash Flow)
    path('income/', views.income_list, name='income_list'),
    path('income/create/', views.income_create, name='income_create'),
    path('income/<int:pk>/edit/', views.income_edit, name='income_edit'),
    path('income/<int:pk>/delete/', views.income_delete, name='income_delete'),

    # Recurring Subscriptions & Fixed Bills
    path('subscriptions/', views.subscription_list, name='subscription_list'),
    path('subscriptions/create/', views.subscription_create, name='subscription_create'),
    path('subscriptions/<int:pk>/edit/', views.subscription_edit, name='subscription_edit'),
    path('subscriptions/<int:pk>/delete/', views.subscription_delete, name='subscription_delete'),
    path('subscriptions/<int:pk>/pay/', views.subscription_mark_paid, name='subscription_mark_paid'),

    # Financial Goals Tracker
    path('goals/', views.goal_list, name='goal_list'),
    path('goals/create/', views.goal_create, name='goal_create'),
    path('goals/<int:pk>/edit/', views.goal_edit, name='goal_edit'),
    path('goals/<int:pk>/delete/', views.goal_delete, name='goal_delete'),
    path('goals/<int:pk>/contribute/', views.goal_contribute, name='goal_contribute'),

    # Financial Analytics Hub
    path('analytics/', views.analytics_view, name='analytics_view'),
    path('analytics/hub/', views.analytics_view, name='analytics'),

    # User Settings
    path('settings/currency/', views.currency_settings, name='currency_settings'),
]

