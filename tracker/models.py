from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


# ─── Currency Configuration ───────────────────────────────────────────────────

CURRENCY_CHOICES = [
    ('INR', 'INR — Indian Rupee (₹)'),
    ('USD', 'USD — US Dollar ($)'),
    ('EUR', 'EUR — Euro (€)'),
    ('GBP', 'GBP — British Pound (£)'),
    ('JPY', 'JPY — Japanese Yen (¥)'),
    ('CNY', 'CNY — Chinese Yuan (¥)'),
    ('KRW', 'KRW — South Korean Won (₩)'),
    ('AED', 'AED — UAE Dirham (د.إ)'),
    ('CHF', 'CHF — Swiss Franc (Fr)'),
    ('AUD', 'AUD — Australian Dollar (A$)'),
    ('CAD', 'CAD — Canadian Dollar (C$)'),
    ('SGD', 'SGD — Singapore Dollar (S$)'),
]

CURRENCY_SYMBOLS = {
    'INR': '₹',
    'USD': '$',
    'EUR': '€',
    'GBP': '£',
    'JPY': '¥',
    'CNY': '¥',
    'KRW': '₩',
    'AED': 'د.إ',
    'CHF': 'Fr',
    'AUD': 'A$',
    'CAD': 'C$',
    'SGD': 'S$',
}


# ─── User Profile ─────────────────────────────────────────────────────────────

