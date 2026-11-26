import concurrent.futures
import hashlib
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path
from lab import Lab, Denied


class TransactionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'transaction.db'
        self.lab = Lab(self.path)

    def tearDown(self):
        self.lab.close()
        self.tmp.cleanup()

    def approved(self, days=60):
        rid = self.lab.submit(days, session=self.lab.simulated_session('requester'))
        digest = self.lab.propose(rid, session=self.lab.simulated_session('controller'))
        self.lab.decide(rid, digest, True, session=self.lab.simulated_session('reviewer'))
        return rid, digest

    def execute(self, rid, digest):
        return self.lab.execute(rid, digest, session=self.lab.simulated_session('executor'))

    def action_count(self):
        return self.lab.db.execute('SELECT COUNT(*) FROM actions').fetchone()[0]

    def test_approval_cannot_be_transplanted(self):
        first, _ = self.approved()
        second, digest = self.approved()
        binding = self.lab._row(first)['approval_digest']
        self.lab.db.execute('UPDATE requests SET approval_digest=? WHERE id=?', (binding, second))
        with self.assertRaises(Denied):
            self.execute(second, digest)
        self.assertEqual(self.action_count(), 0)

    def test_old_policy_approval_requires_reproposal(self):
        rid, _ = self.approved()
        row = self.lab._row(rid)
        old = hashlib.sha256(f"{rid}:{row['version']}:retention-v2:{row['recommendation']}".encode()).hexdigest()
        self.lab.db.execute('UPDATE requests SET digest=?,approval_digest=? WHERE id=?', (old, old, rid))
        with self.assertRaises(Denied):
            self.execute(rid, old)
        new = self.lab.propose(rid, session=self.lab.simulated_session('controller'))
        self.assertNotEqual(old, new)
        with self.assertRaises(Denied):
            self.execute(rid, new)
        self.lab.decide(rid, new, True, session=self.lab.simulated_session('reviewer'))
        self.assertEqual(self.execute(rid, new)['days'], 60)

    def test_execution_event_failure_rolls_back_all_mutations(self):
        rid, digest = self.approved()
        before = self.lab.inventory()
        self.lab.db.execute("""
            CREATE TRIGGER fail_execution BEFORE INSERT ON events
            WHEN NEW.kind='executed'
            BEGIN SELECT RAISE(ABORT,'synthetic event failure'); END
        """)
        with self.assertRaises(sqlite3.IntegrityError):
            self.execute(rid, digest)
        self.assertEqual(self.lab.inventory(), before)
        self.assertEqual(self.action_count(), 0)
        self.assertEqual(self.lab._row(rid)['status'], 'approved')
        self.assertNotIn('executed', [e['kind'] for e in self.lab.events(rid)])
        self.assertFalse(self.lab.db.in_transaction)
        self.lab.db.execute('DROP TRIGGER fail_execution')
        self.assertEqual(self.execute(rid, digest)['revision'], 2)

    def test_approval_event_failure_rolls_back_decision(self):
        rid = self.lab.submit(60, session=self.lab.simulated_session('requester'))
        digest = self.lab.propose(rid, session=self.lab.simulated_session('controller'))
        self.lab.db.execute("""
            CREATE TRIGGER fail_approval BEFORE INSERT ON events
            WHEN NEW.kind='approved'
            BEGIN SELECT RAISE(ABORT,'synthetic event failure'); END
        """)
        with self.assertRaises(sqlite3.IntegrityError):
            self.lab.decide(rid, digest, True, session=self.lab.simulated_session('reviewer'))
        row = self.lab._row(rid)
        self.assertEqual(row['status'], 'proposed')
        self.assertIsNone(row['reviewer'])
        self.assertIsNone(row['approval_digest'])
        self.assertEqual(self.action_count(), 0)

    def race(self, pairs):
        barrier = threading.Barrier(len(pairs), timeout=5)
        def worker(pair):
            other = Lab(self.path)
            try:
                barrier.wait()
                try:
                    result = other.execute(*pair, session=other.simulated_session('executor'))
                    return ('executed', result['days'], result['revision'])
                except Denied:
                    return ('denied', None, None)
            finally:
                other.close()
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(pairs)) as pool:
            return list(pool.map(worker, pairs))

    def test_concurrent_same_request_executes_once(self):
        pair = self.approved()
        outcomes = self.race([pair, pair])
        self.assertCountEqual(outcomes, [('executed', 60, 2), ('denied', None, None)])
        self.assertEqual(self.action_count(), 1)
        self.assertEqual(self.lab.inventory()['revision'], 2)
        self.assertEqual([e['kind'] for e in self.lab.events(pair[0])].count('executed'), 1)

    def test_concurrent_distinct_requests_cannot_use_same_revision_twice(self):
        first = self.approved(60)
        second = self.approved(45)
        outcomes = self.race([first, second])
        self.assertEqual(sorted(x[0] for x in outcomes), ['denied', 'executed'])
        self.assertEqual(self.action_count(), 1)
        winner = next(x for x in outcomes if x[0] == 'executed')
        self.assertEqual(self.lab.inventory()['days'], winner[1])
        self.assertEqual(winner[2], 2)
        self.assertEqual(self.lab.inventory()['revision'], 2)

    def test_rejection_and_execution_are_terminal(self):
        rid, digest = self.approved()
        self.execute(rid, digest)
        with self.assertRaises(Denied):
            self.lab.propose(rid, session=self.lab.simulated_session('controller'))
        with self.assertRaises(Denied):
            self.lab.decide(rid, digest, False, session=self.lab.simulated_session('reviewer'))
        self.assertEqual(self.action_count(), 1)
