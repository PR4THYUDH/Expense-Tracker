from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    
    path('add_expense/', views.add_expense, name='add_expense'),
    
    path('delete_expense/<int:expense_id>/', views.delete_expense, name='delete_expense'),

    path('signup/', views.signup, name='signup')
]