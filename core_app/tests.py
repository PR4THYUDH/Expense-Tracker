import io
import json
from decimal import Decimal
from datetime import date, timedelta
from unittest.mock import patch, MagicMock

import pytest
from django.urls import reverse
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile

from core_app.models import Expense, Income, Budget
from core_app.services.analytics_service import (
    get_total_spending,
    get_monthly_spending,
    get_category_spending,
    get_previous_month_comparison,
    get_budget_status,
    get_financial_context_for_ai,
)
from core_app.services.ai_service import ClaudeAIService


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def user_a(db):
    return User.objects.create_user(username='alice', password='Password123!', email='alice@example.com')


@pytest.fixture
def user_b(db):
    return User.objects.create_user(username='bob', password='Password123!', email='bob@example.com')


@pytest.fixture
def client_a(client, user_a):
    client.login(username='alice', password='Password123!')
    return client


@pytest.fixture
def client_b(client, user_b):
    client.login(username='bob', password='Password123!')
    return client


@pytest.fixture
def expense_a(user_a):
    return Expense.objects.create(
        user=user_a,
        amount=Decimal('1500.50'),
        category='Food & Dining',
        vendor='Cafe Coffee Day',
        date=date.today(),
        description='Coffee and snacks'
    )


@pytest.fixture
def expense_b(user_b):
    return Expense.objects.create(
        user=user_b,
        amount=Decimal('4200.00'),
        category='Shopping',
        vendor='Zara',
        date=date.today(),
        description='Clothing purchase'
    )


# =============================================================================
# 1. AUTHENTICATION TESTS
# =============================================================================

@pytest.mark.django_db
def test_user_registration(client):
    response = client.post(reverse('signup'), {
        'username': 'newuser',
        'password1': 'ComplexPassword99!',
        'password2': 'ComplexPassword99!',
    })
    assert response.status_code == 302
    assert User.objects.filter(username='newuser').exists()


@pytest.mark.django_db
def test_login_and_logout(client, user_a):
    # Login
    login_resp = client.post(reverse('login'), {
        'username': 'alice',
        'password': 'Password123!'
    })
    assert login_resp.status_code == 302

    # Logout
    logout_resp = client.post(reverse('logout'))
    assert logout_resp.status_code in (200, 302)


# =============================================================================
# 2. SECURITY & USER ISOLATION TESTS
# =============================================================================

@pytest.mark.django_db
def test_unauthenticated_user_redirected(client):
    protected_urls = [
        reverse('dashboard'),
        reverse('add_expense'),
        reverse('set_budget'),
        reverse('export_csv'),
        reverse('ai_insights_api'),
        reverse('ask_ai_api'),
    ]
    for url in protected_urls:
        resp = client.get(url)
        assert resp.status_code == 302
        assert '/login/' in resp.url or '/accounts/login/' in resp.url


@pytest.mark.django_db
def test_user_a_cannot_view_user_b_expense_on_dashboard(client_a, expense_a, expense_b):
    response = client_a.get(reverse('dashboard'))
    assert response.status_code == 200
    content = response.content.decode()
    assert 'Cafe Coffee Day' in content
    assert 'Zara' not in content
    assert '4200' not in content


@pytest.mark.django_db
def test_user_a_cannot_edit_user_b_expense(client_a, expense_b):
    url = reverse('edit_expense', kwargs={'expense_id': expense_b.id})
    resp = client_a.get(url)
    assert resp.status_code == 404

    post_resp = client_a.post(url, {
        'amount': '10.00',
        'category': 'Other',
        'date': str(date.today()),
    })
    assert post_resp.status_code == 404
    expense_b.refresh_from_db()
    assert expense_b.amount == Decimal('4200.00')


@pytest.mark.django_db
def test_user_a_cannot_delete_user_b_expense(client_a, expense_b):
    url = reverse('delete_expense', kwargs={'expense_id': expense_b.id})
    resp = client_a.post(url)
    assert resp.status_code == 404
    assert Expense.objects.filter(id=expense_b.id).exists()


