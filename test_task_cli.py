"""Tests for the Task Tracker CLI, written against the project spec.

Run from the folder containing task_cli.py and this file:
    python -m unittest -v test_task_cli.py

Every test runs the real CLI in a fresh temporary directory (as a subprocess),
so it checks what a user would actually experience: positional arguments,
a JSON file in the *current* directory, and exit codes. Standard library only.

Two groups:
  SpecTests        - behavior the project spec explicitly requires.
  RobustnessTests  - "handle errors and edge cases gracefully".
Nothing here depends on your exact wording of messages or list formatting,
except the one output line the spec shows: "Task added successfully (ID: 1)".
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
VALID_STATUSES = {"todo", "in-progress", "done"}
OLD_TIME = "2020-01-01T00:00:00"   # used for seeded tasks so changes are detectable


class CliTestCase(unittest.TestCase):
    """Shared helpers: fresh temp directory per test, run the CLI, read/seed JSON."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.cwd = Path(self._tmp.name)
        self.file = self.cwd / TASKS_FILE

    # --- helpers ---
    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *map(str, args)],
            cwd=self.cwd, capture_output=True, text=True, timeout=10,
        )

    def tasks(self):
        """Read the JSON file the CLI wrote."""
        return json.loads(self.file.read_text(encoding="utf-8"))

    def seed(self, *descriptions_and_status):
        """Write a tasks file directly. Each item: (description, status)."""
        data = []
        for i, (desc, status) in enumerate(descriptions_and_status, start=1):
            data.append({"id": i, "description": desc, "status": status,
                         "createdAt": OLD_TIME, "updatedAt": OLD_TIME})
        self.file.write_text(json.dumps(data), encoding="utf-8")
        return data

    def task_by_id(self, task_id):
        return next(t for t in self.tasks() if t["id"] == task_id)

    def assert_ok(self, result):
        self.assertEqual(result.returncode, 0,
                         f"expected success, got stderr: {result.stderr!r} stdout: {result.stdout!r}")

    def assert_graceful_failure(self, result):
        """Fails with a non-zero exit code, a message, and NO Python traceback."""
        self.assertNotEqual(result.returncode, 0, "expected a non-zero exit code")
        self.assertNotIn("Traceback", result.stderr, f"crashed with a traceback:\n{result.stderr}")
        self.assertTrue((result.stdout + result.stderr).strip(), "expected an error message")


