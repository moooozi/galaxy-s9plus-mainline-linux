#!/usr/bin/env python3
"""Integration test using an ephemeral encrypted key with a signing subkey."""
import base64
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ACTION = Path(__file__).resolve().parent
PASSPHRASE = 'ephemeral fixture with spaces $ and quotes "'


def run(args, *, env, cwd, data=None):
    result = subprocess.run(args, env=env, cwd=cwd, input=data, capture_output=True)
    if result.returncode:
        # No private-key inputs are command arguments or included in output.
        raise RuntimeError('Signing check failed: ' + ' '.join(map(str, args)) + '\n' + result.stderr.decode())
    return result.stdout


with tempfile.TemporaryDirectory(prefix='s9plus-signing-check-') as directory:
    root = Path(directory)
    seed = root / 'seed'
    seed.mkdir(mode=0o700)
    fixture = root / 'checkout'
    fixture.mkdir()
    runner = root / 'runner'
    runner.mkdir()
    environment = dict(os.environ, GNUPGHOME=str(seed), GIT_CONFIG_GLOBAL='/dev/null')
    gpg = ['gpg','--batch','--pinentry-mode','loopback','--passphrase-fd','0']
    run([*gpg,'--quick-gen-key','Ephemeral CI check <ci@example.invalid>','ed25519','cert','1d'],
        env=environment,cwd=root,data=(PASSPHRASE+'\n').encode())
    listing = run(['gpg','--batch','--with-colons','--fingerprint','--list-secret-keys'],env=environment,cwd=root).decode()
    primary = next(line.split(':')[9] for line in listing.splitlines() if line.startswith('fpr:'))
    run([*gpg,'--quick-add-key',primary,'ed25519','sign','1d'],env=environment,cwd=root,data=(PASSPHRASE+'\n').encode())
    listing = run(['gpg','--batch','--with-colons','--with-subkey-fingerprint','--list-secret-keys'],env=environment,cwd=root).decode()
    signer = [line.split(':')[9] for line in listing.splitlines() if line.startswith('fpr:')][-1]
    secret = run([*gpg,'--armor','--export-secret-keys',primary],env=environment,cwd=root,data=(PASSPHRASE+'\n').encode())
    public = run(['gpg','--batch','--armor','--export',primary],env=environment,cwd=root)
    (fixture / 'keys').mkdir()
    (fixture / 'keys/archive.asc').write_bytes(public)
    run(['git','init','-b','main'],env=environment,cwd=fixture)
    ci = dict(environment, GPG_PRIVATE_KEY=base64.b64encode(secret).decode(), GPG_PASSPHRASE=PASSPHRASE,
              GPG_SIGNING_KEY_FINGERPRINT=signer, RUNNER_TEMP=str(runner), GITHUB_ENV=str(root/'github-env'))
    run([sys.executable,str(ACTION/'import-key.py')],env=ci,cwd=fixture)
    for line in (root / 'github-env').read_text().splitlines():
        key,value = line.split('=',1)
        ci[key] = value
    run(['git','-c','user.name=CI check','-c','user.email=ci@example.invalid','commit','--allow-empty','-m','Signing proof'],env=ci,cwd=fixture)
    run(['git','verify-commit','HEAD'],env=ci,cwd=fixture)
    run([sys.executable,str(ACTION/'cleanup.py')],env=ci,cwd=fixture)
    if Path(ci['GNUPGHOME']).exists():
        raise RuntimeError('CI keyring cleanup failed')
    run(['gpgconf','--kill','gpg-agent'],env=environment,cwd=root)
print('Encrypted signing subkey, base64 import, passphrase FD, signed Git commit and cleanup passed')
