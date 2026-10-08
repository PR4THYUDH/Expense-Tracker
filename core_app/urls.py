from django.urls import path
from . import views

urlpatterns = [
    # Public pages
    path('', views.landing_page, name='landing'),
    path('privacy/', views.privacy_policy, name='privacy'),
    path('signup/', views.signup, name='signup'),

    # Authenticated Dashboard & CRUD
    path('dashboard/', views.dashboard, name='dashboard'),
    path('add_expense/', views.add_expense, name='add_expense'),
    path('edit_expense/<int:expense_id>/', views.edit_expense, name='edit_expense'),
    path('delete_expense/<int:expense_id>/', views.delete_expense, name='delete_expense'),

    # Income CRUD
    path('add_income/', views.add_income, name='add_income'),
    path('delete_income/<int:income_id>/', views.delete_income, name='delete_income'),

    # Budgeting & Export
    path('set_budget/', views.set_budget, name='set_budget'),
    path('export_csv/', views.export_csv, name='export_csv'),

    # Claude AI Endpoints
    path('api/scan_receipt/', views.scan_receipt_api, name='scan_receipt_api'),
    path('api/ai_insights/', views.get_ai_insights_api, name='ai_insights_api'),
    path('api/ask_ai/', views.ask_ai_api, name='ask_ai_api'),
]