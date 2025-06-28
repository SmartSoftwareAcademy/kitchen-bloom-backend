from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q, F, Sum
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.base.models import BaseNameDescriptionModel, TimestampedModel, SoftDeleteModel
from apps.base.mixins import BarcodeMixin
from apps.branches.models import Branch as BranchModel  # Renamed to avoid conflict
from apps.crm.models import Customer


User = get_user_model()


class Category(BaseNameDescriptionModel, TimestampedModel, SoftDeleteModel):
    """Product category model for organizing products."""
    name = models.CharField(_('name'), max_length=100, unique=True)
    image = models.ImageField(_('image'), upload_to='categories/', blank=True, null=True)
    description = models.TextField(_('description'), blank=True)
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children',
        verbose_name=_('parent category')
    )
    is_active = models.BooleanField(_('is active'), default=True)
    # Restaurant-specific fields
    is_menu_category = models.BooleanField(_('is menu category'), default=False, help_text=_('Whether this category is for menu items'))
    is_ingredient_category = models.BooleanField(_('is ingredient category'), default=False, help_text=_('Whether this category is for ingredients'))
    display_order = models.PositiveIntegerField(_('display order'), default=0, help_text=_('Order in which categories are displayed'))

    class Meta:
        verbose_name = _('category')
        verbose_name_plural = _('categories')
        ordering = ('display_order', 'name')

    def __str__(self):
        return self.name


class Menu(TimestampedModel, SoftDeleteModel):
    """Menu model for restaurant menu management."""
    name = models.CharField(_('name'), max_length=200)
    description = models.TextField(_('description'), blank=True)
    branch = models.ForeignKey(BranchModel, on_delete=models.CASCADE, related_name='menus', verbose_name=_('branch'))
    is_active = models.BooleanField(_('is active'), default=True)
    is_default = models.BooleanField(_('is default'), default=False, help_text=_('Default menu for this branch'))
    valid_from = models.DateTimeField(_('valid from'), null=True, blank=True)
    valid_until = models.DateTimeField(_('valid until'), null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_menus', verbose_name=_('created by'))

    class Meta:
        verbose_name = _('menu')
        verbose_name_plural = _('menus')
        ordering = ('-is_default', 'name')
        unique_together = (('branch', 'name'),)

    def __str__(self):
        return f"{self.name} - {self.branch.name}"

    def save(self, *args, **kwargs):
        # Ensure only one default menu per branch
        if self.is_default:
            Menu.objects.filter(branch=self.branch, is_default=True).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)

