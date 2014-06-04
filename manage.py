#!/usr/bin/env python

from pkg_resources import require
require('Django>=1.4, < 1.5')

import os
import sys

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "perf.settings")

    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)
