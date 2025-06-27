from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from django.contrib.auth import get_user_model
from django.utils import timezone
from .models import (
    GiftCard, GiftCardRedemption, ExpenseCategory, Expense,
    RevenueCategory, Revenue, RevenueAccount
)
from apps.crm.models import Customer
from .utils import generate_number

User = get_user_model()

class RevenueAccountSerializer(serializers.ModelSerializer):
    """Serializer for revenue accounts."""
    class Meta:
        model = RevenueAccount
        fields = ['id','name','description','is_active','created_at','updated_at',]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate(self, attrs):
        """Validate the revenue account data."""
        if attrs['name'] == '':
            raise serializers.ValidationError({
                'name': _('Name cannot be empty')
            })
        return attrs
    
    def create(self, validated_data):
        """Create a new revenue account."""
        return RevenueAccount.objects.create(**validated_data)
    
    def update(self, instance, validated_data):
        """Update a revenue account."""
        instance.name = validated_data.get('name', instance.name)
        instance.description = validated_data.get('description', instance.description)
        instance.is_active = validated_data.get('is_active', instance.is_active)
        instance.save()
        return instance

class RevenueSerializer(serializers.ModelSerializer):
    """Serializer for revenues."""
    class Meta:
        model = Revenue
        fields = ['id','revenue_number','amount','currency','revenue_date','status','category','branch','employee','notes','created_at','updated_at','payment_date','payment_reference','payment_method']
        read_only_fields = ['id', 'created_at', 'updated_at','payment_date']
    
    def validate(self, attrs):
        """Validate the revenue data."""
        if attrs['amount'] <= 0:
            raise serializers.ValidationError({
                'amount': _('Amount must be greater than zero')
            })
        return attrs
    
    def create(self, validated_data):
        """Create a new revenue."""
        return Revenue.objects.create(**validated_data,revenue_number=generate_number('RE'),revenue_date=timezone.now(),status='draft',branch=self.context['request'].user.branch,employee=self.context['request'].user)
    
    def update(self, instance, validated_data):
        """Update a revenue."""
        instance.amount = validated_data.get('amount', instance.amount)
        instance.currency = validated_data.get('currency', instance.currency)
        instance.revenue_date = validated_data.get('revenue_date', instance.revenue_date)
        instance.status = validated_data.get('status', instance.status)
        instance.category = validated_data.get('category', instance.category)
        instance.branch = validated_data.get('branch', instance.branch)
        instance.employee = validated_data.get('employee', instance.employee)
        instance.notes = validated_data.get('notes', instance.notes)
        instance.save()
        return instance

class RevenueCategorySerializer(serializers.ModelSerializer):
    """Serializer for revenue categories."""
    class Meta:
        model = RevenueCategory
        fields = ['id','name','description','parent','is_active','created_at','updated_at',]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate(self, attrs):
        """Validate the revenue category data."""
        if attrs['name'] == '':
            raise serializers.ValidationError({
                'name': _('Name cannot be empty')
            })
        return attrs
    
    def create(self, validated_data):
        """Create a new revenue category."""
        return RevenueCategory.objects.create(**validated_data)
    
    def update(self, instance, validated_data):
        """Update a revenue category."""
        instance.name = validated_data.get('name', instance.name)
        instance.description = validated_data.get('description', instance.description)
        instance.is_active = validated_data.get('is_active', instance.is_active)
        instance.save()
        return instance

class ExpenseCategorySerializer(serializers.ModelSerializer):
    """Serializer for expense categories."""
    class Meta:
        model = ExpenseCategory
        fields = ['id','name','description','parent','is_active','created_at','updated_at',]
        read_only_fields = ['id', 'created_at', 'updated_at']

class ExpenseSerializer(serializers.ModelSerializer):
    """Serializer for expenses."""
    class Meta:
        model = Expense
        fields = ['id','expense_number','amount','currency','expense_date','status','category','branch','employee','notes','created_at','updated_at',]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate(self, attrs):
        """Validate the expense data."""
        if attrs['amount'] <= 0:
            raise serializers.ValidationError({
                'amount': _('Amount must be greater than zero')
            })
        return attrs
    
    def create(self, validated_data):
        """Create a new expense."""
        return Expense.objects.create(**validated_data,expense_number=generate_number('EX'),expense_date=timezone.now(),status='draft',branch=self.context['request'].user.branch,employee=self.context['request'].user)

