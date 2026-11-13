#!/usr/bin/env python3
"""GPG wrapper: passphrase via a private FD, preserving Git's stdin."""
import os
import re
import subprocess
import sys

fingerprint = os.environ['GPG_SIGNING_KEY_FINGERPRINT']
if not re.fullmatch(r'(?:[0-9A-F]{40}|[0-9A-F]{64})', fingerprint):
    raise SystemExit('Invalid GPG signing fingerprint')
passphrase = os.environ.get('GPG_PASSPHRASE', '')
if '\n' in passphrase or '\r' in passphrase or len(passphrase.encode()) > 4096:
    raise SystemExit('Unsupported passphrase encoding/length')
read_fd, write_fd = os.pipe()
try:
    os.write(write_fd, passphrase.encode() + b'\n')
    os.close(write_fd)
    command = ['gpg', '--batch', '--yes', '--pinentry-mode', 'loopback',
               '--passphrase-fd', str(read_fd), '--local-user', fingerprint + '!',
               *sys.argv[1:]]
    raise SystemExit(subprocess.run(command, pass_fds=(read_fd,)).returncode)
finally:
    os.close(read_fd)
