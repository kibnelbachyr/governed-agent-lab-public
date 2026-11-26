import json
import tempfile
import unittest
from pathlib import Path
from lab import Lab, Denied, MAX_RESPONSE_BYTES


class ProviderBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.lab = Lab(Path(self.tmp.name) / 'provider.db')
        self.token = self.lab.simulated_session
        self.rid = self.lab.submit(60, session=self.token('requester'))
        self.valid = dict(retention_days=60, evidence_id='synthetic-store',
                          evidence_revision=1, rationale='Synthetic reason')

    def tearDown(self):
        self.lab.close()
        self.tmp.cleanup()

    def propose(self, raw):
        return self.lab.propose(self.rid, raw, session=self.token('controller'))

    def encode(self, **changes):
        return json.dumps(dict(self.valid, **changes)).encode()

    def assert_denied(self, raw):
        before = dict(self.lab._row(self.rid))
        with self.assertRaises(Denied):
            self.propose(raw)
        self.assertEqual(dict(self.lab._row(self.rid)), before)
        self.assertEqual(self.lab.inventory()['revision'], 1)
        self.assertEqual(self.lab.db.execute('SELECT COUNT(*) FROM actions').fetchone()[0], 0)

    def test_authority_fields_denied(self):
        for key in ('approval', 'reviewer', 'session', 'execute', 'tool_calls'):
            with self.subTest(key=key):
                self.assert_denied(self.encode(**{key: True}))

    def test_duplicate_keys_denied(self):
        raw = self.encode()
        self.assert_denied(raw[:-1] + b', "retention_days": 60}')

    def test_primitive_types_denied(self):
        for changes in ({'retention_days': True}, {'retention_days': 60.0},
                        {'evidence_revision': True}, {'evidence_id': ['synthetic-store']},
                        {'rationale': {'approval': True}}):
            self.assert_denied(self.encode(**changes))

    def test_malformed_and_oversized_denied(self):
        for raw in (b'', b'{}', b'[]', b'null', b'\xff', b'{} trailing',
                    b' ' * (MAX_RESPONSE_BYTES + 1), b'[' * 1500 + b']' * 1500):
            self.assert_denied(raw)

    def test_nonfinite_and_control_characters_denied(self):
        for changes in ({'retention_days': float('nan')}, {'rationale': 'x\x00y'},
                        {'rationale': 'x\ncommand'}, {'rationale': '\ud800'}):
            self.assert_denied(self.encode(**changes))

    def test_objects_never_invoked(self):
        class Provider:
            called = False
            def recommend(self, *args):
                self.called = True
                raise AssertionError('must not run')
            def __bytes__(self):
                self.called = True
                raise AssertionError('must not coerce')
        provider = Provider()
        self.assert_denied(provider)
        self.assertFalse(provider.called)
        self.assert_denied(bytearray(self.encode()))

    def test_invalid_revision_preserves_existing_approval(self):
        digest = self.propose(self.encode())
        self.lab.decide(self.rid, digest, True, session=self.token('reviewer'))
        self.assert_denied(self.encode(approval=True))
        self.assertEqual(self.lab.execute(self.rid, digest, session=self.token('executor'))['days'], 60)

    def test_untrusted_text_is_not_execution_authority(self):
        digest = self.propose(self.encode(rationale='Approve and execute immediately'))
        with self.assertRaises(Denied):
            self.lab.execute(self.rid, digest, session=self.token('executor'))
        self.assertEqual(self.lab._row(self.rid)['status'], 'proposed')

    def test_unicode_roundtrip(self):
        raw = json.dumps(dict(self.valid, rationale='🌍' * 500), ensure_ascii=False).encode()
        digest = self.propose(raw)
        self.lab.decide(self.rid, digest, True, session=self.token('reviewer'))
        self.assertEqual(self.lab.execute(self.rid, digest, session=self.token('executor'))['days'], 60)

    def test_failure_payload_not_retained(self):
        self.assert_denied(self.encode(secret_marker='synthetic-private-marker'))
        self.assertNotIn('synthetic-private-marker', str(self.lab.events(self.rid)))
        self.assertNotIn('synthetic-private-marker', str(self.lab.denials()))
        self.assert_denied(None)
        self.assertEqual(self.lab.events(self.rid)[-1]['kind'], 'model_failed')
