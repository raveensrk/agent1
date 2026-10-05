#!/usr/bin/env python3
"""Offline checks for template validation, diagram IDs, and Firefox launch gating."""
import json
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET
from unittest.mock import patch

import build

SKILL = Path(__file__).resolve().parent.parent
TEMPLATE = SKILL / "template.html"
QA_TEMPLATE = SKILL / "template-qa.html"
MAPS = (
    (
        SKILL / "architecture.svg",
        (
            "template.html",
            "template-qa.html",
            "scripts/build.py",
            "mmdc",
            "Firefox",
            "~/tmp/fields.json",
            "outside skill directory",
        ),
    ),
    (
        SKILL / "workflow.svg",
        (
            "Explicit request",
            "Proactive offer",
            "template.html",
            "template-qa.html",
            "never overwrite",
            "Firefox",
        ),
    ),
)


class Builder(unittest.TestCase):
    def test_skill_maps(self):
        for path, terms in MAPS:
            root = ET.parse(path).getroot()
            self.assertEqual(root.tag, "{http://www.w3.org/2000/svg}svg")
            self.assertIsNotNone(root.find("{http://www.w3.org/2000/svg}title"))
            self.assertIsNotNone(root.find("{http://www.w3.org/2000/svg}desc"))
            ids = [node.get("id") for node in root.iter() if node.get("id")]
            self.assertEqual(len(ids), len(set(ids)), path)
            text = " ".join(root.itertext())
            for term in terms:
                self.assertIn(term, text, path)

    def test_build_and_failures(self):
        scratch = Path.home() / "tmp"
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as dir:
            dir = Path(dir)
            diagram = dir / "test.mmd"
            diagram.write_text('flowchart TD\nA{{TOKEN}} --> B["Done"]\n')
            fields = {name: "Example" for name in build.TOKEN.findall(TEMPLATE.read_text())}
            fields.pop("DIAGRAMS")
            fields["QA_ITEMS"] = (
                '<div class="qa-item"><h3>4.1 First?</h3><p>First answer.</p></div>'
                '<div class="qa-item"><h3>4.2 Second?</h3><p>Second answer.</p></div>'
            )
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
                with self.assertRaisesRegex(ValueError, "at least one --diagram"):
                    build.render(fields, [], TEMPLATE, dir / "no-diagram.html")
                self.assertFalse((dir / "no-diagram.html").exists())
                build.render(fields, [diagram, diagram], TEMPLATE, output)
                page = output.read_text()
                self.assertNotIn('id="feedback"', page)
                self.assertNotIn('<textarea', page)
                self.assertNotIn('navigator.clipboard', page)
                self.assertIn('id="diagram_1"', page)
                self.assertIn('id="diagram_2"', page)
                self.assertEqual(page.count('class="qa-item"'), 2)
                self.assertIn('4.2 Second?', page)
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

    def test_qa_template(self):
        scratch = Path.home() / "tmp"
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as dir:
            dir = Path(dir)
            fields = {name: "Example" for name in build.TOKEN.findall(QA_TEMPLATE.read_text())}
            fields["QUESTIONS"] = (
                '<fieldset class="question"><legend>1. Explain?</legend>'
                '<div class="answer-options"><label class="choice"><input type="radio" name="explain-mode" value="custom" data-text-mode checked> Write my answer</label>'
                '<textarea name="explain"></textarea></div>'
                '<div class="answer-alternatives"><p>Or choose one alternative:</p>'
                '<label class="choice"><input type="radio" name="explain-alternative" value="all-of-the-above"> All of the above</label>'
                '<label class="choice"><input type="radio" name="explain-alternative" value="none-of-the-above"> None of the above</label>'
                '<label class="choice"><input type="radio" name="explain-alternative" value="i-dont-know"> I don\'t know</label>'
                '<label class="choice"><input type="radio" name="explain-alternative" value="you-decide"> You decide</label></div></fieldset>'
                '<fieldset class="question"><legend>2. Choose?</legend><div class="answer-options">'
                '<label><input type="checkbox" name="choice" value="a"> A</label></div>'
                '<div class="answer-alternatives"><label class="choice"><input type="radio" name="choice-alternative" value="all-of-the-above"> All of the above</label>'
                '<label class="choice"><input type="radio" name="choice-alternative" value="none-of-the-above"> None of the above</label>'
                '<label class="choice"><input type="radio" name="choice-alternative" value="i-dont-know"> I don\'t know</label>'
                '<label class="choice"><input type="radio" name="choice-alternative" value="you-decide"> You decide</label></div></fieldset>'
                '<fieldset class="question"><legend>3. Ready?</legend><div class="answer-options">'
                '<label><input type="radio" name="ready" value="yes"> Yes</label>'
                '<label><input type="radio" name="ready" value="no"> No</label></div>'
                '<div class="answer-alternatives"><label class="choice"><input type="radio" name="ready-alternative" value="all-of-the-above"> All of the above</label>'
                '<label class="choice"><input type="radio" name="ready-alternative" value="none-of-the-above"> None of the above</label>'
                '<label class="choice"><input type="radio" name="ready-alternative" value="i-dont-know"> I don\'t know</label>'
                '<label class="choice"><input type="radio" name="ready-alternative" value="you-decide"> You decide</label></div></fieldset>'
            )
            output = dir / "qa.html"
            build.render(fields, [], QA_TEMPLATE, output, launch=False)
            page = output.read_text()
            self.assertIn('<textarea name="explain">', page)
            self.assertIn('name="choice" value="a"', page)
            self.assertIn('class="answer-alternatives"', page)
            self.assertIn('id="copy-answers"', page)
            self.assertIn("navigator.clipboard.writeText", page)
            self.assertIn('document.execCommand("copy")', page)
            self.assertNotIn('id="export-answers"', page)
            self.assertNotIn("application/json", page)
            for answer in ("All of the above", "None of the above", "I don't know", "You decide"):
                self.assertIn(answer, page)
            self.assertIn('name="ready" value="yes"', page)
            self.assertIn('name="ready" value="no"', page)
            self.assertNotIn("<svg", page)
            with self.assertRaisesRegex(ValueError, "does not accept diagrams"):
                build.render(fields, [Path("unused.svg")], QA_TEMPLATE, dir / "bad.html")

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
