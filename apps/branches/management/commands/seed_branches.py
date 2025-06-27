"""
Management command to seed sample branch data.
"""
import random
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings

from apps.branches.models import Company, Branch
from apps.accounts.models import User


class Command(BaseCommand):
    help = 'Seed sample branch data for development and testing'

    def handle(self, *args, **options):
        self.stdout.write('Seeding sample branch data...')
        
        # Get or create a superuser for branch management
        admin_user = User.objects.filter(is_superuser=True).first()
        if not admin_user:
            admin_user = User.objects.get_or_create(
                email='admin@example.com',
                defaults={
                "password":'admin123',
                'first_name':'Admin',
                'last_name':'User'
                }
            )
            self.stdout.write(self.style.SUCCESS('Created admin user'))
        else:
            self.stdout.write('Using existing admin user')
        
        # Sample companies
        companies = [
            {
                'name': 'Kitchen Bloom',
                'legal_name': 'Kitchen Bloom Limited',
                'tax_id': 'P05123456789',
                'registration_number': 'CPT-123456',
                'primary_contact_email': 'info@kitchenbloom.com',
                'primary_contact_phone': '+254712345678',
                'address': '123 Garden Road',
                'city': 'Nairobi',
                'state': 'Nairobi',
                'postal_code': '00100',
                'country': 'Kenya',
                'branches': [
                    {
                        'name': 'Main Branch',
                        'code': 'MB001',
                        'address': '123 Garden Road',
                        'city': 'Nairobi',
                        'phone': '+254712345678',
                        'is_default': True
                    }
                ]
            },
        ]
        
        created_companies = 0
        created_branches = 0
        
        for company_data in companies:
            branches_data = company_data.pop('branches')
            
            # Create or update company
            company, created = Company.objects.update_or_create(
                name=company_data['name'],
                defaults=company_data
            )
            
            if created:
                created_companies += 1
            
            # Create branches for the company
            for branch_data in branches_data:
                is_default = branch_data.pop('is_default', False)
                
                # Set the first branch as default if none is specified
                if is_default or not Branch.objects.filter(company=company, is_default=True).exists():
                    branch_data['is_default'] = True
                
                # Set manager to admin for now
                branch_data['manager'] = admin_user
                
                # Create or update branch
                branch, created = Branch.objects.update_or_create(
                    company=company,
                    code=branch_data['code'],
                    defaults=branch_data
                )
                
                if created:
                    created_branches += 1
        
        self.stdout.write(self.style.SUCCESS(
            f'Successfully seeded {created_companies} companies and {created_branches} branches.'
        ))
        
        # Print login info for the admin user
        self.stdout.write(self.style.SUCCESS(
            f'\nAdmin login:\n'
            f'Username: {admin_user}\n'
            f'Password: admin123\n\n'
            'Please change the password after first login.'
        ))
