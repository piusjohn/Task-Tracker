"""Tests for the Task Tracker CLI, scoped strictly to the project spec.

Run from the folder containing task_cli.py and this file:
    python -m unittest -v test_task_cli.py

Each test runs the real CLI as a subprocess in a fresh temporary directory,
so it checks what the spec describes: positional arguments, a JSON file in
the current directory, the task properties, and graceful error handling.
Standard library only.
"""

import ast
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "task_cli.py"
TASKS_FILE = "tasks.json"          # change if you name your JSON file differently
REQUIRED_KEYS = {"id", "description", "status", "createdAt", "updatedAt"}
OLD_TIME = "2020-01-01T00:00:00"   # seeded timestamp, so any change is detectable


class CliTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.cwd = Path(self._tmp.name)
        self.file = self.cwd / TASKS_FILE

    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *map(str, args)],
            cwd=self.cwd, capture_output=True, text=True, timeout=10,
        )

    def tasks(self):
        return json.loads(self.file.read_text(encoding="utf-8"))

    def task_by_id(self, task_id):
        return next(t for t in self.tasks() if t["id"] == task_id)

    def seed(self, *items):
        """Write a tasks file directly. Each item is (description, status)."""
        data = [{"id": i, "description": d, "status": s,
                 "createdAt": OLD_TIME, "updatedAt": OLD_TIME}
                for i, (d, s) in enumerate(items, start=1)]
        self.file.write_text(json.dumps(data), encoding="utf-8")

    def assert_ok(self, r):
        self.assertEqual(r.returncode, 0, f"stderr: {r.stderr!r} stdout: {r.stdout!r}")

    def assert_graceful_failure(self, r):
        """Non-zero exit code, an error message, and no Python traceback."""
        self.assertNotEqual(r.returncode, 0)
        self.assertNotIn("Traceback", r.stderr, r.stderr)
        self.assertTrue((r.stdout + r.stderr).strip(), "expected an error message")


class AddTests(CliTestCase):
    def test_prints_spec_message(self):
        r = self.run_cli("add", "Buy groceries")
        self.assert_ok(r)
        self.assertIn("Task added successfully (ID: 1)", r.stdout)

    def test_creates_json_file_in_current_directory(self):
        self.assertFalse(self.file.exists())
        self.run_cli("add", "Buy groceries")
        self.assertTrue(self.file.exists())

    def test_stores_all_required_properties(self):
        self.run_cli("add", "Buy groceries")
        task = self.tasks()[0]
        self.assertEqual(set(task), REQUIRED_KEYS)
        self.assertEqual(task["id"], 1)
        self.assertEqual(task["description"], "Buy groceries")
        self.assertEqual(task["status"], "todo")

    def test_timestamps_are_valid_datetimes(self):
        self.run_cli("add", "Buy groceries")
        task = self.tasks()[0]
        created = datetime.fromisoformat(task["createdAt"])
        updated = datetime.fromisoformat(task["updatedAt"])
        self.assertLessEqual(created, updated)

    def test_ids_are_unique_and_tasks_persist_between_runs(self):
        for name in ("one", "two", "three"):
            self.assert_ok(self.run_cli("add", name))
        ids = [t["id"] for t in self.tasks()]
        self.assertEqual(len(set(ids)), 3)
        self.assertEqual([t["description"] for t in self.tasks()], ["one", "two", "three"])


class UpdateTests(CliTestCase):
    def test_changes_description_and_updated_at_only(self):
        self.seed(("Buy groceries", "todo"))
        self.assert_ok(self.run_cli("update", 1, "Buy groceries and cook dinner"))
        task = self.task_by_id(1)
        self.assertEqual(task["description"], "Buy groceries and cook dinner")
        self.assertNotEqual(task["updatedAt"], OLD_TIME)
        self.assertEqual(task["createdAt"], OLD_TIME)
        self.assertEqual(task["status"], "todo")

    def test_leaves_other_tasks_untouched(self):
        self.seed(("a", "todo"), ("b", "todo"))
        self.run_cli("update", 2, "b changed")
        self.assertEqual(self.task_by_id(1)["description"], "a")
        self.assertEqual(self.task_by_id(1)["updatedAt"], OLD_TIME)


class DeleteTests(CliTestCase):
    def test_removes_only_that_task(self):
        self.seed(("a", "todo"), ("b", "todo"), ("c", "todo"))
        self.assert_ok(self.run_cli("delete", 2))
        self.assertEqual([t["id"] for t in self.tasks()], [1, 3])

    def test_ids_stay_unique_after_deleting_a_middle_task(self):
        self.seed(("a", "todo"), ("b", "todo"), ("c", "todo"))
        self.run_cli("delete", 2)
        self.run_cli("add", "d")
        ids = [t["id"] for t in self.tasks()]
        self.assertEqual(len(ids), len(set(ids)))