@pytest.mark.django_db
def test_user_a_cannot_export_user_b_data_in_csv(client_a, expense_a, expense_b):
    resp = client_a.get(reverse('export_csv'))
    assert resp.status_code == 200
    content = resp.content.decode()
    assert 'Cafe Coffee Day' in content
    assert 'Zara' not in content
    assert '4200.00' not in content


# =============================================================================
# 3. EXPENSE CRUD & VALIDATION TESTS
# =============================================================================

@pytest.mark.django_db
def test_create_expense_valid(client_a, user_a):
    resp = client_a.post(reverse('add_expense'), {
        'amount': '350.75',
        'category': 'Groceries',
        'vendor': 'Blinkit',
        'date': str(date.today()),
        'description': 'Milk and bread'
    })
    assert resp.status_code == 302
    exp = Expense.objects.filter(user=user_a, vendor='Blinkit').first()
    assert exp is not None
    assert exp.amount == Decimal('350.75')
    assert exp.category == 'Groceries'


@pytest.mark.django_db
def test_create_expense_invalid_negative_amount(client_a, user_a):
    initial_count = Expense.objects.filter(user=user_a).count()
    resp = client_a.post(reverse('add_expense'), {
        'amount': '-100.00',
        'category': 'Shopping',
        'date': str(date.today()),
    })
    assert resp.status_code == 302
    assert Expense.objects.filter(user=user_a).count() == initial_count


@pytest.mark.django_db
def test_update_expense_valid(client_a, expense_a):
    url = reverse('edit_expense', kwargs={'expense_id': expense_a.id})
    resp = client_a.post(url, {
        'amount': '1800.00',
        'category': 'Food & Dining',
        'vendor': 'Cafe Coffee Day Special',
        'date': str(expense_a.date),
        'description': 'Updated description'
    })
    assert resp.status_code == 302
    expense_a.refresh_from_db()
    assert expense_a.amount == Decimal('1800.00')
    assert expense_a.vendor == 'Cafe Coffee Day Special'


@pytest.mark.django_db
def test_delete_own_expense(client_a, expense_a):
    url = reverse('delete_expense', kwargs={'expense_id': expense_a.id})
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert not Expense.objects.filter(id=expense_a.id).exists()


@pytest.mark.django_db
def test_filter_and_search_expenses(client_a, user_a):
    Expense.objects.create(user=user_a, amount=Decimal('100'), category='Groceries', vendor='Store A', date=date(2026, 1, 10))
    Expense.objects.create(user=user_a, amount=Decimal('200'), category='Travel', vendor='Airline B', date=date(2026, 2, 15))

    # Filter by category
    resp = client_a.get(reverse('dashboard') + '?category=Travel')
    assert resp.status_code == 200
    assert 'Airline B' in resp.content.decode()
    assert 'Store A' not in resp.content.decode()

    # Search keyword
    resp_search = client_a.get(reverse('dashboard') + '?search=Store')
    assert resp_search.status_code == 200
    assert 'Store A' in resp_search.content.decode()
    assert 'Airline B' not in resp_search.content.decode()


# =============================================================================
# 4. ANALYTICS & BUDGETING TESTS
# =============================================================================

@pytest.mark.django_db
def test_analytics_calculations(user_a):
    today = date.today()
    Expense.objects.create(user=user_a, amount=Decimal('1000.00'), category='Groceries', date=today)
    Expense.objects.create(user=user_a, amount=Decimal('500.00'), category='Food & Dining', date=today)

    total = get_total_spending(user_a)
    assert total == 1500.0

    cats = get_category_spending(user_a)
    assert len(cats) == 2
    assert cats[0]['category'] == 'Groceries'
    assert cats[0]['total'] == 1000.0


