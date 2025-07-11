from datetime import datetime
from django.utils import timezone
from rest_framework import serializers
from .models import (
    Category, Product, Supplier, InventoryTransaction, InventoryAdjustment,
    UnitOfMeasure, BranchStock, Batch, BatchStock, ProductImage,
    Menu, MenuItem, Recipe, RecipeIngredient, Allergy, Modifier, ModifierOption, MenuItemModifier,
    StockCount, PurchaseOrder, PurchaseOrderItem, StockTransfer
)
from django.contrib.auth import get_user_model
from django.db.models import Q
from apps.base.utils import get_request_branch_id
from apps.accounting.serializers import ExpenseSerializer

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']

class UnitOfMeasureSerializer(serializers.ModelSerializer):
    class Meta:
        model = UnitOfMeasure
        fields = ['id', 'code', 'name', 'symbol', 'is_fraction_allowed']
        read_only_fields = ('created_at', 'updated_at')

class AllergySerializer(serializers.ModelSerializer):
    class Meta:
        model = Allergy
        fields = ['id', 'name', 'description', 'severity', 'common_in', 'created_at', 'updated_at']
        read_only_fields = ('created_at', 'updated_at')

class CategorySerializer(serializers.ModelSerializer):
    menu_items_count = serializers.SerializerMethodField()
    products_count = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at')

    def get_menu_items_count(self, obj):
        return obj.menu_items.count()

    def get_products_count(self, obj):
        return obj.products.count()

class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at')

