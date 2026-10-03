from django.contrib import admin
from .models import Category, Budget, Expense


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'description', 'created_at')
    list_filter = ('user',)
    search_fields = ('name', 'user__username')


@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
    list_display = ('category', 'user', 'monthly_limit', 'month_year')
    list_filter = ('user', 'month_year')
    search_fields = ('category__name', 'user__username')


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ('category', 'user', 'amount', 'date', 'notes')
    list_filter = ('user', 'category', 'date')
    search_fields = ('category__name', 'user__username', 'notes')
