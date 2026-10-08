import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, datetime, timedelta
from decimal import Decimal
from django.db.models import Sum, Count, Avg
from ..models import Expense, Income, Budget


def get_user_expenses(user, start_date=None, end_date=None, category=None, search=None):
    """
    Returns user expenses scoped strictly to the authenticated user with optional filtering.
    """
    qs = Expense.objects.filter(user=user)
    if start_date:
        qs = qs.filter(date__gte=start_date)
    if end_date:
        qs = qs.filter(date__lte=end_date)
    if category and category != 'All':
        qs = qs.filter(category=category)
    if search:
        qs = qs.filter(description__icontains=search) | qs.filter(vendor__icontains=search) | qs.filter(category__icontains=search)
    return qs.order_by('-date', '-created_at')


def get_user_incomes(user, start_date=None, end_date=None, search=None):
    """
    Returns user incomes scoped strictly to the authenticated user with optional filtering.
    """
    qs = Income.objects.filter(user=user)
    if start_date:
        qs = qs.filter(date__gte=start_date)
    if end_date:
        qs = qs.filter(date__lte=end_date)
    if search:
        qs = qs.filter(source__icontains=search) | qs.filter(description__icontains=search)
    return qs.order_by('-date', '-created_at')


def get_total_spending(user, start_date=None, end_date=None) -> float:
    """Returns total spending by the user in the given date range."""
    qs = get_user_expenses(user, start_date=start_date, end_date=end_date)
    total = qs.aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
    return float(total)


def get_total_income(user, start_date=None, end_date=None) -> float:
    """Returns total income for the user in the given date range."""
    qs = get_user_incomes(user, start_date=start_date, end_date=end_date)
    total = qs.aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
    return float(total)


def get_monthly_spending(user, year=None) -> list:
    """Returns monthly spending broken down by month for a given year."""
    if not year:
        year = date.today().year

    expenses = Expense.objects.filter(user=user, date__year=year)
    if not expenses.exists():
        return []

    df = pd.DataFrame(list(expenses.values('amount', 'date')))
    df['amount'] = df['amount'].astype(float)
    df['date'] = pd.to_datetime(df['date'])
    df['month'] = df['date'].dt.strftime('%b')
    df['month_num'] = df['date'].dt.month

    monthly = df.groupby(['month_num', 'month'])['amount'].sum().reset_index()
    monthly = monthly.sort_values('month_num')
    return monthly[['month', 'amount']].to_dict(orient='records')


def get_category_spending(user, start_date=None, end_date=None) -> list:
    """Returns breakdown of spending by category."""
    qs = get_user_expenses(user, start_date=start_date, end_date=end_date)
    if not qs.exists():
        return []

    category_data = (
        qs.values('category')
        .annotate(total=Sum('amount'), count=Count('id'))
        .order_by('-total')
    )

    return [
        {
            'category': item['category'],
            'total': float(item['total']),
            'count': item['count']
        }
        for item in category_data
    ]


def get_previous_month_comparison(user) -> dict:
    """
    Computes spending for the current month vs. the previous month
    and the percentage change.
    """
    today = date.today()
    current_year = today.year
    current_month = today.month

    if current_month == 1:
        prev_month = 12
        prev_year = current_year - 1
    else:
        prev_month = current_month - 1
        prev_year = current_year

    current_month_total = float(
        Expense.objects.filter(user=user, date__year=current_year, date__month=current_month)
        .aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
    )

    prev_month_total = float(
        Expense.objects.filter(user=user, date__year=prev_year, date__month=prev_month)
        .aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
    )

    if prev_month_total > 0:
        pct_change = ((current_month_total - prev_month_total) / prev_month_total) * 100
    else:
        pct_change = 100.0 if current_month_total > 0 else 0.0

    return {
        'current_month_total': current_month_total,
        'prev_month_total': prev_month_total,
        'percentage_change': round(pct_change, 1),
        'is_increase': current_month_total > prev_month_total,
    }


