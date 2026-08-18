from __future__ import annotations

import unittest

from tools.techlead_state.frontmatter import FrontMatterError, parse_document


class FrontMatterTests(unittest.TestCase):
    def test_protocol_yaml_subset(self) -> None:
        parsed = parse_document(
            """---
protocol_version: "1.0"
kind: example
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


if __name__ == "__main__":
    unittest.main()
