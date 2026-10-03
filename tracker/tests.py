"""
Unit tests covering budget calculation and threshold alert logic.
"""
import io
from decimal import Decimal
import datetime

from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse

from .models import Category, Budget, Expense, Income, Subscription, FinancialGoal
from .utils import calculate_spent, get_alert_state, get_percent_used, get_budget_summary


class AlertStateTests(TestCase):
    """Tests for the get_alert_state threshold logic."""

    def test_normal_state_below_80_percent(self):
        self.assertEqual(get_alert_state(Decimal('50'), Decimal('100')), 'normal')

    def test_normal_state_at_79_percent(self):
        self.assertEqual(get_alert_state(Decimal('79'), Decimal('100')), 'normal')

    def test_warning_state_at_exactly_80_percent(self):
        self.assertEqual(get_alert_state(Decimal('80'), Decimal('100')), 'warning')

    def test_warning_state_between_80_and_99(self):
        self.assertEqual(get_alert_state(Decimal('95'), Decimal('100')), 'warning')

    def test_danger_state_at_exactly_100_percent(self):
        self.assertEqual(get_alert_state(Decimal('100'), Decimal('100')), 'danger')

    def test_danger_state_above_100_percent(self):
        self.assertEqual(get_alert_state(Decimal('150'), Decimal('100')), 'danger')

    def test_normal_when_no_budget_limit(self):
        self.assertEqual(get_alert_state(Decimal('500'), None), 'normal')

    def test_normal_when_zero_spent(self):
        self.assertEqual(get_alert_state(Decimal('0'), Decimal('100')), 'normal')

    def test_warning_with_fractional_values(self):
        # 80.5 / 100.00 = 80.5% → warning
        self.assertEqual(get_alert_state(Decimal('80.5'), Decimal('100.00')), 'warning')

    def test_danger_with_fractional_overspend(self):
        # 200 / 150 = 133.3% → danger
        self.assertEqual(get_alert_state(Decimal('200'), Decimal('150')), 'danger')

    def test_normal_with_zero_budget(self):
        self.assertEqual(get_alert_state(Decimal('50'), Decimal('0')), 'normal')


class PercentUsedTests(TestCase):
    """Tests for the get_percent_used calculation."""

    def test_zero_spent(self):
        self.assertEqual(get_percent_used(Decimal('0'), Decimal('100')), Decimal('0'))

    def test_half_budget_used(self):
        self.assertEqual(get_percent_used(Decimal('50'), Decimal('100')), Decimal('50'))

    def test_full_budget_used(self):
        self.assertEqual(get_percent_used(Decimal('100'), Decimal('100')), Decimal('100'))

    def test_over_budget_capped_at_100(self):
        # Progress bar should not exceed 100
        self.assertEqual(get_percent_used(Decimal('200'), Decimal('100')), Decimal('100'))

    def test_no_budget_returns_zero(self):
        self.assertEqual(get_percent_used(Decimal('50'), None), Decimal('0'))