@pytest.mark.django_db
def test_budget_calculations_and_warnings(user_a):
    today = date.today()
    Budget.objects.create(user=user_a, month=today.month, year=today.year, amount=Decimal('10000.00'))

    # Under budget (normal)
    Expense.objects.create(user=user_a, amount=Decimal('2000.00'), category='Bills & Services', date=today)
    status = get_budget_status(user_a, month=today.month, year=today.year)
    assert status['has_budget'] is True
    assert status['spent_amount'] == 2000.0
    assert status['remaining_amount'] == 8000.0
    assert status['used_percentage'] == 20.0
    assert status['status_level'] == 'normal'

    # Exceeding 80% (warning)
    Expense.objects.create(user=user_a, amount=Decimal('6500.00'), category='Shopping', date=today)
    status_warning = get_budget_status(user_a, month=today.month, year=today.year)
    assert status_warning['used_percentage'] == 85.0
    assert status_warning['status_level'] == 'warning'

    # Over budget (danger)
    Expense.objects.create(user=user_a, amount=Decimal('2000.00'), category='Shopping', date=today)
    status_danger = get_budget_status(user_a, month=today.month, year=today.year)
    assert status_danger['used_percentage'] == 105.0
    assert status_danger['status_level'] == 'danger'


@pytest.mark.django_db
def test_set_budget_post_action(client_a, user_a):
    today = date.today()
    resp = client_a.post(reverse('set_budget'), {
        'month': today.month,
        'year': today.year,
        'amount': '25000.00'
    })
    assert resp.status_code == 302
    b = Budget.objects.filter(user=user_a, month=today.month, year=today.year).first()
    assert b is not None
    assert b.amount == Decimal('25000.00')


# =============================================================================
# 5. CLAUDE AI SERVICE & API ENDPOINT TESTS
# =============================================================================

def test_ai_service_unconfigured():
    service = ClaudeAIService(api_key="")
    assert not service.is_configured()

    res_receipt = service.scan_receipt(b"fake_image_bytes", "image/jpeg")
    assert res_receipt['success'] is False
    assert res_receipt.get('needs_api_key') is True
    assert "AI features require Anthropic API configuration" in res_receipt['error']

    res_insights = service.generate_financial_insights({"total": 100})
    assert res_insights['success'] is False
    assert res_insights.get('needs_api_key') is True

    res_query = service.answer_financial_query("How much did I spend?", {"total": 100})
    assert res_query['success'] is False
    assert res_query.get('needs_api_key') is True


@pytest.mark.django_db
def test_ai_service_mocked_receipt_scan():
    service = ClaudeAIService(api_key="sk-ant-testkey1234567890")

    mock_json_response = json.dumps({
        "vendor": "SuperMart Express",
        "date": "2026-03-01",
        "total": 1250.75,
        "tax": 62.50,
        "currency": "INR",
        "category": "Groceries",
        "items": [
            {"name": "Olive Oil", "price": 450.00},
            {"name": "Basmati Rice", "price": 800.75}
        ]
    })

    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text=mock_json_response)]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_msg

    with patch.object(service, 'get_client', return_value=mock_client):
        result = service.scan_receipt(b"dummy_image_data", "image/jpeg")
        assert result['success'] is True
        data = result['data']
        assert data['vendor'] == "SuperMart Express"
        assert data['total'] == 1250.75
        assert data['category'] == "Groceries"
        assert len(data['items']) == 2


@pytest.mark.django_db
def test_ai_service_mocked_insights():
    service = ClaudeAIService(api_key="sk-ant-testkey1234567890")

    mock_insights = [
        "Groceries accounted for 65% of your total expenditures this month.",
        "Your spending is currently within the ₹10,000 threshold.",
        "Consider reviewing subscription charges before month-end."
    ]

    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text=json.dumps(mock_insights))]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_msg

    with patch.object(service, 'get_client', return_value=mock_client):
        result = service.generate_financial_insights({"total": 5000})
        assert result['success'] is True
        assert len(result['insights']) == 3
        assert "Groceries" in result['insights'][0]