# =====================================================================
# Behavior the spec explicitly requires
# =====================================================================
class SpecTests(CliTestCase):

    # ---------- add ----------
    def test_add_prints_spec_message(self):
        r = self.run_cli("add", "Buy groceries")
        self.assert_ok(r)
        self.assertIn("Task added successfully (ID: 1)", r.stdout)

    def test_add_creates_json_file_in_current_directory(self):
        self.assertFalse(self.file.exists())
        self.assert_ok(self.run_cli("add", "Buy groceries"))
        self.assertTrue(self.file.exists())

    def test_add_stores_all_required_properties(self):
        self.run_cli("add", "Buy groceries")
        task = self.tasks()[0]
        self.assertEqual(set(task), REQUIRED_KEYS)
        self.assertEqual(task["id"], 1)
        self.assertEqual(task["description"], "Buy groceries")
        self.assertEqual(task["status"], "todo")

    def test_add_timestamps_are_valid_datetimes(self):
        self.run_cli("add", "Buy groceries")
        task = self.tasks()[0]
        created = datetime.fromisoformat(task["createdAt"])
        updated = datetime.fromisoformat(task["updatedAt"])
        self.assertLessEqual(created, updated)

    def test_add_gives_each_task_a_unique_id(self):
        for name in ("one", "two", "three"):
            self.assert_ok(self.run_cli("add", name))
        ids = [t["id"] for t in self.tasks()]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(ids), 3)

    def test_add_persists_across_separate_runs(self):
        self.run_cli("add", "first")
        self.run_cli("add", "second")
        self.assertEqual([t["description"] for t in self.tasks()], ["first", "second"])

    # ---------- update ----------
    def test_update_changes_description_and_updated_at_only(self):
        self.seed(("Buy groceries", "todo"))
        self.assert_ok(self.run_cli("update", 1, "Buy groceries and cook dinner"))
        task = self.task_by_id(1)
        self.assertEqual(task["description"], "Buy groceries and cook dinner")
        self.assertNotEqual(task["updatedAt"], OLD_TIME)
        self.assertEqual(task["createdAt"], OLD_TIME)
        self.assertEqual(task["status"], "todo")

    def test_update_only_touches_the_target_task(self):
        self.seed(("a", "todo"), ("b", "todo"))
        self.run_cli("update", 2, "b changed")
        self.assertEqual(self.task_by_id(1)["description"], "a")
        self.assertEqual(self.task_by_id(1)["updatedAt"], OLD_TIME)

    # ---------- delete ----------
    def test_delete_removes_only_that_task(self):
        self.seed(("a", "todo"), ("b", "todo"), ("c", "todo"))
        self.assert_ok(self.run_cli("delete", 2))
        self.assertEqual([t["id"] for t in self.tasks()], [1, 3])

    def test_ids_stay_unique_after_deleting_a_middle_task(self):
        self.seed(("a", "todo"), ("b", "todo"), ("c", "todo"))
        self.run_cli("delete", 2)
        self.run_cli("add", "d")
        ids = [t["id"] for t in self.tasks()]
        self.assertEqual(len(ids), len(set(ids)))

    # ---------- mark ----------
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

    def test_mark_only_touches_the_target_task(self):
        self.seed(("a", "todo"), ("b", "todo"))
        self.run_cli("mark-done", 2)
        self.assertEqual(self.task_by_id(1)["status"], "todo")

    def test_status_values_are_always_valid(self):
        self.run_cli("add", "a")
        self.run_cli("mark-in-progress", 1)
        self.run_cli("mark-done", 1)
        for t in self.tasks():
            self.assertIn(t["status"], VALID_STATUSES)

    # ---------- list ----------
    def _seed_mixed(self):
        self.seed(("alpha-todo", "todo"), ("bravo-progress", "in-progress"), ("charlie-done", "done"))

    def test_list_shows_all_tasks(self):
        self._seed_mixed()
        r = self.run_cli("list")
        self.assert_ok(r)
        for desc in ("alpha-todo", "bravo-progress", "charlie-done"):
            self.assertIn(desc, r.stdout)

    def test_list_done_shows_only_done(self):
        self._seed_mixed()
        r = self.run_cli("list", "done")
        self.assert_ok(r)
        self.assertIn("charlie-done", r.stdout)
        self.assertNotIn("alpha-todo", r.stdout)
        self.assertNotIn("bravo-progress", r.stdout)

    def test_list_todo_shows_only_todo(self):
        self._seed_mixed()
        r = self.run_cli("list", "todo")
        self.assert_ok(r)
        self.assertIn("alpha-todo", r.stdout)
        self.assertNotIn("bravo-progress", r.stdout)
        self.assertNotIn("charlie-done", r.stdout)

    def test_list_in_progress_shows_only_in_progress(self):
        self._seed_mixed()
        r = self.run_cli("list", "in-progress")
        self.assert_ok(r)
        self.assertIn("bravo-progress", r.stdout)
        self.assertNotIn("alpha-todo", r.stdout)
        self.assertNotIn("charlie-done", r.stdout)

    def test_list_with_no_matches_succeeds(self):
        self.seed(("a", "todo"))
        r = self.run_cli("list", "done")
        self.assert_ok(r)
        self.assertNotIn("Traceback", r.stderr)

    # ---------- constraints ----------
    @unittest.skipUnless(hasattr(sys, "stdlib_module_names"), "needs Python 3.10+")
    def test_uses_only_standard_library(self):
        tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                imported.add(node.module.split(".")[0])
        external = imported - set(sys.stdlib_module_names)
        self.assertEqual(external, set(), f"external imports found: {external}")

    # The spec says the JSON file "should be created if it does not exist".
    # Most implementations only create it on the first write. If you want the
    # strict reading (file exists after ANY command), make `list` create it,
    # then delete the decorator below. Python will tell you when it passes.
    @unittest.expectedFailure
    def test_list_creates_json_file_if_missing(self):
        self.run_cli("list")
        self.assertTrue(self.file.exists())


