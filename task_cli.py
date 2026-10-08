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
    return max(task["id"] for task in tasks)+1

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
        fail('usage: update 1 "buy groceries"')
    id = parse_id(args[0].strip())
    
    timestamp = now()
    tasks = load_tasks()
    if tasks == []:
        fail("No task has been created yet")
    for task in tasks:
        if task["id"] == id:
            task["description"] = args[1].strip()
            task["updatedAt"] = timestamp
        else:
            fail(f"task: {id} has not yet been created")
    save_tasks(tasks)
    print(f"successfully updated task: {task['id']}")
    

def cmd_delete(args):
    if len(args) != 1 or args[0].strip() == "":
        fail('usage: delete 1')
    id = parse_id(args[0].strip())
    tasks = load_tasks()
    if tasks == []:
        fail("No task has been created yet")
    newtask = []
    for task in tasks:
        if task["id"] != id:
            newtask.append(task)
    save_tasks(newtask)
    print(f"successfully deleted task: {id}")

def cmd_progress(args):
    if len(args) != 1 or args[0].strip() == "":
        fail('usage: mark-in-progress 1')
    id = parse_id(args[0].strip())
    tasks = load_tasks()
    for task in tasks:
        if task["id"] == id:
            task["status"] = "in-progress"
    save_tasks(tasks)
    print(f"successfully marked task: {id} status as in-progress")

def cmd_done(args):
    if len(args) != 1 or args[0].strip() == "":
        fail('usage: done 1')
    id = parse_id(args[0].strip())
    tasks = load_tasks()
    for task in tasks:
        if task["id"] == id:
            task["status"] = "done"
    save_tasks(tasks)
    print(f"successfully marked task: {id} status as done")

def cmd_all_list(args):
    tasks = load_tasks()
    if len(args) == 0:
        for task in tasks:
            i = 1
        print(f"{i}: {task["description"]}")
        i+=1
    elif len(args) == 1:
        cmd = args[0].strip()
        
        for task in tasks:
            i = 1
            if cmd == "done":
                if task["status"] == "done":
                    print(f"{i}: {task['description']}")
                    i += 1
            elif cmd == "in-progress":
                if task["status"] == "in-progress":
                    print(f"{i}: {task['description']}")
                    i += 1
            elif cmd == "todo":
                if task["status"] == "todo":
                    print(f"{i}: {task['description']}")
                    i += 1
    else:
        fail("usage: List Done, List Inprogress, List Todo")

    

COMMANDS = {
    "add": cmd_add,
    "update": cmd_update,
    "delete": cmd_delete,
    "mark-in-progress": cmd_progress,
    "mark-done": cmd_done,
    "list": cmd_all_list
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