class MenuItem(TimestampedModel, SoftDeleteModel):
    """Menu item model for finished products/dishes."""
    menu = models.ForeignKey(Menu, on_delete=models.CASCADE, related_name='items', verbose_name=_('menu'))
    name = models.CharField(_('name'), max_length=200)
    description = models.TextField(_('description'), blank=True)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='menu_items', verbose_name=_('category'))
    selling_price = models.DecimalField(_('selling price'), max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    cost_price = models.DecimalField(_('cost price'), max_digits=10, decimal_places=2, validators=[MinValueValidator(0)], help_text=_('Calculated from recipe ingredients'))
    preparation_time = models.DurationField(_('preparation time'), null=True, blank=True, help_text=_('Estimated preparation time'))
    is_available = models.BooleanField(_('is available'), default=True)
    is_featured = models.BooleanField(_('is featured'), default=False)
    display_order = models.PositiveIntegerField(_('display order'), default=0)
    allergens = models.ManyToManyField('Allergy', blank=True, related_name='menu_items')
    nutritional_info = models.JSONField(_('nutritional info'), default=dict, blank=True, help_text=_('Nutritional information'))
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_menu_items', verbose_name=_('created by'))

    class Meta:
        verbose_name = _('menu item')
        verbose_name_plural = _('menu items')
        ordering = ('display_order', 'name')
        unique_together = (('menu', 'name'),)

    def __str__(self):
        return f"{self.name} - {self.menu.name}"

    def calculate_cost_price(self):
        """Calculate cost price from recipe ingredients."""
        total_cost = 0
        if hasattr(self, 'recipe') and self.recipe:
            for recipe_ingredient in self.recipe.ingredients.all():
                ingredient = recipe_ingredient.ingredient
                branch_stock = ingredient.get_stock_for_branch(self.menu.branch)
                if branch_stock:
                    cost_per_unit = branch_stock.cost_price or ingredient.cost_price
                    total_cost += recipe_ingredient.quantity * cost_per_unit
        return total_cost

    def update_cost_price(self):
        """Update the cost price based on current ingredient costs."""
        self.cost_price = self.calculate_cost_price()
        self.save(update_fields=['cost_price'])

    def check_ingredient_availability(self, branch=None):
        """Check if all ingredients are available in sufficient quantities."""
        if not branch:
            branch = self.menu.branch
        
        unavailable_ingredients = []
        if hasattr(self, 'recipe') and self.recipe:
            for recipe_ingredient in self.recipe.ingredients.all():
                ingredient = recipe_ingredient.ingredient
                branch_stock = ingredient.get_stock_for_branch(branch)
                if not branch_stock or branch_stock.current_stock < recipe_ingredient.quantity:
                    unavailable_ingredients.append({
                        'ingredient': ingredient.name,
                        'required': recipe_ingredient.quantity,
                        'available': branch_stock.current_stock if branch_stock else 0
                    })
        
        return unavailable_ingredients

    def update_allergens_from_recipe(self):
        """Update allergens as the union of all ingredient allergens in the recipe."""
        if hasattr(self, 'recipe') and self.recipe:
            allergen_set = set()
            for recipe_ingredient in self.recipe.ingredients.all():
                ingredient = recipe_ingredient.ingredient
                allergen_set.update(ingredient.allergens.all())
            self.allergens.set(allergen_set)
            self.save(update_fields=['allergens'])

class Recipe(TimestampedModel, SoftDeleteModel):
    """Recipe model linking menu items to ingredients."""
    menu_item = models.OneToOneField(MenuItem, on_delete=models.CASCADE, related_name='recipe', verbose_name=_('menu item'))
    instructions = models.TextField(_('instructions'), blank=True, help_text=_('Cooking instructions'))
    cooking_time = models.DurationField(_('cooking time'), null=True, blank=True)
    difficulty_level = models.CharField(_('difficulty level'), max_length=20, choices=[
        ('easy', _('Easy')),
        ('medium', _('Medium')),
        ('hard', _('Hard')),
    ], default='medium')
    servings = models.PositiveIntegerField(_('servings'), default=1, help_text=_('Number of servings this recipe makes'))
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_recipes', verbose_name=_('created by'))

    class Meta:
        verbose_name = _('recipe')
        verbose_name_plural = _('recipes')

    def __str__(self):
        return f"Recipe for {self.menu_item.name}"

    def get_total_cost(self):
        """Calculate total cost of all ingredients."""
        return sum(ingredient.quantity * ingredient.ingredient.cost_price for ingredient in self.ingredients.all())

class RecipeIngredient(TimestampedModel, SoftDeleteModel):
    """Recipe ingredient model linking recipes to ingredients."""
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, related_name='ingredients', verbose_name=_('recipe'))
    ingredient = models.ForeignKey('Product', on_delete=models.CASCADE, related_name='recipe_ingredients', verbose_name=_('ingredient'))
    quantity = models.DecimalField(_('quantity'), max_digits=10, decimal_places=3, validators=[MinValueValidator(0.001)])
    unit_of_measure = models.ForeignKey('UnitOfMeasure', on_delete=models.PROTECT, related_name='recipe_ingredients', verbose_name=_('unit of measure'))
    notes = models.TextField(_('notes'), blank=True, help_text=_('Special notes for this ingredient'))
    is_optional = models.BooleanField(_('is optional'), default=False, help_text=_('Whether this ingredient is optional'))

    class Meta:
        verbose_name = _('recipe ingredient')
        verbose_name_plural = _('recipe ingredients')
        unique_together = (('recipe', 'ingredient'),)

    def __str__(self):
        return f"{self.ingredient.name} - {self.quantity} {self.unit_of_measure.symbol}"

class Supplier(BaseNameDescriptionModel, TimestampedModel, SoftDeleteModel):
    """Supplier/vendor model for tracking product sources."""
    name = models.CharField(_('name'), max_length=200)
    contact_person = models.CharField(_('contact person'), max_length=100, blank=True)
    email = models.EmailField(_('email'), blank=True)
    phone = models.CharField(_('phone'), max_length=20, blank=True)
    address = models.TextField(_('address'), blank=True)
    tax_id = models.CharField(_('tax ID'), max_length=50, blank=True)
    is_active = models.BooleanField(_('is active'), default=True)
    notes = models.TextField(_('notes'), blank=True)

    class Meta:
        verbose_name = _('supplier')
        verbose_name_plural = _('suppliers')
        ordering = ('name',)

    def __str__(self):
        return self.name

class UnitOfMeasure(TimestampedModel, SoftDeleteModel):
    """
    Represents a standard unit of measure for products.
    """
    # Common unit types
    KILOGRAM = 'kg'
    GRAM = 'g'
    LITER = 'L'
    MILLILITER = 'mL'
    PIECE = 'pcs'
    PACK = 'pack'
    BOTTLE = 'bottle'
    BOX = 'box'
    
    UNIT_CHOICES = [
        (KILOGRAM, _('Kilogram (kg)')),
        (GRAM, _('Gram (g)')),
        (LITER, _('Liter (L)')),
        (MILLILITER, _('Milliliter (mL)')),
        (PIECE, _('Piece (pcs)')),
        (PACK, _('Pack')),
        (BOTTLE, _('Bottle')),
        (BOX, _('Box')),
    ]
    
    code = models.CharField(
        max_length=10,
        choices=UNIT_CHOICES,
        unique=True,
        verbose_name=_('unit code')
    )
    name = models.CharField(max_length=50, verbose_name=_('name'))
    symbol = models.CharField(max_length=10, verbose_name=_('symbol'))
    is_fraction_allowed = models.BooleanField(
        default=True,
        verbose_name=_('allow fractions'),
        help_text=_('Whether this unit can have fractional quantities')
    )
    
    class Meta:
        verbose_name = _('unit of measure')
        verbose_name_plural = _('units of measure')
        ordering = ('name',)
    
    def __str__(self):
        return f"{self.name} ({self.symbol})"

