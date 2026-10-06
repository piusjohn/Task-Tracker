import json
import os
import sys
from datetime import datetime

TASKS_FILE = "tasks.json"
VALID_STATUSES = ("done", "in progress", "todo")
