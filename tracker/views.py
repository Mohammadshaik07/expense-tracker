import json
import csv
import io
import datetime
import calendar
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Q, Avg, Max, Count
from django.http import HttpResponse
from django.core.paginator import Paginator
from django.utils import timezone

from .models import (
    Category, Budget, Expense, UserProfile,
    Income, Subscription, FinancialGoal
)
from .forms import (
    RegisterForm, CategoryForm, BudgetForm, ExpenseForm, CurrencyForm,
    IncomeForm, SubscriptionForm, FinancialGoalForm, GoalContributionForm, CSVImportForm
)
from .utils import (
    get_budget_summary,
    get_monthly_spending_trend,
    get_daily_spending_breakdown,
    get_payment_method_breakdown,
)


# ─── Authentication Views ─────────────────────────────────────────────────────

def register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f'Welcome, {user.username}! Your account has been created.')
            return redirect('dashboard')
    else:
        form = RegisterForm()
    return render(request, 'tracker/register.html', {'form': form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    error = None
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            next_url = request.GET.get('next', 'dashboard')
            return redirect(next_url)
        else:
            error = 'Invalid username or password.'
    return render(request, 'tracker/login.html', {'error': error})


def logout_view(request):
    logout(request)
    return redirect('login')


# ─── Dashboard ────────────────────────────────────────────────────────────────

@login_required
def dashboard(request):
    today = datetime.date.today()
    # Allow month navigation via query params
    try:
        year = int(request.GET.get('year', today.year))
        month = int(request.GET.get('month', today.month))
        current_month = datetime.date(year, month, 1)
    except (ValueError, TypeError):
        current_month = today.replace(day=1)

    summary = get_budget_summary(request.user, current_month)

    # Prev / next month navigation
    if current_month.month == 1:
        prev_month = datetime.date(current_month.year - 1, 12, 1)
    else:
        prev_month = datetime.date(current_month.year, current_month.month - 1, 1)

    if current_month.month == 12:
        next_month = datetime.date(current_month.year + 1, 1, 1)
    else:
        next_month = datetime.date(current_month.year, current_month.month + 1, 1)

    # Recent expenses (query optimization: select_related)
    recent_expenses = Expense.objects.filter(
        user=request.user,
        date__year=current_month.year,
        date__month=current_month.month,
    ).select_related('category').order_by('-date', '-created_at')[:8]

    # Chart data
    trend_data = get_monthly_spending_trend(request.user, months_count=6)
    daily_data = get_daily_spending_breakdown(request.user, current_month)

    # Category Breakdown Chart Data
    cat_labels = [row['category'].name for row in summary['category_rows'] if row['spent'] > 0]
    cat_values = [float(row['spent']) for row in summary['category_rows'] if row['spent'] > 0]

    # Category colors list for charts
    palette = ['#6c63ff', '#a855f7', '#ec4899', '#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#14b8a6', '#8b5cf6']
    cat_colors = [palette[i % len(palette)] for i in range(len(cat_labels))]

    category_chart_json = json.dumps({
        'labels': cat_labels,
        'values': cat_values,
        'colors': cat_colors,
    })
    trend_chart_json = json.dumps(trend_data)
    daily_chart_json = json.dumps(daily_data)

    payment_method_data = get_payment_method_breakdown(request.user, current_month)
    payment_method_json = json.dumps(payment_method_data)

    context = {
        'summary': summary,
        'current_month': current_month,
        'prev_month': prev_month,
        'next_month': next_month,
        'recent_expenses': recent_expenses,
        'today': today,
        'category_chart_json': category_chart_json,
        'trend_chart_json': trend_chart_json,
        'daily_chart_json': daily_chart_json,
        'payment_method_json': payment_method_json,
        'quick_expense_form': ExpenseForm(user=request.user),
        'quick_income_form': IncomeForm(),
    }
    return render(request, 'tracker/dashboard.html', context)


# ─── Category CRUD ────────────────────────────────────────────────────────────

@login_required
def category_list(request):
    categories = Category.objects.filter(user=request.user)
    return render(request, 'tracker/category_list.html', {'categories': categories})


@login_required
def category_create(request):
    if request.method == 'POST':
        form = CategoryForm(request.POST, user=request.user)
        if form.is_valid():
            category = form.save(commit=False)
            category.user = request.user
            category.save()
            messages.success(request, f'Category "{category.name}" created.')
            return redirect('category_list')
    else:
        form = CategoryForm(user=request.user)
    return render(request, 'tracker/category_form.html', {'form': form, 'action': 'Create'})


@login_required
def category_edit(request, pk):
    category = get_object_or_404(Category, pk=pk, user=request.user)
    if request.method == 'POST':
        form = CategoryForm(request.POST, instance=category, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, f'Category "{category.name}" updated.')
            return redirect('category_list')
    else:
        form = CategoryForm(instance=category, user=request.user)
    return render(request, 'tracker/category_form.html', {'form': form, 'action': 'Edit', 'object': category})


@login_required
def category_delete(request, pk):
    category = get_object_or_404(Category, pk=pk, user=request.user)
    expense_count = category.expenses.count()
    budget_count = category.budgets.count()
    if request.method == 'POST':
        name = category.name
        category.delete()
        messages.success(request, f'Category "{name}" and all related expenses have been deleted.')
        return redirect('category_list')
    return render(request, 'tracker/category_confirm_delete.html', {
        'object': category,
        'expense_count': expense_count,
        'budget_count': budget_count,
    })


# ─── Budget Management ────────────────────────────────────────────────────────

@login_required
def budget_list(request):
    budgets = Budget.objects.filter(user=request.user).select_related('category')
    return render(request, 'tracker/budget_list.html', {'budgets': budgets})


@login_required
def budget_create(request):
    if not Category.objects.filter(user=request.user).exists():
        messages.warning(request, 'Please create at least one category before setting a budget.')
        return redirect('category_create')
    if request.method == 'POST':
        form = BudgetForm(request.POST, user=request.user)
        if form.is_valid():
            budget = form.save(commit=False)
            budget.user = request.user
            budget.save()
            messages.success(request, f'Budget set for {budget.category.name}.')
            return redirect('budget_list')
    else:
        form = BudgetForm(user=request.user)
    return render(request, 'tracker/budget_form.html', {'form': form, 'action': 'Set'})


@login_required
def budget_edit(request, pk):
    budget = get_object_or_404(Budget, pk=pk, user=request.user)
    if request.method == 'POST':
        form = BudgetForm(request.POST, instance=budget, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Budget updated.')
            return redirect('budget_list')
    else:
        form = BudgetForm(instance=budget, user=request.user)
    return render(request, 'tracker/budget_form.html', {'form': form, 'action': 'Edit', 'object': budget})


@login_required
def budget_delete(request, pk):
    budget = get_object_or_404(Budget, pk=pk, user=request.user)
    if request.method == 'POST':
        budget.delete()
        messages.success(request, 'Budget removed.')
        return redirect('budget_list')
    return render(request, 'tracker/budget_confirm_delete.html', {'object': budget})


# ─── Expense CRUD & Log Section ───────────────────────────────────────────────

@login_required
def expense_list(request):
    """
    Enhanced expense log view with searching, filtering by category/date,
    sorting, pagination, summary statistics, and quick-add form.
    """
    queryset = Expense.objects.filter(user=request.user).select_related('category')

    # Search query
    q = request.GET.get('q', '').strip()
    if q:
        queryset = queryset.filter(
            Q(notes__icontains=q) | Q(category__name__icontains=q)
        )

    # Category filter
    category_id = request.GET.get('category')
    if category_id and category_id.isdigit():
        queryset = queryset.filter(category_id=int(category_id))

    # Date / period filter
    period = request.GET.get('period', 'all')
    today = datetime.date.today()
    if period == 'this_month':
        queryset = queryset.filter(date__year=today.year, date__month=today.month)
    elif period == 'last_month':
        first_day_this_month = today.replace(day=1)
        last_day_last_month = first_day_this_month - datetime.timedelta(days=1)
        queryset = queryset.filter(
            date__year=last_day_last_month.year,
            date__month=last_day_last_month.month
        )
    elif period == '30_days':
        start_30 = today - datetime.timedelta(days=30)
        queryset = queryset.filter(date__gte=start_30)

    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    if date_from:
        try:
            df = datetime.datetime.strptime(date_from, '%Y-%m-%d').date()
            queryset = queryset.filter(date__gte=df)
        except ValueError:
            pass
    if date_to:
        try:
            dt = datetime.datetime.strptime(date_to, '%Y-%m-%d').date()
            queryset = queryset.filter(date__lte=dt)
        except ValueError:
            pass

    # Sorting
    sort = request.GET.get('sort', 'date_desc')
    if sort == 'date_asc':
        queryset = queryset.order_by('date', 'created_at')
    elif sort == 'amount_desc':
        queryset = queryset.order_by('-amount', '-date')
    elif sort == 'amount_asc':
        queryset = queryset.order_by('amount', '-date')
    else:  # default date_desc
        queryset = queryset.order_by('-date', '-created_at')

    # Calculate summary metrics on filtered set
    stats = queryset.aggregate(
        total_amount=Sum('amount'),
        avg_amount=Avg('amount'),
        max_amount=Max('amount'),
        count=Count('id')
    )
    total_amount = stats['total_amount'] or Decimal('0')
    avg_amount = stats['avg_amount'] or Decimal('0')
    max_amount = stats['max_amount'] or Decimal('0')
    count = stats['count'] or 0

    # Pagination (15 items per page)
    paginator = Paginator(queryset, 15)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    # Categories for filter dropdown
    categories = Category.objects.filter(user=request.user)

    # Quick Add Expense Form
    quick_form = ExpenseForm(user=request.user)

    context = {
        'page_obj': page_obj,
        'expenses': page_obj.object_list,
        'categories': categories,
        'q': q,
        'selected_category': category_id,
        'period': period,
        'date_from': date_from,
        'date_to': date_to,
        'sort': sort,
        'total_amount': total_amount,
        'avg_amount': avg_amount,
        'max_amount': max_amount,
        'count': count,
        'quick_form': quick_form,
    }
    return render(request, 'tracker/expense_list.html', context)


@login_required
def export_expenses_csv(request):
    """
    Exports filtered expenses to a downloadable CSV file.
    """
    queryset = Expense.objects.filter(user=request.user).select_related('category')

    # Apply search and filters
    q = request.GET.get('q', '').strip()
    if q:
        queryset = queryset.filter(Q(notes__icontains=q) | Q(category__name__icontains=q))

    category_id = request.GET.get('category')
    if category_id and category_id.isdigit():
        queryset = queryset.filter(category_id=int(category_id))

    period = request.GET.get('period', 'all')
    today = datetime.date.today()
    if period == 'this_month':
        queryset = queryset.filter(date__year=today.year, date__month=today.month)
    elif period == 'last_month':
        first_day_this_month = today.replace(day=1)
        last_day_last_month = first_day_this_month - datetime.timedelta(days=1)
        queryset = queryset.filter(date__year=last_day_last_month.year, date__month=last_day_last_month.month)
    elif period == '30_days':
        start_30 = today - datetime.timedelta(days=30)
        queryset = queryset.filter(date__gte=start_30)

    sort = request.GET.get('sort', 'date_desc')
    if sort == 'date_asc':
        queryset = queryset.order_by('date')
    elif sort == 'amount_desc':
        queryset = queryset.order_by('-amount')
    elif sort == 'amount_asc':
        queryset = queryset.order_by('amount')
    else:
        queryset = queryset.order_by('-date')

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="ExpenseIQ_Export_{today.strftime("%Y%m%d")}.csv"'

    writer = csv.writer(response)
    writer.writerow(['Date', 'Category', 'Amount', 'Notes', 'Created At'])

    for exp in queryset:
        writer.writerow([
            exp.date.strftime('%Y-%m-%d'),
            exp.category.name,
            f"{exp.amount:.2f}",
            exp.notes,
            exp.created_at.strftime('%Y-%m-%d %H:%M:%S'),
        ])

    return response


@login_required
def expense_create(request):
    if request.method == 'GET' and not Category.objects.filter(user=request.user).exists():
        messages.warning(request, 'Please create at least one category before logging expenses.')
        return redirect('category_create')
    if request.method == 'POST':
        form = ExpenseForm(request.POST, user=request.user)
        if form.is_valid():
            expense = form.save(commit=False)
            expense.user = request.user
            expense.save()
            symbol = getattr(request.user, 'profile', None)
            sym = symbol.currency_symbol if symbol else '$'
            messages.success(request, f'Expense of {sym}{expense.amount} logged successfully!')
            # Redirect back to where user came from if specified
            next_url = request.POST.get('next') or request.GET.get('next') or 'dashboard'
            return redirect(next_url)
    else:
        form = ExpenseForm(user=request.user)
    return render(request, 'tracker/expense_form.html', {'form': form, 'action': 'Log'})


@login_required
def expense_edit(request, pk):
    expense = get_object_or_404(Expense, pk=pk, user=request.user)
    if request.method == 'POST':
        form = ExpenseForm(request.POST, instance=expense, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Expense updated successfully.')
            return redirect('expense_list')
    else:
        form = ExpenseForm(instance=expense, user=request.user)
    return render(request, 'tracker/expense_form.html', {'form': form, 'action': 'Edit', 'object': expense})


@login_required
def expense_delete(request, pk):
    expense = get_object_or_404(Expense, pk=pk, user=request.user)
    if request.method == 'POST':
        expense.delete()
        messages.success(request, 'Expense deleted successfully.')
        return redirect('expense_list')
    return render(request, 'tracker/expense_confirm_delete.html', {'object': expense})


# ─── Currency Settings ────────────────────────────────────────────────────────

@login_required
def currency_settings(request):
    """Allow the user to select their preferred display currency."""
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        form = CurrencyForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, f'Currency updated to {profile.get_currency_display()}.')
            return redirect('currency_settings')
    else:
        form = CurrencyForm(instance=profile)
    return render(request, 'tracker/currency_settings.html', {'form': form, 'profile': profile})


# ─── Income Management (Cash Flow Tracking) ───────────────────────────────────

@login_required
def income_list(request):
    """List, filter, and paginate all income streams."""
    queryset = Income.objects.filter(user=request.user)

    q = request.GET.get('q', '').strip()
    if q:
        queryset = queryset.filter(Q(source__icontains=q) | Q(notes__icontains=q))

    period = request.GET.get('period', 'all')
    today = datetime.date.today()
    if period == 'this_month':
        queryset = queryset.filter(date__year=today.year, date__month=today.month)
    elif period == 'last_month':
        first_day_this_month = today.replace(day=1)
        last_day_last_month = first_day_this_month - datetime.timedelta(days=1)
        queryset = queryset.filter(date__year=last_day_last_month.year, date__month=last_day_last_month.month)

    stats = queryset.aggregate(
        total_amount=Sum('amount'),
        avg_amount=Avg('amount'),
        count=Count('id')
    )
    total_amount = stats['total_amount'] or Decimal('0')
    avg_amount = stats['avg_amount'] or Decimal('0')
    count = stats['count'] or 0

    paginator = Paginator(queryset, 15)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    context = {
        'page_obj': page_obj,
        'incomes': page_obj.object_list,
        'q': q,
        'period': period,
        'total_amount': total_amount,
        'avg_amount': avg_amount,
        'count': count,
        'quick_form': IncomeForm(),
    }
    return render(request, 'tracker/income_list.html', context)


@login_required
def income_create(request):
    if request.method == 'POST':
        form = IncomeForm(request.POST)
        if form.is_valid():
            income = form.save(commit=False)
            income.user = request.user
            income.save()
            symbol = getattr(request.user, 'profile', None)
            sym = symbol.currency_symbol if symbol else '$'
            messages.success(request, f'Income of {sym}{income.amount} ({income.source}) recorded!')
            next_url = request.POST.get('next') or request.GET.get('next') or 'income_list'
            return redirect(next_url)
    else:
        form = IncomeForm()
    return render(request, 'tracker/income_form.html', {'form': form, 'action': 'Record'})


@login_required
def income_edit(request, pk):
    income = get_object_or_404(Income, pk=pk, user=request.user)
    if request.method == 'POST':
        form = IncomeForm(request.POST, instance=income)
        if form.is_valid():
            form.save()
            messages.success(request, 'Income entry updated successfully.')
            return redirect('income_list')
    else:
        form = IncomeForm(instance=income)
    return render(request, 'tracker/income_form.html', {'form': form, 'action': 'Edit', 'object': income})


@login_required
def income_delete(request, pk):
    income = get_object_or_404(Income, pk=pk, user=request.user)
    if request.method == 'POST':
        income.delete()
        messages.success(request, 'Income entry removed.')
        return redirect('income_list')
    return render(request, 'tracker/income_confirm_delete.html', {'object': income})


# ─── Recurring Subscriptions & Fixed Bills ────────────────────────────────────

@login_required
def subscription_list(request):
    """Manage active and past recurring subscriptions and bill cycles."""
    subscriptions = Subscription.objects.filter(user=request.user).select_related('category')
    active_subs = [s for s in subscriptions if s.is_active]
    monthly_cost = sum(
        (s.amount if s.billing_cycle == 'monthly' else (s.amount / Decimal('12')))
        for s in active_subs
    )
    yearly_cost = monthly_cost * Decimal('12')

    context = {
        'subscriptions': subscriptions,
        'active_subs': active_subs,
        'monthly_cost': monthly_cost,
        'yearly_cost': yearly_cost,
    }
    return render(request, 'tracker/subscription_list.html', context)


@login_required
def subscription_create(request):
    if request.method == 'POST':
        form = SubscriptionForm(request.POST, user=request.user)
        if form.is_valid():
            sub = form.save(commit=False)
            sub.user = request.user
            sub.save()
            messages.success(request, f'Subscription "{sub.name}" added to tracker.')
            return redirect('subscription_list')
    else:
        form = SubscriptionForm(user=request.user)
    return render(request, 'tracker/subscription_form.html', {'form': form, 'action': 'Add'})


@login_required
def subscription_edit(request, pk):
    sub = get_object_or_404(Subscription, pk=pk, user=request.user)
    if request.method == 'POST':
        form = SubscriptionForm(request.POST, instance=sub, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, f'Subscription "{sub.name}" updated.')
            return redirect('subscription_list')
    else:
        form = SubscriptionForm(instance=sub, user=request.user)
    return render(request, 'tracker/subscription_form.html', {'form': form, 'action': 'Edit', 'object': sub})


@login_required
def subscription_delete(request, pk):
    sub = get_object_or_404(Subscription, pk=pk, user=request.user)
    if request.method == 'POST':
        name = sub.name
        sub.delete()
        messages.success(request, f'Subscription "{name}" deleted.')
        return redirect('subscription_list')
    return render(request, 'tracker/subscription_confirm_delete.html', {'object': sub})


@login_required
def subscription_mark_paid(request, pk):
    """Quick-action to mark recurring bill paid, log expense, and advance due date."""
    subscription = get_object_or_404(Subscription, pk=pk, user=request.user)
    if request.method == 'POST':
        category = subscription.category
        if not category:
            category, _ = Category.objects.get_or_create(
                user=request.user,
                name='Subscriptions',
                defaults={'icon': 'bi-lightning-charge-fill', 'color': '#8b5cf6'}
            )

        Expense.objects.create(
            user=request.user,
            category=category,
            amount=subscription.amount,
            date=datetime.date.today(),
            notes=f"Auto-logged payment for subscription: {subscription.name}",
            payment_method=subscription.payment_method
        )

        old_due = subscription.next_due_date
        if subscription.billing_cycle == 'yearly':
            try:
                subscription.next_due_date = old_due.replace(year=old_due.year + 1)
            except ValueError:
                subscription.next_due_date = old_due + datetime.timedelta(days=365)
        else:
            month = old_due.month % 12 + 1
            year = old_due.year + (old_due.month // 12)
            day = min(old_due.day, calendar.monthrange(year, month)[1])
            subscription.next_due_date = datetime.date(year, month, day)

        subscription.save()
        messages.success(
            request,
            f'Marked "{subscription.name}" as paid! Expense logged and next due date updated to {subscription.next_due_date.strftime("%b %d, %Y")}.'
        )
    return redirect('subscription_list')


# ─── Financial Goals Tracker ──────────────────────────────────────────────────

@login_required
def goal_list(request):
    goals = FinancialGoal.objects.filter(user=request.user)
    total_target = sum(g.target_amount for g in goals)
    total_saved = sum(g.current_amount for g in goals)
    overall_progress = (total_saved / total_target * 100) if total_target > 0 else 0

    context = {
        'goals': goals,
        'total_target': total_target,
        'total_saved': total_saved,
        'overall_progress': overall_progress,
        'contribution_form': GoalContributionForm(),
    }
    return render(request, 'tracker/goal_list.html', context)


@login_required
def goal_create(request):
    if request.method == 'POST':
        form = FinancialGoalForm(request.POST)
        if form.is_valid():
            goal = form.save(commit=False)
            goal.user = request.user
            goal.save()
            messages.success(request, f'Goal "{goal.title}" created successfully!')
            return redirect('goal_list')
    else:
        form = FinancialGoalForm()
    return render(request, 'tracker/goal_form.html', {'form': form, 'action': 'Create'})


@login_required
def goal_edit(request, pk):
    goal = get_object_or_404(FinancialGoal, pk=pk, user=request.user)
    if request.method == 'POST':
        form = FinancialGoalForm(request.POST, instance=goal)
        if form.is_valid():
            form.save()
            messages.success(request, f'Goal "{goal.title}" updated.')
            return redirect('goal_list')
    else:
        form = FinancialGoalForm(instance=goal)
    return render(request, 'tracker/goal_form.html', {'form': form, 'action': 'Edit', 'object': goal})


@login_required
def goal_delete(request, pk):
    goal = get_object_or_404(FinancialGoal, pk=pk, user=request.user)
    if request.method == 'POST':
        title = goal.title
        goal.delete()
        messages.success(request, f'Goal "{title}" removed.')
        return redirect('goal_list')
    return render(request, 'tracker/goal_confirm_delete.html', {'object': goal})


@login_required
def goal_contribute(request, pk):
    goal = get_object_or_404(FinancialGoal, pk=pk, user=request.user)
    if request.method == 'POST':
        form = GoalContributionForm(request.POST)
        if form.is_valid():
            amount = form.cleaned_data['amount']
            goal.current_amount += amount
            goal.save()
            symbol = getattr(request.user, 'profile', None)
            sym = symbol.currency_symbol if symbol else '$'
            messages.success(request, f'Deposited {sym}{amount} towards "{goal.title}"! (Progress: {goal.percent_achieved:.1f}%)')
    return redirect('goal_list')


# ─── CSV Statement Import & Template ──────────────────────────────────────────

@login_required
def import_expenses_csv(request):
    """
    Imports transactions from a user-uploaded CSV file with flexible column matching.
    """
    if request.method == 'POST':
        form = CSVImportForm(request.POST, request.FILES)
        if form.is_valid():
            csv_file = request.FILES['csv_file']
            if not csv_file.name.endswith('.csv'):
                messages.error(request, 'Please upload a valid CSV file ending with .csv.')
                return render(request, 'tracker/csv_import.html', {'form': form})

            try:
                decoded_file = csv_file.read().decode('utf-8-sig')
            except UnicodeDecodeError:
                messages.error(request, 'Unable to decode CSV file. Please ensure it is UTF-8 encoded.')
                return render(request, 'tracker/csv_import.html', {'form': form})

            reader = csv.reader(io.StringIO(decoded_file))
            headers = [h.strip().lower() for h in next(reader, [])]

            date_idx = None
            category_idx = None
            amount_idx = None
            notes_idx = None
            pm_idx = None

            for idx, h in enumerate(headers):
                if 'date' in h:
                    date_idx = idx
                elif 'category' in h or 'cat' in h:
                    category_idx = idx
                elif 'amount' in h or 'cost' in h or 'price' in h:
                    amount_idx = idx
                elif 'note' in h or 'desc' in h or 'merchant' in h:
                    notes_idx = idx
                elif 'payment' in h or 'method' in h:
                    pm_idx = idx

            if date_idx is None or category_idx is None or amount_idx is None:
                messages.error(request, 'CSV must contain at least "Date", "Category", and "Amount" columns.')
                return render(request, 'tracker/csv_import.html', {'form': form})

            imported_count = 0
            skipped_count = 0

            for row in reader:
                if not row or all(not cell.strip() for cell in row):
                    continue
                try:
                    raw_date = row[date_idx].strip()
                    raw_cat = row[category_idx].strip()
                    raw_amt = row[amount_idx].strip().replace('$', '').replace('₹', '').replace(',', '').strip()
                    raw_notes = row[notes_idx].strip() if notes_idx is not None and notes_idx < len(row) else ''
                    raw_pm = row[pm_idx].strip() if pm_idx is not None and pm_idx < len(row) else 'UPI / Card'

                    amt = Decimal(raw_amt)
                    if amt <= 0:
                        skipped_count += 1
                        continue

                    parsed_date = None
                    for fmt in ('%Y-%m-%d', '%d-%m-%Y', '%m/%d/%Y', '%d/%m/%Y', '%Y/%m/%d'):
                        try:
                            parsed_date = datetime.datetime.strptime(raw_date, fmt).date()
                            break
                        except ValueError:
                            pass
                    if not parsed_date:
                        skipped_count += 1
                        continue

                    category, _ = Category.objects.get_or_create(
                        user=request.user,
                        name=raw_cat if raw_cat else 'General',
                        defaults={'description': 'Imported category'}
                    )

                    Expense.objects.create(
                        user=request.user,
                        category=category,
                        amount=amt,
                        date=parsed_date,
                        notes=raw_notes,
                        payment_method=raw_pm if raw_pm else 'UPI / Card'
                    )
                    imported_count += 1
                except Exception:
                    skipped_count += 1

            if imported_count > 0:
                messages.success(request, f'Successfully imported {imported_count} transaction(s)! ({skipped_count} skipped)')
                return redirect('expense_list')
            else:
                messages.warning(request, 'No valid transactions could be imported. Please verify your CSV format.')
    else:
        form = CSVImportForm()
    return render(request, 'tracker/csv_import.html', {'form': form})


@login_required
def download_csv_template(request):
    """Generates a downloadable sample CSV template for users."""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="expense_import_template.csv"'
    writer = csv.writer(response)
    writer.writerow(['Date', 'Category', 'Amount', 'Notes', 'Payment Method'])
    writer.writerow(['2026-10-01', 'Dining', '24.50', 'Starbucks Coffee', 'Credit Card'])
    writer.writerow(['2026-10-02', 'Groceries', '85.20', 'Supermarket run', 'UPI / Card'])
    writer.writerow(['2026-10-03', 'Transport', '15.00', 'Metro pass recharge', 'Cash'])
    return response


# ─── Deep-Dive Analytics & Financial Intelligence ─────────────────────────────

@login_required
def analytics_view(request):
    """Executive financial intelligence dashboard with cash flow & payment methods."""
    today = datetime.date.today()
    try:
        year = int(request.GET.get('year', today.year))
        month = int(request.GET.get('month', today.month))
        current_month = datetime.date(year, month, 1)
    except (ValueError, TypeError):
        current_month = today.replace(day=1)

    summary = get_budget_summary(request.user, current_month)
    trend_data = get_monthly_spending_trend(request.user, months_count=6)
    payment_data = get_payment_method_breakdown(request.user, current_month)
    daily_data = get_daily_spending_breakdown(request.user, current_month)

    # Top expenses this month
    top_expenses = Expense.objects.filter(
        user=request.user,
        date__year=current_month.year,
        date__month=current_month.month
    ).select_related('category').order_by('-amount')[:5]

    context = {
        'summary': summary,
        'current_month': current_month,
        'trend_json': json.dumps(trend_data),
        'payment_json': json.dumps(payment_data),
        'daily_json': json.dumps(daily_data),
        'top_expenses': top_expenses,
    }
    return render(request, 'tracker/analytics.html', context)