class ProductImage(TimestampedModel, SoftDeleteModel):
    """Product image model for inventory items."""
    image = models.ImageField(_('image'), upload_to='products/', null=True, blank=True)
    product = models.ForeignKey("Product",on_delete=models.CASCADE,related_name='images',verbose_name=_('product'))
    is_default = models.BooleanField(_('is default'),default=False)
    is_active = models.BooleanField(_('is active'),default=True)

    def __str__(self):
        return f"{self.product.name} - {self.image.url if self.image else None}"
    
    def save(self, *args, **kwargs):
        # If this image is being set as default, unset other defaults for this product
        if self.is_default:
            ProductImage.objects.filter(
                product=self.product,
                is_default=True
            ).exclude(pk=self.pk).update(is_default=False)
        
        super().save(*args, **kwargs)
    
    class Meta:
        verbose_name = _('product image')

class Allergy(models.Model):
    """Represents a food allergy that customers may have."""
    class Severity(models.TextChoices):
        MILD = 'mild', _('Mild')
        MODERATE = 'moderate', _('Moderate')
        SEVERE = 'severe', _('Severe')
        LIFE_THREATENING = 'life_threatening', _('Life Threatening')
    
    name = models.CharField(_('name'), max_length=100)
    description = models.TextField(_('description'), blank=True)
    severity = models.CharField(_('severity'), max_length=20, choices=Severity.choices, default=Severity.MODERATE)
    common_in = models.CharField(_('common in'), max_length=255, blank=True, help_text=_('Common ingredients/foods containing this allergen'))
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)
    
    class Meta:
        verbose_name = _('allergy')
        verbose_name_plural = _('allergies')
        ordering = ['-severity', 'name']
    
    def __str__(self):
        return f"{self.name} ({self.get_severity_display()})"

