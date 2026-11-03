#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Exercise rejection cases in a disposable Git repository; uses no real secrets."""
import io
import json
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]
archive = subprocess.check_output(['git', 'archive', 'HEAD'], cwd=ROOT)
with tempfile.TemporaryDirectory(prefix='znm2-privacy-check-') as temporary:
    work = Path(temporary)
    with tarfile.open(fileobj=io.BytesIO(archive)) as source:
        for member in source.getmembers():
            rel = PurePosixPath(member.name)
            assert not rel.is_absolute() and '..' not in rel.parts
            if member.isdir():
                (work / member.name).mkdir(parents=True, exist_ok=True)
            else:
                assert member.isfile(), 'Unexpected non-file in project archive'
                path = work / member.name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(source.extractfile(member).read())
    def git(*args):
        subprocess.run(['git', *args], cwd=work, check=True, capture_output=True)
    def check():
        return subprocess.run([sys.executable, 'tests/check_repository.py'], cwd=work,
                              capture_output=True, text=True)
    git('init', '-q', '-b', 'codex/privacy-check')
    git('add', '.')
    assert check().returncode == 0, 'Clean source archive should pass'
    (work / 'private').mkdir()
    (work / 'private/probe.txt').write_text('harmless test fixture\n')
    git('add', '-f', 'private/probe.txt')
    result = check()
    assert result.returncode != 0 and 'Forbidden tracked artifact: private/probe.txt' in result.stderr
    git('rm', '--cached', '-f', 'private/probe.txt')
    (work / 'private/probe.txt').unlink()
    # Only a marker and deliberately invalid body, never a real key.
    (work / 'probe.txt').write_text('-----BEGIN ' + 'PRIVATE KEY-----\nINVALID TEST DATA\n')
    git('add', 'probe.txt')
    result = check()
    assert result.returncode != 0 and 'Potential private value: probe.txt' in result.stderr
print(json.dumps({'passed': True, 'clean_archive_accepted': True,
                  'forced_private_file_rejected': True, 'private_key_marker_rejected': True}, indent=2))