class CalculateSpentTests(TestCase):
    """Tests for the calculate_spent aggregation."""

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.other_user = User.objects.create_user(username='other', password='testpass')
        self.category = Category.objects.create(user=self.user, name='Food')
        self.other_category = Category.objects.create(user=self.other_user, name='Food')

    def test_returns_zero_when_no_expenses(self):
        month = datetime.date(2023, 10, 1)
        result = calculate_spent(self.user, self.category, month)
        self.assertEqual(result, Decimal('0'))

    def test_sums_expenses_for_correct_month(self):
        month = datetime.date(2023, 10, 1)
        Expense.objects.create(user=self.user, category=self.category, amount=Decimal('45.50'), date=datetime.date(2023, 10, 15))
        Expense.objects.create(user=self.user, category=self.category, amount=Decimal('20.00'), date=datetime.date(2023, 10, 1))
        result = calculate_spent(self.user, self.category, month)
        self.assertEqual(result, Decimal('65.50'))

    def test_excludes_expenses_from_other_months(self):
        month = datetime.date(2023, 10, 1)
        Expense.objects.create(user=self.user, category=self.category, amount=Decimal('100.00'), date=datetime.date(2023, 9, 30))
        Expense.objects.create(user=self.user, category=self.category, amount=Decimal('50.00'), date=datetime.date(2023, 10, 15))
        result = calculate_spent(self.user, self.category, month)
        self.assertEqual(result, Decimal('50.00'))

    def test_excludes_other_users_expenses(self):
        month = datetime.date(2023, 10, 1)
        Expense.objects.create(user=self.other_user, category=self.other_category, amount=Decimal('999.00'), date=datetime.date(2023, 10, 5))
        Expense.objects.create(user=self.user, category=self.category, amount=Decimal('30.00'), date=datetime.date(2023, 10, 5))
        result = calculate_spent(self.user, self.category, month)
        self.assertEqual(result, Decimal('30.00'))


class BudgetSummaryTests(TestCase):
    """Integration tests for the get_budget_summary function."""

    def setUp(self):
        self.user = User.objects.create_user(username='summaryuser', password='testpass')
        self.month = datetime.date(2023, 10, 1)
        self.food = Category.objects.create(user=self.user, name='Food')
        self.transport = Category.objects.create(user=self.user, name='Transport')
        Budget.objects.create(user=self.user, category=self.food, monthly_limit=Decimal('300'), month_year=self.month)
        Budget.objects.create(user=self.user, category=self.transport, monthly_limit=Decimal('100'), month_year=self.month)

    def test_summary_with_no_expenses(self):
        summary = get_budget_summary(self.user, self.month)
        self.assertEqual(summary['total_spent'], Decimal('0'))
        self.assertEqual(summary['total_budget'], Decimal('400'))
        self.assertEqual(summary['overall_alert'], 'normal')

    def test_summary_warning_alert(self):
        # Spend 80% of food budget (240/300)
        Expense.objects.create(user=self.user, category=self.food, amount=Decimal('240'), date=datetime.date(2023, 10, 10))
        summary = get_budget_summary(self.user, self.month)
        food_row = next(r for r in summary['category_rows'] if r['category'].name == 'Food')
        self.assertEqual(food_row['alert'], 'warning')

    def test_summary_danger_alert(self):
        # Overspend food budget
        Expense.objects.create(user=self.user, category=self.food, amount=Decimal('350'), date=datetime.date(2023, 10, 10))
        summary = get_budget_summary(self.user, self.month)
        food_row = next(r for r in summary['category_rows'] if r['category'].name == 'Food')
        self.assertEqual(food_row['alert'], 'danger')

    def test_total_spent_aggregation(self):
        Expense.objects.create(user=self.user, category=self.food, amount=Decimal('100'), date=datetime.date(2023, 10, 5))
        Expense.objects.create(user=self.user, category=self.transport, amount=Decimal('50'), date=datetime.date(2023, 10, 12))
        summary = get_budget_summary(self.user, self.month)
        self.assertEqual(summary['total_spent'], Decimal('150'))
        self.assertEqual(summary['total_remaining'], Decimal('250'))

    def test_category_without_budget_shows_none_limit(self):
        extra = Category.objects.create(user=self.user, name='Entertainment')
        Expense.objects.create(user=self.user, category=extra, amount=Decimal('50'), date=datetime.date(2023, 10, 1))
        summary = get_budget_summary(self.user, self.month)
        extra_row = next(r for r in summary['category_rows'] if r['category'].name == 'Entertainment')
        self.assertIsNone(extra_row['budget_limit'])
        self.assertEqual(extra_row['alert'], 'normal')


