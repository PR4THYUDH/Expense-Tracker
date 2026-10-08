from django import forms
from .models import Expense, Budget, CATEGORY_CHOICES
from datetime import date

class ExpenseForm(forms.ModelForm):
    date = forms.DateField(
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'w-full rounded-lg border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-100 text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 py-2.5 px-3 shadow-sm'
        }),
        initial=date.today
    )
    category = forms.ChoiceField(
        choices=CATEGORY_CHOICES,
        widget=forms.Select(attrs={
            'class': 'w-full rounded-lg border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-100 text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 py-2.5 px-3 shadow-sm'
        })
    )
    amount = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=0.01,
        widget=forms.NumberInput(attrs={
            'step': '0.01',
            'placeholder': '0.00',
            'class': 'w-full rounded-lg border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-100 text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 py-2.5 px-3 shadow-sm'
        })
    )
    vendor = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'e.g. Amazon, Uber, Grocery Store',
            'class': 'w-full rounded-lg border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-100 text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 py-2.5 px-3 shadow-sm'
        })
    )
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'rows': 2,
            'placeholder': 'Optional description or notes...',
            'class': 'w-full rounded-lg border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-100 text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 py-2.5 px-3 shadow-sm'
        })
    )

    class Meta:
        model = Expense
        fields = ['amount', 'category', 'vendor', 'date', 'description']

class BudgetForm(forms.ModelForm):
    MONTH_CHOICES = [
        (1, 'January'), (2, 'February'), (3, 'March'), (4, 'April'),
        (5, 'May'), (6, 'June'), (7, 'July'), (8, 'August'),
        (9, 'September'), (10, 'October'), (11, 'November'), (12, 'December')
    ]
    month = forms.ChoiceField(
        choices=MONTH_CHOICES,
        widget=forms.Select(attrs={
            'class': 'w-full rounded-lg border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-100 text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 py-2 px-3 shadow-sm'
        })
    )
    year = forms.IntegerField(
        widget=forms.NumberInput(attrs={
            'class': 'w-full rounded-lg border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-100 text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 py-2 px-3 shadow-sm'
        }),
        initial=date.today().year
    )
    amount = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=0.01,
        widget=forms.NumberInput(attrs={
            'step': '0.01',
            'placeholder': 'Monthly budget amount',
            'class': 'w-full rounded-lg border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-100 text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 py-2 px-3 shadow-sm'
        })
    )

    class Meta:
        model = Budget
        fields = ['month', 'year', 'amount']

class ReceiptUploadForm(forms.Form):
    receipt_image = forms.FileField(
        required=True,
        widget=forms.FileInput(attrs={
            'accept': 'image/jpeg,image/png,image/webp,image/gif',
            'class': 'block w-full text-sm text-slate-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-semibold file:bg-indigo-50 file:text-indigo-700 hover:file:bg-indigo-100 dark:file:bg-indigo-900/40 dark:file:text-indigo-300'
        })
    )

    def clean_receipt_image(self):
        uploaded_file = self.cleaned_data['receipt_image']
        allowed_types = ['image/jpeg', 'image/png', 'image/webp', 'image/gif']
        if uploaded_file.content_type not in allowed_types:
            raise forms.ValidationError("Invalid file type. Please upload a JPEG, PNG, WEBP, or GIF image.")
        if uploaded_file.size > 5 * 1024 * 1024:
            raise forms.ValidationError("File size exceeds 5MB limit. Please upload a smaller receipt image.")
        return uploaded_file