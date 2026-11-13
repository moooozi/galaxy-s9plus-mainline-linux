#!/usr/bin/env python3
"""Import an owner-provided CI key without logging/exporting private material."""
import base64
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

fingerprint = re.sub(r'\s+', '', os.environ.get('GPG_SIGNING_KEY_FINGERPRINT', '')).upper()
if not re.fullmatch(r'(?:[0-9A-F]{40}|[0-9A-F]{64})', fingerprint):
    raise SystemExit('Set GPG_SIGNING_KEY_FINGERPRINT to a complete signing fingerprint')
key = os.environ.get('GPG_PRIVATE_KEY', '').encode()
if not key:
    raise SystemExit('GPG_PRIVATE_KEY is missing from this repository')
if b'-----BEGIN PGP PRIVATE KEY BLOCK-----' not in key:
    try:
        key = base64.b64decode(key, validate=True)
    except ValueError:
        raise SystemExit('GPG_PRIVATE_KEY must be armored or base64 encoded') from None
home = Path(tempfile.mkdtemp(prefix='s9plus-gnupg-', dir=os.environ['RUNNER_TEMP']))
home.chmod(0o700)
os.environ['GNUPGHOME'] = str(home)
os.environ['GPG_SIGNING_KEY_FINGERPRINT'] = fingerprint
# Record only non-secret paths/identity. Cleanup can also run after a failure.
with open(os.environ['GITHUB_ENV'], 'a') as stream:
    stream.write(f'GNUPGHOME={home}\nGPG_SIGNING_KEY_FINGERPRINT={fingerprint}\n')
result = subprocess.run(['gpg', '--batch', '--import'], input=key, capture_output=True)
if result.returncode:
    raise SystemExit('GPG private-key import failed')
listing = subprocess.check_output(['gpg', '--batch', '--with-colons', '--with-subkey-fingerprint',
                                  '--list-secret-keys', fingerprint], text=True, stderr=subprocess.DEVNULL)
if fingerprint not in {line.split(':')[9] for line in listing.splitlines() if line.startswith('fpr:')}:
    raise SystemExit('Imported secret key does not contain the configured fingerprint')
# Require the checked-in public trust anchor to contain the selected signer.
public = Path('keys/archive.asc')
if not public.exists():
    public = Path('image/releases/keys/archive.asc')
shown = subprocess.check_output(['gpg', '--batch', '--with-colons', '--with-subkey-fingerprint',
                                '--show-keys', str(public)], text=True, stderr=subprocess.DEVNULL)
if fingerprint not in {line.split(':')[9] for line in shown.splitlines() if line.startswith('fpr:')}:
    raise SystemExit('Public repository key does not match GPG_SIGNING_KEY_FINGERPRINT')
wrapper = home / 'gpg-wrapper'
shutil.copyfile(Path(__file__).with_name('gpg-wrapper.py'), wrapper)
wrapper.chmod(0o700)
proof = home / 'signing-check.txt'
proof.write_text('Galaxy S9+ CI signing-key verification\n')
subprocess.run([str(wrapper), '--armor', '--detach-sign', str(proof)], check=True)
verification = subprocess.check_output(['gpg', '--batch', '--status-fd', '1', '--verify',
                                       str(proof) + '.asc', str(proof)], text=True, stderr=subprocess.DEVNULL)
if not any(line.startswith('[GNUPG:] VALIDSIG ' + fingerprint + ' ') for line in verification.splitlines()):
    raise SystemExit('Signature did not use the exact configured fingerprint')
public_output = home / 'archive.asc'
public_output.write_bytes(subprocess.check_output(['gpg', '--batch', '--armor', '--export', fingerprint]))
subprocess.run(['git', 'config', 'gpg.program', str(wrapper)], check=True)
subprocess.run(['git', 'config', 'user.signingkey', fingerprint + '!'], check=True)
subprocess.run(['git', 'config', 'commit.gpgsign', 'true'], check=True)
subprocess.run(['git', 'config', 'tag.gpgsign', 'true'], check=True)
with open(os.environ['GITHUB_ENV'], 'a') as stream:
    stream.write(f'GPG_SIGNING_WRAPPER={wrapper}\nGPG_PUBLIC_KEY_FILE={public_output}\n')
print('Verified signing key and passphrase for fingerprint ' + fingerprint)
