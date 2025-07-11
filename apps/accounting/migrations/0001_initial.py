# Generated by Django 5.2.3 on 2025-06-28 09:12

import django.core.validators
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Expense',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('deleted_at', models.DateTimeField(blank=True, null=True, verbose_name='deleted at')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='created at')),
                ('updated_at', models.DateTimeField(auto_now=True, db_index=True, verbose_name='updated at')),
                ('expense_number', models.CharField(db_index=True, default=None, editable=False, help_text='Auto-generated expense number', max_length=20, unique=True, verbose_name='expense number')),
                ('expense_date', models.DateField(default=django.utils.timezone.now, verbose_name='expense date')),
                ('amount', models.DecimalField(decimal_places=2, help_text='Total amount of the expense', max_digits=14, validators=[django.core.validators.MinValueValidator(0.01)], verbose_name='amount')),
                ('currency', models.CharField(default='KES', help_text='Currency code (e.g., KES, USD)', max_length=3, verbose_name='currency')),
                ('description', models.TextField(help_text='Detailed description of the expense', verbose_name='description')),
                ('payment_method', models.CharField(choices=[('cash', 'Cash'), ('bank_transfer', 'Bank Transfer'), ('check', 'Check'), ('card', 'Card'), ('mpesa', 'M-Pesa'), ('paypal', 'PayPal'), ('online_payment', 'Online Payment'), ('loyalty_points', 'Loyalty Points'), ('gift_card', 'Gift Card'), ('mobile_money', 'Mobile Money'), ('other', 'Other')], default='cash', help_text='How was this expense paid?', max_length=20, verbose_name='payment method')),
                ('payment_reference', models.CharField(blank=True, help_text='Transaction ID, check number, or other reference', max_length=100, verbose_name='payment reference')),
                ('payment_date', models.DateField(blank=True, help_text='When the payment was made', null=True, verbose_name='payment date')),
                ('status', models.CharField(choices=[('draft', 'Draft'), ('submitted', 'Submitted for Approval'), ('approved', 'Approved'), ('paid', 'Paid'), ('rejected', 'Rejected'), ('cancelled', 'Cancelled')], default='draft', help_text='Current status of the expense', max_length=20, verbose_name='status')),
                ('approved_at', models.DateTimeField(blank=True, help_text='When the expense was approved', null=True, verbose_name='approved at')),
                ('expense_type', models.CharField(choices=[('operational', 'Operational'), ('payroll', 'Payroll'), ('inventory', 'Inventory'), ('marketing', 'Marketing'), ('utilities', 'Utilities'), ('rent', 'Rent'), ('maintenance', 'Maintenance'), ('travel', 'Travel'), ('other', 'Other')], default='operational', help_text='Type of expense', max_length=20, verbose_name='expense type')),
                ('receipt', models.FileField(blank=True, help_text='Expense receipt or proof of payment', null=True, upload_to='expenses/receipts/%Y/%m/%d/', verbose_name='receipt')),
                ('notes', models.TextField(blank=True, help_text='Additional notes about the expense', verbose_name='notes')),
            ],
            options={
                'verbose_name': 'expense',
                'verbose_name_plural': 'expenses',
                'ordering': ['-expense_date', '-created_at'],
            },
        ),
        migrations.CreateModel(
            name='ExpenseAccount',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('deleted_at', models.DateTimeField(blank=True, null=True, verbose_name='deleted at')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='created at')),
                ('updated_at', models.DateTimeField(auto_now=True, db_index=True, verbose_name='updated at')),
                ('name', models.CharField(help_text='Name of the expense account', max_length=100, verbose_name='account name')),
                ('code', models.CharField(help_text='Unique code for the account', max_length=20, unique=True, verbose_name='account code')),
                ('account_type', models.CharField(choices=[('sales', 'Sales'), ('operating', 'Operating Expenses'), ('non_operating', 'Non-Operating Expenses'), ('other', 'Other Expenses')], default='sales', help_text='Type of expense account', max_length=20, verbose_name='account type')),
                ('description', models.TextField(blank=True, help_text='Detailed description of the account', verbose_name='description')),
                ('is_active', models.BooleanField(default=True, help_text='Whether this account is active', verbose_name='is active')),
            ],
            options={
                'verbose_name': 'expense account',
                'verbose_name_plural': 'expense accounts',
                'ordering': ['code'],
            },
        ),
        migrations.CreateModel(
            name='ExpenseCategory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('deleted_at', models.DateTimeField(blank=True, null=True, verbose_name='deleted at')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='created at')),
                ('updated_at', models.DateTimeField(auto_now=True, db_index=True, verbose_name='updated at')),
                ('name', models.CharField(max_length=100, verbose_name='name')),
                ('description', models.TextField(blank=True, verbose_name='description')),
                ('is_active', models.BooleanField(default=True, verbose_name='is active')),
            ],
            options={
                'verbose_name': 'expense category',
                'verbose_name_plural': 'expense categories',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='GiftCard',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('deleted_at', models.DateTimeField(blank=True, null=True, verbose_name='deleted at')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='created at')),
                ('updated_at', models.DateTimeField(auto_now=True, db_index=True, verbose_name='updated at')),
                ('code', models.CharField(db_index=True, help_text='Unique code for the gift card', max_length=20, unique=True, verbose_name='gift card code')),
                ('initial_value', models.DecimalField(decimal_places=2, help_text='Original value of the gift card', max_digits=14, validators=[django.core.validators.MinValueValidator(0.01)], verbose_name='initial value')),
                ('current_balance', models.DecimalField(decimal_places=2, help_text='Current available balance', max_digits=14, validators=[django.core.validators.MinValueValidator(0)], verbose_name='current balance')),
                ('currency', models.CharField(choices=[('KES', 'Kenyan Shilling (KES)'), ('USD', 'US Dollar (USD)')], default='KES', help_text='Currency of the gift card value', max_length=3, verbose_name='currency')),
                ('status', models.CharField(choices=[('active', 'Active'), ('redeemed', 'Redeemed'), ('expired', 'Expired'), ('voided', 'Voided')], db_index=True, default='active', help_text='Current status of the gift card', max_length=20, verbose_name='status')),
                ('issue_date', models.DateTimeField(default=django.utils.timezone.now, help_text='When the gift card was issued', verbose_name='issue date')),
                ('expiry_date', models.DateTimeField(blank=True, help_text='When the gift card expires (optional)', null=True, verbose_name='expiry date')),
                ('notes', models.TextField(blank=True, help_text='Any additional notes about this gift card', verbose_name='notes')),
            ],
            options={
                'verbose_name': 'gift card',
                'verbose_name_plural': 'gift cards',
                'ordering': ['-issue_date', 'code'],
            },
        ),
        migrations.CreateModel(
            name='GiftCardRedemption',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('deleted_at', models.DateTimeField(blank=True, null=True, verbose_name='deleted at')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='created at')),
                ('updated_at', models.DateTimeField(auto_now=True, db_index=True, verbose_name='updated at')),
                ('amount', models.DecimalField(decimal_places=2, help_text='Amount redeemed or refunded', max_digits=12, verbose_name='amount')),
                ('redemption_type', models.CharField(choices=[('purchase', 'Purchase'), ('redemption', 'Redemption'), ('void', 'Void'), ('refund', 'Refund')], default='redemption', help_text='Type of redemption transaction', max_length=20, verbose_name='redemption type')),
                ('balance_after', models.DecimalField(decimal_places=2, help_text='Gift card balance after this transaction', max_digits=12, verbose_name='balance after')),
                ('notes', models.TextField(blank=True, help_text='Additional notes about this redemption', verbose_name='notes')),
            ],
            options={
                'verbose_name': 'gift card redemption',
                'verbose_name_plural': 'gift card redemptions',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='Revenue',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('deleted_at', models.DateTimeField(blank=True, null=True, verbose_name='deleted at')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='created at')),
                ('updated_at', models.DateTimeField(auto_now=True, db_index=True, verbose_name='updated at')),
                ('revenue_number', models.CharField(db_index=True, default=None, editable=False, help_text='Auto-generated revenue number', max_length=20, unique=True, verbose_name='revenue number')),
                ('revenue_date', models.DateField(default=django.utils.timezone.now, verbose_name='revenue date')),
                ('amount', models.DecimalField(decimal_places=2, help_text='Total amount of the revenue', max_digits=14, validators=[django.core.validators.MinValueValidator(0.01)], verbose_name='amount')),
                ('currency', models.CharField(default='KES', help_text='Currency code (e.g., KES, USD)', max_length=3, verbose_name='currency')),
                ('description', models.TextField(help_text='Detailed description of the revenue', verbose_name='description')),
                ('revenue_type', models.CharField(choices=[('sales', 'Sales'), ('subscriptions', 'Subscriptions'), ('other', 'Other')], default='sales', help_text='Type of revenue', max_length=20, verbose_name='revenue type')),
                ('receipt', models.FileField(blank=True, help_text='Revenue receipt or proof of payment', null=True, upload_to='revenues/receipts/%Y/%m/%d/', verbose_name='receipt')),
                ('notes', models.TextField(blank=True, help_text='Additional notes about the revenue', verbose_name='notes')),
                ('status', models.CharField(choices=[('draft', 'Draft'), ('submitted', 'Submitted for Approval'), ('approved', 'Approved'), ('paid', 'Paid'), ('rejected', 'Rejected'), ('cancelled', 'Cancelled')], default='draft', help_text='Status of the revenue', max_length=20, verbose_name='status')),
                ('payment_date', models.DateField(blank=True, help_text='Date when the revenue was paid', null=True, verbose_name='payment date')),
                ('payment_method', models.CharField(choices=[('cash', 'Cash'), ('cheque', 'Cheque'), ('bank_transfer', 'Bank Transfer'), ('mpesa', 'M-Pesa'), ('card', 'Card'), ('paypal', 'PayPal'), ('online_payment', 'Online Payment'), ('loyalty_points', 'Loyalty Points'), ('gift_card', 'Gift Card'), ('other', 'Other')], default='cash', help_text='How was this revenue paid?', max_length=20, verbose_name='payment method')),
                ('payment_reference', models.CharField(blank=True, help_text='Transaction ID, check number, or other reference', max_length=100, verbose_name='payment reference')),
            ],
            options={
                'verbose_name': 'revenue',
                'verbose_name_plural': 'revenues',
                'ordering': ['-revenue_date', '-created_at'],
            },
        ),
        migrations.CreateModel(
            name='RevenueAccount',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('deleted_at', models.DateTimeField(blank=True, null=True, verbose_name='deleted at')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='created at')),
                ('updated_at', models.DateTimeField(auto_now=True, db_index=True, verbose_name='updated at')),
                ('name', models.CharField(help_text='Name of the revenue account', max_length=100, verbose_name='account name')),
                ('code', models.CharField(help_text='Unique code for the account', max_length=20, unique=True, verbose_name='account code')),
                ('account_type', models.CharField(choices=[('sales', 'Sales'), ('service', 'Service'), ('interest', 'Interest Income'), ('other', 'Other Income')], default='sales', help_text='Type of revenue account', max_length=20, verbose_name='account type')),
                ('description', models.TextField(blank=True, help_text='Detailed description of the account', verbose_name='description')),
                ('is_active', models.BooleanField(default=True, help_text='Whether this account is active', verbose_name='is active')),
            ],
            options={
                'verbose_name': 'revenue account',
                'verbose_name_plural': 'revenue accounts',
                'ordering': ['code'],
            },
        ),
        migrations.CreateModel(
            name='RevenueCategory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('deleted_at', models.DateTimeField(blank=True, null=True, verbose_name='deleted at')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='created at')),
                ('updated_at', models.DateTimeField(auto_now=True, db_index=True, verbose_name='updated at')),
                ('name', models.CharField(help_text='Name of the revenue category', max_length=100, verbose_name='name')),
                ('description', models.TextField(blank=True, help_text='Detailed description of the category', verbose_name='description')),
                ('is_active', models.BooleanField(default=True, help_text='Whether this category is active', verbose_name='is active')),
            ],
            options={
                'verbose_name': 'revenue category',
                'verbose_name_plural': 'revenue categories',
                'ordering': ['name'],
            },
        ),
    ]