class ExpenseFormValidationTests(TestCase):
    """Test form-level validation for expenses."""

    def setUp(self):
        self.user = User.objects.create_user(username='formuser', password='testpass123')
        self.category = Category.objects.create(user=self.user, name='Food')
        self.client = Client()
        self.client.login(username='formuser', password='testpass123')

    def test_reject_negative_amount(self):
        response = self.client.post(reverse('expense_create'), {
            'amount': '-10.00',
            'date': '2023-10-15',
            'category': self.category.pk,
            'notes': '',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, 'form', 'amount', 'Expense amount must be greater than zero.')

    def test_reject_zero_amount(self):
        response = self.client.post(reverse('expense_create'), {
            'amount': '0.00',
            'date': '2023-10-15',
            'category': self.category.pk,
            'notes': '',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, 'form', 'amount', 'Expense amount must be greater than zero.')

    def test_valid_expense_redirects(self):
        response = self.client.post(reverse('expense_create'), {
            'amount': '45.50',
            'date': '2023-10-15',
            'category': self.category.pk,
            'notes': 'Lunch with client',
        })
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('dashboard'))

    def test_expense_saved_to_correct_user(self):
        self.client.post(reverse('expense_create'), {
            'amount': '25.00',
            'date': '2023-10-15',
            'category': self.category.pk,
            'notes': '',
        })
        self.assertEqual(Expense.objects.filter(user=self.user).count(), 1)


class AuthenticationTests(TestCase):
    """Tests that unauthenticated users are redirected."""

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse('dashboard'))
        self.assertRedirects(response, '/login/?next=/dashboard/')

    def test_expense_create_requires_login(self):
        response = self.client.get(reverse('expense_create'))
        self.assertRedirects(response, '/login/?next=/expenses/create/')

    def test_category_list_requires_login(self):
        response = self.client.get(reverse('category_list'))
        self.assertRedirects(response, '/login/?next=/categories/')

    def test_budget_list_requires_login(self):
        response = self.client.get(reverse('budget_list'))
        self.assertRedirects(response, '/login/?next=/budgets/')


class UserIsolationTests(TestCase):
    """Tests that users cannot access each other's data."""

    def setUp(self):
        self.user1 = User.objects.create_user(username='user1', password='testpass123')
        self.user2 = User.objects.create_user(username='user2', password='testpass123')
        self.cat1 = Category.objects.create(user=self.user1, name='Food')
        self.cat2 = Category.objects.create(user=self.user2, name='Food')
        self.expense1 = Expense.objects.create(user=self.user1, category=self.cat1, amount=Decimal('50'), date=datetime.date(2023, 10, 1))
        self.client = Client()

    def test_user_cannot_edit_other_users_expense(self):
        self.client.login(username='user2', password='testpass123')
        response = self.client.get(reverse('expense_edit', args=[self.expense1.pk]))
        self.assertEqual(response.status_code, 404)

    def test_user_cannot_delete_other_users_category(self):
        self.client.login(username='user2', password='testpass123')
        response = self.client.post(reverse('category_delete', args=[self.cat1.pk]))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Category.objects.filter(pk=self.cat1.pk).exists())


class PromptExampleRequestTests(TestCase):
    """Test specifically targeting the example request in the prompt."""

    def setUp(self):
        self.user = User.objects.create_user(username='demo_user', password='password123')
        self.client = Client()
        self.client.login(username='demo_user', password='password123')

    def test_example_request_with_category_name_string(self):
        # Example Request: amount=45.50, date=2023-10-15, category=Food, notes=Lunch with client
        # Response: Redirect to dashboard with HTTP 302
        response = self.client.post(reverse('expense_create'), {
            'amount': '45.50',
            'date': '2023-10-15',
            'category': 'Food',
            'notes': 'Lunch with client',
        })
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('dashboard'))

        expense = Expense.objects.filter(user=self.user).first()
        self.assertIsNotNone(expense)
        self.assertEqual(expense.amount, Decimal('45.50'))
        self.assertEqual(str(expense.date), '2023-10-15')
        self.assertEqual(expense.category.name, 'Food')
        self.assertEqual(expense.notes, 'Lunch with client')


