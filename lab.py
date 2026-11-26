"""Offline reference slice: synthetic retention-change governance only."""
from dataclasses import dataclass
from contextlib import contextmanager
from functools import wraps
import hashlib
import json
import sqlite3
import uuid
from datetime import datetime, timezone

POLICY_VERSION = 'retention-v1'

class Denied(ValueError):
    pass


def audit_denials(operation, has_request=True):
    """Record expected policy/validation denials after the operation has rolled back."""
    def decorate(method):
        @wraps(method)
        def wrapped(self, *args, **kwargs):
            try:
                return method(self, *args, **kwargs)
            except Denied:
                rid = (args[0] if args else kwargs.get('rid')) if has_request else None
                self._record_denial(operation, rid)
                raise
        return wrapped
    return decorate

@dataclass(frozen=True)
class Recommendation:
    retention_days: int
    evidence_id: str
    evidence_revision: int
    rationale: str

class FakeModel:
    """Deterministic read-only adapter, not an actual LLM."""
    def recommend(self, requested_days, inventory):
        return Recommendation(requested_days, inventory['id'], inventory['revision'],
                              'Review the requested retention against the synthetic policy.')

class Lab:
    def __init__(self, path):
        self.db = sqlite3.connect(path, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS inventory(id TEXT PRIMARY KEY, days INTEGER NOT NULL, revision INTEGER NOT NULL);
        INSERT OR IGNORE INTO inventory VALUES('synthetic-store', 30, 1);
        CREATE TABLE IF NOT EXISTS requests(id TEXT PRIMARY KEY, requested_days INTEGER NOT NULL, version INTEGER NOT NULL DEFAULT 0,
            recommendation TEXT, digest TEXT, status TEXT NOT NULL, reviewer TEXT, approval_digest TEXT);
        CREATE TABLE IF NOT EXISTS actions(request_id TEXT PRIMARY KEY REFERENCES requests(id), digest TEXT NOT NULL, new_days INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY AUTOINCREMENT, request_id TEXT NOT NULL REFERENCES requests(id),
            at TEXT NOT NULL, kind TEXT NOT NULL, detail TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS denials(seq INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id TEXT REFERENCES requests(id), at TEXT NOT NULL, operation TEXT NOT NULL);
        ''')

    def close(self):
        self.db.close()

    @contextmanager
    def tx(self):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            yield
            self.db.execute('COMMIT')
        except BaseException:
            self.db.execute('ROLLBACK')
            raise

    def _event(self, rid, kind, detail):
        self.db.execute('INSERT INTO events(request_id,at,kind,detail) VALUES(?,?,?,?)',
                        (rid, datetime.now(timezone.utc).isoformat(),kind,json.dumps(detail, sort_keys=True)))

    def _record_denial(self, operation, rid):
        # Never persist raw unknown IDs, payloads, exception messages or credentials.
        with self.tx():
            known = None
            if isinstance(rid, str) and len(rid) == 36:
                row = self.db.execute('SELECT id FROM requests WHERE id=?', (rid,)).fetchone()
                if row is not None:
                    known = row['id']
            self.db.execute('INSERT INTO denials(request_id,at,operation) VALUES(?,?,?)',
                            (known, datetime.now(timezone.utc).isoformat(), operation))

    def denials(self):
        return [dict(row) for row in self.db.execute('SELECT * FROM denials ORDER BY seq')]

    def _row(self, rid):
        if not isinstance(rid, str) or len(rid) != 36:
            raise Denied('invalid request identifier')
        row = self.db.execute('SELECT * FROM requests WHERE id=?',(rid,)).fetchone()
        if row is None:
            raise Denied('unknown request')
        return row

    def inventory(self):
        return dict(self.db.execute('SELECT * FROM inventory WHERE id=?',('synthetic-store',)).fetchone())

    @audit_denials('submit', has_request=False)
    def submit(self, days):
        if type(days) is not int:
            raise Denied('requested days must be integer')
        rid = str(uuid.uuid4())
        with self.tx():
            self.db.execute('INSERT INTO requests(id,requested_days,status) VALUES(?,?,?)',(rid,days,'submitted'))
            self._event(rid,'submitted',{'days':days})
        return rid

    def _policy(self, request, rec, inventory):
        if type(rec.retention_days) is not int or rec.retention_days != request['requested_days']:
            raise Denied('recommendation differs from request')
        if not 30 <= rec.retention_days <= 90:
            raise Denied('retention outside synthetic 30–90 day policy')
        if rec.evidence_id != inventory['id'] or type(rec.evidence_revision) is not int or rec.evidence_revision != inventory['revision']:
            raise Denied('missing or stale evidence')
        if not isinstance(rec.rationale,str) or not rec.rationale.strip() or len(rec.rationale)>500:
            raise Denied('invalid rationale')

    @audit_denials('propose')
    def propose(self, rid, model=None):
        model = model if model is not None else FakeModel()
        # Untrusted adapter runs outside transaction and has no action capability.
        initial = self._row(rid)
        snapshot = self.inventory()
        try:
            rec = model.recommend(initial['requested_days'],dict(snapshot))
        except Exception as exc:
            with self.tx():
                self._event(rid,'model_failed',{'error_type':type(exc).__name__})
            raise Denied('model failed; no recommendation recorded') from exc
        if not isinstance(rec,Recommendation):
            raise Denied('invalid recommendation schema')
        with self.tx():
            row = self._row(rid)
            if row['status'] in ('executed','rejected'):
                raise Denied('terminal request')
            if row['version'] != initial['version']:
                raise Denied('concurrent recommendation revision')
            self._policy(row,rec,self.inventory())
            ver = row['version']+1
            payload = json.dumps(rec.__dict__,sort_keys=True,separators=(',',':'))
            digest = hashlib.sha256(f'{rid}:{ver}:{POLICY_VERSION}:{payload}'.encode()).hexdigest()
            self.db.execute('UPDATE requests SET version=?,recommendation=?,digest=?,status=?,reviewer=NULL,approval_digest=NULL WHERE id=?',
                            (ver,payload,digest,'proposed',rid))
            self._event(rid,'proposed',{'version':ver,'digest':digest,'policy':POLICY_VERSION,'recommendation':rec.__dict__})
        return digest

    @audit_denials('decide')
    def decide(self,rid,digest,reviewer,approve):
        # Only the simulated human CLI calls this; reviewer is a label, NOT identity authentication.
        if not isinstance(reviewer,str) or not reviewer.strip() or len(reviewer)>80 or type(approve) is not bool:
            raise Denied('invalid decision')
        with self.tx():
            row = self._row(rid)
            if row['status']!='proposed' or row['digest']!=digest:
                raise Denied('no current matching recommendation')
            status = 'approved' if approve else 'rejected'
            if approve:
                self._policy(row,Recommendation(**json.loads(row['recommendation'])),self.inventory())
            self.db.execute('UPDATE requests SET status=?,reviewer=?,approval_digest=? WHERE id=?',
                            (status,reviewer,digest if approve else None,rid))
            self._event(rid,status,{'reviewer':reviewer,'digest':digest})

    @audit_denials('execute')
    def execute(self,rid,digest):
        # Only a synthetic SQLite mutation; transactional authorization and idempotency.
        with self.tx():
            row = self._row(rid)
            if row['status']!='approved' or row['digest']!=digest or row['approval_digest']!=digest:
                raise Denied('current approval required; replay or stale approval denied')
            rec = Recommendation(**json.loads(row['recommendation']))
            self._policy(row,rec,self.inventory())
            self.db.execute('INSERT INTO actions VALUES(?,?,?)',(rid,digest,rec.retention_days))
            self.db.execute('UPDATE inventory SET days=?,revision=revision+1 WHERE id=?',(rec.retention_days,rec.evidence_id))
            self.db.execute('UPDATE requests SET status=? WHERE id=?',('executed',rid))
            self._event(rid,'executed',{'digest':digest,'days':rec.retention_days,'idempotency_key':rid})
        return self.inventory()

    def events(self,rid):
        return [dict(row) for row in self.db.execute('SELECT * FROM events WHERE request_id=? ORDER BY seq',(rid,))]

if __name__ == '__main__':
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as tmp:
        lab = Lab(Path(tmp)/'demo.db')
        request = lab.submit(60)
        digest = lab.propose(request)
        print('Proposed:',digest)
        answer = input('Approve synthetic change to 60 days? [y/N] ').strip().lower()
        lab.decide(request,digest,'local-demo-reviewer',answer=='y')
        if answer=='y':
            print('Simulated result:',lab.execute(request,digest))
        print(json.dumps(lab.events(request),indent=2))
        lab.close()