class Product(BarcodeMixin, BaseNameDescriptionModel, TimestampedModel, SoftDeleteModel):
    """Product model for inventory items.
    Products are shared across branches but can have different stock levels per branch.
    """
    # Basic Information
    SKU = models.CharField(_('SKU'), max_length=50, unique=True)
    barcode = models.CharField(_('barcode'), max_length=100, blank=True, unique=True, db_index=True)
    name = models.CharField(_('name'), max_length=200)
    description = models.TextField(_('description'), blank=True)
    
    # Product Type Classification
    PRODUCT_TYPES = (
        ('ingredient', _('Ingredient')),
        ('finished_product', _('Finished Product')),
        ('beverage', _('Beverage')),
        ('supplies', _('Supplies')),
    )
    product_type = models.CharField(_('product type'), max_length=20, choices=PRODUCT_TYPES, default='ingredient', help_text=_('Type of product for inventory management'))
    
    # Categorization
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='products',
        verbose_name=_('category')
    )
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='products',
        verbose_name=_('supplier')
    )
    
    # Units and Pricing
    unit_of_measure = models.ForeignKey(
        UnitOfMeasure,
        on_delete=models.PROTECT,
        related_name='products',
        verbose_name=_('unit of measure'),
        help_text=_('Standard unit for this product')
    )
    cost_price = models.DecimalField(
        _('cost price'),
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text=_('Default cost price for new branches')
    )
    selling_price = models.DecimalField(
        _('selling price'),
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text=_('Default selling price for new branches')
    )
    
    # Batch/Lot Tracking
    track_batches = models.BooleanField(
        _('track batches/lots'),
        default=False,
        help_text=_('Enable batch/lot tracking for this product')
    )
    track_expiry = models.BooleanField(
        _('track expiry dates'),
        default=False,
        help_text=_('Enable expiry date tracking for this product')
    )
    
    # Restaurant-specific fields
    allergens = models.ManyToManyField('Allergy', blank=True, related_name='products')  # For ingredients, set allergens to indicate which allergens the ingredient contains
    nutritional_info = models.JSONField(_('nutritional info'), default=dict, blank=True, help_text=_('Nutritional information'))
    is_available_for_sale = models.BooleanField(_('available for sale'), default=True, help_text=_('Whether this product can be sold directly'))
    is_available_for_recipes = models.BooleanField(_('available for recipes'), default=True, help_text=_('Whether this product can be used in recipes'))
    
    # Status
    is_active = models.BooleanField(_('is active'), default=True)
    notes = models.TextField(_('notes'), blank=True)
    
    # Relationships
    branches = models.ManyToManyField(
        BranchModel,
        through='BranchStock',
        related_name='products',
        verbose_name=_('branches')
    )
    
    # KDS station type
    KDS_STATION_TYPES = [
        ('hot_kitchen', _('Hot Kitchen')),
        ('cold_kitchen', _('Cold Kitchen')),
        ('prep', _('Prep Station')),
        ('beverage', _('Beverage Station')),
    ]
    kds_station_type = models.CharField(
        _('KDS station type'),
        max_length=50,
        choices=KDS_STATION_TYPES,
        default='hot_kitchen',
        help_text=_('Default kitchen station for this product')
    )
    
    class Meta:
        verbose_name = _('product')
        verbose_name_plural = _('products')
        ordering = ('name',)
        indexes = [
            models.Index(fields=['SKU'], name='product_sku_idx'),
            models.Index(fields=['barcode'], name='product_barcode_idx'),
            models.Index(fields=['is_active'], name='product_active_idx'),
            models.Index(fields=['product_type'], name='product_type_idx'),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.SKU})"
    
    def save(self, *args, **kwargs):
        """Save the product, ensuring required fields are set."""
        # Let BarcodeMixin handle barcode generation
        super().save(*args, **kwargs)

    def get_stock_for_branch(self, branch):
        """Get stock level for a specific branch."""
        try:
            return self.branch_stock.get(branch=branch)
        except BranchStock.DoesNotExist:
            return None
    
    def add_to_branch(self, branch, **kwargs):
        """Add this product to a branch with optional stock level."""
        return BranchStock.objects.create(product=self,branch=branch,**kwargs)
    
    def get_default_image(self):
        """Get the default image for this product."""
        return self.images.filter(is_default=True, is_active=True).first()
    
    def get_first_image(self):
        """Get the first active image for this product."""
        return self.images.filter(is_active=True).first()
    
    def get_image_url(self):
        """Get the URL of the default or first image."""
        default_image = self.get_default_image()
        if default_image and default_image.image:
            return default_image.image.url
        
        first_image = self.get_first_image()
        if first_image and first_image.image:
            return first_image.image.url
        
        return None
    
    def has_images(self):
        """Check if the product has any active images."""
        return self.images.filter(is_active=True).exists()
    
    def is_ingredient(self):
        """Check if this product is an ingredient."""
        return self.product_type == 'ingredient'
    
    def is_finished_product(self):
        """Check if this product is a finished product."""
        return self.product_type == 'finished_product'
    
    def is_beverage(self):
        """Check if this product is a beverage."""
        return self.product_type == 'beverage'
    
    def get_stock_status(self, branch=None):
        """Get stock status for a branch."""
        if not branch:
            return 'unknown'
        
        branch_stock = self.get_stock_for_branch(branch)
        if not branch_stock:
            return 'not_available'
        
        if branch_stock.current_stock <= 0:
            return 'out_of_stock'
        elif branch_stock.current_stock <= branch_stock.reorder_level:
            return 'low_stock'
        else:
            return 'in_stock'
    
    def get_related_recipes(self):
        """Get recipes that use this ingredient."""
        return Recipe.objects.filter(ingredients__ingredient=self, menu_item__is_active=True)
    
    def get_usage_in_recipes(self):
        """Get how this ingredient is used in recipes."""
        return self.recipe_ingredients.filter(recipe__menu_item__is_active=True)

    def get_kds_station_type(self):
        """Return the KDS station type for this product."""
        return self.kds_station_type

class ProductVariant(BarcodeMixin, BaseNameDescriptionModel, TimestampedModel, SoftDeleteModel):
    """Product variant model for tracking different variants of a product."""
    product = models.ForeignKey(Product,on_delete=models.CASCADE,related_name='variants',verbose_name=_('product'))
    sku = models.CharField(_('SKU'),max_length=50,unique=True)
    barcode = models.CharField(_('barcode'),max_length=100,blank=True,unique=True, db_index=True)
    name = models.CharField(_('name'),max_length=200)
    description = models.TextField(_('description'),blank=True)
    category = models.ForeignKey(Category,on_delete=models.SET_NULL,null=True,blank=True,related_name='variants',verbose_name=_('category'))
    supplier = models.ForeignKey(Supplier,on_delete=models.SET_NULL,null=True,blank=True,related_name='variants',verbose_name=_('supplier'))
    unit_of_measure = models.ForeignKey(UnitOfMeasure,on_delete=models.PROTECT,related_name='variants',verbose_name=_('unit of measure'),help_text=_('Standard unit for this product variant'))
    cost_price = models.DecimalField(_('cost price'),max_digits=10,decimal_places=2,validators=[MinValueValidator(0)],help_text=_('Default cost price for new branches'))
    selling_price = models.DecimalField(_('selling price'),max_digits=10,decimal_places=2,validators=[MinValueValidator(0)],help_text=_('Default selling price for new branches'))
    is_active = models.BooleanField(_('is active'),default=True)
    notes = models.TextField(_('notes'),blank=True)
    
    class Meta:
        verbose_name = _('product variant')
        verbose_name_plural = _('product variants')
        ordering = ('name',)
        indexes = [
            models.Index(fields=['sku'],name='productvariant_sku_idx'),
            models.Index(fields=['barcode'],name='productvariant_barcode_idx'),
            models.Index(fields=['is_active'],name='productvariant_active_idx'),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.sku})"

