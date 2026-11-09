#!/usr/bin/env python3
"""Build the owner-approved MIT-0 distribution for ClawHub, without editing source."""
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "skills/gde-benzin"
FILES = ("SKILL.md", "agents/openai.yaml", "references/api.md",
         "references/api-terms.md", "scripts/gde_benzin.py")
MIT0 = '''MIT No Attribution License

Copyright (c) 2026 Dmitry Tylnyi

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
'''


def build(output):
    output = Path(output).resolve()
    if output == ROOT or output in ROOT.parents or output.is_relative_to(SOURCE):
        raise ValueError("Output must not overwrite the repository or source skill")
    if output.exists():
        raise ValueError("Output directory already exists; choose a new path")
    files = {name: (SOURCE / name).read_text(encoding="utf-8") for name in FILES}
    if "license: MIT\n" not in files["SKILL.md"]:
        raise ValueError("Unexpected source license; review the distribution before building")
    files["SKILL.md"] = files["SKILL.md"].replace("license: MIT\n", "license: MIT-0\n", 1)
    old = "Код официального skill распространяется под MIT."
    if old not in files["references/api-terms.md"]:
        raise ValueError("API terms changed; review the license note before building")
    files["references/api-terms.md"] = files["references/api-terms.md"].replace(
        old, "Код этой сборки для ClawHub предоставляется под MIT-0. "
        "Код основной версии на GitHub распространяется под MIT.", 1)
    files["LICENSE"] = MIT0
    output.mkdir(parents=True)
    for name, value in files.items():
        path = output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value, encoding="utf-8")
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        print(build(args.output))
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
