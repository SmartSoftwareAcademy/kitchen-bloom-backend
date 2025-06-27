from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction

from apps.branches.models import Branch
from apps.crm.models import Customer
from apps.sales.models import Order
from apps.loyalty.models import LoyaltyProgram,LoyaltyTier,LoyaltyTransaction,LoyaltyReward,LoyaltyRedemption

class Command(BaseCommand):
    help = 'Seed initial loyalty data'

    def handle(self, *args, **options):
        with transaction.atomic():
            # Create sample loyalty programs
            branch = Branch.objects.first()  # Get first branch
            
            # Points-based program
            points_program = LoyaltyProgram.objects.create(
                name='Points Rewards Program',
                program_type=LoyaltyProgram.ProgramType.POINTS,
                status=LoyaltyProgram.Status.ACTIVE,
                points_per_dollar=1.00,
                minimum_points_for_reward=1000,
                points_expiry_days=365,
                branch=branch,
                description='Earn 1 point for every dollar spent. Redeem points for rewards.'
            )

            # Create tiers for points program
            bronze_tier = LoyaltyTier.objects.create(
                program=points_program,
                name='Bronze',
                minimum_points=0,
                discount_percentage=0,
                special_benefits='Welcome to our loyalty program!'
            )

            silver_tier = LoyaltyTier.objects.create(
                program=points_program,
                name='Silver',
                minimum_points=5000,
                discount_percentage=5,
                special_benefits='5% discount on all purchases'
            )

            gold_tier = LoyaltyTier.objects.create(
                program=points_program,
                name='Gold',
                minimum_points=20000,
                discount_percentage=10,
                special_benefits='10% discount and free shipping'
            )

            # Create rewards
            free_coffee = LoyaltyReward.objects.create(
                program=points_program,
                name='Free Coffee',
                description='Get a free coffee with your next purchase',
                points_required=500,
                value=5.00,
                stock_quantity=100,
                is_active=True
            )

            ten_percent_discount = LoyaltyReward.objects.create(
                program=points_program,
                name='10% Discount Coupon',
                description='10% off your next purchase',
                points_required=1000,
                value=0.00,
                stock_quantity=50,
                is_active=True
            )

            # Create sample transactions for existing customers
            customers = Customer.objects.all()
            for customer in customers[:5]:  # Process first 5 customers
                # Get customer's recent orders
                orders = Order.objects.filter(customer=customer).order_by('-created_at')[:3]
                
                for order in orders:
                    points = points_program.calculate_points(order.total_amount)
                    LoyaltyTransaction.objects.create(
                        customer=customer,
                        program=points_program,
                        transaction_type=LoyaltyTransaction.TransactionType.EARN,
                        points=points,
                        reference_order=order,
                        notes=f"Points earned from order {order.order_number}"
                    )
                    
                    # Update customer tier
                    points_program.update_customer_tier(customer)

            self.stdout.write(
                self.style.SUCCESS('Successfully seeded loyalty data')
            )