def get_budget_status(user, month=None, year=None) -> dict:
    """
    Calculates monthly budget targets, actual spent, remaining, and category budgets.
    Supports both overall monthly budget and granular category budgets.
    """
    today = date.today()
    target_month = month or today.month
    target_year = year or today.year

    # Overall budget (category='')
    overall_budget_obj = Budget.objects.filter(user=user, month=target_month, year=target_year, category='').first()
    budget_limit = float(overall_budget_obj.amount) if overall_budget_obj else 0.0

    total_spent = float(
        Expense.objects.filter(user=user, date__year=target_year, date__month=target_month)
        .aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
    )

    remaining = max(0.0, budget_limit - total_spent) if budget_limit > 0 else 0.0
    used_percentage = round((total_spent / budget_limit) * 100, 1) if budget_limit > 0 else 0.0

    status_level = 'normal'
    if budget_limit > 0:
        if total_spent > budget_limit:
            status_level = 'danger'  # Exceeded
        elif used_percentage >= 80:
            status_level = 'warning'  # Near limit

    # Category-specific budgets
    cat_budgets = Budget.objects.filter(user=user, month=target_month, year=target_year).exclude(category='')
    category_budget_list = []

    for cb in cat_budgets:
        cat_spent = float(
            Expense.objects.filter(
                user=user,
                date__year=target_year,
                date__month=target_month,
                category=cb.category
            ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
        )
        cat_amount = float(cb.amount)
        cat_remaining = max(0.0, cat_amount - cat_spent)
        cat_pct = round((cat_spent / cat_amount) * 100, 1) if cat_amount > 0 else 0.0

        cat_status = 'normal'
        if cat_spent > cat_amount:
            cat_status = 'danger'
        elif cat_pct >= 80:
            cat_status = 'warning'

        category_budget_list.append({
            'category': cb.category,
            'budget_amount': cat_amount,
            'spent_amount': cat_spent,
            'remaining_amount': cat_remaining,
            'used_percentage': cat_pct,
            'status_level': cat_status,
        })

    return {
        'has_budget': budget_limit > 0,
        'budget_amount': budget_limit,
        'spent_amount': total_spent,
        'remaining_amount': remaining,
        'used_percentage': used_percentage,
        'status_level': status_level,
        'month': target_month,
        'year': target_year,
        'category_budgets': category_budget_list,
        'has_category_budgets': len(category_budget_list) > 0,
    }


def get_kpi_summary(user) -> dict:
    """
    Computes all high-level dashboard KPIs:
    - Total balance (Lifetime Income minus Lifetime Expenses)
    - Total Lifetime Spending
    - Total Lifetime Income
    - This Month's Income
    - This Month's Expenses
    - Previous Month's Spending
    - MoM percentage change
    - Savings rate this month
    - Top spending category
    """
    comparison = get_previous_month_comparison(user)
    total_lifetime_expenses = get_total_spending(user)
    total_lifetime_income = get_total_income(user)
    net_lifetime_balance = total_lifetime_income - total_lifetime_expenses

    today = date.today()
    this_month_income = float(
        Income.objects.filter(user=user, date__year=today.year, date__month=today.month)
        .aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
    )
    this_month_expenses = comparison['current_month_total']
    this_month_balance = this_month_income - this_month_expenses

    if this_month_income > 0:
        savings_rate = round(((this_month_income - this_month_expenses) / this_month_income) * 100, 1)
    else:
        savings_rate = 0.0

    # Top category this month
    top_cat_item = (
        Expense.objects.filter(user=user, date__year=today.year, date__month=today.month)
        .values('category')
        .annotate(total=Sum('amount'))
        .order_by('-total')
        .first()
    )
    top_category = top_cat_item['category'] if top_cat_item else 'None'
    top_category_amount = float(top_cat_item['total']) if top_cat_item else 0.0

    return {
        'net_balance': net_lifetime_balance,
        'this_month_balance': this_month_balance,
        'total_lifetime_income': total_lifetime_income,
        'this_month_income': this_month_income,
        'total_lifetime': total_lifetime_expenses,
        'this_month_total': this_month_expenses,
        'prev_month_total': comparison['prev_month_total'],
        'mom_percentage_change': comparison['percentage_change'],
        'mom_is_increase': comparison['is_increase'],
        'savings_rate': savings_rate,
        'top_category': top_category,
        'top_category_amount': top_category_amount,
    }


def get_financial_context_for_ai(user) -> dict:
    """
    Constructs a controlled, verified financial summary for Claude.
    Omits raw identifiers and account numbers to safeguard privacy.
    Includes incomes, expenses, categories, budget utilization, and largest transactions.
    """
    today = date.today()
    kpis = get_kpi_summary(user)
    budget = get_budget_status(user)
    categories = get_category_spending(user)
    monthly = get_monthly_spending(user, year=today.year)

    # Top 5 largest expenses ever
    largest_qs = Expense.objects.filter(user=user).order_by('-amount')[:5]
    largest_expenses = [
        {
            'date': exp.date.isoformat(),
            'category': exp.category,
            'amount': float(exp.amount),
            'vendor': exp.vendor or 'N/A'
        }
        for exp in largest_qs
    ]

    # Recent 5 transactions
    recent_qs = Expense.objects.filter(user=user).order_by('-date', '-created_at')[:5]
    recent_transactions = [
        {
            'date': exp.date.isoformat(),
            'category': exp.category,
            'amount': float(exp.amount),
            'vendor': exp.vendor or 'N/A'
        }
        for exp in recent_qs
    ]

    return {
        "report_date": today.isoformat(),
        "net_balance": kpis['net_balance'],
        "this_month_income": kpis['this_month_income'],
        "this_month_expenses": kpis['this_month_total'],
        "total_lifetime_spend": kpis['total_lifetime'],
        "month_over_month_change_pct": kpis['mom_percentage_change'],
        "top_spending_category": kpis['top_category'],
        "monthly_budget": budget['budget_amount'],
        "budget_used_percentage": budget['used_percentage'],
        "budget_status": budget['status_level'],
        "category_budgets": budget['category_budgets'],
        "categories_breakdown": categories[:6],
        "largest_expenses": largest_expenses,
        "monthly_spending_trend": monthly,
        "recent_transactions": recent_transactions
    }


# =========================================================================
# PLOTLY CHART GENERATION
# =========================================================================

def build_spending_trend_chart(user_expenses) -> str:
    """Builds an interactive Plotly spending trend chart."""
    if not user_expenses.exists():
        return "<div class='text-center py-12 text-slate-400'>No expense data available to generate trend chart.</div>"

    df = pd.DataFrame(list(user_expenses.values('amount', 'date')))
    df['date'] = pd.to_datetime(df['date'])
    df['amount'] = df['amount'].astype(float)

    daily = df.groupby(df['date'].dt.date)['amount'].sum().reset_index()
    daily = daily.sort_values('date')

    fig = px.area(
        daily,
        x='date',
        y='amount',
        labels={'date': 'Date', 'amount': 'Spent (₹)'},
        color_discrete_sequence=['#4f46e5'],
    )

    fig.update_layout(
        margin=dict(l=20, r=20, t=25, b=20),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(family='Inter, sans-serif', color='#64748b', size=12),
        hovermode='x unified',
        xaxis=dict(showgrid=True, gridcolor='#f1f5f9'),
        yaxis=dict(showgrid=True, gridcolor='#f1f5f9', zeroline=False),
        height=320,
    )

    return fig.to_html(full_html=False, include_plotlyjs=False, config={'displayModeBar': False})


def build_category_breakdown_chart(user_expenses) -> str:
    """Builds an interactive Plotly donut chart for category distribution."""
    if not user_expenses.exists():
        return "<div class='text-center py-12 text-slate-400'>No expense data available for category chart.</div>"

    df = pd.DataFrame(list(user_expenses.values('amount', 'category')))
    df['amount'] = df['amount'].astype(float)

    cat_totals = df.groupby('category')['amount'].sum().reset_index()
    cat_totals = cat_totals.sort_values('amount', ascending=False)

    colors = ['#4f46e5', '#3b82f6', '#06b6d4', '#10b981', '#f59e0b', '#ec4899', '#8b5cf6', '#94a3b8']

    fig = px.pie(
        cat_totals,
        names='category',
        values='amount',
        hole=0.55,
        color_discrete_sequence=colors
    )

    fig.update_traces(
        textposition='inside',
        textinfo='percent',
        hoverinfo='label+value+percent',
        marker=dict(line=dict(color='#ffffff', width=2))
    )

    fig.update_layout(
        margin=dict(l=10, r=10, t=10, b=10),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(family='Inter, sans-serif', color='#64748b', size=12),
        showlegend=True,
        legend=dict(orientation='h', yanchor='bottom', y=-0.2, xanchor='center', x=0.5),
        height=320,
    )

    return fig.to_html(full_html=False, include_plotlyjs=False, config={'displayModeBar': False})