class MarkTests(CliTestCase):
    def test_mark_in_progress(self):
        self.seed(("a", "todo"))
        self.assert_ok(self.run_cli("mark-in-progress", 1))
        task = self.task_by_id(1)
        self.assertEqual(task["status"], "in-progress")
        self.assertNotEqual(task["updatedAt"], OLD_TIME)
        self.assertEqual(task["createdAt"], OLD_TIME)

    def test_mark_done(self):
        self.seed(("a", "in-progress"))
        self.assert_ok(self.run_cli("mark-done", 1))
        task = self.task_by_id(1)
        self.assertEqual(task["status"], "done")
        self.assertNotEqual(task["updatedAt"], OLD_TIME)

    def test_marking_leaves_other_tasks_untouched(self):
        self.seed(("a", "todo"), ("b", "todo"))
        self.run_cli("mark-done", 2)
        self.assertEqual(self.task_by_id(1)["status"], "todo")


class ListTests(CliTestCase):
    def setUp(self):
        super().setUp()
        self.seed(("alpha-todo", "todo"), ("bravo-progress", "in-progress"), ("charlie-done", "done"))

    def check(self, args, shown, hidden):
        r = self.run_cli("list", *args)
        self.assert_ok(r)
        for d in shown:
            self.assertIn(d, r.stdout)
        for d in hidden:
            self.assertNotIn(d, r.stdout)

    def test_list_all(self):
        self.check([], ["alpha-todo", "bravo-progress", "charlie-done"], [])

    def test_list_done(self):
        self.check(["done"], ["charlie-done"], ["alpha-todo", "bravo-progress"])

    def test_list_todo(self):
        self.check(["todo"], ["alpha-todo"], ["bravo-progress", "charlie-done"])

    def test_list_in_progress(self):
        self.check(["in-progress"], ["bravo-progress"], ["alpha-todo", "charlie-done"])

    def test_list_with_no_matches_succeeds(self):
        self.seed(("a", "todo"))
        self.assert_ok(self.run_cli("list", "done"))


class ConstraintTests(CliTestCase):
    @unittest.skipUnless(hasattr(sys, "stdlib_module_names"), "needs Python 3.10+")
    def test_uses_only_standard_library(self):
        tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                imported.add(node.module.split(".")[0])
        self.assertEqual(imported - set(sys.stdlib_module_names), set())


class ErrorHandlingTests(CliTestCase):
    """The spec: 'handle errors and edge cases gracefully'."""

    def test_no_command(self):
        self.assert_graceful_failure(self.run_cli())

    def test_unknown_command(self):
        self.assert_graceful_failure(self.run_cli("explode"))

    def test_add_without_description(self):
        self.assert_graceful_failure(self.run_cli("add"))

    def test_add_empty_description(self):
        self.assert_graceful_failure(self.run_cli("add", ""))
        self.assertFalse(self.file.exists())

    def test_missing_arguments(self):
        self.seed(("a", "todo"))
        for cmd in (("update",), ("update", 1), ("delete",),
                    ("mark-done",), ("mark-in-progress",)):
            with self.subTest(cmd=cmd):
                self.assert_graceful_failure(self.run_cli(*cmd))

    def test_non_numeric_id(self):
        self.seed(("a", "todo"))
        for cmd in (("update", "abc", "x"), ("delete", "abc"),
                    ("mark-done", "abc"), ("mark-in-progress", "abc")):
            with self.subTest(cmd=cmd):
                self.assert_graceful_failure(self.run_cli(*cmd))

    def test_nonexistent_id(self):
        self.seed(("a", "todo"))
        for cmd in (("update", 99, "x"), ("delete", 99),
                    ("mark-done", 99), ("mark-in-progress", 99)):
            with self.subTest(cmd=cmd):
                self.assert_graceful_failure(self.run_cli(*cmd))

    def test_failed_commands_do_not_change_the_file(self):
        self.seed(("a", "todo"), ("b", "done"))
        before = self.file.read_text(encoding="utf-8")
        self.run_cli("update", 99, "x")
        self.run_cli("delete", "abc")
        self.run_cli("mark-done", 99)
        self.assertEqual(self.file.read_text(encoding="utf-8"), before)

    def test_list_invalid_status(self):
        self.seed(("a", "todo"))
        self.assert_graceful_failure(self.run_cli("list", "finished"))

    def test_list_when_file_missing(self):
        self.assert_ok(self.run_cli("list"))

    def test_empty_json_file_is_treated_as_no_tasks(self):
        self.file.write_text("", encoding="utf-8")
        self.assert_ok(self.run_cli("list"))
        self.assert_ok(self.run_cli("add", "after empty file"))
        self.assertEqual(len(self.tasks()), 1)

    def test_corrupt_json_fails_gracefully_and_is_not_overwritten(self):
        self.file.write_text("{not valid json", encoding="utf-8")
        for cmd in (("list",), ("add", "x"), ("delete", 1)):
            with self.subTest(cmd=cmd):
                self.assert_graceful_failure(self.run_cli(*cmd))
        self.assertEqual(self.file.read_text(encoding="utf-8"), "{not valid json")


if __name__ == "__main__":
    unittest.main(verbosity=2)