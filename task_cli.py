# """Task Tracker CLI. Standard library only.

# Usage:
#     python task_cli.py add "Buy groceries"
#     python task_cli.py update 1 "Buy groceries and cook dinner"
#     python task_cli.py delete 1
#     python task_cli.py mark-in-progress 1
#     python task_cli.py mark-done 1
#     python task_cli.py list
#     python task_cli.py list todo|in-progress|done
# """

# import json
# import os
# import sys
# from datetime import datetime

# # The JSON file lives in the directory you run the command from.
# TASKS_FILE = "tasks.json"
# VALID_STATUSES = ("todo", "in-progress", "done")


# # ---------- helpers ----------

# def fail(message):
#     """Print an error message and exit with a non-zero code."""
#     print(f"Error: {message}")
#     sys.exit(1)


# def now():
#     """Current date and time as a readable ISO string, e.g. 2026-10-05T14:30:00."""
#     return datetime.now().isoformat(timespec="seconds")


# def parse_id(text):
#     """Turn the ID argument (always a string) into an int, or fail clearly."""
#     try:
#         return int(text)
#     except ValueError:
#         fail(f"'{text}' is not a valid task ID (use a whole number).")


# # ---------- storage layer ----------

# def load_tasks():
#     """Read all tasks from the JSON file. Missing file means no tasks yet."""
#     if not os.path.exists(TASKS_FILE):
#         return []
#     try:
#         with open(TASKS_FILE, "r", encoding="utf-8") as f:
#             content = f.read().strip()
#             if content == "":
#                 return []  # empty file: treat as no tasks
#             tasks = json.loads(content)
#     except json.JSONDecodeError:
#         fail(f"{TASKS_FILE} is not valid JSON. Fix or delete it.")
#     except OSError as e:
#         fail(f"could not read {TASKS_FILE}: {e}")
#     if not isinstance(tasks, list):
#         fail(f"{TASKS_FILE} should contain a list of tasks.")
#     return tasks


# def save_tasks(tasks):
#     """Write all tasks to the JSON file.

#     We write to a temporary file first, then swap it in. If the program
#     crashes mid-write, the original file is not left half-written.
#     """
#     temp_file = TASKS_FILE + ".tmp"
#     try:
#         with open(temp_file, "w", encoding="utf-8") as f:
#             json.dump(tasks, f, indent=2)
#         os.replace(temp_file, TASKS_FILE)
#     except OSError as e:
#         fail(f"could not write {TASKS_FILE}: {e}")


# def find_task(tasks, task_id):
#     """Return the task dict with this ID, or fail if there is none."""
#     for task in tasks:
#         if task["id"] == task_id:
#             return task
#     fail(f"no task with ID {task_id}.")


# def next_id(tasks):
#     """One higher than the largest existing ID. Deleting a task in the middle
#     never causes a duplicate ID. (Deleting the highest ID does free it for
#     reuse: a limitation worth thinking about.)"""
#     if not tasks:
#         return 1
#     return max(task["id"] for task in tasks) + 1


# # ---------- commands ----------
# # Each command receives the list of arguments that came after the command name.

# def cmd_add(args):
#     if len(args) != 1 or args[0].strip() == "":
#         fail('usage: add "description"')
#     tasks = load_tasks()
#     timestamp = now()
#     task = {
#         "id": next_id(tasks),
#         "description": args[0].strip(),
#         "status": "todo",
#         "createdAt": timestamp,
#         "updatedAt": timestamp,
#     }
#     tasks.append(task)
#     save_tasks(tasks)
#     print(f"Task added successfully (ID: {task['id']})")


# def cmd_update(args):
#     if len(args) != 2 or args[1].strip() == "":
#         fail('usage: update ID "new description"')
#     task_id = parse_id(args[0])
#     tasks = load_tasks()
#     task = find_task(tasks, task_id)
#     task["description"] = args[1].strip()
#     task["updatedAt"] = now()
#     save_tasks(tasks)
#     print(f"Task {task_id} updated successfully")


# def cmd_delete(args):
#     if len(args) != 1:
#         fail("usage: delete ID")
#     task_id = parse_id(args[0])
#     tasks = load_tasks()
#     task = find_task(tasks, task_id)  # fails if the ID doesn't exist
#     tasks.remove(task)
#     save_tasks(tasks)
#     print(f"Task {task_id} deleted successfully")


# def set_status(args, new_status, command_name):
#     """Shared logic for mark-in-progress and mark-done."""
#     if len(args) != 1:
#         fail(f"usage: {command_name} ID")
#     task_id = parse_id(args[0])
#     tasks = load_tasks()
#     task = find_task(tasks, task_id)
#     task["status"] = new_status
#     task["updatedAt"] = now()
#     save_tasks(tasks)
#     print(f"Task {task_id} marked as {new_status}")


# def cmd_mark_in_progress(args):
#     set_status(args, "in-progress", "mark-in-progress")


# def cmd_mark_done(args):
#     set_status(args, "done", "mark-done")


# def cmd_list(args):
#     if len(args) > 1:
#         fail("usage: list [todo|in-progress|done]")
#     status_filter = args[0] if args else None
#     if status_filter is not None and status_filter not in VALID_STATUSES:
#         fail(f"unknown status '{status_filter}'. Use: {', '.join(VALID_STATUSES)}")

#     tasks = load_tasks()
#     if status_filter:
#         tasks = [t for t in tasks if t["status"] == status_filter]

#     if not tasks:
#         print("No tasks found.")
#         return
#     for t in tasks:
#         print(f"[{t['id']}] {t['description']}")
#         print(f"     status: {t['status']} | created: {t['createdAt']} | updated: {t['updatedAt']}")


# # ---------- entry point ----------

# # Maps the command typed by the user to the function that handles it.
# COMMANDS = {
#     "add": cmd_add,
#     "update": cmd_update,
#     "delete": cmd_delete,
#     "mark-in-progress": cmd_mark_in_progress,
#     "mark-done": cmd_mark_done,
#     "list": cmd_list,
# }


# def main():
#     # sys.argv[0] is the script name, so real arguments start at index 1.
#     if len(sys.argv) < 2:
#         fail("no command given. Available: " + ", ".join(COMMANDS))
#     command = sys.argv[1]
#     handler = COMMANDS.get(command)
#     if handler is None:
#         fail(f"unknown command '{command}'. Available: " + ", ".join(COMMANDS))
#     handler(sys.argv[2:])


# # Runs main() only when this file is executed directly, not when imported.
# if __name__ == "__main__":
#     main()