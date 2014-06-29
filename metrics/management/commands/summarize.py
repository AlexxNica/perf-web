from django.core.management.base import BaseCommand, CommandError
from metrics.views import resummarize

class Command(BaseCommand):
    help = 'Recompute time-range summaries and save the results to the database'

    def handle(self, *args, **options):
        resummarize()
