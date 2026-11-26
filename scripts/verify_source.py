"""Narrow tracked-tree hygiene checks; not a complete security scanner."""
import ast
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_IMPORTS = {
    'dataclasses', 'contextlib', 'functools', 'hashlib', 'hmac',
    'secrets', 'json', 'sqlite3', 'uuid', 'datetime', 'tempfile', 'pathlib',
}
FORBIDDEN_CALLS = {'eval', 'exec', 'compile', '__import__'}
FORBIDDEN_NAMES = {'.env', '.netrc', 'id_rsa', 'id_ed25519', 'credentials.json'}
FORBIDDEN_SUFFIXES = {'.pem', '.key', '.pfx', '.p12', '.db', '.sqlite', '.sqlite3', '.pyc'}
PATTERNS = (
    re.compile(r'-----BEGIN ' + r'(?:RSA |EC |OPENSSH |DSA |ENCRYPTED )?PRIVATE KEY-----'),
    re.compile(r'\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})\b'),
    re.compile(r'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b'),
    re.compile(r'(?i)\b(?:api[_-]?key|client[_-]?secret|password|accountkey)\s*[:=]\s*["\x27]?[A-Za-z0-9+/=_-]{24,}'),
)


def tracked_files(root):
    raw = subprocess.check_output(['git', 'ls-files', '-z'], cwd=root)
    return [Path(name.decode('utf-8')) for name in raw.split(b'\0') if name]


def inspect_python(source, runtime=False):
    """Return reason labels only; never echo source or credential values."""
    errors = []
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return ['invalid Python syntax']
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = ([n.name.split('.')[0] for n in node.names]
                     if isinstance(node, ast.Import) else
                     [(node.module or '').split('.')[0]])
            if runtime and (getattr(node, 'level', 0) or any(n not in RUNTIME_IMPORTS for n in names)):
                errors.append('runtime import outside allowlist')
        if isinstance(node, ast.Call):
            name = (node.func.id if isinstance(node.func, ast.Name) else
                    node.func.attr if isinstance(node.func, ast.Attribute) else None)
            if name in FORBIDDEN_CALLS:
                errors.append('dynamic code execution call')
    return sorted(set(errors))


def inspect_file(path, source):
    errors = []
    if (path.name.lower() in FORBIDDEN_NAMES or
            path.name.lower().startswith('.env.') or
            path.suffix.lower() in FORBIDDEN_SUFFIXES):
        errors.append('sensitive/generated filename')
    if any(pattern.search(source) for pattern in PATTERNS):
        errors.append('selected credential pattern')
    if path.suffix == '.py':
        errors.extend(inspect_python(source, runtime=path == Path('lab.py')))
        if any(line.rstrip() != line for line in source.splitlines()):
            errors.append('trailing whitespace')
        if not source.endswith('\n'):
            errors.append('missing final newline')
    return errors


def main():
    paths = tracked_files(ROOT)
    failures = []
    for path in paths:
        full = ROOT / path
        if full.is_symlink() or not full.is_file():
            failures.append((path, 'nonregular tracked file'))
            continue
        try:
            source = full.read_text(encoding='utf-8')
        except (UnicodeError, OSError):
            failures.append((path, 'non-UTF-8 or unreadable tracked file'))
            continue
        failures.extend((path, reason) for reason in inspect_file(path, source))
    for path, reason in failures:
        print(f'{path}: {reason}', file=sys.stderr)
    print(f'Tracked files checked: {len(paths)}; findings: {len(failures)}')
    return bool(failures)


if __name__ == '__main__':
    sys.exit(main())