class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ['id', 'image', 'is_default', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ('created_at', 'updated_at')

class BranchStockSerializer(serializers.ModelSerializer):
    branch_name = serializers.CharField(source='branch.name', read_only=True)
    unit_of_measure = UnitOfMeasureSerializer(source='product.unit_of_measure', read_only=True)
    
    class Meta:
        model = BranchStock
        fields = [
            'id', 'branch', 'branch_name', 'current_stock', 'reorder_level',
            'cost_price', 'selling_price', 'last_restocked', 'unit_of_measure', 
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ('created_at', 'updated_at')

class ProductCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating products with images and initial stock."""
    images = serializers.ListField(
        child=serializers.ImageField(),
        required=False,
        write_only=True
    )
    default_image_index = serializers.IntegerField(required=False, write_only=True)
    initial_stock = serializers.DictField(
        child=serializers.DictField(child=serializers.DecimalField(max_digits=10, decimal_places=3)),
        required=False,
        write_only=True,
        help_text="Initial stock levels by branch ID. Format: {'branch_id': {'current_stock': 10, 'reorder_level': 5}}"
    )
    
    class Meta:
        model = Product
        fields = [
            'id', 'name', 'SKU', 'barcode', 'description', 'product_type', 'category',
            'supplier', 'unit_of_measure', 'cost_price', 'selling_price',
            'allergens', 'nutritional_info', 'is_available_for_sale', 'is_available_for_recipes',
            'is_active', 'notes', 'kds_station_type', 'track_batches', 'track_expiry',
            'images', 'default_image_index', 'initial_stock'
        ]
        read_only_fields = ('created_at', 'updated_at')
    
    def validate(self, data):
        # Validate unit of measure if provided
        if 'unit_of_measure' in data:
            unit = data['unit_of_measure']
            # Remove validation for non-existent quantity field
            pass
            
        # Validate initial_stock data if provided
        if 'initial_stock' in data:
            from apps.branches.models import Branch
            
            initial_stock = data['initial_stock']
            if not isinstance(initial_stock, dict):
                raise serializers.ValidationError({
                    'initial_stock': 'Must be a dictionary mapping branch IDs to stock data.'
                })
                
            # Validate each branch's stock data
            for branch_id, stock_data in initial_stock.items():
                try:
                    branch_id_int = int(branch_id)
                    if not Branch.objects.filter(id=branch_id_int, is_active=True).exists():
                        raise serializers.ValidationError({
                            'initial_stock': f'Branch with ID {branch_id} does not exist or is inactive.'
                        })
                except (ValueError, TypeError):
                    raise serializers.ValidationError({
                        'initial_stock': f'Invalid branch ID: {branch_id}. Must be an integer.'
                    })
                    
                if not isinstance(stock_data, dict):
                    raise serializers.ValidationError({
                        'initial_stock': f'Stock data for branch {branch_id} must be a dictionary.'
                    })
                    
                # Validate current_stock and reorder_level if provided
                for field in ['current_stock', 'reorder_level']:
                    if field in stock_data:
                        try:
                            value = stock_data[field]
                            if value is not None:
                                float(value)  # Will raise ValueError if not a number
                        except (ValueError, TypeError):
                            raise serializers.ValidationError({
                                'initial_stock': f'{field} must be a number for branch {branch_id}.'
                            })
                
        return data
    
    def create(self, validated_data):
        allergens_data = validated_data.pop('allergens', None)
        images_data = validated_data.pop('images', [])
        default_image_index = validated_data.pop('default_image_index', 0)
        initial_stock_data = validated_data.pop('initial_stock', {})
        
        # Attach initial stock data to the product instance for the signal handler
        product = Product(**validated_data)
        if initial_stock_data:
            product._initial_stock_data = initial_stock_data
        # Attach user for initial stock transaction
        request = self.context.get('request')
        if request and hasattr(request, 'user') and request.user.is_authenticated:
            product._created_by = request.user
        # Save the product (this will trigger the post_save signal)
        product.save()
        
        # Always set allergens if submitted (even if empty, to clear)
        if allergens_data is not None or allergens_data != []:
            product.allergens.set(allergens_data)
        # Create product images
        for index, image in enumerate(images_data):
            is_default = index == default_image_index
            ProductImage.objects.create(
                product=product,
                image=image,
                is_default=is_default,
                is_active=True
            )
        
        return product

class ProductSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    unit_of_measure_detail = UnitOfMeasureSerializer(source='unit_of_measure', read_only=True)
    branch_stock = serializers.SerializerMethodField()
    images = ProductImageSerializer(many=True, read_only=True)
    default_image = serializers.SerializerMethodField()
    stock_status = serializers.SerializerMethodField()
    
    class Meta:
        model = Product
        fields = [
            'id', 'name', 'SKU', 'barcode', 'description', 'product_type', 'category', 'category_name',
            'supplier', 'supplier_name', 'unit_of_measure', 'unit_of_measure_detail',
            'cost_price', 'selling_price', 'branch_stock', 'images', 'default_image',
            'allergens', 'nutritional_info', 'is_available_for_sale', 'is_available_for_recipes',
            'stock_status', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ('created_at', 'updated_at')
    
    def get_branch_stock(self, obj):
        branch_id = get_request_branch_id(self.context.get('request'))
        queryset = obj.branch_stock.all()
        if branch_id:
            queryset = queryset.filter(branch_id=branch_id)
        return BranchStockSerializer(queryset, many=True, context=self.context).data
    
    def get_default_image(self, obj):
        """Get the default image for the product."""
        default_image = obj.images.filter(is_default=True, is_active=True).first()
        if default_image:
            return default_image.image.url if default_image.image else None
        # If no default image, return the first active image
        first_image = obj.images.filter(is_active=True).first()
        return first_image.image.url if first_image and first_image.image else None
    
    def get_stock_status(self, obj):
        """Get stock status for the current branch."""
        request = self.context.get('request')
        if request and hasattr(request, 'branch'):
            return obj.get_stock_status(request.branch)
        return 'unknown'

class InventoryTransactionSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    branch_name = serializers.CharField(source='branch.name', read_only=True)
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)
    
    class Meta:
        model = InventoryTransaction
        fields = [
            'id', 'product', 'product_name', 'branch', 'branch_name', 'branch_stock',
            'transaction_type', 'quantity', 'reference', 'notes', 'created_by',
            'created_by_username', 'created_at', 'updated_at'
        ]
        read_only_fields = ('created_by', 'created_at', 'updated_at')
    
    def validate(self, data):
        # Ensure branch is provided for non-global transactions
        if 'branch' not in data and data.get('transaction_type') not in ['purchase', 'initial']:
            raise serializers.ValidationError({
                'branch': 'Branch is required for this transaction type.'
            })
        
        # Validate branch_stock belongs to the specified branch and product
        if 'branch_stock' in data and 'product' in data:
            branch_stock = data['branch_stock']
            if branch_stock.product != data['product'] or \
               (data.get('branch') and branch_stock.branch != data['branch']):
                raise serializers.ValidationError({
                    'branch_stock': 'Branch stock does not match the specified product and branch.'
                })
        
        return data
    
    def create(self, validated_data):
        # Set the created_by user from the request
        request = self.context.get('request')
        if request and hasattr(request, 'user') and request.user.is_authenticated:
            validated_data['created_by'] = request.user
            
        # If branch_stock is not provided but branch is, get or create it
        if 'branch' in validated_data and 'branch_stock' not in validated_data:
            branch = validated_data['branch']
            product = validated_data['product']
            branch_stock, _ = BranchStock.objects.get_or_create(
                branch=branch,
                product=product,
                defaults={
                    'current_stock': 0,
                    'reorder_level': 0,
                    'is_active': True
                }
            )
            validated_data['branch_stock'] = branch_stock
            
        return super().create(validated_data)

class BatchSerializer(serializers.ModelSerializer):
    """Serializer for Batch model with product details."""
    product_name = serializers.CharField(source='product.name', read_only=True)
    status = serializers.SerializerMethodField()
    
    class Meta:
        model = Batch
        fields = [
            'id', 'batch_number', 'product', 'product_name', 'manufactured_date',
            'expiry_date', 'is_active', 'status', 'notes', 'created_at', 'updated_at'
        ]
        read_only_fields = ('created_at', 'updated_at', 'status')
    
    def get_status(self, obj):
        """Get batch status based on expiry date and stock levels."""
        if obj.expiry_date and obj.expiry_date < timezone.now().date():
            return 'expired'
        return 'active' if obj.is_active else 'inactive'
    
    def validate(self, data):
        """Validate batch data."""
        product = data.get('product')
        
        if product and not product.track_batches:
            raise serializers.ValidationError({
                'product': 'Batch tracking is not enabled for this product.'
            })
            
        if product and product.track_expiry and not data.get('expiry_date'):
            raise serializers.ValidationError({
                'expiry_date': 'Expiry date is required for this product.'
            })
            
        return data

class BatchStockSerializer(serializers.ModelSerializer):
    """Serializer for BatchStock model with batch and branch details."""
    batch_number = serializers.CharField(source='batch.batch_number', read_only=True)
    product_name = serializers.CharField(source='batch.product.name', read_only=True)
    product_id = serializers.IntegerField(source='batch.product.id', read_only=True)
    branch_name = serializers.CharField(source='branch.name', read_only=True)
    expiry_date = serializers.DateField(source='batch.expiry_date', read_only=True)
    available_quantity = serializers.DecimalField(
        max_digits=10,
        decimal_places=3,
        read_only=True
    )
    
    class Meta:
        model = BatchStock
        fields = [
            'id', 'batch', 'batch_number', 'product_name', 'product_id',
            'branch', 'branch_name', 'quantity', 'reserved_quantity',
            'available_quantity', 'expiry_date', 'last_checked', 'created_at'
        ]
        read_only_fields = ('available_quantity', 'last_checked', 'created_at')
    
    def validate(self, data):
        """Validate batch stock data."""
        batch = data.get('batch')
        branch = data.get('branch')
        
        if batch and branch and BatchStock.objects.filter(
            batch=batch, branch=branch
        ).exclude(pk=self.instance.pk if self.instance else None).exists():
            raise serializers.ValidationError(
                'Stock entry for this batch and branch already exists.'
            )
            
        return data

class BatchStockUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating batch stock quantities."""
    class Meta:
        model = BatchStock
        fields = ['quantity', 'reserved_quantity']
    
    def validate_quantity(self, value):
        if value < 0:
            raise serializers.ValidationError("Quantity cannot be negative.")
        return value
    
    def validate_reserved_quantity(self, value):
        if value < 0:
            raise serializers.ValidationError("Reserved quantity cannot be negative.")
        return value
    
    def validate(self, data):
        quantity = data.get('quantity', 0)
        reserved_quantity = data.get('reserved_quantity', 0)
        
        if reserved_quantity > quantity:
            raise serializers.ValidationError(
                "Reserved quantity cannot exceed total quantity."
            )
        
        return data

class BatchDetailSerializer(BatchSerializer):
    """Detailed batch serializer with stock information."""
    stock = serializers.SerializerMethodField()
    
    class Meta(BatchSerializer.Meta):
        fields = BatchSerializer.Meta.fields + ['stock']
    
    def get_stock(self, obj):
        """Get stock information for all branches."""
        branch_id = get_request_branch_id(self.context.get('request'))
        queryset = obj.branch_stock.all()
        
        if branch_id:
            queryset = queryset.filter(branch_id=branch_id)
            
        return BatchStockSerializer(
            queryset,
            many=True,
            context=self.context
        ).data

class InventoryAdjustmentSerializer(serializers.ModelSerializer):
    """Serializer for inventory adjustments with batch support."""
    product_name = serializers.CharField(source='product.name', read_only=True)
    branch_name = serializers.CharField(source='branch.name', read_only=True)
    requested_by_username = serializers.CharField(source='requested_by.username', read_only=True)
    reviewed_by_username = serializers.CharField(source='reviewed_by.username', read_only=True, allow_null=True)
    batch_number = serializers.CharField(source='batch.batch_number', read_only=True)
    batch_id = serializers.PrimaryKeyRelatedField(
        queryset=Batch.objects.all(),
        source='batch',
        required=False,
        allow_null=True,
        write_only=True
    )
    
    class Meta:
        model = InventoryAdjustment
        fields = [
            'id', 'product', 'product_name', 'branch', 'branch_name',
            'quantity_before', 'quantity_after', 'reason', 'status',
            'requested_by', 'requested_by_username', 'reviewed_by',
            'reviewed_by_username', 'reviewed_at', 'review_notes',
            'batch', 'batch_id', 'batch_number', 'created_at', 'updated_at'
        ]
        read_only_fields = (
            'status', 'reviewed_by', 'reviewed_at', 'review_notes',
            'created_at', 'updated_at', 'requested_by', 'batch_number'
        )
    
    def validate(self, data):
        """Validate batch information if product requires batch tracking."""
        product = data.get('product') or (self.instance and self.instance.product)
        batch = data.get('batch')
        # Ensure branch is provided
        if 'branch' not in data and not getattr(self.instance, 'branch', None):
            raise serializers.ValidationError({
                'branch': 'Branch is required for inventory adjustments.'
            })
            
        # If creating a new adjustment or changing the branch/product
        if (self.instance is None or 'branch' in data or 'product' in data):
            branch = data.get('branch', getattr(self.instance, 'branch', None))
            product = data.get('product', getattr(self.instance, 'product', None))
            
            if branch and product:
                # Get or create branch stock
                branch_stock, _ = BranchStock.objects.get_or_create(
                    branch=branch,
                    product=product,
                    defaults={
                        'current_stock': 0,
                        'reorder_level': 0,
                        'is_active': True
                    }
                )
                data['branch_stock'] = branch_stock
                
                # Set quantity_before to current stock if not set
                if 'quantity_before' not in data:
                    data['quantity_before'] = branch_stock.current_stock
        
        return data
    
    def create(self, validated_data):
        # Set the requested_by user from the request
        request = self.context.get('request')
        if request and hasattr(request, 'user') and request.user.is_authenticated:
            validated_data['requested_by'] = request.user
            
        return super().create(validated_data)
    
    def update(self, instance, validated_data):
        # Only allow updating review_notes and status
        if 'review_notes' in validated_data:
            instance.review_notes = validated_data['review_notes']
        if 'status' in validated_data:
            instance.status = validated_data['status']
            if validated_data['status'] in ['approved', 'rejected']:
                instance.reviewed_by = self.context['request'].user
                instance.reviewed_at = timezone.now()
        
        instance.save()
        return instance

# Restaurant-specific serializers
class RecipeIngredientCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating recipe ingredients."""
    class Meta:
        model = RecipeIngredient
        fields = ['ingredient', 'quantity', 'unit_of_measure', 'notes', 'is_optional']
        extra_kwargs = {
            'ingredient': {'required': True},
            'quantity': {'required': True},
            'unit_of_measure': {'required': True}
        }

class RecipeIngredientSerializer(serializers.ModelSerializer):
    ingredient_name = serializers.CharField(source='ingredient.name', read_only=True)
    ingredient_sku = serializers.CharField(source='ingredient.SKU', read_only=True)
    unit_of_measure_detail = UnitOfMeasureSerializer(source='unit_of_measure', read_only=True)
    
    class Meta:
        model = RecipeIngredient
        fields = [
            'id', 'ingredient', 'ingredient_name', 'ingredient_sku', 'quantity',
            'unit_of_measure', 'unit_of_measure_detail', 'notes', 'is_optional'
        ]

class RecipeSerializer(serializers.ModelSerializer):
    ingredients = RecipeIngredientSerializer(many=True, read_only=True)
    
    class Meta:
        model = Recipe
        fields = [
            'id', 'instructions', 'cooking_time', 'difficulty_level', 'servings',
            'ingredients', 'created_at', 'updated_at'
        ]
        read_only_fields = ('created_at', 'updated_at')

class MenuItemSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    recipe = RecipeSerializer(read_only=True)
    cost_price_calculated = serializers.SerializerMethodField()
    ingredient_availability = serializers.SerializerMethodField()
    
    class Meta:
        model = MenuItem
        fields = [
            'id', 'name','image', 'description', 'category', 'category_name', 'selling_price',
            'cost_price', 'cost_price_calculated', 'preparation_time', 'is_available',
            'is_featured', 'display_order', 'allergens', 'nutritional_info',
            'recipe', 'ingredient_availability', 'created_at', 'updated_at'
        ]
        read_only_fields = ('created_at', 'updated_at')
    
    def get_cost_price_calculated(self, obj):
        """Get the calculated cost price from recipe ingredients."""
        return obj.calculate_cost_price()
    
    def get_ingredient_availability(self, obj):
        """Get ingredient availability for this menu item."""
        request = self.context.get('request')
        if request and hasattr(request, 'branch'):
            return obj.check_ingredient_availability(request.branch)
        return []

class MenuItemCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating menu items with images and recipes."""
    allergens = serializers.PrimaryKeyRelatedField(queryset=Allergy.objects.all(), many=True, required=False)
    recipe_ingredients = RecipeIngredientCreateSerializer(many=True, required=False)
    recipe_instructions = serializers.CharField(write_only=True, required=False, allow_blank=True)
    cooking_time = serializers.DurationField(write_only=True, required=False, allow_null=True)
    difficulty_level = serializers.ChoiceField(
        write_only=True,
        required=False,
        choices=[
            ('easy', 'Easy'),
            ('medium', 'Medium'),
            ('hard', 'Hard')
        ],
        default='medium'
    )
    servings = serializers.IntegerField(write_only=True, required=False, min_value=1, default=1)
    initial_stock = serializers.DictField(
        child=serializers.DictField(child=serializers.DecimalField(max_digits=10, decimal_places=3)),
        required=False,
        write_only=True,
        help_text="Initial stock levels by branch ID. Format: {'branch_id': {'current_stock': 10, 'reorder_level': 5}}"
    )
    
    class Meta:
        model = MenuItem
        fields = [
            'id', 'menu', 'name','image','description', 'category', 'selling_price',
            'cost_price', 'preparation_time', 'is_available', 'is_featured',
            'display_order', 'allergens', 'nutritional_info','recipe_ingredients', 'recipe_instructions', 
            'cooking_time', 'difficulty_level', 'servings','initial_stock'
        ]
        read_only_fields = ('created_at', 'updated_at')
        
    def validate(self, data):
        # Enforce recipe_ingredients is required and not empty
        recipe_ingredients = data.get('recipe_ingredients')
        if not recipe_ingredients or len(recipe_ingredients) == 0:
            raise serializers.ValidationError({
                'recipe_ingredients': 'You must provide at least one ingredient for the menu item recipe.'
            })
        # Validate initial_stock data if provided
        if 'initial_stock' in data:
            from apps.branches.models import Branch
            initial_stock = data['initial_stock']
            if not isinstance(initial_stock, dict):
                raise serializers.ValidationError({
                    'initial_stock': 'Must be a dictionary mapping branch IDs to stock data.'
                })
            for branch_id, stock_data in initial_stock.items():
                try:
                    branch_id_int = int(branch_id)
                    if not Branch.objects.filter(id=branch_id_int, is_active=True).exists():
                        raise serializers.ValidationError({
                            'initial_stock': f'Branch with ID {branch_id} does not exist or is inactive.'
                        })
                except (ValueError, TypeError):
                    raise serializers.ValidationError({
                        'initial_stock': f'Invalid branch ID: {branch_id}. Must be an integer.'
                    })
                if not isinstance(stock_data, dict):
                    raise serializers.ValidationError({
                        'initial_stock': f'Stock data for branch {branch_id} must be a dictionary.'
                    })
                for field in ['current_stock', 'reorder_level']:
                    if field in stock_data:
                        try:
                            value = stock_data[field]
                            if value is not None:
                                float(value)
                        except (ValueError, TypeError):
                            raise serializers.ValidationError({
                                'initial_stock': f'{field} must be a number for branch {branch_id}.'
                            })
        return data
    
    def create(self, validated_data):
        # Handle allergens (m2m) field properly
        allergens_data = validated_data.pop('allergens', None)
        # Defensive pop to ensure allergens is not in validated_data
        validated_data.pop('allergens', None)
        # Extract recipe data if provided
        recipe_ingredients_data = validated_data.pop('recipe_ingredients', [])
        recipe_instructions = validated_data.pop('recipe_instructions', '')
        cooking_time = validated_data.pop('cooking_time', None)
        difficulty_level = validated_data.pop('difficulty_level', 'medium')
        servings = validated_data.pop('servings', 1)
        image_data = validated_data.pop('image', None)
        initial_stock_data = validated_data.pop('initial_stock', {})
        print(validated_data)
        menu_item = MenuItem.objects.create(**validated_data)

        # Set allergens if provided, else clear
        if allergens_data is not None and allergens_data != []:
            menu_item.allergens.set(allergens_data)
        # else:  # Optionally clear if you want to remove all allergens when not provided
        #     menu_item.allergens.clear()

        # Create recipe if ingredients are provided
        if recipe_ingredients_data:
            recipe = Recipe.objects.create(
                menu_item=menu_item,
                instructions=recipe_instructions,
                cooking_time=cooking_time,
                difficulty_level=difficulty_level,
                servings=servings,
                created_by=self.context['request'].user
            )
            for ingredient_data in recipe_ingredients_data:
                RecipeIngredient.objects.create(recipe=recipe, **ingredient_data)
            menu_item.update_allergens_from_recipe()
        # Attach initial stock data to the menu_item instance for the signal handler
        if initial_stock_data:
            menu_item._initial_stock_data = initial_stock_data
        # Attach user for initial stock transaction
        request = self.context.get('request')
        if request and hasattr(request, 'user') and request.user.is_authenticated:
            menu_item._created_by = request.user
        menu_item.save()
        return menu_item

class MenuSerializer(serializers.ModelSerializer):
    items = MenuItemSerializer(many=True, read_only=True)
    branch_name = serializers.CharField(source='branch.name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    
    class Meta:
        model = Menu
        fields = [
            'id', 'name', 'description', 'branch', 'branch_name', 'is_active',
            'is_default', 'valid_from', 'valid_until', 'items', 'created_by_name',
            'created_at', 'updated_at'
        ]
        read_only_fields = ('created_at', 'updated_at')

class ModifierOptionSerializer(serializers.ModelSerializer):
    """Serializer for modifier options."""
    allergens = AllergySerializer(many=True, read_only=True)
    
    class Meta:
        model = ModifierOption
        fields = [
            'id', 'name', 'description', 'price_adjustment', 'is_active',
            'display_order', 'allergens', 'created_at', 'updated_at'
        ]
        read_only_fields = ('created_at', 'updated_at')

class ModifierSerializer(serializers.ModelSerializer):
    """Serializer for menu modifiers."""
    options = ModifierOptionSerializer(many=True, read_only=True)
    branch_name = serializers.CharField(source='branch.name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    menu_items_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Modifier
        fields = [
            'id', 'name', 'description', 'modifier_type', 'price', 'min_selections',
            'max_selections', 'is_active', 'image', 'display_order', 'branch',
            'branch_name', 'options', 'created_by_name', 'menu_items_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = ('created_at', 'updated_at')
    
    def get_menu_items_count(self, obj):
        """Get the number of menu items using this modifier."""
        return obj.menu_items.count()

class MenuItemModifierSerializer(serializers.ModelSerializer):
    """Serializer for menu item modifiers."""
    modifier_name = serializers.CharField(source='modifier.name', read_only=True)
    menu_item_name = serializers.CharField(source='menu_item.name', read_only=True)
    
    class Meta:
        model = MenuItemModifier
        fields = [
            'id', 'menu_item', 'menu_item_name', 'modifier', 'modifier_name',
            'is_required', 'display_order', 'created_at', 'updated_at'
        ]
        read_only_fields = ('created_at', 'updated_at')

class StockCountSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    branch_name = serializers.CharField(source='branch.name', read_only=True)
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)

    class Meta:
        model = StockCount
        fields = [
            'id', 'product', 'product_name', 'branch', 'branch_name',
            'counted_quantity', 'date', 'notes', 'user', 'user_name',
            'created_at', 'updated_at'
        ]
        read_only_fields = ('created_at', 'updated_at', 'product_name', 'branch_name', 'user_name')

class PurchaseOrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    class Meta:
        model = PurchaseOrderItem
        fields = ['id', 'product', 'product_name', 'quantity']

class PurchaseOrderSerializer(serializers.ModelSerializer):
    items = PurchaseOrderItemSerializer(many=True)
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    expenses = ExpenseSerializer(many=True, read_only=True, source='accounting_expenses')
    class Meta:
        model = PurchaseOrder
        fields = ['id', 'supplier', 'supplier_name', 'expected_delivery', 'status', 'notes', 'items', 'created_by', 'created_at', 'updated_at', 'expenses']
        read_only_fields = ('created_by', 'created_at', 'updated_at')

    def create(self, validated_data):
        items_data = validated_data.pop('items', [])
        purchase_order = PurchaseOrder.objects.create(**validated_data)
        for item_data in items_data:
            PurchaseOrderItem.objects.create(purchase_order=purchase_order, **item_data)
        return purchase_order

    def update(self, instance, validated_data):
        items_data = validated_data.pop('items', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if items_data is not None:
            instance.items.all().delete()
            for item_data in items_data:
                PurchaseOrderItem.objects.create(purchase_order=instance, **item_data)
        return instance

class StockTransferSerializer(serializers.ModelSerializer):
    source_branch_name = serializers.CharField(source='source_branch.name', read_only=True)
    target_branch_name = serializers.CharField(source='target_branch.name', read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)
    class Meta:
        model = StockTransfer
        fields = ['id', 'source_branch', 'source_branch_name', 'target_branch', 'target_branch_name', 'product', 'product_name', 'quantity', 'status', 'notes', 'created_by', 'created_at', 'updated_at']
        read_only_fields = ('created_by', 'created_at', 'updated_at')

class MinimalCatalogProductSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    default_image = serializers.SerializerMethodField()
    type = serializers.SerializerMethodField()
    stock = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'description', 'category', 'category_name',
            'selling_price', 'cost_price', 'type', 'default_image', 'stock'
        ]

    def get_type(self, obj):
        return 'product'

    def get_default_image(self, obj):
        img = obj.get_default_image()
        return img.image.url if img else None

    def get_stock(self, obj):
        request = self.context.get('request')
        branch_id = None
        if request:
            branch_id = request.query_params.get('branch_id')
        if branch_id is not None:
            try:
                branch_id_int = int(branch_id)
            except (TypeError, ValueError):
                branch_id_int = branch_id
            stock_obj = None
            # Try both int and str for branch_id
            for bs in obj.branch_stock.all():
                if getattr(bs, 'branch_id', None) == branch_id_int or str(getattr(bs, 'branch_id', '')) == str(branch_id):
                    stock_obj = bs
                    break
            if not stock_obj:
                # fallback to queryset if not prefetched
                stock_obj = obj.branch_stock.filter(branch_id=branch_id).first()
            if stock_obj:
                return float(stock_obj.current_stock)
        return None

class MinimalCatalogMenuItemSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    default_image = serializers.SerializerMethodField()
    type = serializers.SerializerMethodField()
    track_inventory = serializers.BooleanField(read_only=True)
    stock = serializers.SerializerMethodField()
    is_available = serializers.BooleanField(read_only=True)

    class Meta:
        model = MenuItem
        fields = [
            'id', 'name', 'description', 'category', 'category_name',
            'selling_price', 'cost_price', 'type', 'default_image', 'track_inventory', 'stock', 'is_available'
        ]

    def get_type(self, obj):
        return 'menu_item'

    def get_default_image(self, obj):
        # If you add images to MenuItem, update this logic
        return None

    def get_stock(self, obj):
        request = self.context.get('request')
        branch_id = None
        if request:
            branch_id = request.query_params.get('branch_id')
        if branch_id is not None:
            try:
                branch_id_int = int(branch_id)
            except (TypeError, ValueError):
                branch_id_int = branch_id
            stock_obj = None
            for bs in obj.branch_stock.all():
                if getattr(bs, 'branch_id', None) == branch_id_int or str(getattr(bs, 'branch_id', '')) == str(branch_id):
                    stock_obj = bs
                    break
            if not stock_obj:
                stock_obj = obj.branch_stock.filter(branch_id=branch_id).first()
            if stock_obj:
                return float(stock_obj.current_stock)
        return None
