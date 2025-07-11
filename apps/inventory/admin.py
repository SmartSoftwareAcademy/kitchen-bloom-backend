from django.contrib import admin
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from apps.branches.models import Branch
from .models import (
    Category, Menu, MenuItem, Recipe, RecipeIngredient, Supplier, UnitOfMeasure, ProductImage, Product, ProductVariant, BranchStock, Batch, BatchStock, InventoryTransaction, InventoryAdjustment, Allergy
)


class BranchStockInline(admin.TabularInline):
    model = BranchStock
    extra = 1
    fields = ('branch', 'current_stock', 'reorder_level', 'cost_price', 'selling_price', 'is_active')
    readonly_fields = ('branch', 'last_restocked')
    show_change_link = True
    
    def has_add_permission(self, request, obj=None):
        return False


class InventoryTransactionInline(admin.TabularInline):
    model = InventoryTransaction
    extra = 0
    readonly_fields = ('branch', 'created_at', 'created_by', 'transaction_type', 'quantity', 'reference', 'notes')
    fields = ('branch', 'transaction_type', 'quantity', 'reference', 'created_at', 'created_by', 'notes')
    can_delete = False
    show_change_link = True
    
    def has_add_permission(self, request, obj=None):
        return False


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    fields = ('image', 'is_default', 'is_active')
    readonly_fields = ('created_at', 'updated_at')


class CategoryFilter(admin.SimpleListFilter):
    title = _('category')
    parameter_name = 'category'
    
    def lookups(self, request, model_admin):
        categories = Category.objects.filter(is_active=True)
        return [(cat.id, cat.name) for cat in categories]
    
    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(category_id=self.value())
        return queryset


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'parent', 'is_active', 'is_menu_category', 'is_ingredient_category', 'display_order')
    search_fields = ('name', 'description')
    list_filter = ('is_active', 'is_menu_category', 'is_ingredient_category')
    list_display_links = ('name',)
    list_editable = ('is_active', 'is_menu_category', 'is_ingredient_category', 'display_order')
    ordering = ('display_order', 'name')


class RecipeIngredientInline(admin.TabularInline):
    model = RecipeIngredient
    extra = 1

class MenuItemInline(admin.TabularInline):
    model = MenuItem
    extra = 0

@admin.register(Menu)
class MenuAdmin(admin.ModelAdmin):
    list_display = ('name', 'branch', 'is_active', 'is_default', 'valid_from', 'valid_until')
    search_fields = ('name', 'description')
    list_filter = ('is_active', 'is_default', 'branch')
    ordering = ('-is_default', 'name')
    inlines=[MenuItemInline,]


@admin.register(MenuItem)
class MenuItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'menu','image', 'category', 'selling_price', 'cost_price', 'is_available', 'is_featured', 'display_order', 'get_allergens', 'track_inventory')
    search_fields = ('name', 'description')
    list_filter = ('is_available', 'is_featured', 'menu', 'category')
    fieldsets = (
        (None, {
            'fields': ('menu','name', 'description', 'category', 'selling_price', 'cost_price', 'is_available', 'is_featured', 'display_order')
        }),
        ('Inventory', {
            'fields': ('track_inventory',)
        }),
        ('Allergens', {
            'fields': ('allergens',)
        }),
    )
    list_display_links = ('name',)
    list_editable = ('is_available', 'is_featured', 'display_order', 'track_inventory')
    ordering = ('display_order', 'name')
    filter_horizontal = ('allergens',)
    def get_allergens(self, obj):
        return ", ".join([a.name for a in obj.allergens.all()])
    get_allergens.short_description = 'Allergens'


@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    list_display = ('menu_item', 'difficulty_level', 'servings', 'created_by')
    search_fields = ('menu_item__name', 'instructions')
    list_filter = ('difficulty_level',)
    inlines = [RecipeIngredientInline]


@admin.register(RecipeIngredient)
class RecipeIngredientAdmin(admin.ModelAdmin):
    list_display = ('recipe', 'ingredient', 'quantity', 'unit_of_measure', 'is_optional')
    search_fields = ('ingredient__name', 'recipe__menu_item__name')
    list_filter = ('is_optional', 'unit_of_measure')



