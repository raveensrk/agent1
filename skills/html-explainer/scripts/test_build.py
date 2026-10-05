#!/usr/bin/env python3
"""Offline checks for template validation, diagram IDs, and Firefox launch gating."""
import json
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import build

TEMPLATE = Path(__file__).resolve().parent.parent / "template.html"


class Builder(unittest.TestCase):
    def test_build_and_failures(self):
        scratch = Path.home() / "tmp"
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as dir:
            dir = Path(dir)
            diagram = dir / "test.mmd"
            diagram.write_text('flowchart TD\nA{{TOKEN}} --> B["Done"]\n')
            fields = {name: "Example" for name in build.TOKEN.findall(TEMPLATE.read_text())}
            fields.pop("DIAGRAMS")
            output = dir / "page.html"

            def execute(command, **kwargs):
                if "--svgId" in command:
                    svg = Path(command[command.index("-o") + 1])
                    id = command[command.index("--svgId") + 1]
                    svg.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" id="{id}"></svg>')
                return subprocess.CompletedProcess(command, 0)

            with patch.object(build.shutil, "which", return_value="/opt/homebrew/bin/mmdc"), \
                 patch.object(build.subprocess, "check_output", return_value="/browser\n"), \
                 patch.object(build.os, "access", return_value=True), \
                 patch.object(build.subprocess, "run", side_effect=execute) as run:
                build.render(fields, [diagram, diagram], TEMPLATE, output)
                page = output.read_text()
                self.assertNotIn('id="feedback"', page)
                self.assertNotIn('<textarea', page)
                self.assertNotIn('navigator.clipboard', page)
                self.assertIn('id="diagram_1"', page)
                self.assertIn('id="diagram_2"', page)
                self.assertIn('A{{TOKEN}} --', page)  # Diagram syntax is not template syntax.
                self.assertEqual(run.call_args.args[0], ["open", "-a", "Firefox", str(output)])
                for source in re.findall(r'class="mermaid-source">(.*?)</script>', page):
                    self.assertEqual(json.loads(source), diagram.read_text())
                svg = dir / "direct.svg"
                svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" id="authored"></svg>')
                mixed = dir / "mixed.html"
                build.render(fields, [svg, diagram], TEMPLATE, mixed, launch=False)
                self.assertIn(svg.read_text(), mixed.read_text())
                self.assertIn('id="diagram_2"', mixed.read_text())
                run.reset_mock()
                with self.assertRaisesRegex(ValueError, "overwrite"):
                    build.render(fields, [diagram], TEMPLATE, output)
                self.assertFalse(run.called)
                fields["EXPLANATION"] = "{{MISSING}}"
                with self.assertRaisesRegex(ValueError, "unfilled"):
                    build.render(fields, [diagram], TEMPLATE, dir / "bad.html")
                self.assertFalse(run.called)
                self.assertFalse((dir / "bad.html").exists())
                fields["EXPLANATION"] = "Example"
                run.side_effect = subprocess.CalledProcessError(1, "mmdc")
                with self.assertRaises(subprocess.CalledProcessError):
                    build.render(fields, [diagram], TEMPLATE, dir / "failed.html")
                self.assertEqual(run.call_count, 1)
                self.assertFalse((dir / "failed.html").exists())

    def test_svg_inputs(self):
        scratch = Path.home() / "tmp"
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as dir:
            dir = Path(dir)
            fields = {name: "Example" for name in build.TOKEN.findall(TEMPLATE.read_text())}
            fields.pop("DIAGRAMS")
            svg = dir / "direct.svg"
            source = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><title id="direct_title">Direct</title></svg>'
            svg.write_text(source)
            output = dir / "direct.html"
            with patch.object(build.shutil, "which", side_effect=AssertionError("SVG needs no renderer")), \
                 patch.object(build.subprocess, "run") as run:
                build.render(fields, [svg], TEMPLATE, output, launch=False)
                self.assertIn(source, output.read_text())
                self.assertNotIn('class="mermaid-source"', output.read_text())
                for source in ("<svg>", "<div/>", '<svg><g id="same"/><g id="same"/></svg>'):
                    svg.write_text(source)
                    with self.assertRaisesRegex(ValueError, "SVG|duplicate"):
                        build.render(fields, [svg], TEMPLATE, dir / "bad.html")
                    self.assertFalse((dir / "bad.html").exists())
                svg.write_text('<svg id="same"/>')
                with self.assertRaisesRegex(ValueError, "duplicate"):
                    build.render(fields, [svg, svg], TEMPLATE, dir / "duplicate.html")
                self.assertFalse((dir / "duplicate.html").exists())
                run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
