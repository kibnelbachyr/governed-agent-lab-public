import json
import tempfile
import unittest
from pathlib import Path
from lab import Lab, Denied, FakeModel


class AuthorityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'authority.db'
        self.lab = Lab(self.path)

    def tearDown(self):
        self.lab.close()
        self.tmp.cleanup()

    def token(self, role):
        return self.lab.simulated_session(role)

    def proposal(self):
        rid = self.lab.submit(60, session=self.token('requester'))
        digest = self.lab.propose(rid, session=self.token('controller'))
        return rid, digest

    def approve(self, rid, digest):
        self.lab.decide(rid, digest, True, session=self.token('reviewer'))

    def assert_no_action(self):
        self.assertEqual(self.lab.inventory()['revision'], 1)
        self.assertEqual(self.lab.db.execute('SELECT COUNT(*) FROM actions').fetchone()[0], 0)

    def test_missing_and_forged_session(self):
        for token in (None, 'reviewer', 'fabricated', 42):
            with self.subTest(token=token):
                with self.assertRaises(Denied):
                    self.lab.submit(60, session=token)
        self.assertEqual(self.lab.db.execute('SELECT COUNT(*) FROM requests').fetchone()[0], 0)

    def test_role_matrix(self):
        rid, digest = self.proposal()
        operations = {
            'requester': lambda t: self.lab.submit(60, session=t),
            'controller': lambda t: self.lab.propose(rid, session=t),
            'reviewer': lambda t: self.lab.decide(rid, digest, True, session=t),
            'executor': lambda t: self.lab.execute(rid, digest, session=t),
        }
        for allowed, operation in operations.items():
            for role in operations:
                if role != allowed:
                    with self.subTest(allowed=allowed, attempted=role):
                        with self.assertRaises(Denied):
                            operation(self.token(role))
        self.assertEqual(self.lab._row(rid)['status'], 'proposed')
        self.assert_no_action()

    def test_sessions_not_persisted_or_audited(self):
        rid, digest = self.proposal()
        old = self.token('reviewer')
        self.approve(rid, digest)
        self.assertNotIn(old, str(self.lab.events(rid)))
        self.assertNotIn(old, str(self.lab.denials()))
        self.lab.close()
        self.assertNotIn(old.encode(), self.path.read_bytes())
        self.lab = Lab(self.path)
        with self.assertRaises(Denied):
            self.lab.decide(rid, digest, True, session=old)
        self.assertEqual(self.lab.execute(rid, digest, session=self.token('executor'))['days'], 60)

    def test_persisted_payload_change_denied(self):
        rid, digest = self.proposal()
        self.approve(rid, digest)
        payload = json.loads(self.lab._row(rid)['recommendation'])
        payload['rationale'] = 'changed after approval'
        self.lab.db.execute('UPDATE requests SET recommendation=? WHERE id=?', (json.dumps(payload), rid))
        with self.assertRaises(Denied):
            self.lab.execute(rid, digest, session=self.token('executor'))
        self.assert_no_action()

    def test_wrong_persisted_reviewer_denied(self):
        rid, digest = self.proposal()
        self.approve(rid, digest)
        self.lab.db.execute("UPDATE requests SET reviewer='requester' WHERE id=?", (rid,))
        with self.assertRaises(Denied):
            self.lab.execute(rid, digest, session=self.token('executor'))
        self.assert_no_action()

    def test_malformed_persisted_payload_denied(self):
        rid, digest = self.proposal()
        self.lab.db.execute("UPDATE requests SET recommendation='[]' WHERE id=?", (rid,))
        with self.assertRaises(Denied):
            self.approve(rid, digest)
        self.assert_no_action()

    def test_oversized_request_denied(self):
        with self.assertRaises(Denied):
            self.lab.submit(2**100, session=self.token('requester'))

    def test_terminal_request_never_calls_adapter(self):
        rid, digest = self.proposal()
        self.lab.decide(rid, digest, False, session=self.token('reviewer'))
        class Spy:
            called = False
            def recommend(self, *args):
                self.called = True
                return FakeModel().recommend(*args)
        spy = Spy()
        with self.assertRaises(Denied):
            self.lab.propose(rid, spy, session=self.token('controller'))
        self.assertFalse(spy.called)
        self.assert_no_action()
