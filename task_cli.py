import json
import os
import sys
from datetime import datetime

TASKS_FILE = "tasks.json"
VALID_STATUSES = ("done", "in progress", "todo")

def fail(message):
    """Print an error message and exit with no-zero code"""
    print(f"Error: {message}")
    sys.exit()

def now():