# =====================================================================
# Error handling and edge cases
# =====================================================================
class RobustnessTests(CliTestCase):

    # ---------- bad invocation ----------
    def test_no_arguments(self):
        self.assert_graceful_failure(self.run_cli())

    def test_unknown_command(self):
        self.assert_graceful_failure(self.run_cli("explode"))

    def test_commands_are_not_run_on_unknown_input(self):
        self.run_cli("explode")
        self.assertFalse(self.file.exists())

    # ---------- add ----------
    def test_add_without_description(self):
        self.assert_graceful_failure(self.run_cli("add"))

    def test_add_empty_description(self):
        self.assert_graceful_failure(self.run_cli("add", ""))
        self.assertFalse(self.file.exists())

    def test_add_whitespace_only_description(self):
        self.assert_graceful_failure(self.run_cli("add", "   "))

    def test_add_description_with_quotes_unicode_and_symbols(self):
        text = 'Buy "milk" & café ☕ — 50% off, it\'s <great>'
        self.assert_ok(self.run_cli("add", text))
        self.assertEqual(self.tasks()[0]["description"], text)

    def test_add_very_long_description(self):
        text = "x" * 5000
        self.assert_ok(self.run_cli("add", text))
        self.assertEqual(self.tasks()[0]["description"], text)

    # ---------- bad IDs ----------
    def test_non_numeric_id_for_every_id_command(self):
        self.seed(("a", "todo"))
        for cmd in (("update", "abc", "x"), ("delete", "abc"),
                    ("mark-done", "abc"), ("mark-in-progress", "abc")):
            with self.subTest(cmd=cmd):
                self.assert_graceful_failure(self.run_cli(*cmd))

    def test_nonexistent_id_for_every_id_command(self):
        self.seed(("a", "todo"))
        for cmd in (("update", 99, "x"), ("delete", 99),
                    ("mark-done", 99), ("mark-in-progress", 99)):
            with self.subTest(cmd=cmd):
                self.assert_graceful_failure(self.run_cli(*cmd))

    def test_negative_zero_and_decimal_ids(self):
        self.seed(("a", "todo"))
        for bad in ("-1", "0", "1.5"):
            with self.subTest(id=bad):
                self.assert_graceful_failure(self.run_cli("delete", bad))
        self.assertEqual(len(self.tasks()), 1)  # nothing was deleted

    def test_missing_arguments(self):
        self.seed(("a", "todo"))
        for cmd in (("update",), ("update", 1), ("delete",),
                    ("mark-done",), ("mark-in-progress",)):
            with self.subTest(cmd=cmd):
                self.assert_graceful_failure(self.run_cli(*cmd))

    def test_failed_commands_do_not_modify_the_file(self):
        original = self.seed(("a", "todo"), ("b", "done"))
        self.run_cli("update", 99, "x")
        self.run_cli("delete", 99)
        self.run_cli("mark-done", "abc")
        self.assertEqual(self.tasks(), original)

    def test_update_with_empty_description(self):
        self.seed(("a", "todo"))
        self.assert_graceful_failure(self.run_cli("update", 1, ""))
        self.assertEqual(self.task_by_id(1)["description"], "a")

    def test_delete_same_task_twice(self):
        self.seed(("a", "todo"))
        self.assert_ok(self.run_cli("delete", 1))
        self.assert_graceful_failure(self.run_cli("delete", 1))

    # ---------- list ----------
    def test_list_invalid_status(self):
        self.seed(("a", "todo"))
        self.assert_graceful_failure(self.run_cli("list", "finished"))

    def test_list_when_file_missing(self):
        r = self.run_cli("list")
        self.assert_ok(r)
        self.assertNotIn("Traceback", r.stderr)

    def test_list_when_no_tasks(self):
        self.file.write_text("[]", encoding="utf-8")
        r = self.run_cli("list")
        self.assert_ok(r)
        self.assertNotIn("Traceback", r.stderr)

    # ---------- damaged storage ----------
    def test_empty_json_file_is_treated_as_no_tasks(self):
        self.file.write_text("", encoding="utf-8")
        self.assert_ok(self.run_cli("list"))
        self.assert_ok(self.run_cli("add", "after empty file"))
        self.assertEqual(len(self.tasks()), 1)

    def test_corrupt_json_fails_gracefully_and_is_not_destroyed(self):
        self.file.write_text("{not valid json", encoding="utf-8")
        for cmd in (("list",), ("add", "x"), ("delete", 1), ("mark-done", 1)):
            with self.subTest(cmd=cmd):
                self.assert_graceful_failure(self.run_cli(*cmd))
        self.assertEqual(self.file.read_text(encoding="utf-8"), "{not valid json")

    def test_json_with_wrong_shape_fails_gracefully(self):
        self.file.write_text('{"id": 1}', encoding="utf-8")   # an object, not a list
        self.assert_graceful_failure(self.run_cli("list"))

    # ---------- scale ----------
    def test_many_tasks(self):
        self.seed(*[(f"task {i}", "todo") for i in range(200)])
        self.assert_ok(self.run_cli("add", "one more"))
        ids = [t["id"] for t in self.tasks()]
        self.assertEqual(len(ids), 201)
        self.assertEqual(len(set(ids)), 201)


if __name__ == "__main__":
    unittest.main(verbosity=2)