from django.core.management.base import BaseCommand
from news_app.models import UserQuota
from django.contrib.auth.models import User
from django.utils import timezone

class Command(BaseCommand):
    help = 'Creates UserQuota for users without one' 

    def handle(self, *args, **options):
        # Get all users who don't have a UserQuota entry
        users_without_quota = User.objects.filter(quota__isnull=True)
        
        # Create UserQuota entries for users without one
        created_count = 0
        for user in users_without_quota:
            UserQuota.objects.create(
                user=user,
                quota_limit=10,
                used_quota=0
            )
            created_count += 1
        
       
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully created {created_count} new UserQuota entries'
            )
        )
       