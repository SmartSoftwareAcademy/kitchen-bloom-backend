from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction

from apps.accounting.models import GiftCard

class Command(BaseCommand):
    help = 'Update status of gift cards (e.g., expire old cards, notify about soon-to-expire cards)'
    
    def add_arguments(self, parser):
        parser.add_argument('--expire',action='store_true',help='Mark expired gift cards as expired')
        parser.add_argument('--notify-days',type=int,default=30,help='Number of days before expiry to notify (default: 30)')
        parser.add_argument('--dry-run',action='store_true',help='Run without making any changes')
    
    def handle(self, *args, **options):
        expire = options['expire']
        notify_days = options['notify_days']
        dry_run = options['dry_run']
        now = timezone.now()
        
        if expire:
            self.stdout.write('Checking for expired gift cards...')
            expired_cards = GiftCard.objects.filter(
                status='active',
                expiry_date__isnull=False,
                expiry_date__lte=now
            )
            
            self.stdout.write(f'Found {expired_cards.count()} expired gift cards')
            
            if not dry_run:
                with transaction.atomic():
                    for card in expired_cards:
                        old_status = card.status
                        card.status = 'expired'
                        card.save(update_fields=['status', 'updated_at'])
                        self.stdout.write(self.style.SUCCESS(
                            f'Marked gift card {card.code} as expired (was {old_status})'
                        ))
        
        # Check for gift cards expiring soon
        expiry_threshold = now + timedelta(days=notify_days)
        expiring_soon = GiftCard.objects.filter(
            status='active',
            expiry_date__isnull=False,
            expiry_date__lte=expiry_threshold,
            expiry_date__gt=now
        )
        
        self.stdout.write('\nGift cards expiring soon:')
        if expiring_soon.exists():
            for card in expiring_soon:
                days_left = (card.expiry_date - now).days
                self.stdout.write(
                    f'- {card.code}: {card.currency} {card.current_balance:.2f} '
                    f'(Expires in {days_left} days on {card.expiry_date.strftime("%Y-%m-%d")}) '
                    f'for {card.issued_to.name if card.issued_to else "no customer"}'
                )
        else:
            self.stdout.write('No gift cards expiring soon.')
        
        # Summary
        active_count = GiftCard.objects.filter(status='active').count()
        expired_count = GiftCard.objects.filter(status='expired').count()
        redeemed_count = GiftCard.objects.filter(status='redeemed').count()
        voided_count = GiftCard.objects.filter(status='voided').count()
        
        self.stdout.write('\nGift Card Summary:')
        self.stdout.write(f'Active: {active_count}')
        self.stdout.write(f'Expired: {expired_count}')
        self.stdout.write(f'Redeemed: {redeemed_count}')
        self.stdout.write(f'Voided: {voided_count}')
