"""
Utility functions for budget summary calculations, alert threshold logic,
and high-performance analytics query aggregations.
"""
import datetime
import calendar
from decimal import Decimal
from django.db.models import Sum
from django.db.models.functions import TruncMonth, TruncDay

from .models import Category, Budget, Expense, Income, Subscription, FinancialGoal


ALERT_WARNING_THRESHOLD = Decimal('80')   # percent
ALERT_DANGER_THRESHOLD = Decimal('100')   # percent


def calculate_spent(user, category, month_date):
    """
    Return the total amount spent for a user's category in the given month.
    """
    result = Expense.objects.filter(
        user=user,
        category=category,
        date__year=month_date.year,
        date__month=month_date.month,
    ).aggregate(total=Sum('amount'))['total']
    return result or Decimal('0')


def get_alert_state(spent, budget_limit):
    """
    Determine the alert state based on spent vs budget_limit.

    Returns one of: 'normal', 'warning', 'danger'
    """
    if budget_limit is None or budget_limit <= 0:
        return 'normal'
    percent = (Decimal(str(spent)) / Decimal(str(budget_limit))) * Decimal('100')
    if percent >= ALERT_DANGER_THRESHOLD:
        return 'danger'
    elif percent >= ALERT_WARNING_THRESHOLD:
        return 'warning'
    return 'normal'


def get_percent_used(spent, budget_limit):
    """Return percentage of budget used, capped at 100 for the progress bar."""
    if budget_limit is None or budget_limit <= 0:
        return Decimal('0')
    percent = (Decimal(str(spent)) / Decimal(str(budget_limit))) * Decimal('100')
    return min(percent, Decimal('100'))


