#!/usr/bin/env python3
"""Remove this job's ephemeral signing keyring; never touch a user's keyring."""
import os
from pathlib import Path
import shutil
import subprocess

value = os.environ.get('GNUPGHOME')
if value:
    home = Path(value).resolve()
    parent = Path(os.environ['RUNNER_TEMP']).resolve()
    if home.parent != parent or not home.name.startswith('s9plus-gnupg-'):
        raise SystemExit('Refusing to remove an unexpected keyring path')
    subprocess.run(['gpgconf', '--kill', 'gpg-agent'], check=False)
    shutil.rmtree(home, ignore_errors=True)
