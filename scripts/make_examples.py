#!/usr/bin/env python3
"""Regenerate output_examples/ by running run.py on every file in input_examples/.

Outputs are produced by the agent, never written by hand.
"""
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
(root / "output_examples").mkdir(exist_ok=True)
for inp in sorted((root / "input_examples").glob("*.json")):
    res = subprocess.run([sys.executable, "run.py", "--input", str(inp.relative_to(root))],
                         cwd=root, capture_output=True, text=True, check=True)
    (root / "output_examples" / f"{inp.stem}.md").write_text(res.stdout)
    print("wrote", f"output_examples/{inp.stem}.md")