def get_budget_summary(user, month_date):
    """
    Build a comprehensive dashboard summary using aggregated DB queries
    including Income, Cash Flow, Savings Rate, Category Limits, and Smart Insights.
    """
    categories = list(Category.objects.filter(user=user))
    month_start = month_date.replace(day=1)

    # Aggregated query for expense totals by category
    expense_totals = dict(
        Expense.objects.filter(
            user=user,
            date__year=month_date.year,
            date__month=month_date.month,
        ).values('category_id').annotate(total=Sum('amount')).values_list('category_id', 'total')
    )

    # Total income for current month
    total_income = Income.objects.filter(
        user=user,
        date__year=month_date.year,
        date__month=month_date.month,
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0')

    # Aggregated query for budget limits by category
    budget_map = {
        b.category_id: b
        for b in Budget.objects.filter(user=user, month_year=month_start).select_related('category')
    }

    category_rows = []
    grand_spent = Decimal('0')
    grand_budget = Decimal('0')

    for category in categories:
        spent = expense_totals.get(category.id) or Decimal('0')
        grand_spent += spent

        budget = budget_map.get(category.id)
        budget_limit = budget.monthly_limit if budget else None

        if budget_limit is not None:
            grand_budget += budget_limit

        remaining = (budget_limit - spent) if budget_limit is not None else None
        alert = get_alert_state(spent, budget_limit)
        percent = get_percent_used(spent, budget_limit)

        category_rows.append({
            'category': category,
            'spent': spent,
            'budget_limit': budget_limit,
            'remaining': remaining,
            'alert': alert,
            'percent': percent,
            'budget': budget,
        })

    overall_alert = get_alert_state(grand_spent, grand_budget) if grand_budget > 0 else 'normal'
    overall_percent = get_percent_used(grand_spent, grand_budget) if grand_budget > 0 else Decimal('0')
    total_remaining = (grand_budget - grand_spent) if grand_budget > 0 else None

    # Net Cash Flow & Savings Rate
    net_cash_flow = total_income - grand_spent
    savings_rate = Decimal('0')
    if total_income > 0:
        savings_rate = max(Decimal('0'), (net_cash_flow / total_income) * Decimal('100'))

    # Calculate run rate and projected spending
    today = datetime.date.today()
    days_in_month = calendar.monthrange(month_date.year, month_date.month)[1]
    if month_date.year == today.year and month_date.month == today.month:
        days_passed = max(1, today.day)
    elif month_date < today:
        days_passed = days_in_month
    else:
        days_passed = 1

    daily_avg = grand_spent / Decimal(str(days_passed))
    projected_total = daily_avg * Decimal(str(days_in_month))

    # Active subscriptions & upcoming bills
    active_subs = list(
        Subscription.objects.filter(user=user, is_active=True).select_related('category').order_by('next_due_date')
    )
    monthly_recurring_total = sum(
        (s.amount if s.billing_cycle == 'monthly' else (s.amount / Decimal('12')))
        for s in active_subs
    )

    # Upcoming bills within next 30 days
    upcoming_bills = [
        s for s in active_subs
        if 0 <= s.days_until_due <= 30
    ][:5]

    # Active savings goals
    active_goals = list(FinancialGoal.objects.filter(user=user).order_by('target_date', '-created_at')[:4])

    # Generate Smart Financial Insights
    smart_insights = []

    # 1. Budget Pace Alert
    if grand_budget > 0 and projected_total > grand_budget:
        over_proj = projected_total - grand_budget
        smart_insights.append({
            'type': 'danger',
            'icon': 'bi-exclamation-octagon-fill',
            'title': 'Budget Runway Warning',
            'message': f'At your current pace of {daily_avg:.2f}/day, you are projected to exceed your overall monthly budget by {over_proj:.2f}.'
        })
    elif grand_budget > 0 and overall_alert == 'normal' and days_passed > 10:
        smart_insights.append({
            'type': 'success',
            'icon': 'bi-shield-check',
            'title': 'Spending Under Control',
            'message': f'Great job! You have used only {overall_percent:.1f}% of your budget with {days_in_month - days_passed} days left.'
        })

    # 2. Overspent Category Alert
    danger_cats = [r for r in category_rows if r['alert'] == 'danger']
    if danger_cats:
        names = ', '.join([r['category'].name for r in danger_cats[:2]])
        smart_insights.append({
            'type': 'danger',
            'icon': 'bi-fire',
            'title': 'Category Limit Exceeded',
            'message': f'{names} has surpassed 100% of its monthly limit. Consider curbing discretionary purchases here.'
        })

    # 3. Cash Flow & Savings Rate Insight
    if total_income > 0:
        if net_cash_flow < 0:
            smart_insights.append({
                'type': 'warning',
                'icon': 'bi-arrow-down-circle-fill',
                'title': 'Negative Cash Flow Alert',
                'message': f'Your monthly expenses exceed income by {abs(net_cash_flow):.2f}. Review unessential spending.'
            })
        elif savings_rate >= 30:
            smart_insights.append({
                'type': 'success',
                'icon': 'bi-stars',
                'title': 'Super Saver Status',
                'message': f'Impressive! You are saving {savings_rate:.1f}% of your total income this month.'
            })

    # 4. Top Spending Category
    if grand_spent > 0 and category_rows:
        top_cat = max(category_rows, key=lambda r: r['spent'])
        if top_cat['spent'] > 0:
            share = (top_cat['spent'] / grand_spent) * Decimal('100')
            smart_insights.append({
                'type': 'info',
                'icon': 'bi-pie-chart-fill',
                'title': f'Top Category: {top_cat["category"].name}',
                'message': f'{top_cat["category"].name} accounts for {share:.1f}% of your total spending ({top_cat["spent"]:.2f}).'
            })

    return {
        'category_rows': category_rows,
        'total_spent': grand_spent,
        'total_budget': grand_budget,
        'total_remaining': total_remaining,
        'overall_percent': overall_percent,
        'overall_alert': overall_alert,
        'total_income': total_income,
        'net_cash_flow': net_cash_flow,
        'savings_rate': savings_rate,
        'daily_avg': daily_avg,
        'projected_total': projected_total,
        'days_passed': days_passed,
        'days_in_month': days_in_month,
        'upcoming_bills': upcoming_bills,
        'monthly_recurring_total': monthly_recurring_total,
        'active_goals': active_goals,
        'smart_insights': smart_insights[:4],
    }


def get_monthly_spending_trend(user, months_count=6):
    """
    Returns 6-month historical spending and income trend data for charts.
    """
    today = datetime.date.today()
    labels = []
    expense_data = []
    income_data = []

    for i in range(months_count - 1, -1, -1):
        target_month = (today.month - 1 - i) % 12 + 1
        target_year = today.year + (today.month - 1 - i) // 12
        target_date = datetime.date(target_year, target_month, 1)

        exp_total = Expense.objects.filter(
            user=user,
            date__year=target_year,
            date__month=target_month,
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')

        inc_total = Income.objects.filter(
            user=user,
            date__year=target_year,
            date__month=target_month,
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')

        labels.append(target_date.strftime('%b %Y'))
        expense_data.append(float(exp_total))
        income_data.append(float(inc_total))

    return {
        'labels': labels,
        'expenses': expense_data,
        'income': income_data,
        'data': expense_data,  # Backwards compatibility with existing tests/views
    }


def get_daily_spending_breakdown(user, month_date):
    """
    Returns day-by-day spending breakdown for the current month.
    """
    days_in_month = calendar.monthrange(month_date.year, month_date.month)[1]
    daily_expenses = dict(
        Expense.objects.filter(
            user=user,
            date__year=month_date.year,
            date__month=month_date.month,
        ).values('date__day').annotate(total=Sum('amount')).values_list('date__day', 'total')
    )

    labels = [str(d) for d in range(1, days_in_month + 1)]
    data = [float(daily_expenses.get(d, 0)) for d in range(1, days_in_month + 1)]

    return {'labels': labels, 'data': data}


def get_payment_method_breakdown(user, month_date):
    """
    Returns distribution of expenses by payment method for the month.
    """
    qs = Expense.objects.filter(
        user=user,
        date__year=month_date.year,
        date__month=month_date.month,
    ).values('payment_method').annotate(total=Sum('amount')).order_by('-total')

    labels = [row['payment_method'] or 'Other' for row in qs]
    data = [float(row['total']) for row in qs]
    colors = ['#6c63ff', '#3b82f6', '#10b981', '#f59e0b', '#ec4899']

    return {
        'labels': labels,
        'data': data,
        'colors': [colors[i % len(colors)] for i in range(len(labels))]
    }

