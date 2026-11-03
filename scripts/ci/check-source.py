#!/usr/bin/env python3
"""Fast checks that do not build an image or touch attached phones."""
import ast
import json
from pathlib import Path
import subprocess

REPO = Path(__file__).resolve().parents[2]
for directory in ('scripts', 'image', 'experiments'):
    for path in (REPO / directory).rglob('*'):
        if not path.is_file():
            continue
        if path.suffix == '.py' or path.name in ('s9plus-bluetooth', 's9plus-boot-errors'):
            ast.parse(path.read_text(), filename=str(path))
        elif path.suffix == '.sh' or path.name in ('s9plus-audio', 's9plus-plasma-display'):
            subprocess.run(['bash', '-n', str(path)], check=True)
        elif path.suffix == '.json':
            json.loads(path.read_text())
for directory in ('scripts/ci/tests', 'scripts/flash/tests'):
    subprocess.run(['python3', '-m', 'unittest', 'discover', '-s', directory, '-v'], cwd=REPO, check=True)
print('Source syntax and regression checks passed')
