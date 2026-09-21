from __future__ import annotations

import unittest

from tools.techlead_state.frontmatter import FrontMatterError, dump_document, parse_document


class FrontMatterTests(unittest.TestCase):
    def test_protocol_yaml_subset(self) -> None:
        parsed = parse_document(
            """---
protocol_version: "2.0"
enabled: true
count: 2
refs:
  - WI-001
  - WI-002
criteria: [{"id":"CR-001","methods":["deterministic"]}]
optional: null
---
# Body
"""
        )
        self.assertEqual(parsed.metadata["refs"], ["WI-001", "WI-002"])
        self.assertEqual(parsed.metadata["criteria"][0]["id"], "CR-001")
        self.assertIsNone(parsed.metadata["optional"])
        self.assertEqual(parsed.body, "# Body\n")

    def test_rejects_nested_block_mapping(self) -> None:
        with self.assertRaisesRegex(FrontMatterError, "nested block mappings"):
            parse_document("---\nouter:\n  inner: value\n---\n")

    def test_rejects_duplicate_keys(self) -> None:
        with self.assertRaisesRegex(FrontMatterError, "duplicate key"):
            parse_document("---\nkind: first\nkind: second\n---\n")

    def test_dump_document_round_trips_protocol_values(self) -> None:
        metadata = {
            "id": "WI-001",
            "title": "Quoted: title",
            "active_revision": None,
            "review_required": False,
            "refs": ["WI-002", "WI-003"],
        }
        rendered = dump_document(metadata, "# Body\n")
        parsed = parse_document(rendered)
        self.assertEqual(parsed.metadata, metadata)
        self.assertEqual(parsed.body, "# Body\n")


if __name__ == "__main__":
    unittest.main()
