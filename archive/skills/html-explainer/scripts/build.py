#!/usr/bin/env python3
"""Fill HTML templates with local SVG, Mermaid, or Q&A form content."""
import argparse
import html
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET

TOKEN = re.compile(r"\{\{([A-Z_]+)\}\}")
SVG = ("svg", "{http://www.w3.org/2000/svg}svg")


def render(fields, diagrams, template, output, launch=True):
    """Fields and SVG are trusted local markup; title and page ID are escaped."""
    page = re.sub(r"<!--.*?-->", "", template.read_text(), flags=re.S)
    has_diagrams = "DIAGRAMS" in TOKEN.findall(page)
    required = set(TOKEN.findall(page)) - {"DIAGRAMS"}
    if not isinstance(fields, dict) or set(fields) != required:
        raise ValueError("fields must contain exactly: " + ", ".join(sorted(required)))
    if not all(isinstance(value, str) for value in fields.values()):
        raise ValueError("all field values must be strings")
    if any(TOKEN.search(value) for value in fields.values()):
        raise ValueError("unfilled template field; fill it before opening Firefox")
    scratch = Path.home() / "tmp"
    output_dir = output.parent.resolve()
    if not output.resolve().is_relative_to(scratch.resolve()) or output_dir == scratch.resolve():
        raise ValueError("output must be inside a per-invocation directory under ~/tmp")
    if not output_dir.is_dir():
        raise ValueError("create the per-invocation output directory before building")
    if has_diagrams and not diagrams:
        raise ValueError("provide at least one --diagram FILE.svg or FILE.mmd")
    if diagrams and not has_diagrams:
        raise ValueError("selected template does not accept diagrams")
    if any(not path.resolve().is_relative_to(output_dir) for path in diagrams):
        raise ValueError("diagram sources must be inside the output invocation directory")
    if output.exists():
        raise ValueError(f"refusing to overwrite {output}; choose the next NN")
    if any(path.suffix.lower() not in (".svg", ".mmd") for path in diagrams):
        raise ValueError("diagrams must be authored .svg or Mermaid .mmd files")
    sources = [path.read_text() for path in diagrams]
    if any(path.suffix.lower() == ".mmd" for path in diagrams):
        cli = shutil.which("mmdc")
        node = shutil.which("node")
        if not cli or not node:
            raise ValueError("renderer missing; approve installation, then run npm install -g @mermaid-js/mermaid-cli@12.0.0")
        # SVG-only builds need no renderer; resolve it only for Mermaid input.
        probe = """import {createRequire} from 'node:module';
const require = createRequire(process.argv[1]);
const {default: puppeteer} = await import(require.resolve('puppeteer'));
console.log(process.env.PUPPETEER_EXECUTABLE_PATH || await puppeteer.executablePath({headless: 'shell'}));"""
        browser = subprocess.check_output(
            [node, "--input-type=module", "-e", probe, str(Path(cli).resolve())],
            text=True, timeout=15,
        ).strip()
        if not os.access(browser, os.X_OK):
            raise ValueError("browser missing; approve download, then run npx puppeteer browsers install chrome-headless-shell")
        env = dict(os.environ, PUPPETEER_EXECUTABLE_PATH=browser)
    blocks = []
    ids = set()
    with tempfile.TemporaryDirectory(prefix="explain_", dir=output_dir) as dir:
        for index, (path, source) in enumerate(zip(diagrams, sources), 1):
            if path.suffix.lower() == ".svg":
                try:
                    root = ET.fromstring(source)
                except ET.ParseError as err:
                    raise ValueError(f"invalid SVG in {path}: {err}") from err
                if root.tag not in SVG:
                    raise ValueError(f"expected an SVG root in {path}")
                for node in root.iter():
                    id = node.get("id")
                    if id is not None:
                        if id in ids:
                            raise ValueError(f"duplicate SVG id {id!r}; prefix IDs per diagram")
                        ids.add(id)
                blocks.append(f'<div class="flow">{source}</div>')
                continue
            svg = Path(dir) / f"diagram_{index}.svg"
            subprocess.run(
                [cli, "-i", str(path), "-o", str(svg), "-t", "dark", "-b", "transparent", "--svgId", f"diagram_{index}"],
                env=env, check=True, timeout=45,
            )
            image = svg.read_text()
            if "<svg" not in image:
                raise ValueError(f"renderer did not produce SVG for {path}")
            # JSON preserves arrows containing '-->' without ending an HTML comment.
            saved = json.dumps(source).replace("<", "\\u003c")
            blocks.append(f'<script type="application/json" class="mermaid-source">{saved}</script>\n<div class="flow">{image}</div>')
    values = dict(fields, DIAGRAMS="\n".join(blocks))
    for key in ("TITLE", "PAGE_ID"):
        values[key] = html.escape(values[key], quote=True)
    page = TOKEN.sub(lambda match: values[match[1]], page)
    if has_diagrams and "<svg" not in page:
        raise ValueError("page has no rendered diagram")
    with output.open("x") as file:
        file.write(page)
    if launch:
        subprocess.run(["open", "-a", "Firefox", str(output.resolve())], check=True, timeout=15)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fields", type=Path, help="JSON mapping of template fields to trusted HTML strings")
    parser.add_argument("-d", "--diagram", type=Path, action="append", help="authored SVG or Mermaid file; repeat for multiple diagrams")
    parser.add_argument("--template", type=Path, default=Path(__file__).resolve().parent.parent / "template.html", help="HTML template to fill")
    parser.add_argument("-o", "--output", type=Path, required=True, help="new HTML path inside per-invocation directory under ~/tmp")
    parser.add_argument("--no-open", action="store_true", help="build without launching Firefox")
    args = parser.parse_args()
    try:
        if not args.fields.resolve().is_relative_to(args.output.parent.resolve()):
            raise ValueError("fields JSON must be inside the output invocation directory")
        render(json.loads(args.fields.read_text()), args.diagram or [],
               args.template, args.output, launch=not args.no_open)
    except (OSError, ValueError, subprocess.SubprocessError) as err:
        parser.exit(1, f"{err}\n")
    print(args.output.resolve())


if __name__ == "__main__":
    main()
