import unittest
from pathlib import Path
from scripts.verify_source import inspect_file, inspect_python


class SourceVerifierTests(unittest.TestCase):
    def test_runtime_import_allowlist(self):
        self.assertEqual(inspect_python('import sqlite3\n', runtime=True), [])
        self.assertIn('runtime import outside allowlist',
                      inspect_python('import requests\n', runtime=True))

    def test_dynamic_call(self):
        self.assertIn('dynamic code execution call',
                      inspect_python('eval("1")\n'))

    def test_invalid_syntax(self):
        self.assertIn('invalid Python syntax', inspect_python('def :'))

    def test_sensitive_path(self):
        self.assertIn('sensitive/generated filename', inspect_file(Path('.env'), ''))

    def test_selected_credential_pattern(self):
        marker = 'gh' + 'p_' + 'x' * 36
        self.assertIn('selected credential pattern', inspect_file(Path('sample.txt'), marker))

    def test_source_hygiene(self):
        self.assertIn('trailing whitespace', inspect_file(Path('test.py'), 'x = 1  \n'))
        self.assertIn('missing final newline', inspect_file(Path('test.py'), 'x = 1'))

    def test_regex_compile_is_not_python_execution(self):
        self.assertEqual(inspect_python('import re\nre.compile("pattern")\n'), [])
        for source in ('compile("1", "", "eval")', 'builtins.compile("1", "", "eval")',
                       'builtins.exec("pass")', '__import__("os")'):
            with self.subTest(source=source):
                self.assertIn('dynamic code execution call', inspect_python(source))