class BranchStock(TimestampedModel, SoftDeleteModel):
    """
    Tracks product stock levels per branch.
    This allows each branch to have different stock levels and pricing for the same product.
    """
    product = models.ForeignKey(Product,on_delete=models.CASCADE,related_name='branch_stock',verbose_name=_('product'))
    branch = models.ForeignKey(BranchModel,on_delete=models.CASCADE,related_name='stock_items',verbose_name=_('branch'))
    current_stock = models.DecimalField(_('current stock'),max_digits=10,decimal_places=3,default=0,validators=[MinValueValidator(0)])
    reorder_level = models.DecimalField(_('reorder level'),max_digits=10,decimal_places=3,default=0,validators=[MinValueValidator(0)])
    cost_price = models.DecimalField(_('cost price'),max_digits=10,decimal_places=2,null=True,blank=True,validators=[MinValueValidator(0)],help_text=_('Leave blank to use product default'))
    selling_price = models.DecimalField(_('selling price'),max_digits=10,decimal_places=2,null=True,blank=True,validators=[MinValueValidator(0)],help_text=_('Leave blank to use product default'))
    last_restocked = models.DateTimeField(_('last restocked'), null=True, blank=True)
    is_active = models.BooleanField(_('is active'), default=True)
    
    class Meta:
        verbose_name = _('branch stock')
        verbose_name_plural = _('branch stock levels')
        unique_together = (('product', 'branch'),)
        ordering = ('product__name', 'branch__name')
    
    def __str__(self):
        return f"{self.product.name} at {self.branch.name}"
    
    def clean(self):
        # Removed company validation since Supplier model doesn't have a company field
        # If company validation is needed in the future, add a company field to the Supplier model
        # and uncomment the following code:
        # if hasattr(self, 'branch') and hasattr(self, 'product') and hasattr(self.product, 'supplier') and self.product.supplier:
        #     if self.branch.company != self.product.supplier.company:
        #         raise ValidationError({
        #             'branch': _('Branch and supplier must belong to the same company')
        #         })
        pass
    
    def save(self, *args, **kwargs):
        # Set default prices from product if not set
        if self.cost_price is None:
            self.cost_price = self.product.cost_price
        if self.selling_price is None:
            self.selling_price = self.product.selling_price
        
        super().save(*args, **kwargs)

class Batch(TimestampedModel, SoftDeleteModel):
    """Tracks batches or lots for products that require it.
    Each batch has a unique identifier and optional expiry date.
    """
    batch_number = models.CharField(_('batch/lot number'),max_length=100,help_text=_('Unique identifier for this batch/lot'))
    product = models.ForeignKey('Product',on_delete=models.CASCADE,related_name='batches',verbose_name=_('product'))
    manufactured_date = models.DateField(_('manufactured date'),null=True,blank=True,help_text=_('Date when this batch was manufactured'))
    expiry_date = models.DateField(_('expiry date'),null=True,blank=True,help_text=_('Expiry date for this batch (if applicable)'))
    notes = models.TextField(_('notes'), blank=True)
    is_active = models.BooleanField(_('is active'), default=True)

    class Meta:
        verbose_name = _('batch')
        verbose_name_plural = _('batches')
        ordering = ['expiry_date', 'batch_number']
        unique_together = [['product', 'batch_number']]
        constraints = [
            models.CheckConstraint(
                check=Q(expiry_date__isnull=True) | Q(manufactured_date__isnull=True) | Q(expiry_date__gte=F('manufactured_date')),
                name='valid_expiry_date'
            )
        ]

    def __str__(self):
        return f"{self.product.name} - {self.batch_number}"

    def clean(self):
        if self.expiry_date and self.manufactured_date and self.expiry_date < self.manufactured_date:
            raise ValidationError({
                'expiry_date': _('Expiry date cannot be before manufactured date')
            })

        if self.product and not self.product.track_batches:
            raise ValidationError({
                'product': _('Batch tracking is not enabled for this product')
            })

        if self.product and self.product.track_expiry and not self.expiry_date:
            raise ValidationError({
                'expiry_date': _('Expiry date is required for this product')
            })

