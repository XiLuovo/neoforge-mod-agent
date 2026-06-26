from __future__ import annotations

import unittest
import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

REMOVED_DOC_NAMES = {
    "project-learning-plan-cn.md",
    "learning-roadmap-cn.md",
    "learning-docs-index-cn.md",
}


class DocumentationLinkTests(unittest.TestCase):
    def test_docs_do_not_reference_removed_learning_docs(self) -> None:
        markdown_files = [
            PROJECT_ROOT / "README.md",
            *[
                path
                for path in sorted((PROJECT_ROOT / "docs").rglob("*.md"))
                if "本地材料" not in path.relative_to(PROJECT_ROOT).parts
            ],
        ]
        stale_references: list[str] = []

        for markdown_file in markdown_files:
            text = markdown_file.read_text(encoding="utf-8")
            for line_number, line in enumerate(text.splitlines(), start=1):
                for doc_name in REMOVED_DOC_NAMES:
                    pattern = rf"(?<![A-Za-z0-9_-]){re.escape(doc_name)}(?![A-Za-z0-9_-])"
                    if re.search(pattern, line):
                        relative_file = markdown_file.relative_to(PROJECT_ROOT).as_posix()
                        stale_references.append(f"{relative_file}:{line_number} -> {doc_name}")

        self.assertEqual([], stale_references)


if __name__ == "__main__":
    unittest.main()
