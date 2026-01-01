from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Expense
from .forms import ExpenseForm
from django.contrib.auth.forms import UserCreationForm
import pandas as pd
import plotly.express as px 
from plotly.offline import plot
from .forms import ExpenseForm
import pandas as pd
import plotly.express as px

# The main page that displays all expenses and future charts
@login_required
def dashboard(request):
    expenses = Expense.objects.filter(user=request.user).order_by('-date') 

    # For filtering
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    if start_date and end_date:
        expenses = expenses.filter(date__range=[start_date, end_date])
    

    expense_chart = get_expense_chart(expenses) 
    
    
    context = {
        'expenses': expenses,
        'form': ExpenseForm(),
        'current_user': request.user,
        'expense_chart': expense_chart, 
        'start_date': start_date, 
        'end_date': end_date,
    }
    return render(request, 'core_app/dashboard.html', context)


@login_required
def add_expense(request):
    if request.method == 'POST':
        form = ExpenseForm(request.POST)
        if form.is_valid():
            expense = form.save(commit=False) 
            expense.user = request.user 
            expense.save()
            return redirect('dashboard')
    
    return redirect('dashboard') 

@login_required
def delete_expense(request, expense_id):
    expense = get_object_or_404(Expense, pk=expense_id, user=request.user)
    
    if request.method == 'POST':
        expense.delete()
    
    return redirect('dashboard')

def signup(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('login') 
    else:
        form = UserCreationForm()

    context = {'form': form}
    return render(request, 'core_app/signup.html', context)

def get_expense_chart(user_expenses):

    if not user_expenses:
        return "<p>No expense data to generate a chart.</p>"

    df = pd.DataFrame(list(user_expenses.values('amount', 'date')))
    df['date'] = pd.to_datetime(df['date'])

    daily_spending = df.groupby(df['date'].dt.date)['amount'].sum().reset_index()
    daily_spending['amount'] = daily_spending['amount'].astype(float)

    fig = px.bar(
        daily_spending,
        x='date',
        y='amount',
        title='Daily Spending Overview',
        labels={'date': 'Date', 'amount': 'Total Spent (₹)'},
        template='plotly_white'
    )

    chart_div = fig.to_html(full_html=False, include_plotlyjs=True)
    return chart_div




    