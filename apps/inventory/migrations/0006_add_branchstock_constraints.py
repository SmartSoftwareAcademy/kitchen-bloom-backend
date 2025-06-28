from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0005_alter_branchstock_options_and_more'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='branchstock',
            unique_together=set(),
        ),
        migrations.AddConstraint(
            model_name='branchstock',
            constraint=models.UniqueConstraint(
                condition=models.Q(('product__isnull', False)),
                fields=('product', 'branch'),
                name='unique_product_branch_stock',
                violation_error_message='A stock entry for this product already exists for this branch.'
            ),
        ),
        migrations.AddConstraint(
            model_name='branchstock',
            constraint=models.UniqueConstraint(
                condition=models.Q(('menu_item__isnull', False)),
                fields=('menu_item', 'branch'),
                name='unique_menu_item_branch_stock',
                violation_error_message='A stock entry for this menu item already exists for this branch.'
            ),
        ),
    ]
