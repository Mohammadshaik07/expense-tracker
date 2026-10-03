import os
import datetime
from decimal import Decimal
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_tracker.settings')
django.setup()

from django.contrib.auth.models import User
from tracker.models import Category, Budget, Expense, Income, Subscription, FinancialGoal, UserProfile

# Create or reset demo user
user, created = User.objects.get_or_create(username='demo')
user.set_password('password123')
user.email = 'demo@expenseiq.io'
user.save()

profile, _ = UserProfile.objects.get_or_create(user=user)
profile.currency = 'USD'
profile.save()

# Clear existing demo data for clean state
Category.objects.filter(user=user).delete()
Income.objects.filter(user=user).delete()
Subscription.objects.filter(user=user).delete()
FinancialGoal.objects.filter(user=user).delete()

today = datetime.date.today()
first_of_month = today.replace(day=1)

# Categories
cats = {
    'Housing': Category.objects.create(user=user, name='Housing & Rent', icon='bi-house-door-fill', color='#3b82f6'),
    'Groceries': Category.objects.create(user=user, name='Groceries', icon='bi-cart-fill', color='#10b981'),
    'Dining': Category.objects.create(user=user, name='Dining & Cafes', icon='bi-cup-hot-fill', color='#ef4444'),
    'Tech': Category.objects.create(user=user, name='Tech & Software', icon='bi-laptop', color='#8b5cf6'),
    'Transport': Category.objects.create(user=user, name='Transport & Gas', icon='bi-car-front-fill', color='#14b8a6'),
    'Investments': Category.objects.create(user=user, name='Investments', icon='bi-cash-coin', color='#f59e0b'),
}

# Budgets
Budget.objects.create(user=user, category=cats['Groceries'], monthly_limit=Decimal('600.00'), month_year=first_of_month)
Budget.objects.create(user=user, category=cats['Dining'], monthly_limit=Decimal('350.00'), month_year=first_of_month)
Budget.objects.create(user=user, category=cats['Tech'], monthly_limit=Decimal('200.00'), month_year=first_of_month)
Budget.objects.create(user=user, category=cats['Transport'], monthly_limit=Decimal('180.00'), month_year=first_of_month)

# Incomes
Income.objects.create(user=user, source='Salary', amount=Decimal('6250.00'), date=first_of_month, notes='Primary Senior Engineer Paycheck')
Income.objects.create(user=user, source='Freelance', amount=Decimal('1450.00'), date=today - datetime.timedelta(days=2), notes='UI Architecture Consulting Client')

# Expenses
Expense.objects.create(user=user, category=cats['Housing'], amount=Decimal('1650.00'), date=first_of_month, payment_method='Net Banking', notes='Monthly Apartment Lease')
Expense.objects.create(user=user, category=cats['Groceries'], amount=Decimal('142.30'), date=today - datetime.timedelta(days=3), payment_method='UPI / Card', notes='Whole Foods Market')
Expense.objects.create(user=user, category=cats['Groceries'], amount=Decimal('89.40'), date=today - datetime.timedelta(days=1), payment_method='Credit Card', notes='Trader Joe\'s')
Expense.objects.create(user=user, category=cats['Dining'], amount=Decimal('54.00'), date=today - datetime.timedelta(days=4), payment_method='Credit Card', notes='Sushi dinner with team')
Expense.objects.create(user=user, category=cats['Dining'], amount=Decimal('18.50'), date=today, payment_method='UPI / Card', notes='Artisan espresso & bagel')
Expense.objects.create(user=user, category=cats['Tech'], amount=Decimal('42.00'), date=today - datetime.timedelta(days=5), payment_method='Credit Card', notes='GitHub Copilot & JetBrains')
Expense.objects.create(user=user, category=cats['Transport'], amount=Decimal('45.00'), date=today - datetime.timedelta(days=2), payment_method='UPI / Card', notes='Gas station fill-up')

# Subscriptions
Subscription.objects.create(
    user=user, category=cats['Tech'], name='AWS Cloud Hosting',
    amount=Decimal('45.00'), billing_cycle='monthly',
    next_due_date=today + datetime.timedelta(days=4),
    payment_method='Credit Card', is_active=True, notes='Production web services'
)
Subscription.objects.create(
    user=user, category=cats['Tech'], name='Spotify Family',
    amount=Decimal('16.99'), billing_cycle='monthly',
    next_due_date=today + datetime.timedelta(days=7),
    payment_method='Credit Card', is_active=True
)
Subscription.objects.create(
    user=user, category=cats['Housing'], name='High-speed Fiber Internet',
    amount=Decimal('70.00'), billing_cycle='monthly',
    next_due_date=today + datetime.timedelta(days=11),
    payment_method='Net Banking', is_active=True
)

# Financial Goals
FinancialGoal.objects.create(
    user=user, title='6-Month Emergency Reserve',
    target_amount=Decimal('15000.00'), current_amount=Decimal('10500.00'),
    target_date=today + datetime.timedelta(days=180),
    color='#10b981', notes='High Yield Savings Account safety cushion'
)
FinancialGoal.objects.create(
    user=user, title='Tokyo Autumn Journey',
    target_amount=Decimal('4500.00'), current_amount=Decimal('3200.00'),
    target_date=today + datetime.timedelta(days=90),
    color='#ec4899', notes='Flights, hotels, and rail pass'
)
FinancialGoal.objects.create(
    user=user, title='Home Workstation Upgrade',
    target_amount=Decimal('2800.00'), current_amount=Decimal('2100.00'),
    target_date=today + datetime.timedelta(days=45),
    color='#6366f1', notes='OLED monitor & studio ergonomics'
)

print('Successfully seeded demo user "demo" with password "password123"')
