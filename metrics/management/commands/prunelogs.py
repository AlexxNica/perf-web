from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

import os
import re
import sys
from datetime import datetime

LOG_RE = re.compile(r'^(\d{4}-\d\d-\d\d-\d\d:\d\d:\d\d)-[a-f0-9]+.json$')

# Number of logs to retain for each target
NUM_RETAIN = 5

class Command(BaseCommand):
    help = 'Clean up old log files'

    def handle(self, *args, **options):
        first = True
        for target in os.listdir(settings.LOG_ROOT):
            if not os.path.isdir(target):
                continue

            target_dir = os.path.join(settings.LOG_ROOT, target)

            to_sort = []
            for f in os.listdir(target_dir):
                m = LOG_RE.match(f)
                if not m:
                    print >>sys.stderr, "Log file " + f + " doesn't match pattern"
                    continue
                date = datetime.strptime(m.group(1), "%Y-%m-%d-%H:%M:%S")
                to_sort.append((date, f))

            to_sort.sort(lambda a, b: cmp(a[0], b[0]))
            if len(to_sort) <= NUM_RETAIN:
                continue

            if first:
                first = False
            else:
                print

            print target + ":"
            for (date, f) in to_sort[:len(to_sort)-NUM_RETAIN]:
                print "Removing: " + f
                os.remove(os.path.join(target_dir, f))