class GiftCardRedemptionSerializer(serializers.ModelSerializer):
    """Serializer for gift card redemption history."""
    redemption_type_display = serializers.CharField(source='get_redemption_type_display',read_only=True)
    redeemed_by_name = serializers.SerializerMethodField()
    
    class Meta:
        model = GiftCardRedemption
        fields = ['id','gift_card','redemption_type','redemption_type_display','amount','balance_after','redeemed_by','redeemed_by_name','order','notes','created_at','updated_at',]
        read_only_fields = ['id', 'created_at', 'updated_at', 'balance_after','redemption_type_display','redeemed_by_name']
    
    def get_redeemed_by_name(self, obj):
        if obj.redeemed_by:
            return obj.redeemed_by.get_full_name() or obj.redeemed_by.email
        return None

class GiftCardSerializer(serializers.ModelSerializer):
    """Serializer for gift card details."""
    status_display = serializers.CharField(source='get_status_display',read_only=True)
    currency_display = serializers.CharField(source='get_currency_display',read_only=True)
    issued_to_name = serializers.CharField(source='issued_to.name',read_only=True)
    issued_by_name = serializers.SerializerMethodField()
    is_active = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = GiftCard
        fields = ['id','code','initial_value','current_balance','currency','currency_display','status','status_display','issue_date','expiry_date','issued_to','issued_to_name','issued_by','issued_by_name','is_active','notes','created_at','updated_at',]
        read_only_fields = ['id', 'created_at', 'updated_at', 'current_balance','status_display', 'currency_display', 'is_active','issued_to_name', 'issued_by_name']
    
    def get_issued_by_name(self, obj):
        if obj.issued_by:
            return obj.issued_by.get_full_name() or obj.issued_by.username
        return None
    
    def validate(self, attrs):
        """Validate the gift card data."""
        expiry_date = attrs.get('expiry_date')
        if expiry_date and expiry_date < timezone.now():
            raise serializers.ValidationError({
                'expiry_date': _('Expiry date cannot be in the past')
            })
        
        return attrs

class GiftCardCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating new gift cards."""
    customer_email = serializers.EmailField(write_only=True, required=False)
    customer_phone = serializers.CharField(write_only=True, required=False, max_length=20)
    
    class Meta:
        model = GiftCard
        fields = ['code','initial_value','currency','expiry_date','customer_email','customer_phone','notes',]
        extra_kwargs = {
            'code': {'required': True},
            'initial_value': {'required': True},
            'currency': {'required': True},
        }
    
    def validate(self, attrs):
        """Validate the gift card creation data."""
        email = attrs.pop('customer_email', None)
        phone = attrs.pop('customer_phone', None)
        
        if not email and not phone:
            raise serializers.ValidationError({
                'customer': _('Either customer email or phone is required')
            })
        
        try:
            if email:
                customer = Customer.objects.get(email=email)
            else:
                customer = Customer.objects.get(phone=phone)
        except Customer.DoesNotExist:
            raise serializers.ValidationError({
                'customer': _('Customer not found with the provided details')
            })
        
        attrs['issued_to'] = customer
        return attrs
    
    def create(self, validated_data):
        """Create a new gift card."""
        return GiftCard.objects.create(**validated_data,issued_by=self.context['request'].user,status='active',current_balance=validated_data['initial_value'])

class GiftCardRedeemSerializer(serializers.Serializer):
    """Serializer for redeeming gift cards."""
    amount = serializers.DecimalField(max_digits=12,decimal_places=2,min_value=0.01,required=True)
    order_id = serializers.IntegerField(required=False, allow_null=True)
    
    def validate_amount(self, value):
        """Validate the redemption amount."""
        if value <= 0:
            raise serializers.ValidationError(_('Amount must be greater than zero'))
        return value
    
    def validate(self, attrs):
        """Validate the redemption data."""
        gift_card = self.context.get('gift_card')
        if not gift_card:
            raise serializers.ValidationError(_('Gift card not found'))
        
        if not gift_card.is_active:
            raise serializers.ValidationError(_('This gift card is not active'))
            
        if attrs['amount'] > gift_card.current_balance:
            raise serializers.ValidationError({
                'amount': _('Amount exceeds the available balance')
            })
            
        return attrs