@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ('name', 'contact_person', 'email', 'phone', 'is_active')
    search_fields = ('name', 'contact_person', 'email', 'phone', 'tax_id')
    list_filter = ('is_active',)
    ordering = ('name',)


@admin.register(UnitOfMeasure)
class UnitOfMeasureAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'symbol', 'is_fraction_allowed')
    search_fields = ('code', 'name', 'symbol')
    list_filter = ('is_fraction_allowed',)
    ordering = ('name',)


@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    list_display = ('product', 'is_default', 'is_active')
    search_fields = ('product__name',)
    list_filter = ('is_default', 'is_active')


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    inlines=[ProductImageInline]
    list_display = ('SKU', 'name', 'product_type', 'category', 'supplier', 'unit_of_measure', 'cost_price', 'selling_price', 'is_active', 'get_allergens')
    search_fields = ('SKU', 'name', 'barcode', 'description')
    list_filter = ('product_type', 'category', 'supplier', 'unit_of_measure', 'is_active')
    list_display_links = ('SKU', 'name')
    list_editable = ('is_active',)
    
    ordering = ('name',)
    filter_horizontal = ('allergens',)
    def get_allergens(self, obj):
        return ", ".join([a.name for a in obj.allergens.all()])
    get_allergens.short_description = 'Allergens'


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = ('sku', 'name', 'product', 'category', 'supplier', 'unit_of_measure', 'cost_price', 'selling_price', 'is_active')
    search_fields = ('sku', 'name', 'barcode', 'description')
    list_filter = ('product', 'category', 'supplier', 'unit_of_measure', 'is_active')
    ordering = ('name',)


@admin.register(BranchStock)
class BranchStockAdmin(admin.ModelAdmin):
    list_display = ('product', 'branch', 'current_stock', 'reorder_level', 'cost_price', 'selling_price', 'last_restocked', 'is_active')
    search_fields = ('product__name', 'branch__name')
    list_filter = ('branch', 'is_active')
    ordering = ('product__name', 'branch__name')


@admin.register(Batch)
class BatchAdmin(admin.ModelAdmin):
    list_display = ('batch_number', 'product', 'manufactured_date', 'expiry_date', 'is_active')
    search_fields = ('batch_number', 'product__name')
    list_filter = ('product', 'is_active')
    ordering = ('expiry_date', 'batch_number')


@admin.register(BatchStock)
class BatchStockAdmin(admin.ModelAdmin):
    list_display = ('batch', 'branch', 'quantity', 'reserved_quantity', 'last_checked')
    search_fields = ('batch__batch_number', 'branch__name')
    list_filter = ('branch',)
    ordering = ('batch__expiry_date', 'batch__batch_number')


@admin.register(InventoryTransaction)
class InventoryTransactionAdmin(admin.ModelAdmin):
    list_display = ('product', 'branch', 'transaction_type', 'quantity', 'reference', 'created_by', 'related_order', 'created_at')
    search_fields = ('product__name', 'branch__name', 'reference', 'notes')
    list_filter = ('transaction_type', 'branch', 'created_by')
    ordering = ('-created_at',)


@admin.register(InventoryAdjustment)
class InventoryAdjustmentAdmin(admin.ModelAdmin):
    list_display = ('product', 'branch', 'branch_stock', 'quantity_before', 'quantity_after', 'reason', 'status', 'requested_by', 'reviewed_by', 'reviewed_at')
    search_fields = ('product__name', 'branch__name', 'reason', 'review_notes')
    list_filter = ('status', 'branch', 'requested_by', 'reviewed_by')
    ordering = ('-created_at',)


@admin.register(Allergy)
class AllergyAdmin(admin.ModelAdmin):
    list_display = ('name', 'severity', 'description', 'common_in', 'created_at')
    search_fields = ('name', 'description', 'common_in')
    list_filter = ('severity',)
    ordering = ('name',)