class BatchStock(TimestampedModel, SoftDeleteModel):
    """Tracks stock levels for specific batches at each branch."""
    batch = models.ForeignKey(Batch,on_delete=models.CASCADE,related_name='branch_stock',verbose_name=_('batch'))
    branch = models.ForeignKey(BranchModel,on_delete=models.CASCADE,related_name='batch_stock',verbose_name=_('branch'))
    quantity = models.DecimalField(_('quantity'),max_digits=10,decimal_places=3,default=0,validators=[MinValueValidator(0)])
    reserved_quantity = models.DecimalField(_('reserved quantity'),max_digits=10,decimal_places=3,default=0,validators=[MinValueValidator(0)])
    last_checked = models.DateTimeField(_('last checked'),auto_now=True,help_text=_('When this batch stock was last checked or updated'))

    class Meta:
        verbose_name = _('batch stock')
        verbose_name_plural = _('batch stock')
        unique_together = [['batch', 'branch']]
        ordering = ['batch__expiry_date', 'batch__batch_number']

    def __str__(self):
        return f"{self.batch} at {self.branch.name} - {self.quantity} in stock"

    def clean(self):
        if self.quantity < 0:
            raise ValidationError({
                'quantity': _('Quantity cannot be negative')
            })
        if self.reserved_quantity < 0:
            raise ValidationError({
                'reserved_quantity': _('Reserved quantity cannot be negative')
            })
        if self.reserved_quantity > self.quantity:
            raise ValidationError({
                'reserved_quantity': _('Cannot reserve more than available quantity')
            })

    @property
    def available_quantity(self):
        """Calculate available quantity (total - reserved)."""
        return self.quantity - self.reserved_quantity

class InventoryTransaction(BaseNameDescriptionModel, TimestampedModel, SoftDeleteModel):
    """Tracks all inventory movements across branches."""
    TRANSACTION_TYPES = (
        ('purchase', _('Purchase')),
        ('sale', _('Sale')),
        ('return', _('Return')),
        ('adjustment', _('Adjustment')),
        ('transfer', _('Transfer')),
        ('waste', _('Waste')),
        ('production', _('Production')),
    )

    product = models.ForeignKey(Product,on_delete=models.CASCADE,related_name='inventory_transactions',verbose_name=_('product'))
    branch = models.ForeignKey(BranchModel,on_delete=models.CASCADE,related_name='inventory_transactions',verbose_name=_('branch'),null=True,blank=True)
    branch_stock = models.ForeignKey('BranchStock',on_delete=models.CASCADE,related_name='transactions',verbose_name=_('branch stock'),null=True,blank=True)
    transaction_type = models.CharField(_('transaction type'),max_length=20,choices=TRANSACTION_TYPES)
    quantity = models.DecimalField(_('quantity'),max_digits=10,decimal_places=3,validators=[MinValueValidator(0.001)])
    reference = models.CharField(_('reference'), max_length=100, blank=True)
    notes = models.TextField(_('notes'), blank=True)
    created_by = models.ForeignKey(User,on_delete=models.SET_NULL,null=True,related_name='inventory_transactions',verbose_name=_('created by'))
    # related_order will be added when sales app is created
    related_order = models.ForeignKey('sales.Order',on_delete=models.SET_NULL,null=True,blank=True,related_name='inventory_transactions',verbose_name=_('related order'))

    class Meta:
        verbose_name = _('inventory transaction')
        verbose_name_plural = _('inventory transactions')
        ordering = ('-created_at',)

    def save(self, *args, **kwargs):
        """Save inventory transaction."""
        super().save(*args, **kwargs)

class InventoryAdjustment(BaseNameDescriptionModel, TimestampedModel, SoftDeleteModel):
    """Tracks manual inventory adjustments with approval workflow.
    Each adjustment is specific to a branch.
    """
    STATUS_CHOICES = (
        ('pending', _('Pending')),
        ('approved', _('Approved')),
        ('rejected', _('Rejected')),
    )

    product = models.ForeignKey(Product,on_delete=models.CASCADE,related_name='adjustments',verbose_name=_('product'))
    branch = models.ForeignKey(BranchModel,on_delete=models.CASCADE,related_name='inventory_adjustments',verbose_name=_('branch'),null=True,blank=True)
    branch_stock = models.ForeignKey(BranchStock,on_delete=models.CASCADE,related_name='adjustments',verbose_name=_('branch stock'),null=True,blank=True)
    quantity_before = models.DecimalField(_('quantity before'),max_digits=10,decimal_places=3)
    quantity_after = models.DecimalField(_('quantity after'),max_digits=10,decimal_places=3,validators=[MinValueValidator(0)])
    reason = models.TextField(_('reason'))
    status = models.CharField(_('status'),max_length=20,choices=STATUS_CHOICES,default='pending')
    requested_by = models.ForeignKey(User,on_delete=models.SET_NULL,null=True,related_name='requested_adjustments',verbose_name=_('requested by'))
    reviewed_by = models.ForeignKey(User,on_delete=models.SET_NULL,null=True,blank=True,related_name='reviewed_adjustments',verbose_name=_('reviewed by'))
    reviewed_at = models.DateTimeField(_('reviewed at'), null=True, blank=True)
    review_notes = models.TextField(_('review notes'), blank=True)

    class Meta:
        verbose_name = _('inventory adjustment')
        verbose_name_plural = _('inventory adjustments')
        ordering = ('-created_at',)

    def save(self, *args, **kwargs):
        """Save inventory adjustment."""
        super().save(*args, **kwargs)

