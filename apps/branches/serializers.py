from rest_framework import serializers
from django.db.models import Sum
from apps.branches.models import Company, Branch
from apps.base.utils import get_request_branch_id


class CompanySerializer(serializers.ModelSerializer):
    """Serializer for Company model."""
    branch_count = serializers.SerializerMethodField()
    active_branch_count = serializers.SerializerMethodField()
    branches = serializers.SerializerMethodField()

    class Meta:
        model = Company
        fields = [
            'id', 'name', 'legal_name', 'tax_id', 'registration_number',
            'logo', 'primary_contact_email', 'primary_contact_phone',
            'website', 'address', 'city', 'state', 'postal_code',
            'country', 'is_active', 'currency', 'timezone',
            'branch_count', 'active_branch_count', 'branches', 'created_at',
            'updated_at'
        ]
        read_only_fields = ['branch_count', 'active_branch_count', 'created_at', 'updated_at']

    def get_branch_count(self, obj):
        """Get total number of branches for the company."""
        return obj.branches.count()

    def get_active_branch_count(self, obj):
        """Get number of active branches for the company."""
        return obj.branches.filter(is_active=True).count()

    def get_branches(self, obj):
        """Get branches for the company with user context."""
        request = self.context.get('request')
        branch_id = get_request_branch_id(request)
        branches = obj.branches.filter(is_active=True)
        if branch_id:
            user_branch = branches.filter(id=branch_id).first()
        else:
            user = getattr(request, 'user', None)
            user_branch = None
            if user and hasattr(user, 'branch'):
                try:
                    user_branch = branches.get(id=user.branch.id)
                except Branch.DoesNotExist:
                    pass
            if not user_branch:
                user_branch = branches.filter(is_default=True).first()
            if not user_branch and branches.exists():
                user_branch = branches.first()
        if user_branch:
            return {
                'id': user_branch.id,
                'name': user_branch.name,
                'code': user_branch.code,
                'address': user_branch.address,
                'city': user_branch.city,
                'state': user_branch.state,
                'postal_code': user_branch.postal_code,
                'country': user_branch.country,
                'phone': user_branch.phone,
                'email': user_branch.email,
                'is_active': user_branch.is_active,
                'is_default': user_branch.is_default,
                'opening_hours': user_branch.opening_hours or {}
            }
        return None

class BranchSerializer(serializers.ModelSerializer):
    """Serializer for Branch model."""
    company_name = serializers.CharField(source='company.name', read_only=True)
    manager_name = serializers.CharField(source='manager.get_full_name', read_only=True)
    logo=serializers.URLField(source='company.logo', read_only=True)
    order_count = serializers.SerializerMethodField()
    active_order_count = serializers.SerializerMethodField()
    total_sales = serializers.SerializerMethodField()

    class Meta:
        model = Branch
        fields = [
            'id', 'company', 'company_name','logo', 'code', 'name', 'manager',
            'manager_name', 'address', 'city', 'state', 'postal_code',
            'country', 'phone', 'email', 'is_active', 'is_default',
            'opening_hours', 'location', 'metadata', 'order_count',
            'active_order_count', 'total_sales', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'order_count', 'active_order_count', 'total_sales', 'created_at', 'updated_at'
        ]

    def get_order_count(self, obj):
        """Get total number of orders for the branch."""
        from apps.sales.models import Order
        return Order.objects.filter(branch=obj).count()

    def get_active_order_count(self, obj):
        """Get number of active orders for the branch."""
        from apps.sales.models import Order
        return Order.objects.filter(
            branch=obj,
            status__in=['draft', 'confirmed', 'processing', 'ready']
        ).count()

    def get_total_sales(self, obj):
        """Get total sales amount for the branch."""
        from apps.sales.models import Order
        return Order.objects.filter(
            branch=obj,
            status='completed'
        ).aggregate(Sum('total_amount'))['total_amount__sum'] or 0

    def validate(self, data):
        """Validate branch data."""
        # Ensure branch code is unique within company
        if 'code' in data and 'company' in data:
            if Branch.objects.filter(
                company=data['company'],
                code=data['code']
            ).exclude(pk=self.instance.pk if self.instance else None).exists():
                raise serializers.ValidationError(
                    {'code': 'Branch code must be unique within company'}
                )
        return data

    def create(self, validated_data):
        """Create a new branch."""
        # Set default branch if no default exists for company
        if not Branch.objects.filter(
            company=validated_data['company'],
            is_default=True
        ).exists():
            validated_data['is_default'] = True
        
        # Create branch
        branch = super().create(validated_data)
        
        # Update company metadata with new branch
        company = branch.company
        company.metadata['branch_count'] = company.branches.count()
        company.save()
        
        return branch

    def update(self, instance, validated_data):
        """Update branch."""
        # Handle default branch changes
        if 'is_default' in validated_data and validated_data['is_default']:
            Branch.objects.filter(
                company=instance.company,
                is_default=True
            ).exclude(pk=instance.pk).update(is_default=False)
        
        # Update branch
        branch = super().update(instance, validated_data)
        
        # Update company metadata
        company = branch.company
        company.metadata['branch_count'] = company.branches.count()
        company.save()
        
        return branch


class BranchStatsSerializer(serializers.Serializer):
    """Serializer for branch statistics."""
    total_branches = serializers.IntegerField()
    active_branches = serializers.IntegerField()
    total_sales = serializers.DecimalField(max_digits=10, decimal_places=2)
    total_orders = serializers.IntegerField()
    average_sales = serializers.DecimalField(max_digits=10, decimal_places=2)
    top_branches = serializers.SerializerMethodField()

    def get_top_branches(self, obj):
        """Get top performing branches."""
        from apps.sales.models import Order
        top_branches = Branch.objects.annotate(
            total_sales=Sum('orders__total_amount')
        ).order_by('-total_sales')[:5]
        return BranchSerializer(top_branches, many=True).data
