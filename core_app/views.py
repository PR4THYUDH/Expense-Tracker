import csv
import json
from datetime import date
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login as auth_login
from django.http import HttpResponse, JsonResponse
from django.contrib import messages
from django.views.decorators.http import require_POST

from .models import Expense, Budget, DEFAULT_CATEGORIES
from .forms import ExpenseForm, BudgetForm, ReceiptUploadForm
from .services.analytics_service import (
    get_user_expenses,
    get_kpi_summary,
    get_budget_status,
    build_spending_trend_chart,
    build_category_breakdown_chart,
    get_financial_context_for_ai,
)
from .services.ai_service import ClaudeAIService


def landing_page(request):
    """Public landing page explaining features, AI integration, and privacy."""
    if request.user.is_authenticated:
        return redirect('dashboard')
    ai_service = ClaudeAIService()
    return render(request, 'core_app/landing.html', {
        'ai_ready': ai_service.is_configured()
    })


def privacy_policy(request):
    """Detailed privacy and security commitment page."""
    return render(request, 'core_app/privacy.html')


@login_required
def dashboard(request):
    """
    Main user dashboard with top KPIs, Plotly trend and category charts,
    budget status, filters, and expense listing.
    """
    start_date = request.GET.get('start_date') or ''
    end_date = request.GET.get('end_date') or ''
    category = request.GET.get('category') or ''
    search = request.GET.get('search') or ''

    # Filtered expenses for table and visualization
    user_expenses = get_user_expenses(
        request.user,
        start_date=start_date or None,
        end_date=end_date or None,
        category=category or None,
        search=search or None,
    )

    # Top KPI Metrics (unfiltered / month-over-month)
    kpis = get_kpi_summary(request.user)

    # Budget Status
    today = date.today()
    budget_info = get_budget_status(request.user, month=today.month, year=today.year)

    # Plotly Charts
    spending_trend_chart = build_spending_trend_chart(user_expenses)
    category_chart = build_category_breakdown_chart(user_expenses)

    # Forms
    expense_form = ExpenseForm()
    budget_form = BudgetForm(initial={'month': today.month, 'year': today.year})
    receipt_form = ReceiptUploadForm()

    ai_service = ClaudeAIService()

    context = {
        'expenses': user_expenses,
        'kpis': kpis,
        'budget_info': budget_info,
        'spending_trend_chart': spending_trend_chart,
        'category_chart': category_chart,
        'expense_form': expense_form,
        'budget_form': budget_form,
        'receipt_form': receipt_form,
        'start_date': start_date,
        'end_date': end_date,
        'selected_category': category,
        'search_query': search,
        'all_categories': DEFAULT_CATEGORIES,
        'ai_configured': ai_service.is_configured(),
        'current_year': today.year,
        'current_month': today.strftime('%B'),
    }
    return render(request, 'core_app/dashboard.html', context)


@login_required
@require_POST
def add_expense(request):
    """Add a new expense record scoped strictly to the authenticated user."""
    form = ExpenseForm(request.POST)
    if form.is_valid():
        expense = form.save(commit=False)
        expense.user = request.user
        expense.save()
        messages.success(request, f"Expense of ₹{expense.amount} in {expense.category} added successfully.")
    else:
        error_msg = "; ".join([f"{k}: {', '.join(v)}" for k, v in form.errors.items()])
        messages.error(request, f"Failed to add expense: {error_msg}")
    return redirect('dashboard')


@login_required
def edit_expense(request, expense_id):
    """Edit an existing expense record. Scoped strictly to the logged-in user."""
    expense = get_object_or_404(Expense, pk=expense_id, user=request.user)

    if request.method == 'POST':
        form = ExpenseForm(request.POST, instance=expense)
        if form.is_valid():
            form.save()
            messages.success(request, "Expense updated successfully.")
            return redirect('dashboard')
        else:
            messages.error(request, "Please correct the errors in the form.")
    else:
        form = ExpenseForm(instance=expense)

    return render(request, 'core_app/edit_expense.html', {
        'form': form,
        'expense': expense
    })


