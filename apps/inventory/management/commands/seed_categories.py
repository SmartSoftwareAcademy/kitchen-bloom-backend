from django.core.management.base import BaseCommand
from apps.inventory.models import Category

class Command(BaseCommand):
    help = 'Seed common bar/restaurant categories (menu and ingredient/product categories)'

    def handle(self, *args, **options):
        
        categories_data = [
            # Menu Categories
            {
                'name': 'Appetizers',
                'description': 'Starters and small plates',
                'is_menu_category': True,
                'is_ingredient_category': False,
                'display_order': 1
            },
            {
                'name': 'Salads',
                'description': 'Fresh salads and greens',
                'is_menu_category': True,
                'is_ingredient_category': False,
                'display_order': 2
            },
            {
                'name': 'Main Courses',
                'description': 'Primary dishes and entrees',
                'is_menu_category': True,
                'is_ingredient_category': False,
                'display_order': 3
            },
            {
                'name': 'Pasta & Rice',
                'description': 'Pasta dishes and rice specialties',
                'is_menu_category': True,
                'is_ingredient_category': False,
                'display_order': 4
            },
            {
                'name': 'Grilled Items',
                'description': 'Grilled meats and seafood',
                'is_menu_category': True,
                'is_ingredient_category': False,
                'display_order': 5
            },
            {
                'name': 'Desserts',
                'description': 'Sweet treats and desserts',
                'is_menu_category': True,
                'is_ingredient_category': False,
                'display_order': 6
            },
            {
                'name': 'Beverages',
                'description': 'Drinks and beverages',
                'is_menu_category': True,
                'is_ingredient_category': False,
                'display_order': 7
            },
            # Ingredient/Product Categories
            {
                'name': 'Vegetables',
                'description': 'Fresh vegetables and produce',
                'is_menu_category': False,
                'is_ingredient_category': True,
                'display_order': 8
            },
            {
                'name': 'Meat & Poultry',
                'description': 'Fresh meat and poultry',
                'is_menu_category': False,
                'is_ingredient_category': True,
                'display_order': 9
            },
            {
                'name': 'Seafood',
                'description': 'Fresh seafood and fish',
                'is_menu_category': False,
                'is_ingredient_category': True,
                'display_order': 10
            },
            {
                'name': 'Dairy',
                'description': 'Dairy products and eggs',
                'is_menu_category': False,
                'is_ingredient_category': True,
                'display_order': 11
            },
            {
                'name': 'Pantry',
                'description': 'Dry goods and pantry items',
                'is_menu_category': False,
                'is_ingredient_category': True,
                'display_order': 12
            },
        ]

        for cat_data in categories_data:
            category, created = Category.objects.get_or_create(
                name=cat_data['name'],
                defaults={
                    'description': cat_data['description'],
                    'is_menu_category': cat_data['is_menu_category'],
                    'is_ingredient_category': cat_data['is_ingredient_category'],
                    'display_order': cat_data['display_order']
                }
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created category: {category.name}"))
            else:
                self.stdout.write(f"Category already exists: {category.name}")

        self.stdout.write(self.style.SUCCESS('Category seeding complete.')) 