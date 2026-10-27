"""Pictures of the guide's Mermaid diagrams (the desktop app shows Mermaid as code)."""

from __future__ import annotations

import os
import stat
import unittest

from support import GuideTestCase

from own_guide import diagrams

FAKE_MMDC = """#!/usr/bin/env python3
import sys, pathlib
args = sys.argv[1:]
src, out = pathlib.Path(args[args.index("-i") + 1]), pathlib.Path(args[args.index("-o") + 1])
log = pathlib.Path(__file__).with_name("calls.log")
log.write_text(log.read_text() + "x" if log.exists() else "x")
if "BROKEN" in src.read_text():
    print("Parse error on line 2", file=sys.stderr)
    sys.exit(1)
out.write_bytes(b"\\x89PNG fake")
"""

PAGE = """# How shop runs

## The whole-project map

```mermaid
flowchart TD
  A[Web app] --> B[API]
```

## The flows
"""


class DiagramsTest(GuideTestCase):
    def setUp(self) -> None:
        super().setUp()
        tool = self.tmp / "bin" / "mmdc"
        tool.parent.mkdir()
        tool.write_text(FAKE_MMDC, encoding="utf-8")
        tool.chmod(tool.stat().st_mode | stat.S_IEXEC)
        os.environ["OWN_MMDC"] = str(tool)
        self.calls = tool.with_name("calls.log")
        self.guide = self.guides / "shop"
        (self.guide / "flows").mkdir(parents=True)
        (self.guide / "FLOW.md").write_text(PAGE, encoding="utf-8")

    def tearDown(self) -> None:
        os.environ.pop("OWN_MMDC", None)
        super().tearDown()

    def run_count(self) -> int:
        return len(self.calls.read_text()) if self.calls.exists() else 0

    def test_picture_goes_right_above_the_code(self) -> None:
        report = diagrams.render_guide(self.guide)
        text = (self.guide / "FLOW.md").read_text(encoding="utf-8")
        self.assertEqual(report["pages"][0]["drawn"], ["flow-1"])
        self.assertIn("![flow-1: picture of the diagram below](diagrams/flow-1.png)\n```mermaid", text)
        self.assertTrue((self.guide / "diagrams" / "flow-1.png").is_file())

    def test_unchanged_diagram_is_not_drawn_again_and_lines_never_pile_up(self) -> None:
        diagrams.render_guide(self.guide)
        diagrams.render_guide(self.guide)
        text = (self.guide / "FLOW.md").read_text(encoding="utf-8")
        self.assertEqual(self.run_count(), 1)
        self.assertEqual(text.count("own:diagram flow-1"), 1)

    def test_changed_diagram_is_redrawn(self) -> None:
        diagrams.render_guide(self.guide)
        page = self.guide / "FLOW.md"
        page.write_text(page.read_text(encoding="utf-8").replace("B[API]", "B[API] --> C[(DB)]"), encoding="utf-8")
        report = diagrams.render_guide(self.guide)
        self.assertEqual(report["pages"][0]["drawn"], ["flow-1"])
        self.assertEqual(self.run_count(), 2)
        self.assertEqual(page.read_text(encoding="utf-8").count("own:diagram flow-1"), 1)

    def test_flow_pages_link_up_to_the_shared_diagrams_folder(self) -> None:
        (self.guide / "flows" / "who-am-i.md").write_text(
            "# Who am I\n\n```mermaid\nsequenceDiagram\n  A->>B: hi\n```\n", encoding="utf-8")
        diagrams.render_guide(self.guide)
        text = (self.guide / "flows" / "who-am-i.md").read_text(encoding="utf-8")
        self.assertIn("](../diagrams/flows-who-am-i-1.png)", text)

    def test_a_flow_page_named_flow_never_overwrites_the_map_picture(self) -> None:
        (self.guide / "flows" / "flow.md").write_text(
            "# Flow\n\n```mermaid\nflowchart TD\n  X --> Y\n```\n", encoding="utf-8")
        diagrams.render_guide(self.guide)
        pictures = sorted(p.name for p in (self.guide / "diagrams").glob("*.png"))
        self.assertEqual(pictures, ["flow-1.png", "flows-flow-1.png"])
        self.assertEqual([p.name for p in (self.guide / "diagrams").iterdir() if p.name.startswith(".")], [])

    def test_a_broken_diagram_keeps_its_old_picture_and_is_retried(self) -> None:
        diagrams.render_guide(self.guide)
        page = self.guide / "FLOW.md"
        page.write_text(page.read_text(encoding="utf-8").replace("B[API]", "B[API] BROKEN"), encoding="utf-8")
        report = diagrams.render_guide(self.guide)
        self.assertEqual(report["pages"][0]["failed"][0]["error"], "Parse error on line 2")
        self.assertIn("diagrams/flow-1.png", page.read_text(encoding="utf-8"))
        diagrams.render_guide(self.guide)
        self.assertEqual(self.run_count(), 3)  # retried, because the fingerprint still differs

    def test_without_the_drawing_tool_nothing_changes(self) -> None:
        os.environ["OWN_MMDC"] = str(self.tmp / "nowhere" / "mmdc")
        before = (self.guide / "FLOW.md").read_text(encoding="utf-8")
        report = diagrams.render_guide(self.guide)
        self.assertIsNone(report["mmdc"])
        self.assertIn("npm install -g @mermaid-js/mermaid-cli", report["note"])
        self.assertEqual((self.guide / "FLOW.md").read_text(encoding="utf-8"), before)

    def test_a_drawing_tool_path_with_a_tilde_is_expanded(self) -> None:
        home = self.tmp / "home"
        tool = home / "bin" / "mmdc"
        tool.parent.mkdir(parents=True)
        tool.write_text("#!/bin/sh\n", encoding="utf-8")
        saved = {k: os.environ.get(k) for k in ("HOME", "OWN_MMDC")}
        try:
            os.environ.update(HOME=str(home), OWN_MMDC="~/bin/mmdc")
            self.assertEqual(diagrams.find_mmdc(), str(tool))
        finally:
            for key, value in saved.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


if __name__ == "__main__":
    unittest.main()