@login_required
@require_POST
def delete_expense(request, expense_id):
    """Delete an expense record. Scoped strictly to the logged-in user."""
    expense = get_object_or_404(Expense, pk=expense_id, user=request.user)
    amount = expense.amount
    expense.delete()
    messages.success(request, f"Expense of ₹{amount} was deleted.")
    return redirect('dashboard')


@login_required
@require_POST
def set_budget(request):
    """Create or update monthly budget for the user."""
    form = BudgetForm(request.POST)
    if form.is_valid():
        month = int(form.cleaned_data['month'])
        year = int(form.cleaned_data['year'])
        amount = form.cleaned_data['amount']

        Budget.objects.update_or_create(
            user=request.user,
            month=month,
            year=year,
            defaults={'amount': amount}
        )
        messages.success(request, f"Budget for {month}/{year} updated to ₹{amount}.")
    else:
        messages.error(request, "Invalid budget values. Please provide a positive amount.")
    return redirect('dashboard')


@login_required
def export_csv(request):
    """
    Export authenticated user's expenses to CSV.
    Enforces strict user scoping and respects active dashboard filters.
    """
    start_date = request.GET.get('start_date') or None
    end_date = request.GET.get('end_date') or None
    category = request.GET.get('category') or None
    search = request.GET.get('search') or None

    expenses = get_user_expenses(
        request.user,
        start_date=start_date,
        end_date=end_date,
        category=category,
        search=search
    )

    response = HttpResponse(content_type='text/csv')
    timestamp = date.today().isoformat()
    response['Content-Disposition'] = f'attachment; filename="expenses_{request.user.username}_{timestamp}.csv"'

    writer = csv.writer(response)
    writer.writerow(['Date', 'Category', 'Vendor', 'Description', 'Amount (INR)'])

    for exp in expenses:
        writer.writerow([
            exp.date.isoformat(),
            exp.category,
            exp.vendor or '',
            exp.description or '',
            f"{exp.amount:.2f}"
        ])

    return response


# =========================================================================
# CLAUDE AI ENDPOINTS
# =========================================================================

@login_required
@require_POST
def scan_receipt_api(request):
    """
    Receives an uploaded receipt image, sends it to Claude Vision,
    and returns validated structured data for user review BEFORE saving.
    """
    if 'receipt_image' not in request.FILES:
        return JsonResponse({'success': False, 'error': 'No receipt image uploaded.'}, status=400)

    form = ReceiptUploadForm(request.POST, request.FILES)
    if not form.is_valid():
        return JsonResponse({'success': False, 'error': form.errors.as_text()}, status=400)

    uploaded_file = form.cleaned_data['receipt_image']
    image_bytes = uploaded_file.read()
    content_type = uploaded_file.content_type

    ai_service = ClaudeAIService()
    result = ai_service.scan_receipt(image_bytes=image_bytes, content_type=content_type)

    return JsonResponse(result, status=200 if result.get('success') else 400)


@login_required
def get_ai_insights_api(request):
    """
    Aggregates user's verified financial stats and asks Claude for
    objective spending patterns and savings commentary.
    """
    context_data = get_financial_context_for_ai(request.user)
    ai_service = ClaudeAIService()
    result = ai_service.generate_financial_insights(context_data)
    return JsonResponse(result, status=200 if result.get('success') else 400)


@login_required
@require_POST
def ask_ai_api(request):
    """
    Answers a natural language financial question using pre-computed,
    verified backend data. Never runs arbitrary SQL.
    """
    try:
        body = json.loads(request.body)
        question = body.get('question', '').strip()
    except (json.JSONDecodeError, AttributeError):
        question = request.POST.get('question', '').strip()

    if not question:
        return JsonResponse({'success': False, 'error': 'Please provide a question.'}, status=400)

    context_data = get_financial_context_for_ai(request.user)
    ai_service = ClaudeAIService()
    result = ai_service.answer_financial_query(question, context_data)
    return JsonResponse(result, status=200 if result.get('success') else 400)


# =========================================================================
# AUTHENTICATION
# =========================================================================

def signup(request):
    """User registration view with auto-login on success."""
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            auth_login(request, user)
            messages.success(request, f"Welcome to FinTrack, {user.username}! Your account has been created.")
            return redirect('dashboard')
    else:
        form = UserCreationForm()

    return render(request, 'core_app/signup.html', {'form': form})