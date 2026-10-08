from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from decimal import Decimal

DEFAULT_CATEGORIES = [
    'Food & Dining',
    'Groceries',
    'Transportation',
    'Housing & Utilities',
    'Entertainment',
    'Shopping',
    'Healthcare',
    'Travel',
    'Education',
    'Personal Care',
    'Bills & Services',
    'Other',
]

CATEGORY_CHOICES = [(cat, cat) for cat in DEFAULT_CATEGORIES]

class Expense(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='expenses')
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    category = models.CharField(max_length=100, default='Other')
    description = models.TextField(blank=True, default='')
    vendor = models.CharField(max_length=255, blank=True, default='')
    date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.user.username}'s {self.category} expense of ₹{self.amount} on {self.date}"

class Budget(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='budgets')
    month = models.PositiveSmallIntegerField()
    year = models.PositiveSmallIntegerField()
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'month', 'year')
        ordering = ['-year', '-month']

    def __str__(self):
        return f"{self.user.username} Budget ({self.month}/{self.year}): ₹{self.amount}"