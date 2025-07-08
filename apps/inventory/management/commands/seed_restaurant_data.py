from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from decimal import Decimal, ROUND_HALF_UP
import os
from django.core.files import File
from django.conf import settings

from apps.inventory.models import (
    Category, Product, Supplier, UnitOfMeasure, Menu, MenuItem, Recipe, RecipeIngredient,
    BranchStock, ProductImage, Allergy
)
from apps.branches.models import Branch
from apps.crm.models import Customer
from apps.accounts.models import User
from apps.sales.models import Order, OrderItem
from apps.base.mixins import generate_unique_barcode

class Command(BaseCommand):
    help = 'Seed restaurant-specific data including categories, products, menus, and recipes'

    def add_arguments(self, parser):
        parser.add_argument(
            '--branch-id',
            type=int,
            help='Branch ID to associate data with',
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing data before seeding',
        )

    def handle(self, *args, **options):
        branch_id = options.get('branch_id')
        clear_existing = options.get('clear')

        if clear_existing:
            self.stdout.write('Clearing existing data...')
            MenuItem.objects.all().delete()
            Recipe.objects.all().delete()
            Menu.objects.all().delete()
            OrderItem.objects.all().delete()
            Order.objects.all().delete()
            ProductImage.objects.all().delete()
            Product.objects.all().delete()
            BranchStock.objects.all().delete()
            Category.objects.all().delete()
           

        # Get or create branch
        if branch_id:
            try:
                branch = Branch.objects.get(id=branch_id)
            except Branch.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'Branch with ID {branch_id} not found'))
                return
        else:
            branch = Branch.objects.first()
            if not branch:
                self.stdout.write(self.style.ERROR('No branches found. Please create a branch first.'))
                return

        # Get or create admin user
        admin_user = User.objects.filter(is_superuser=True).first()
        if not admin_user:
            admin_user = User.objects.create_superuser(
                username='admin',
                email='admin@example.com',
                password='admin123'
            )

        with transaction.atomic():
            self.stdout.write('Seeding restaurant data...')
            
            # Create categories with images
            categories = self.create_categories()
            
            # Create units of measure
            units = self.create_units_of_measure()
            
            # Create suppliers
            suppliers = self.create_suppliers()
            
            # Create ingredients (products)
            ingredients = self.create_ingredients(categories, units, suppliers)
            
            # Create beverages
            beverages = self.create_beverages(categories, units, suppliers)
            
            # Create finished products
            finished_products = self.create_finished_products(categories, units, suppliers)
            
            # Create menu
            menu = self.create_menu(branch, admin_user)
            
            # Create menu items with recipes
            self.create_menu_items(menu, categories, ingredients, admin_user)
            
            # Add products to branch stock
            self.create_branch_stock(branch, ingredients + beverages + finished_products)

        self.stdout.write(self.style.SUCCESS('Restaurant data seeded successfully!'))

    def create_categories(self):
        """Create restaurant categories with proper grouping."""
        categories_data = [
            # Menu Categories (for finished dishes)
            {
                'name': 'Appetizers',
                'description': 'Starters and small plates',
                'is_menu_category': True,
                'display_order': 1,
                'image_name': 'appetizers.jpg'
            },
            {
                'name': 'Salads',
                'description': 'Fresh salads and greens',
                'is_menu_category': True,
                'display_order': 2,
                'image_name': 'salads.jpg'
            },
            {
                'name': 'Main Courses',
                'description': 'Primary dishes and entrees',
                'is_menu_category': True,
                'display_order': 3,
                'image_name': 'main-courses.jpg'
            },
            {
                'name': 'Pasta & Rice',
                'description': 'Pasta dishes and rice specialties',
                'is_menu_category': True,
                'display_order': 4,
                'image_name': 'pasta-rice.jpg'
            },
            {
                'name': 'Grilled Items',
                'description': 'Grilled meats and seafood',
                'is_menu_category': True,
                'display_order': 5,
                'image_name': 'grilled.jpg'
            },
            {
                'name': 'Desserts',
                'description': 'Sweet treats and desserts',
                'is_menu_category': True,
                'display_order': 6,
                'image_name': 'desserts.jpg'
            },
            {
                'name': 'Beverages',
                'description': 'Drinks and beverages',
                'is_menu_category': True,
                'display_order': 7,
                'image_name': 'beverages.jpg'
            },
            
            # Ingredient Categories
            {
                'name': 'Vegetables',
                'description': 'Fresh vegetables and produce',
                'is_ingredient_category': True,
                'display_order': 8,
                'image_name': 'vegetables.jpg'
            },
            {
                'name': 'Meat & Poultry',
                'description': 'Fresh meat and poultry',
                'is_ingredient_category': True,
                'display_order': 9,
                'image_name': 'meat-poultry.jpg'
            },
            {
                'name': 'Seafood',
                'description': 'Fresh seafood and fish',
                'is_ingredient_category': True,
                'display_order': 10,
                'image_name': 'seafood.jpg'
            },
            {
                'name': 'Dairy',
                'description': 'Dairy products and eggs',
                'is_ingredient_category': True,
                'display_order': 11,
                'image_name': 'dairy.jpg'
            },
            {
                'name': 'Pantry',
                'description': 'Dry goods and pantry items',
                'is_ingredient_category': True,
                'display_order': 12,
                'image_name': 'pantry.jpg'
            },
        ]

        categories = []
        for cat_data in categories_data:
            category, created = Category.objects.get_or_create(
                name=cat_data['name'],
                defaults={
                    'description': cat_data['description'],
                    'is_menu_category': cat_data.get('is_menu_category', False),
                    'is_ingredient_category': cat_data.get('is_ingredient_category', False),
                    'display_order': cat_data['display_order'],
                    'is_active': True
                }
            )
            categories.append(category)
            
            if created:
                self.stdout.write(f'Created category: {category.name}')

        return categories

    def create_units_of_measure(self):
        """Create units of measure for products."""
        units_data = [
            ('kg', 'Kilogram', 'kg'),
            ('g', 'Gram', 'g'),
            ('L', 'Liter', 'L'),
            ('mL', 'Milliliter', 'mL'),
            ('pcs', 'Piece', 'pcs'),
            ('pack', 'Pack', 'pack'),
            ('bottle', 'Bottle', 'bottle'),
            ('box', 'Box', 'box'),
            ('cup', 'Cup', 'cup'),
        ]

        units = []
        for code, name, symbol in units_data:
            unit, created = UnitOfMeasure.objects.get_or_create(
                code=code,
                defaults={
                    'name': name,
                    'symbol': symbol,
                    'is_fraction_allowed': True
                }
            )
            units.append(unit)
            
            if created:
                self.stdout.write(f'Created unit: {unit.name}')

        return units

    def create_suppliers(self):
        """Create suppliers for products."""
        suppliers_data = [
            {
                'name': 'Fresh Market Suppliers',
                'contact_person': 'John Smith',
                'email': 'john@freshmarket.com',
                'phone': '+1234567890',
                'address': '123 Market St, City, State 12345'
            },
            {
                'name': 'Premium Meats Co.',
                'contact_person': 'Sarah Johnson',
                'email': 'sarah@premiummeats.com',
                'phone': '+1234567891',
                'address': '456 Meat Ave, City, State 12345'
            },
            {
                'name': 'Ocean Fresh Seafood',
                'contact_person': 'Mike Wilson',
                'email': 'mike@oceanfresh.com',
                'phone': '+1234567892',
                'address': '789 Harbor Rd, City, State 12345'
            },
            {
                'name': 'Beverage Distributors',
                'contact_person': 'Lisa Brown',
                'email': 'lisa@beveragedist.com',
                'phone': '+1234567893',
                'address': '321 Drink Blvd, City, State 12345'
            }
        ]

        suppliers = []
        for sup_data in suppliers_data:
            supplier, created = Supplier.objects.get_or_create(
                name=sup_data['name'],
                defaults=sup_data
            )
            suppliers.append(supplier)
            
            if created:
                self.stdout.write(f'Created supplier: {supplier.name}')

        return suppliers

    def create_ingredients(self, categories, units, suppliers):
        """Create ingredient products."""
        ingredients_data = [
            # Vegetables
            {
                'name': 'Fresh Tomatoes',
                'SKU': 'VEG001',
                'category': next(c for c in categories if c.name == 'Vegetables'),
                'unit_of_measure': next(u for u in units if u.code == 'kg'),
                'cost_price': Decimal('2.50'),
                'selling_price': Decimal('3.00'),
                'product_type': 'ingredient',
                'supplier': suppliers[0]
            },
            {
                'name': 'Lettuce',
                'SKU': 'VEG002',
                'category': next(c for c in categories if c.name == 'Vegetables'),
                'unit_of_measure': next(u for u in units if u.code == 'pcs'),
                'cost_price': Decimal('1.20'),
                'selling_price': Decimal('1.50'),
                'product_type': 'ingredient',
                'supplier': suppliers[0]
            },
            {
                'name': 'Onions',
                'SKU': 'VEG003',
                'category': next(c for c in categories if c.name == 'Vegetables'),
                'unit_of_measure': next(u for u in units if u.code == 'kg'),
                'cost_price': Decimal('1.80'),
                'selling_price': Decimal('2.20'),
                'product_type': 'ingredient',
                'supplier': suppliers[0]
            },
            {
                'name': 'Garlic',
                'SKU': 'VEG004',
                'category': next(c for c in categories if c.name == 'Vegetables'),
                'unit_of_measure': next(u for u in units if u.code == 'kg'),
                'cost_price': Decimal('4.00'),
                'selling_price': Decimal('5.00'),
                'product_type': 'ingredient',
                'supplier': suppliers[0]
            },
            
            # Meat & Poultry
            {
                'name': 'Chicken Breast',
                'SKU': 'MEAT001',
                'category': next(c for c in categories if c.name == 'Meat & Poultry'),
                'unit_of_measure': next(u for u in units if u.code == 'kg'),
                'cost_price': Decimal('8.50'),
                'selling_price': Decimal('10.00'),
                'product_type': 'ingredient',
                'supplier': suppliers[1]
            },
            {
                'name': 'Ground Beef',
                'SKU': 'MEAT002',
                'category': next(c for c in categories if c.name == 'Meat & Poultry'),
                'unit_of_measure': next(u for u in units if u.code == 'kg'),
                'cost_price': Decimal('12.00'),
                'selling_price': Decimal('14.00'),
                'product_type': 'ingredient',
                'supplier': suppliers[1]
            },
            {
                'name': 'Pork Chops',
                'SKU': 'MEAT003',
                'category': next(c for c in categories if c.name == 'Meat & Poultry'),
                'unit_of_measure': next(u for u in units if u.code == 'kg'),
                'cost_price': Decimal('10.50'),
                'selling_price': Decimal('12.50'),
                'product_type': 'ingredient',
                'supplier': suppliers[1]
            },
            
            # Seafood
            {
                'name': 'Salmon Fillet',
                'SKU': 'FISH001',
                'category': next(c for c in categories if c.name == 'Seafood'),
                'unit_of_measure': next(u for u in units if u.code == 'kg'),
                'cost_price': Decimal('18.00'),
                'selling_price': Decimal('22.00'),
                'product_type': 'ingredient',
                'supplier': suppliers[2]
            },
            {
                'name': 'Shrimp',
                'SKU': 'FISH002',
                'category': next(c for c in categories if c.name == 'Seafood'),
                'unit_of_measure': next(u for u in units if u.code == 'kg'),
                'cost_price': Decimal('25.00'),
                'selling_price': Decimal('30.00'),
                'product_type': 'ingredient',
                'supplier': suppliers[2]
            },
            
            # Dairy
            {
                'name': 'Milk',
                'SKU': 'DAIRY001',
                'category': next(c for c in categories if c.name == 'Dairy'),
                'unit_of_measure': next(u for u in units if u.code == 'L'),
                'cost_price': Decimal('2.00'),
                'selling_price': Decimal('2.50'),
                'product_type': 'ingredient',
                'supplier': suppliers[0]
            },
            {
                'name': 'Cheese',
                'SKU': 'DAIRY002',
                'category': next(c for c in categories if c.name == 'Dairy'),
                'unit_of_measure': next(u for u in units if u.code == 'kg'),
                'cost_price': Decimal('8.00'),
                'selling_price': Decimal('10.00'),
                'product_type': 'ingredient',
                'supplier': suppliers[0]
            },
            {
                'name': 'Eggs',
                'SKU': 'DAIRY003',
                'category': next(c for c in categories if c.name == 'Dairy'),
                'unit_of_measure': next(u for u in units if u.code == 'pack'),
                'cost_price': Decimal('3.50'),
                'selling_price': Decimal('4.50'),
                'product_type': 'ingredient',
                'supplier': suppliers[0]
            },
            
            # Pantry
            {
                'name': 'Olive Oil',
                'SKU': 'PANTRY001',
                'category': next(c for c in categories if c.name == 'Pantry'),
                'unit_of_measure': next(u for u in units if u.code == 'L'),
                'cost_price': Decimal('6.00'),
                'selling_price': Decimal('8.00'),
                'product_type': 'ingredient',
                'supplier': suppliers[0]
            },
            {
                'name': 'Pasta',
                'SKU': 'PANTRY002',
                'category': next(c for c in categories if c.name == 'Pantry'),
                'unit_of_measure': next(u for u in units if u.code == 'kg'),
                'cost_price': Decimal('3.00'),
                'selling_price': Decimal('4.00'),
                'product_type': 'ingredient',
                'supplier': suppliers[0]
            },
            {
                'name': 'Rice',
                'SKU': 'PANTRY003',
                'category': next(c for c in categories if c.name == 'Pantry'),
                'unit_of_measure': next(u for u in units if u.code == 'kg'),
                'cost_price': Decimal('2.50'),
                'selling_price': Decimal('3.50'),
                'product_type': 'ingredient',
                'supplier': suppliers[0]
            },
        ]
        ingredients = []
        for ing_data in ingredients_data:
            ing_data['barcode'] = generate_unique_barcode('ING')
            # Patch: round prices to 2 decimal places
            ing_data['cost_price'] = Decimal(str(ing_data['cost_price'])).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            ing_data['selling_price'] = Decimal(str(ing_data['selling_price'])).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            ingredient, created = Product.objects.get_or_create(
                SKU=ing_data['SKU'],
                defaults=ing_data
            )
            ingredients.append(ingredient)
            if created:
                self.stdout.write(f'Created ingredient: {ingredient.name}')
        return ingredients

    def create_beverages(self, categories, units, suppliers):
        """Create beverage products."""
        beverages_data = [
            {
                'name': 'Coca Cola',
                'SKU': 'BEV001',
                'category': next(c for c in categories if c.name == 'Beverages'),
                'unit_of_measure': next(u for u in units if u.code == 'bottle'),
                'cost_price': Decimal('0.80'),
                'selling_price': Decimal('2.50'),
                'product_type': 'beverage',
                'supplier': suppliers[3]
            },
            {
                'name': 'Sprite',
                'SKU': 'BEV002',
                'category': next(c for c in categories if c.name == 'Beverages'),
                'unit_of_measure': next(u for u in units if u.code == 'bottle'),
                'cost_price': Decimal('0.80'),
                'selling_price': Decimal('2.50'),
                'product_type': 'beverage',
                'supplier': suppliers[3]
            },
            {
                'name': 'Orange Juice',
                'SKU': 'BEV003',
                'category': next(c for c in categories if c.name == 'Beverages'),
                'unit_of_measure': next(u for u in units if u.code == 'L'),
                'cost_price': Decimal('3.00'),
                'selling_price': Decimal('5.00'),
                'product_type': 'beverage',
                'supplier': suppliers[3]
            },
            {
                'name': 'Coffee',
                'SKU': 'BEV004',
                'category': next(c for c in categories if c.name == 'Beverages'),
                'unit_of_measure': next(u for u in units if u.code == 'cup'),
                'cost_price': Decimal('1.50'),
                'selling_price': Decimal('3.50'),
                'product_type': 'beverage',
                'supplier': suppliers[3]
            },
        ]
        beverages = []
        for bev_data in beverages_data:
            bev_data['barcode'] = generate_unique_barcode('BEV')
            # Patch: round prices to 2 decimal places
            bev_data['cost_price'] = Decimal(str(bev_data['cost_price'])).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            bev_data['selling_price'] = Decimal(str(bev_data['selling_price'])).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            beverage, created = Product.objects.get_or_create(
                SKU=bev_data['SKU'],
                defaults=bev_data
            )
            beverages.append(beverage)
            if created:
                self.stdout.write(f'Created beverage: {beverage.name}')
        return beverages

    def create_finished_products(self, categories, units, suppliers):
        """Create finished product items."""
        finished_products_data = [
            {
                'name': 'Garlic Bread',
                'SKU': 'FIN001',
                'category': next(c for c in categories if c.name == 'Appetizers'),
                'unit_of_measure': next(u for u in units if u.code == 'pcs'),
                'cost_price': Decimal('2.00'),
                'selling_price': Decimal('4.50'),
                'product_type': 'finished_product',
                'supplier': suppliers[0]
            },
            {
                'name': 'French Fries',
                'SKU': 'FIN002',
                'category': next(c for c in categories if c.name == 'Appetizers'),
                'unit_of_measure': next(u for u in units if u.code == 'pack'),
                'cost_price': Decimal('1.50'),
                'selling_price': Decimal('3.50'),
                'product_type': 'finished_product',
                'supplier': suppliers[0]
            },
        ]
        finished_products = []
        for fin_data in finished_products_data:
            fin_data['barcode'] = generate_unique_barcode('FIN')
            # Patch: round prices to 2 decimal places
            fin_data['cost_price'] = Decimal(str(fin_data['cost_price'])).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            fin_data['selling_price'] = Decimal(str(fin_data['selling_price'])).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            finished_product, created = Product.objects.get_or_create(
                SKU=fin_data['SKU'],
                defaults=fin_data
            )
            finished_products.append(finished_product)
            if created:
                self.stdout.write(f'Created finished product: {finished_product.name}')
        return finished_products

    def create_menu(self, branch, admin_user):
        """Create the main menu for the restaurant."""
        menu, created = Menu.objects.get_or_create(
            name='Main Menu',
            branch=branch,
            defaults={
                'description': 'Our signature dishes and favorites',
                'is_active': True,
                'is_default': True,
                'created_by': admin_user
            }
        )
        
        if created:
            self.stdout.write(f'Created menu: {menu.name}')
        
        return menu

    def create_menu_items(self, menu, categories, ingredients, admin_user):
        """Create menu items with recipes."""
        # First, ensure all ingredients have unique barcodes
        for ingredient in ingredients:
            if not ingredient.barcode:
                ingredient.barcode = generate_unique_barcode('ING')
                ingredient.save()

        menu_items_data = [
            {
                'name': 'Caesar Salad',
                'description': 'Fresh romaine lettuce with Caesar dressing, croutons, and parmesan cheese',
                'category': next(c for c in categories if c.name == 'Salads'),
                'selling_price': Decimal('12.00'),
                'preparation_time': timezone.timedelta(minutes=10),
                'allergens': ['dairy', 'gluten'],
                'ingredients': [
                    {'ingredient': 'Lettuce', 'quantity': 0.2, 'unit': 'kg'},
                    {'ingredient': 'Cheese', 'quantity': 0.05, 'unit': 'kg'},
                    {'ingredient': 'Olive Oil', 'quantity': 0.02, 'unit': 'L'},
                ]
            },
            {
                'name': 'Grilled Chicken Breast',
                'description': 'Tender grilled chicken breast with herbs and spices',
                'category': next(c for c in categories if c.name == 'Main Courses'),
                'selling_price': Decimal('18.00'),
                'preparation_time': timezone.timedelta(minutes=25),
                'allergens': [],
                'ingredients': [
                    {'ingredient': 'Chicken Breast', 'quantity': 0.25, 'unit': 'kg'},
                    {'ingredient': 'Olive Oil', 'quantity': 0.01, 'unit': 'L'},
                    {'ingredient': 'Garlic', 'quantity': 0.01, 'unit': 'kg'},
                ]
            },
            {
                'name': 'Pasta Carbonara',
                'description': 'Classic pasta with eggs, cheese, and pancetta',
                'category': next(c for c in categories if c.name == 'Pasta & Rice'),
                'selling_price': Decimal('16.00'),
                'preparation_time': timezone.timedelta(minutes=20),
                'allergens': ['dairy', 'eggs', 'gluten'],
                'ingredients': [
                    {'ingredient': 'Pasta', 'quantity': 0.15, 'unit': 'kg'},
                    {'ingredient': 'Eggs', 'quantity': 2, 'unit': 'pcs'},
                    {'ingredient': 'Cheese', 'quantity': 0.08, 'unit': 'kg'},
                ]
            },
            {
                'name': 'Grilled Salmon',
                'description': 'Fresh salmon fillet grilled to perfection',
                'category': next(c for c in categories if c.name == 'Grilled Items'),
                'selling_price': Decimal('24.00'),
                'preparation_time': timezone.timedelta(minutes=30),
                'allergens': [],
                'ingredients': [
                    {'ingredient': 'Salmon Fillet', 'quantity': 0.2, 'unit': 'kg'},
                    {'ingredient': 'Olive Oil', 'quantity': 0.01, 'unit': 'L'},
                    {'ingredient': 'Lemon', 'quantity': 0.5, 'unit': 'pcs'},
                ]
            },
            {
                'name': 'Chocolate Cake',
                'description': 'Rich chocolate cake with chocolate ganache',
                'category': next(c for c in categories if c.name == 'Desserts'),
                'selling_price': Decimal('8.00'),
                'preparation_time': timezone.timedelta(minutes=5),
                'allergens': ['dairy', 'eggs', 'gluten'],
                'ingredients': [
                    {'ingredient': 'Flour', 'quantity': 0.1, 'unit': 'kg'},
                    {'ingredient': 'Eggs', 'quantity': 3, 'unit': 'pcs'},
                    {'ingredient': 'Milk', 'quantity': 0.25, 'unit': 'L'},
                ]
            },
        ]

        for item_data in menu_items_data:
            # Calculate cost_price from ingredients if possible
            cost_price = None
            if 'ingredients' in item_data and item_data['ingredients']:
                cost_price = sum(
                    Decimal(str(ing['quantity'])) * next((i.cost_price for i in ingredients if i.name == ing['ingredient']), Decimal('0'))
                    for ing in item_data['ingredients']
                )
            if not cost_price:
                cost_price = Decimal(item_data['selling_price']) * Decimal('0.5')
            # Patch: round prices to 2 decimal places
            item_data['selling_price'] = Decimal(str(item_data['selling_price'])).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            cost_price = Decimal(str(cost_price)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            # Remove allergens from defaults, handle after creation
            menu_item, created = MenuItem.objects.get_or_create(
                menu=menu,
                name=item_data['name'],
                defaults={
                    'description': item_data.get('description', ''),
                    'category': item_data.get('category'),
                    'selling_price': item_data['selling_price'],
                    'cost_price': cost_price,
                    'preparation_time': item_data.get('preparation_time'),
                    'is_available': item_data.get('is_available', True),
                    'is_featured': item_data.get('is_featured', False),
                    'display_order': item_data.get('display_order', 0),
                    'nutritional_info': item_data.get('nutritional_info', {}),
                    'created_by': admin_user
                }
            )
            if created:
                self.stdout.write(f'Created menu item: {menu_item.name}')

                # Assign allergens (ManyToMany) after creation
                allergen_names = item_data.get('allergens', [])
                if allergen_names:
                    allergen_objs = []
                    for allergen_name in allergen_names:
                        allergen_obj, _ = Allergy.objects.get_or_create(name=allergen_name)
                        allergen_objs.append(allergen_obj)
                    menu_item.allergens.set(allergen_objs)

                # Create recipe
                recipe, recipe_created = Recipe.objects.get_or_create(
                    menu_item=menu_item,
                    defaults={
                        'instructions': f'Prepare {menu_item.name} according to standard recipe.',
                        'cooking_time': item_data['preparation_time'],
                        'difficulty_level': 'medium',
                        'servings': 1,
                        'created_by': admin_user
                    }
                )

                if recipe_created:
                    # Add recipe ingredients
                    for ing_data in item_data['ingredients']:
                        ingredient_name = ing_data['ingredient']
                        ingredient = next((i for i in ingredients if ingredient_name in i.name), None)
                        if ingredient:
                            # Use code for unit lookup
                            unit = UnitOfMeasure.objects.get(code=ing_data['unit'])
                            RecipeIngredient.objects.create(
                                recipe=recipe,
                                ingredient=ingredient,
                                quantity=ing_data['quantity'],
                                unit_of_measure=unit,
                                notes=f'Used in {menu_item.name}'
                            )
                    self.stdout.write(f'  - Created recipe with {len(item_data["ingredients"])} ingredients')

    def create_branch_stock(self, branch, products):
        """Create branch stock for all products with proper decimal handling."""
        for product in products:
            # Calculate initial stock based on product type with proper decimal precision
            if product.product_type == 'ingredient':
                initial_stock = Decimal('10.0').quantize(Decimal('0.001'), rounding=ROUND_HALF_UP)
                reorder_level = Decimal('2.0').quantize(Decimal('0.001'), rounding=ROUND_HALF_UP)
            elif product.product_type == 'beverage':
                initial_stock = Decimal('50.0').quantize(Decimal('0.001'), rounding=ROUND_HALF_UP)
                reorder_level = Decimal('10.0').quantize(Decimal('0.001'), rounding=ROUND_HALF_UP)
            else:
                initial_stock = Decimal('20.0').quantize(Decimal('0.001'), rounding=ROUND_HALF_UP)
                reorder_level = Decimal('5.0').quantize(Decimal('0.001'), rounding=ROUND_HALF_UP)
            
            # Ensure prices are properly quantized to 2 decimal places
            cost_price = Decimal(str(product.cost_price)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP) if product.cost_price is not None else None
            selling_price = Decimal(str(product.selling_price)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP) if product.selling_price is not None else None
            
            branch_stock, created = BranchStock.objects.get_or_create(
                product=product,
                branch=branch,
                defaults={
                    'current_stock': initial_stock,
                    'reorder_level': reorder_level,
                    'cost_price': cost_price,
                    'selling_price': selling_price,
                    'is_active': True
                }
            )
            
            if created:
                self.stdout.write(
                    f'  - Created stock for {product.name}: {initial_stock} units, '
                    f'Cost: {cost_price}, Selling: {selling_price}'
                ) 