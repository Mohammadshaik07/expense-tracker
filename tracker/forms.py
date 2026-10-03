from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import (
    Category, Budget, Expense, UserProfile,
    Income, Subscription, FinancialGoal,
    CATEGORY_ICON_CHOICES, CATEGORY_COLOR_CHOICES, PAYMENT_METHOD_CHOICES
)
import datetime


class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'


class CategoryChoiceField(forms.ModelChoiceField):
    """
    Custom choice field that accepts either category primary keys (integers)
    or category names (strings), and resolves them strictly within the user's scope.
    If a category name is provided and does not exist yet for this user, it automatically creates it.
    """
    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def to_python(self, value):
        if value in self.empty_values:
            return None
        # Handle Category instance directly
        if isinstance(value, Category):
            return value
        # Try integer ID lookup
        if isinstance(value, int) or (isinstance(value, str) and value.isdigit()):
            try:
                return self.queryset.get(pk=int(value))
            except (self.queryset.model.DoesNotExist, ValueError):
                pass
        # Try category name lookup (case-insensitive)
        if isinstance(value, str) and value.strip():
            cat = self.queryset.filter(name__iexact=value.strip()).first()
            if cat:
                return cat
            # If not found and user is provided, create the category automatically
            if self.user and self.user.is_authenticated:
                cat, _ = Category.objects.get_or_create(
                    user=self.user,
                    name=value.strip(),
                    defaults={'description': ''}
                )
                return cat
        return super().to_python(value)


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ('name', 'icon', 'color', 'description')
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Dining, Transport, Rent'}),
            'icon': forms.Select(attrs={'class': 'form-select'}),
            'color': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Optional description'}),
        }

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        if 'icon' in self.fields:
            self.fields['icon'].required = False
        if 'color' in self.fields:
            self.fields['color'].required = False

    def clean_name(self):
        name = self.cleaned_data.get('name', '').strip()
        if not name:
            raise forms.ValidationError('Category name cannot be empty.')
        if self.user:
            qs = Category.objects.filter(user=self.user, name__iexact=name)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError(f'You already have a category named "{name}".')
        return name


class BudgetForm(forms.ModelForm):
    month_year = forms.DateField(
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'month'}),
        input_formats=['%Y-%m', '%Y-%m-%d'],
        help_text='Select the month and year for this budget.'
    )

    class Meta:
        model = Budget
        fields = ('category', 'monthly_limit', 'month_year')
        widgets = {
            'monthly_limit': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01', 'placeholder': '0.00'}),
        }

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        qs = Category.objects.filter(user=user) if user else Category.objects.none()
        self.fields['category'] = CategoryChoiceField(
            queryset=qs,
            user=user,
            widget=forms.Select(attrs={'class': 'form-select'})
        )

    def clean_monthly_limit(self):
        value = self.cleaned_data.get('monthly_limit')
        if value is not None and value <= 0:
            raise forms.ValidationError('Monthly limit must be a positive amount.')
        return value

    def clean_month_year(self):
        """Normalize to the first day of the given month."""
        value = self.cleaned_data.get('month_year')
        if value:
            return value.replace(day=1)
        return value

    def clean(self):
        cleaned_data = super().clean()
        category = cleaned_data.get('category')
        month_year = cleaned_data.get('month_year')
        if category and month_year and self.user:
            month_start = month_year.replace(day=1)
            qs = Budget.objects.filter(user=self.user, category=category, month_year=month_start)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError(
                    f'A budget for {category.name} in {month_start.strftime("%B %Y")} already exists. '
                    'You can edit the existing budget from the budget list.'
                )
        return cleaned_data


class ExpenseForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields = ('amount', 'date', 'category', 'payment_method', 'notes')
        widgets = {
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01', 'placeholder': '0.00'}),
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'payment_method': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Merchant, description, or notes…'}),
        }

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        if 'payment_method' in self.fields:
            self.fields['payment_method'].required = False
        qs = Category.objects.filter(user=user) if user else Category.objects.none()
        self.fields['category'] = CategoryChoiceField(
            queryset=qs,
            user=user,
            widget=forms.Select(attrs={'class': 'form-select'})
        )

    def clean_amount(self):
        value = self.cleaned_data.get('amount')
        if value is not None and value <= 0:
            raise forms.ValidationError('Expense amount must be greater than zero.')
        return value


class IncomeForm(forms.ModelForm):
    """Form to record income streams for accurate cash flow analysis."""
    class Meta:
        model = Income
        fields = ('source', 'amount', 'date', 'notes')
        widgets = {
            'source': forms.Select(attrs={'class': 'form-select'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01', 'placeholder': '0.00'}),
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Employer, client, or memo…'}),
        }

    def clean_amount(self):
        value = self.cleaned_data.get('amount')
        if value is not None and value <= 0:
            raise forms.ValidationError('Income amount must be greater than zero.')
        return value


class SubscriptionForm(forms.ModelForm):
    """Form to manage recurring subscriptions, software licenses, and utility bills."""
    class Meta:
        model = Subscription
        fields = ('name', 'category', 'amount', 'billing_cycle', 'next_due_date', 'payment_method', 'is_active', 'notes')
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Netflix, Spotify, AWS, Gym, Wifi'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01', 'placeholder': '0.00'}),
            'billing_cycle': forms.Select(attrs={'class': 'form-select'}),
            'next_due_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'payment_method': forms.Select(attrs={'class': 'form-select'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Account info or renewal notes…'}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user:
            self.fields['category'].queryset = Category.objects.filter(user=user)
        self.fields['category'].widget.attrs['class'] = 'form-select'

    def clean_amount(self):
        value = self.cleaned_data.get('amount')
        if value is not None and value <= 0:
            raise forms.ValidationError('Subscription cost must be greater than zero.')
        return value


class FinancialGoalForm(forms.ModelForm):
    """Form to create or update personal savings goals."""
    class Meta:
        model = FinancialGoal
        fields = ('title', 'target_amount', 'current_amount', 'target_date', 'color', 'notes')
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Emergency Fund, New Laptop, Japan Trip'}),
            'target_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01', 'placeholder': '0.00'}),
            'current_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.00', 'placeholder': '0.00'}),
            'target_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'color': forms.Select(choices=CATEGORY_COLOR_CHOICES, attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Why are you saving for this?'}),
        }

    def clean_target_amount(self):
        value = self.cleaned_data.get('target_amount')
        if value is not None and value <= 0:
            raise forms.ValidationError('Target goal amount must be greater than zero.')
        return value


class GoalContributionForm(forms.Form):
    """Form to add money towards a savings goal."""
    amount = forms.DecimalField(
        max_digits=10, decimal_places=2, min_value=0.01,
        widget=forms.NumberInput(attrs={'class': 'form-control form-control-lg', 'step': '0.01', 'placeholder': '0.00'})
    )


class CSVImportForm(forms.Form):
    """Form for bulk uploading bank statements or transaction CSV files."""
    csv_file = forms.FileField(
        label='Select CSV File',
        help_text='File must be a UTF-8 encoded .csv with columns: Date, Category, Amount, Notes (Payment Method is optional)',
        widget=forms.FileInput(attrs={'class': 'form-control', 'accept': '.csv'})
    )


class CurrencyForm(forms.ModelForm):
    """Form for selecting the user's preferred display currency."""
    class Meta:
        model = UserProfile
        fields = ('currency',)
        widgets = {
            'currency': forms.Select(attrs={'class': 'form-select form-select-lg'}),
        }
        labels = {
            'currency': 'Preferred Currency',
        }


