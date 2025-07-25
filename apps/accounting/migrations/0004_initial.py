# Generated by Django 5.2.3 on 2025-06-28 09:12

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('accounting', '0003_initial'),
        ('branches', '0001_initial'),
        ('crm', '0001_initial'),
        ('sales', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='giftcardredemption',
            name='order',
            field=models.ForeignKey(blank=True, help_text='Related order (if applicable)', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='gift_card_redemptions', to='sales.order', verbose_name='order'),
        ),
        migrations.AddField(
            model_name='giftcardredemption',
            name='redeemed_by',
            field=models.ForeignKey(blank=True, help_text='User who processed the redemption', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='gift_card_redemptions', to=settings.AUTH_USER_MODEL, verbose_name='redeemed by'),
        ),
        migrations.AddField(
            model_name='revenue',
            name='branch',
            field=models.ForeignKey(help_text='Branch where revenue was generated', on_delete=django.db.models.deletion.PROTECT, related_name='revenues', to='branches.branch', verbose_name='branch'),
        ),
        migrations.AddField(
            model_name='revenue',
            name='created_by',
            field=models.ForeignKey(help_text='User who created this revenue', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_revenues', to=settings.AUTH_USER_MODEL, verbose_name='created by'),
        ),
        migrations.AddField(
            model_name='revenue',
            name='customer',
            field=models.ForeignKey(blank=True, help_text='Customer associated with this revenue (if applicable)', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='revenues', to='crm.customer', verbose_name='customer'),
        ),
        migrations.AddField(
            model_name='revenue',
            name='deleted_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='deleted_%(class)ss', to=settings.AUTH_USER_MODEL, verbose_name='deleted by'),
        ),
        migrations.AddField(
            model_name='revenue',
            name='last_modified_by',
            field=models.ForeignKey(help_text='User who last modified this revenue', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='modified_revenues', to=settings.AUTH_USER_MODEL, verbose_name='last modified by'),
        ),
        migrations.AddField(
            model_name='revenueaccount',
            name='deleted_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='deleted_%(class)ss', to=settings.AUTH_USER_MODEL, verbose_name='deleted by'),
        ),
        migrations.AddField(
            model_name='revenueaccount',
            name='parent',
            field=models.ForeignKey(blank=True, help_text='Parent account (for hierarchical accounts)', null=True, on_delete=django.db.models.deletion.PROTECT, related_name='subaccounts', to='accounting.revenueaccount', verbose_name='parent account'),
        ),
        migrations.AddField(
            model_name='revenuecategory',
            name='default_account',
            field=models.ForeignKey(blank=True, help_text='Default revenue account for this category', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='default_categories', to='accounting.revenueaccount', verbose_name='default account'),
        ),
        migrations.AddField(
            model_name='revenuecategory',
            name='deleted_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='deleted_%(class)ss', to=settings.AUTH_USER_MODEL, verbose_name='deleted by'),
        ),
        migrations.AddField(
            model_name='revenuecategory',
            name='parent',
            field=models.ForeignKey(blank=True, help_text='Parent category (if this is a subcategory)', null=True, on_delete=django.db.models.deletion.PROTECT, related_name='subcategories', to='accounting.revenuecategory', verbose_name='parent'),
        ),
        migrations.AddField(
            model_name='revenue',
            name='category',
            field=models.ForeignKey(help_text='Revenue category', on_delete=django.db.models.deletion.PROTECT, related_name='revenues', to='accounting.revenuecategory', verbose_name='category'),
        ),
        migrations.AddConstraint(
            model_name='expenseaccount',
            constraint=models.UniqueConstraint(fields=('name', 'parent'), name='unique_expense_account_name_per_parent'),
        ),
        migrations.AddConstraint(
            model_name='expensecategory',
            constraint=models.UniqueConstraint(fields=('name', 'parent'), name='unique_category_name_per_parent'),
        ),
        migrations.AddIndex(
            model_name='expense',
            index=models.Index(fields=['expense_date'], name='accounting__expense_7b88ca_idx'),
        ),
        migrations.AddIndex(
            model_name='expense',
            index=models.Index(fields=['category'], name='accounting__categor_29f01d_idx'),
        ),
        migrations.AddIndex(
            model_name='expense',
            index=models.Index(fields=['currency'], name='accounting__currenc_032ac6_idx'),
        ),
        migrations.AddIndex(
            model_name='giftcard',
            index=models.Index(fields=['code'], name='giftcard_code_idx'),
        ),
        migrations.AddIndex(
            model_name='giftcard',
            index=models.Index(fields=['status'], name='giftcard_status_idx'),
        ),
        migrations.AddIndex(
            model_name='giftcard',
            index=models.Index(fields=['expiry_date'], name='giftcard_expiry_idx'),
        ),
        migrations.AddConstraint(
            model_name='revenueaccount',
            constraint=models.UniqueConstraint(fields=('name', 'parent'), name='unique_revenue_account_name_per_parent'),
        ),
        migrations.AddIndex(
            model_name='revenue',
            index=models.Index(fields=['revenue_date'], name='accounting__revenue_546c0b_idx'),
        ),
        migrations.AddIndex(
            model_name='revenue',
            index=models.Index(fields=['category'], name='accounting__categor_2886eb_idx'),
        ),
        migrations.AddIndex(
            model_name='revenue',
            index=models.Index(fields=['status'], name='accounting__status_347045_idx'),
        ),
    ]