class CategoryCrudTests(TestCase):
    """Comprehensive tests for Category CRUD interface and isolation."""

    def setUp(self):
        self.user = User.objects.create_user(username='catuser', password='password123')
        self.client = Client()
        self.client.login(username='catuser', password='password123')

    def test_category_create(self):
        response = self.client.post(reverse('category_create'), {
            'name': 'Groceries',
            'description': 'Weekly grocery shopping'
        })
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('category_list'))
        self.assertTrue(Category.objects.filter(user=self.user, name='Groceries').exists())

    def test_category_list(self):
        Category.objects.create(user=self.user, name='Utilities')
        response = self.client.get(reverse('category_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Utilities')

    def test_category_edit(self):
        cat = Category.objects.create(user=self.user, name='Bills')
        response = self.client.post(reverse('category_edit', args=[cat.pk]), {
            'name': 'Monthly Bills',
            'description': 'Updated description'
        })
        self.assertEqual(response.status_code, 302)
        cat.refresh_from_db()
        self.assertEqual(cat.name, 'Monthly Bills')

    def test_category_duplicate_name_rejected_for_same_user(self):
        Category.objects.create(user=self.user, name='Travel')
        response = self.client.post(reverse('category_create'), {
            'name': 'Travel',
            'description': 'Another travel'
        })
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, 'form', 'name', 'You already have a category named "Travel".')

    def test_duplicate_category_name_allowed_for_different_users(self):
        other_user = User.objects.create_user(username='other_user', password='password123')
        Category.objects.create(user=other_user, name='Rent')
        response = self.client.post(reverse('category_create'), {
            'name': 'Rent',
            'description': 'My rent'
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Category.objects.filter(user=self.user, name='Rent').exists())

    def test_safe_category_deletion_with_active_expenses(self):
        cat = Category.objects.create(user=self.user, name='Shopping')
        Expense.objects.create(user=self.user, category=cat, amount=Decimal('50'), date=datetime.date.today())
        # GET confirmation page shows active expense count
        get_res = self.client.get(reverse('category_delete', args=[cat.pk]))
        self.assertEqual(get_res.status_code, 200)
        self.assertContains(get_res, 'logged expense')

        # POST performs safe cascade deletion per schema
        post_res = self.client.post(reverse('category_delete', args=[cat.pk]))
        self.assertEqual(post_res.status_code, 302)
        self.assertFalse(Category.objects.filter(pk=cat.pk).exists())
        self.assertFalse(Expense.objects.filter(category_id=cat.pk).exists())


class BudgetManagementTests(TestCase):
    """Tests for setting and updating monthly category budgets."""

    def setUp(self):
        self.user = User.objects.create_user(username='budget_mgr', password='password123')
        self.category = Category.objects.create(user=self.user, name='Dining')
        self.client = Client()
        self.client.login(username='budget_mgr', password='password123')

    def test_budget_create(self):
        response = self.client.post(reverse('budget_create'), {
            'category': self.category.pk,
            'monthly_limit': '250.00',
            'month_year': '2023-11',
        })
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('budget_list'))
        budget = Budget.objects.filter(user=self.user, category=self.category).first()
        self.assertIsNotNone(budget)
        self.assertEqual(budget.monthly_limit, Decimal('250.00'))

    def test_budget_edit(self):
        budget = Budget.objects.create(
            user=self.user,
            category=self.category,
            monthly_limit=Decimal('200.00'),
            month_year=datetime.date(2023, 11, 1)
        )
        response = self.client.post(reverse('budget_edit', args=[budget.pk]), {
            'category': self.category.pk,
            'monthly_limit': '350.00',
            'month_year': '2023-11',
        })
        self.assertEqual(response.status_code, 302)
        budget.refresh_from_db()
        self.assertEqual(budget.monthly_limit, Decimal('350.00'))

    def test_budget_duplicate_month_rejected(self):
        Budget.objects.create(
            user=self.user,
            category=self.category,
            monthly_limit=Decimal('200.00'),
            month_year=datetime.date(2023, 11, 1)
        )
        response = self.client.post(reverse('budget_create'), {
            'category': self.category.pk,
            'monthly_limit': '300.00',
            'month_year': '2023-11',
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(len(response.context['form'].non_field_errors()) > 0)


class IncomeManagementTests(TestCase):
    """Tests for Income logging and cash flow calculation."""

    def setUp(self):
        self.user = User.objects.create_user(username='income_user', password='password123')
        self.client = Client()
        self.client.login(username='income_user', password='password123')

    def test_income_create(self):
        response = self.client.post(reverse('income_create'), {
            'source': 'Salary',
            'amount': '5000.00',
            'date': '2026-10-01',
            'notes': 'Monthly paycheck'
        })
        self.assertEqual(response.status_code, 302)
        income = Income.objects.filter(user=self.user, source='Salary').first()
        self.assertIsNotNone(income)
        self.assertEqual(income.amount, Decimal('5000.00'))

    def test_income_edit(self):
        income = Income.objects.create(
            user=self.user,
            source='Freelance',
            amount=Decimal('800.00'),
            date=datetime.date(2026, 10, 2)
        )
        response = self.client.post(reverse('income_edit', args=[income.pk]), {
            'source': 'Freelance',
            'amount': '1200.00',
            'date': '2026-10-02',
            'notes': 'Updated invoice'
        })
        self.assertEqual(response.status_code, 302)
        income.refresh_from_db()
        self.assertEqual(income.amount, Decimal('1200.00'))

    def test_income_delete(self):
        income = Income.objects.create(
            user=self.user,
            source='Bonus',
            amount=Decimal('500.00'),
            date=datetime.date(2026, 10, 3)
        )
        response = self.client.post(reverse('income_delete', args=[income.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Income.objects.filter(pk=income.pk).exists())

    def test_income_negative_or_zero_amount_rejected(self):
        response = self.client.post(reverse('income_create'), {
            'source': 'Salary',
            'amount': '-100.00',
            'date': '2026-10-01',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, 'form', 'amount', 'Income amount must be greater than zero.')

    def test_cash_flow_summary_calculation(self):
        today = datetime.date(2026, 10, 1)
        cat = Category.objects.create(user=self.user, name='Living')
        Income.objects.create(user=self.user, source='Salary', amount=Decimal('4000.00'), date=today)
        Expense.objects.create(user=self.user, category=cat, amount=Decimal('1500.00'), date=today)
        summary = get_budget_summary(self.user, today)
        self.assertEqual(summary['total_income'], Decimal('4000.00'))
        self.assertEqual(summary['total_spent'], Decimal('1500.00'))
        self.assertEqual(summary['net_cash_flow'], Decimal('2500.00'))
        self.assertGreater(summary['savings_rate'], 0)


class SubscriptionManagementTests(TestCase):
    """Tests for recurring subscriptions and automated bill payment."""

    def setUp(self):
        self.user = User.objects.create_user(username='sub_user', password='password123')
        self.category = Category.objects.create(user=self.user, name='Entertainment')
        self.client = Client()
        self.client.login(username='sub_user', password='password123')

    def test_subscription_create(self):
        response = self.client.post(reverse('subscription_create'), {
            'name': 'Netflix',
            'category': self.category.pk,
            'amount': '15.99',
            'billing_cycle': 'monthly',
            'next_due_date': '2026-10-15',
            'payment_method': 'Credit Card',
            'is_active': 'on'
        })
        self.assertEqual(response.status_code, 302)
        sub = Subscription.objects.filter(user=self.user, name='Netflix').first()
        self.assertIsNotNone(sub)
        self.assertEqual(sub.amount, Decimal('15.99'))

    def test_subscription_mark_paid(self):
        sub = Subscription.objects.create(
            user=self.user,
            name='Spotify',
            category=self.category,
            amount=Decimal('9.99'),
            billing_cycle='monthly',
            next_due_date=datetime.date(2026, 10, 10),
            payment_method='UPI / Card',
            is_active=True
        )
        response = self.client.post(reverse('subscription_mark_paid', args=[sub.pk]))
        self.assertEqual(response.status_code, 302)
        # Verify an expense was logged
        exp = Expense.objects.filter(user=self.user, amount=Decimal('9.99')).first()
        self.assertIsNotNone(exp)
        self.assertIn('Spotify', exp.notes)
        # Verify due date advanced to next month (November 10)
        sub.refresh_from_db()
        self.assertEqual(sub.next_due_date, datetime.date(2026, 11, 10))


class FinancialGoalTests(TestCase):
    """Tests for savings goals and progress contributions."""

    def setUp(self):
        self.user = User.objects.create_user(username='goal_user', password='password123')
        self.client = Client()
        self.client.login(username='goal_user', password='password123')

    def test_goal_create(self):
        response = self.client.post(reverse('goal_create'), {
            'title': 'Emergency Fund',
            'target_amount': '10000.00',
            'current_amount': '2500.00',
            'target_date': '2027-12-31',
            'color': '#10b981',
            'notes': '6 months of living expenses'
        })
        self.assertEqual(response.status_code, 302)
        goal = FinancialGoal.objects.filter(user=self.user, title='Emergency Fund').first()
        self.assertIsNotNone(goal)
        self.assertEqual(goal.current_amount, Decimal('2500.00'))

    def test_goal_contribute(self):
        goal = FinancialGoal.objects.create(
            user=self.user,
            title='New Laptop',
            target_amount=Decimal('2000.00'),
            current_amount=Decimal('500.00'),
            target_date=datetime.date(2026, 12, 31),
            color='#6366f1'
        )
        response = self.client.post(reverse('goal_contribute', args=[goal.pk]), {
            'amount': '250.00'
        })
        self.assertEqual(response.status_code, 302)
        goal.refresh_from_db()
        self.assertEqual(goal.current_amount, Decimal('750.00'))


class CSVImportTests(TestCase):
    """Tests for CSV statement upload and downloadable template."""

    def setUp(self):
        self.user = User.objects.create_user(username='csv_user', password='password123')
        self.client = Client()
        self.client.login(username='csv_user', password='password123')

    def test_download_csv_template(self):
        response = self.client.get(reverse('download_csv_template'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertIn('expense_import_template.csv', response['Content-Disposition'])
        self.assertIn(b'Date,Category,Amount,Notes,Payment Method', response.content)

    def test_import_expenses_csv_valid(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        csv_data = b"Date,Category,Amount,Notes,Payment Method\n2026-10-01,Groceries,75.50,Weekly food,Debit Card\n2026-10-02,Dining,32.00,Lunch,Cash\n"
        upload_file = SimpleUploadedFile("transactions.csv", csv_data, content_type="text/csv")

        response = self.client.post(reverse('import_expenses_csv'), {
            'csv_file': upload_file
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Expense.objects.filter(user=self.user).count(), 2)
        self.assertTrue(Category.objects.filter(user=self.user, name='Groceries').exists())
        self.assertTrue(Category.objects.filter(user=self.user, name='Dining').exists())


class AnalyticsViewTests(TestCase):
    """Tests for executive analytics and financial intelligence hub."""

    def setUp(self):
        self.user = User.objects.create_user(username='analytics_user', password='password123')
        self.client = Client()

    def test_analytics_view_unauthenticated_redirects(self):
        response = self.client.get(reverse('analytics'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)

    def test_analytics_view_authenticated(self):
        self.client.login(username='analytics_user', password='password123')
        response = self.client.get(reverse('analytics'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'tracker/analytics.html')
        self.assertIn('summary', response.context)
        self.assertIn('trend_json', response.context)


