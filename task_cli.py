import json
import os
import sys
from datetime import datetime

TASKS_FILE = "tasks.json"
VALID_STATUSES = ("done", "in progress", "todo")

# ---------- helpers ----------
def fail(message):
    """Print an error message and exit with no-zero code"""
    print(f"Error: {message}")
    sys.exit()


def now():
    return datetime.now().isoformat(timespec="seconds")

def parse_id(text):
    try:
        return int(text)
    except ValueError:
        fail(f"'{text}' is not a valid task ID (use a whole number).")

# ---------- storage layer ----------


def load_tasks():
    if not os.path.exists(TASKS_FILE):
        return []
    try:
        with open(TASKS_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if content == "":
                return []
            task = json.loads(content)
    except json.JSONDecodeError:
        fail(f"{TASKS_FILE} is not valid, fix or delete it.")
    except OSError as e:
        fail(f"could not read {TASKS_FILE}: {e}")
    if not isinstance(task, list):
        fail(f"{TASKS_FILE} should contain a list of tasks")
    return task


def save_tasks(tasks):
    temp = TASKS_FILE + ".tmp"
    try:
        with open(temp, "w", encoding="utf-8") as f:
             json.dump(tasks, f, indent=2)
        os.replace(temp, TASKS_FILE)
    except OSError as e:
        fail(f"could not write {TASKS_FILE}: {e}")


def find_task(tasks, task_id):
    for task in tasks:
        if task["id"] == task_id:
            return task
    fail(f"no task with ID {task_id}")


def next_id(tasks):
    if not tasks:
        return 1
    return max(tasks["id"] for task in tasks)+1

def cmd_add(args):
    if len(args) != 1 or args[0].strip() == "":
        fail('usage: add "description"')
    timestamp = now()
    tasks = load_tasks() # returns a list of available task in the json file and stores it in "tasks" variable
    task = {
        "id": next_id(tasks),
        "status": "todo",
        "description": args[0].strip(),
        "updatedAt": timestamp,
        "createdAt": timestamp,
    }
    tasks.append(task)
    save_tasks(tasks)
    print(f"successfully added task: {task['id']}")

def cmd_update(args):
    if len(args) != 2 or args[1].strip() == "":
        fail('usage: add "description"')
    id = parse_id(args[0].strip())
    
    timestamp = now()
    tasks = load_tasks()
    for task in tasks:
        if task["id"] == id:
            task["description"] = args[1].strip()
            task["updatedAt"] = timestamp

    save_tasks(tasks)
    print(f"successfully updated task: {task['id']}")
    



COMMANDS = {
    "add": cmd_add,
    "update": cmd_update
}

def main():
    if len(sys.argv) < 2:
        fail(f"no command given, Available: " + ", ".join(COMMANDS))
    command = sys.argv[1]
    handler = COMMANDS.get(command)
    if handler is None:
        fail(f"wrong {command}. Available: " + ", ".join({COMMANDS}))
    handler(sys.argv[2:])

if __name__ == "__main__":
    main()