class UserProfile(models.Model):
    """Stores per-user preferences such as preferred currency."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='INR')

    def __str__(self):
        return f"{self.user.username} profile (currency: {self.currency})"

    @property
    def currency_symbol(self):
        return CURRENCY_SYMBOLS.get(self.currency, self.currency)


# ─── Category ─────────────────────────────────────────────────────────────────

CATEGORY_ICON_CHOICES = [
    ('bi-tag-fill', 'Tag (Default)'),
    ('bi-cup-hot-fill', 'Food & Coffee'),
    ('bi-cart-fill', 'Groceries & Shopping'),
    ('bi-car-front-fill', 'Transport & Fuel'),
    ('bi-house-door-fill', 'Rent & Housing'),
    ('bi-lightning-charge-fill', 'Utilities & Bills'),
    ('bi-film', 'Entertainment & Movies'),
    ('bi-heart-pulse-fill', 'Health & Medical'),
    ('bi-mortarboard-fill', 'Education'),
    ('bi-airplane-fill', 'Travel & Vacation'),
    ('bi-laptop', 'Tech & Gadgets'),
    ('bi-gift-fill', 'Gifts & Charity'),
    ('bi-cash-coin', 'Investments'),
    ('bi-shield-check', 'Insurance'),
    ('bi-three-dots', 'Other / Misc'),
]

CATEGORY_COLOR_CHOICES = [
    ('#6c63ff', 'Indigo / Purple'),
    ('#3b82f6', 'Sky Blue'),
    ('#10b981', 'Emerald Green'),
    ('#f59e0b', 'Amber Gold'),
    ('#ef4444', 'Coral Red'),
    ('#ec4899', 'Rose Pink'),
    ('#8b5cf6', 'Violet'),
    ('#14b8a6', 'Teal'),
    ('#64748b', 'Slate Grey'),
]

PAYMENT_METHOD_CHOICES = [
    ('UPI / Card', 'UPI / Debit Card'),
    ('Credit Card', 'Credit Card'),
    ('Cash', 'Cash'),
    ('Net Banking', 'Net Banking / Wire'),
    ('Other', 'Other'),
]


class Category(models.Model):
    """Expense category belonging to a specific user with custom icon and color."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='categories')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, default='')
    icon = models.CharField(max_length=50, choices=CATEGORY_ICON_CHOICES, default='bi-tag-fill', blank=True)
    color = models.CharField(max_length=20, choices=CATEGORY_COLOR_CHOICES, default='#6c63ff', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'name')
        ordering = ['name']
        verbose_name_plural = 'Categories'
        indexes = [
            models.Index(fields=['user', 'name']),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.icon:
            self.icon = 'bi-tag-fill'
        if not self.color:
            self.color = '#6c63ff'
        super().save(*args, **kwargs)


# ─── Budget ───────────────────────────────────────────────────────────────────

class Budget(models.Model):
    """Monthly budget limit for a user's category."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='budgets')
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='budgets')
    monthly_limit = models.DecimalField(max_digits=10, decimal_places=2)
    month_year = models.DateField(help_text='Set to the first day of the month this budget applies to.')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'category', 'month_year')
        ordering = ['-month_year']
        indexes = [
            models.Index(fields=['user', 'month_year']),
        ]

    def __str__(self):
        return f"{self.category.name} - {self.month_year.strftime('%B %Y')} ({self.monthly_limit})"


# ─── Expense ──────────────────────────────────────────────────────────────────

class Expense(models.Model):
    """An individual expense logged by a user."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='expenses')
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='expenses')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateField(default=timezone.now)
    notes = models.TextField(blank=True, default='')
    payment_method = models.CharField(max_length=30, choices=PAYMENT_METHOD_CHOICES, default='UPI / Card', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-created_at']
        indexes = [
            models.Index(fields=['user', 'date']),
            models.Index(fields=['user', 'category', 'date']),
        ]

    def __str__(self):
        return f"{self.category.name}: {self.amount} on {self.date}"

    def save(self, *args, **kwargs):
        if not self.payment_method:
            self.payment_method = 'UPI / Card'
        super().save(*args, **kwargs)


# ─── Income (Cash Flow Tracking) ──────────────────────────────────────────────

INCOME_SOURCE_CHOICES = [
    ('Salary', 'Salary / Primary Job'),
    ('Freelance', 'Freelance / Consulting'),
    ('Business', 'Business / Sales'),
    ('Investments', 'Investments / Dividends'),
    ('Rental', 'Rental Income'),
    ('Gifts', 'Gifts / Bonus'),
    ('Other', 'Other Income'),
]


class Income(models.Model):
    """Income entry logged by a user for cash flow and savings rate calculations."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='incomes')
    source = models.CharField(max_length=50, choices=INCOME_SOURCE_CHOICES, default='Salary')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateField(default=timezone.now)
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-created_at']
        indexes = [
            models.Index(fields=['user', 'date']),
        ]

    def __str__(self):
        return f"{self.source}: +{self.amount} on {self.date}"


# ─── Recurring Subscriptions & Fixed Bills ────────────────────────────────────

SUBSCRIPTION_CYCLE_CHOICES = [
    ('monthly', 'Monthly'),
    ('yearly', 'Yearly'),
    ('quarterly', 'Quarterly'),
]


class Subscription(models.Model):
    """Tracks recurring subscriptions and bills with upcoming due date notifications."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='subscriptions')
    name = models.CharField(max_length=100)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='subscriptions')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    billing_cycle = models.CharField(max_length=20, choices=SUBSCRIPTION_CYCLE_CHOICES, default='monthly')
    next_due_date = models.DateField()
    payment_method = models.CharField(max_length=30, choices=PAYMENT_METHOD_CHOICES, default='Credit Card')
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['next_due_date', 'name']

    def __str__(self):
        return f"{self.name} ({self.amount} / {self.billing_cycle})"

    @property
    def days_until_due(self):
        today = timezone.now().date()
        return (self.next_due_date - today).days


# ─── Financial Goals Tracker ──────────────────────────────────────────────────

class FinancialGoal(models.Model):
    """Tracks personal financial savings milestones."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='goals')
    title = models.CharField(max_length=100)
    target_amount = models.DecimalField(max_digits=10, decimal_places=2)
    current_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    target_date = models.DateField(null=True, blank=True)
    icon = models.CharField(max_length=50, default='bi-bullseye')
    color = models.CharField(max_length=20, default='#10b981')
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['target_date', '-created_at']

    def __str__(self):
        return f"{self.title}: {self.current_amount} / {self.target_amount}"

    @property
    def percent_achieved(self):
        if self.target_amount <= 0:
            return 0
        p = (self.current_amount / self.target_amount) * 100
        return min(float(p), 100.0)

    @property
    def remaining_amount(self):
        return max(self.target_amount - self.current_amount, 0)