@pytest.mark.django_db
def test_ai_service_mocked_ask_ai_query():
    service = ClaudeAIService(api_key="sk-ant-testkey1234567890")

    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text="Your top expense this month was ₹4,200 on Shopping.")]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_msg

    with patch.object(service, 'get_client', return_value=mock_client):
        result = service.answer_financial_query("What was my highest expense?", {"top_category": "Shopping"})
        assert result['success'] is True
        assert "₹4,200" in result['answer']


@pytest.mark.django_db
def test_scan_receipt_api_endpoint_with_mock(client_a):
    test_image = SimpleUploadedFile("test_receipt.jpg", b"fake_jpeg_content", content_type="image/jpeg")

    with patch('core_app.views.ClaudeAIService') as MockService:
        instance = MockService.return_value
        instance.scan_receipt.return_value = {
            'success': True,
            'data': {
                'vendor': 'Organic Farm',
                'date': '2026-03-02',
                'total': 890.0,
                'category': 'Groceries',
                'items': []
            }
        }

        resp = client_a.post(reverse('scan_receipt_api'), {'receipt_image': test_image})
        assert resp.status_code == 200
        data = resp.json()
        assert data['success'] is True
        assert data['data']['vendor'] == 'Organic Farm'


@pytest.mark.django_db
def test_ask_ai_api_endpoint_with_mock(client_a):
    with patch('core_app.views.ClaudeAIService') as MockService:
        instance = MockService.return_value
        instance.answer_financial_query.return_value = {
            'success': True,
            'answer': 'You spent ₹1,500.50 on dining.'
        }

        resp = client_a.post(
            reverse('ask_ai_api'),
            data=json.dumps({'question': 'How much did I spend on dining?'}),
            content_type='application/json'
        )
        assert resp.status_code == 200
        assert 'dining' in resp.json()['answer']


# =============================================================================
# 6. INCOME & CATEGORY BUDGETING TESTS
# =============================================================================

@pytest.mark.django_db
def test_create_income_valid(client_a, user_a):
    resp = client_a.post(reverse('add_income'), {
        'amount': '50000.00',
        'source': 'Salary',
        'date': str(date.today()),
        'description': 'Monthly tech salary'
    })
    assert resp.status_code == 302
    inc = Income.objects.filter(user=user_a, source='Salary').first()
    assert inc is not None
    assert inc.amount == Decimal('50000.00')


@pytest.mark.django_db
def test_user_a_cannot_delete_user_b_income(client_a, user_b):
    inc_b = Income.objects.create(
        user=user_b,
        amount=Decimal('25000.00'),
        source='Freelance',
        date=date.today()
    )
    url = reverse('delete_income', kwargs={'income_id': inc_b.id})
    resp = client_a.post(url)
    assert resp.status_code == 404
    assert Income.objects.filter(id=inc_b.id).exists()


@pytest.mark.django_db
def test_category_budget_tracking(user_a):
    today = date.today()
    # Create category budget for Food & Dining
    Budget.objects.create(
        user=user_a,
        month=today.month,
        year=today.year,
        category='Food & Dining',
        amount=Decimal('4000.00')
    )
    Expense.objects.create(
        user=user_a,
        amount=Decimal('3500.00'),
        category='Food & Dining',
        date=today
    )

    status = get_budget_status(user_a, month=today.month, year=today.year)
    assert status['has_category_budgets'] is True
    cat_b = status['category_budgets'][0]
    assert cat_b['category'] == 'Food & Dining'
    assert cat_b['spent_amount'] == 3500.0
    assert cat_b['budget_amount'] == 4000.0
    assert cat_b['status_level'] == 'warning'  # >80% used


@pytest.mark.django_db
def test_ask_ai_input_length_limit(client_a):
    long_question = "What did I spend " + ("a" * 500)
    resp = client_a.post(
        reverse('ask_ai_api'),
        data=json.dumps({'question': long_question}),
        content_type='application/json'
    )
    assert resp.status_code == 400
    assert "too long" in resp.json()['error']
