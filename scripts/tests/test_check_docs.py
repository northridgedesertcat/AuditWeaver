import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
import subprocess

from scripts.check_docs import check_file, ignored_link_issues, markdown_destinations, target_issue


class DocumentationLinkTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / "docs" / "README.md"
        self.source.parent.mkdir()
        (self.root / "target.md").touch()

    def test_relative_files_and_fragments(self):
        self.assertIsNone(target_issue(self.source, "../target.md#heading", self.root))
        self.assertIsNone(target_issue(self.source, "#heading", self.root))

    def test_missing_destination(self):
        self.assertEqual(target_issue(self.source, "missing.md", self.root), "destination does not exist")

    def test_encoded_spaces(self):
        (self.root / "a file.md").touch()
        self.assertIsNone(target_issue(self.source, "../a%20file.md", self.root))

    def test_external_links_are_not_fetched(self):
        for target in ("https://example.invalid/a", "mailto:test@example.invalid", "//example.invalid/a"):
            self.assertIsNone(target_issue(self.source, target, self.root))

    def test_machine_paths_are_rejected(self):
        for target in ("file:///D:/private.md", "D:/private.md", r"D:\private.md", "/private.md", r"..\target.md"):
            self.assertIsNotNone(target_issue(self.source, target, self.root))

    def test_local_only_links_are_rejected_even_when_file_exists(self):
        for directory in ("document", "devtools"):
            (self.root / directory).mkdir()
            (self.root / directory / "private.md").touch()
            self.assertIn("local-only", target_issue(self.source, f"../{directory}/private.md", self.root))

    def test_links_must_stay_within_repository(self):
        self.assertIn("leaves", target_issue(self.source, "../../outside.md", self.root))

    def test_fences_and_inline_code_are_skipped(self):
        text = '```md\n[example](missing.md)\n```\n`[code](missing.md)`\n[real](../target.md)'
        self.assertEqual(list(markdown_destinations(text)), [(5, "../target.md")])

    def test_balanced_parentheses_angles_and_titles(self):
        text = '[one](a(b).md "title") ![two](<a file.png>) [three](c.md)'
        self.assertEqual([target for _, target in markdown_destinations(text)], ["a(b).md", "a file.png", "c.md"])

    def test_reference_definitions_and_undefined_references(self):
        text = '[source][ref]\n[ref]: ../target.md "title"\n[missing][unknown]'
        self.assertEqual(list(markdown_destinations(text)), [(2, "../target.md"), (3, "missing-reference:unknown")])

    def test_check_file_reports_source_line(self):
        self.source.write_text('# Example\n[missing](absent.md)\n', encoding="utf-8")
        issues = check_file(self.source, self.root)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].line, 2)

    def test_git_ignored_destination_is_reported(self):
        self.source.write_text('[local](../target.md)', encoding="utf-8")
        result = subprocess.CompletedProcess([], 0, stdout=b"target.md\0", stderr=b"")
        with patch("scripts.check_docs.subprocess.run", return_value=result) as run:
            issues = ignored_link_issues([self.source], self.root)
        self.assertEqual(len(issues), 1)
        self.assertIn("ignored by Git", issues[0].reason)
        self.assertEqual(run.call_args.kwargs["input"], b"target.md\0")

    def test_git_errors_are_not_silently_ignored(self):
        self.source.write_text('[local](../target.md)', encoding="utf-8")
        result = subprocess.CompletedProcess([], 128, stdout=b"", stderr=b"git failure")
        with patch("scripts.check_docs.subprocess.run", return_value=result):
            with self.assertRaisesRegex(RuntimeError, "git failure"):
                ignored_link_issues([self.source], self.root)


if __name__ == "__main__":
    unittest.main()