class Modifier(TimestampedModel, SoftDeleteModel):
    """Menu modifier model for add-ons, customizations, and options."""
    name = models.CharField(_('name'), max_length=200)
    description = models.TextField(_('description'), blank=True)
    modifier_type = models.CharField(_('modifier type'), max_length=20, choices=[
        ('single', _('Single Selection')),
        ('multiple', _('Multiple Selection')),
        ('required', _('Required')),
        ('optional', _('Optional')),
    ], default='optional')
    price = models.DecimalField(_('price'), max_digits=10, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    min_selections = models.PositiveIntegerField(_('minimum selections'), default=0)
    max_selections = models.PositiveIntegerField(_('maximum selections'), default=1, help_text=_('Use 0 for unlimited'))
    is_active = models.BooleanField(_('is active'), default=True)
    image = models.ImageField(_('image'), upload_to='modifiers/', blank=True, null=True)
    display_order = models.PositiveIntegerField(_('display order'), default=0)
    branch = models.ForeignKey(BranchModel, on_delete=models.CASCADE, related_name='modifiers', verbose_name=_('branch'))
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_modifiers', verbose_name=_('created by'))

    class Meta:
        verbose_name = _('modifier')
        verbose_name_plural = _('modifiers')
        ordering = ('display_order', 'name')
        unique_together = (('branch', 'name'),)

    def __str__(self):
        return f"{self.name} - {self.branch.name}"


class ModifierOption(TimestampedModel, SoftDeleteModel):
    """Individual options within a modifier."""
    modifier = models.ForeignKey(Modifier, on_delete=models.CASCADE, related_name='options', verbose_name=_('modifier'))
    name = models.CharField(_('name'), max_length=200)
    description = models.TextField(_('description'), blank=True)
    price_adjustment = models.DecimalField(_('price adjustment'), max_digits=10, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    is_active = models.BooleanField(_('is active'), default=True)
    display_order = models.PositiveIntegerField(_('display order'), default=0)
    allergens = models.ManyToManyField(Allergy, blank=True, related_name='modifier_options')

    class Meta:
        verbose_name = _('modifier option')
        verbose_name_plural = _('modifier options')
        ordering = ('display_order', 'name')
        unique_together = (('modifier', 'name'),)

    def __str__(self):
        return f"{self.name} ({self.modifier.name})"


class MenuItemModifier(TimestampedModel, SoftDeleteModel):
    """Links menu items to modifiers."""
    menu_item = models.ForeignKey(MenuItem, on_delete=models.CASCADE, related_name='modifiers', verbose_name=_('menu item'))
    modifier = models.ForeignKey(Modifier, on_delete=models.CASCADE, related_name='menu_items', verbose_name=_('modifier'))
    is_required = models.BooleanField(_('is required'), default=False)
    display_order = models.PositiveIntegerField(_('display order'), default=0)

    class Meta:
        verbose_name = _('menu item modifier')
        verbose_name_plural = _('menu item modifiers')
        unique_together = (('menu_item', 'modifier'),)
        ordering = ('display_order',)

    def __str__(self):
        return f"{self.menu_item.name} - {self.modifier.name}"

class StockCount(TimestampedModel, SoftDeleteModel):
    """Model for recording physical stock counts."""
    product = models.ForeignKey('Product', on_delete=models.CASCADE, related_name='stock_counts')
    branch = models.ForeignKey('branches.Branch', on_delete=models.CASCADE, related_name='stock_counts')
    counted_quantity = models.DecimalField(_('counted quantity'), max_digits=10, decimal_places=3)
    date = models.DateField(_('date'))
    notes = models.TextField(_('notes'), blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='stock_counts')

    class Meta:
        verbose_name = _('stock count')
        verbose_name_plural = _('stock counts')
        ordering = ('-date', 'product__name')

    def __str__(self):
        return f"{self.product.name} @ {self.branch.name} on {self.date} ({self.counted_quantity})"

    def save(self, *args, **kwargs):
        """Save stock count."""
        super().save(*args, **kwargs)

class PurchaseOrder(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('ordered', 'Ordered'),
        ('received', 'Received'),
        ('cancelled', 'Cancelled'),
    ]
    supplier = models.ForeignKey('Supplier', on_delete=models.CASCADE, related_name='purchase_orders')
    receiving_branch = models.ForeignKey('branches.Branch', on_delete=models.CASCADE, related_name='receiving_purchase_orders', verbose_name='receiving branch')
    expected_delivery = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_purchase_orders')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"PO #{self.id} - {self.supplier.name}"

    def save(self, *args, **kwargs):
        """Save purchase order."""
        super().save(*args, **kwargs)

class PurchaseOrderItem(models.Model):
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('Product', on_delete=models.CASCADE)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.product.name} x {self.quantity} (PO #{self.purchase_order.id})"

class StockTransfer(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    source_branch = models.ForeignKey('branches.Branch', on_delete=models.CASCADE, related_name='outgoing_transfers')
    target_branch = models.ForeignKey('branches.Branch', on_delete=models.CASCADE, related_name='incoming_transfers')
    product = models.ForeignKey('Product', on_delete=models.CASCADE)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_stock_transfers')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Transfer {self.product.name} x {self.quantity} from {self.source_branch.name} to {self.target_branch.name}"

    def save(self, *args, **kwargs):
        """Save stock transfer."""
        super().save(*args, **kwargs)


# Django Signals for automatic stock management
@receiver(post_save, sender=Product)
def create_branch_stock_for_product(sender, instance, created, **kwargs):
    """Automatically create BranchStock entries when a product is created."""
    if created:
        # Get all active branches
        from apps.branches.models import Branch
        branches = Branch.objects.filter(is_active=True)
        
        for branch in branches:
            BranchStock.objects.get_or_create(
                product=instance,
                branch=branch,
                defaults={
                    'current_stock': 0,
                    'reorder_level': 0,
                    'cost_price': instance.cost_price,
                    'selling_price': instance.selling_price,
                    'is_active': True
                }
            )


@receiver(post_save, sender=MenuItem)
def create_branch_stock_for_menu_item(sender, instance, created, **kwargs):
    """Automatically create BranchStock entries when a menu item is created."""
    if created:
        # Get the branch from the menu
        branch = instance.menu.branch
        
        # Create a product for the menu item if it doesn't exist
        product, product_created = Product.objects.get_or_create(
            name=instance.name,
            defaults={
                'SKU': f'MI-{instance.id}',
                'description': instance.description,
                'product_type': 'finished_product',
                'category': instance.category,
                'unit_of_measure': UnitOfMeasure.objects.filter(code='pcs').first(),
                'cost_price': instance.cost_price,
                'selling_price': instance.selling_price,
                'is_available_for_sale': True,
                'is_available_for_recipes': False,
                'is_active': True
            }
        )
        
        # Create BranchStock for the menu item's product
        BranchStock.objects.get_or_create(
            product=product,
            branch=branch,
            defaults={
                'current_stock': 0,
                'reorder_level': 0,
                'cost_price': instance.cost_price,
                'selling_price': instance.selling_price,
                'is_active': True
            }
        )


@receiver(post_save, sender=PurchaseOrder)
def create_inventory_transaction_for_purchase(sender, instance, created, **kwargs):
    """Create inventory transactions when purchase orders are received."""
    if instance.status == 'received' and not created:
        # Get the previous status
        try:
            old_instance = PurchaseOrder.objects.get(pk=instance.pk)
            if old_instance.status != 'received':
                # Create inventory transactions for all items
                for item in instance.items.all():
                    # Get or create branch stock
                    branch_stock, created = BranchStock.objects.get_or_create(
                        product=item.product,
                        branch=instance.receiving_branch,
                        defaults={
                            'current_stock': 0,
                            'reorder_level': 0,
                            'is_active': True
                        }
                    )
                    
                    # Update stock level
                    branch_stock.current_stock += item.quantity
                    branch_stock.last_restocked = timezone.now()
                    branch_stock.save()
                    
                    # Create inventory transaction
                    InventoryTransaction.objects.create(
                        product=item.product,
                        branch=instance.receiving_branch,
                        branch_stock=branch_stock,
                        transaction_type='purchase',
                        quantity=item.quantity,
                        reference=f'PO-{instance.id}',
                        notes=f'Purchase order {instance.id} received',
                        created_by=instance.created_by,
                        related_order=None
                    )
        except PurchaseOrder.DoesNotExist:
            pass


@receiver(post_save, sender=InventoryAdjustment)
def create_inventory_transaction_for_adjustment(sender, instance, created, **kwargs):
    """Create inventory transactions when adjustments are approved."""
    if instance.status == 'approved' and not created:
        # Get the previous status
        try:
            old_instance = InventoryAdjustment.objects.get(pk=instance.pk)
            if old_instance.status != 'approved':
                # Calculate the adjustment quantity
                adjustment_quantity = instance.quantity_after - instance.quantity_before
                
                # Get or create branch stock
                branch_stock, created = BranchStock.objects.get_or_create(
                    product=instance.product,
                    branch=instance.branch,
                    defaults={
                        'current_stock': 0,
                        'reorder_level': 0,
                        'is_active': True
                    }
                )
                
                # Update stock level
                branch_stock.current_stock = instance.quantity_after
                branch_stock.save()
                
                # Create inventory transaction
                InventoryTransaction.objects.create(
                    product=instance.product,
                    branch=instance.branch,
                    branch_stock=branch_stock,
                    transaction_type='adjustment',
                    quantity=adjustment_quantity,
                    reference=f'ADJ-{instance.id}',
                    notes=f'Adjustment: {instance.reason}',
                    created_by=instance.reviewed_by,
                    related_order=None
                )
        except InventoryAdjustment.DoesNotExist:
            pass
