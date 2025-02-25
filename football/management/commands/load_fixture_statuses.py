from django.core.management.base import BaseCommand
from football.models import FixtureStatus

class Command(BaseCommand):
    help = 'Load default fixture statuses'

    def handle(self, *args, **options):
        self.stdout.write('Loading fixture statuses...')
        FixtureStatus.create_default_statuses()
        self.stdout.write(self.style.SUCCESS('Successfully loaded fixture statuses'))