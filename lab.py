"""Offline reference slice: synthetic retention-change governance only."""
from dataclasses import dataclass
from contextlib import contextmanager
from functools import wraps
import hashlib
import hmac
import secrets
import json
import sqlite3
import uuid
from datetime import datetime, timezone

POLICY_VERSION = 'retention-v3'


def approval_binding(rid, version, digest, reviewer):
    """Consistency binding, not a signature against a malicious database writer."""
    data = json.dumps([rid, version, POLICY_VERSION, digest, reviewer, 'approve'],
                      separators=(',', ':'))
    return hashlib.sha256(data.encode('utf-8')).hexdigest()

# In-process simulated credentials, not externally authenticated identities.
PRINCIPALS = {'requester': 'submit', 'reviewer': 'decide', 'executor': 'execute', 'controller': 'propose'}


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

MAX_RESPONSE_BYTES = 4096
_DEFAULT_RESPONSE = object()

def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key')
        result[key] = value
    return result

def _reject_constant(value):
    raise ValueError('nonfinite JSON number')

def parse_response(raw):
    """Only bounded UTF-8 JSON data crosses the recommendation boundary."""
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_RESPONSE_BYTES:
        raise Denied('invalid provider response size or type')
    try:
        data = json.loads(raw.decode('utf-8'), object_pairs_hook=_unique_object,
                          parse_constant=_reject_constant)
        if type(data) is not dict or set(data) != {
            'retention_days', 'evidence_id', 'evidence_revision', 'rationale'
        }:
            raise ValueError('unexpected response fields')
        if (type(data['retention_days']) is not int or
            type(data['evidence_revision']) is not int or
            type(data['evidence_id']) is not str or
            type(data['rationale']) is not str):
            raise ValueError('invalid primitive types')
        for value in (data['evidence_id'], data['rationale']):
            value.encode('utf-8')
            if any(ord(ch) < 32 or 127 <= ord(ch) <= 159 for ch in value):
                raise ValueError('control character')
        return Recommendation(**data)
    except (ValueError, TypeError, UnicodeError, RecursionError) as exc:
        raise Denied('invalid provider response') from exc

class FakeModel:
    """Deterministic read-only adapter, not an actual LLM."""
    def recommend(self, requested_days, inventory):
        return Recommendation(requested_days, inventory['id'], inventory['revision'],
                              'Review the requested retention against the synthetic policy.')

class Lab:
    def __init__(self, path):
        self._sessions = {name: secrets.token_urlsafe(32) for name in PRINCIPALS}
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

    def simulated_session(self, principal):
        """Trusted local harness only: explicitly simulates identity issuance."""
        if type(principal) is not str or principal not in self._sessions:
            raise Denied('unknown simulated principal')
        return self._sessions[principal]

    def _authorize(self, session, operation):
        if type(session) is str and len(session) <= 128 and session.isascii():
            for principal, token in self._sessions.items():
                if hmac.compare_digest(session.encode('utf-8', errors='replace'), token.encode()) and PRINCIPALS[principal] == operation:
                    return principal
        raise Denied('missing or unauthorized simulated session')

    def close(self):
        self.db.close()

    @contextmanager
    def tx(self):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            yield
            self.db.execute('COMMIT')
        except BaseException:
            if self.db.in_transaction:
                self.db.execute('ROLLBACK')
            raise

    def _event(self, rid, kind, detail):
        self.db.execute('INSERT INTO events(request_id,at,kind,detail) VALUES(?,?,?,?)',
                        (rid, datetime.now(timezone.utc).isoformat(),kind,json.dumps(detail, sort_keys=True)))

    def _record_denial(self, operation, rid):
        # Never persist raw unknown IDs, payloads, exception messages or credentials.
        with self.tx():
            known = None
            if type(rid) is str and len(rid) == 36 and rid.isascii():
                row = self.db.execute('SELECT id FROM requests WHERE id=?', (rid,)).fetchone()
                if row is not None:
                    known = row['id']
            self.db.execute('INSERT INTO denials(request_id,at,operation) VALUES(?,?,?)',
                            (known, datetime.now(timezone.utc).isoformat(), operation))

    def denials(self):
        return [dict(row) for row in self.db.execute('SELECT * FROM denials ORDER BY seq')]

    def _row(self, rid):
        if type(rid) is not str or len(rid) != 36 or not rid.isascii():
            raise Denied('invalid request identifier')
        row = self.db.execute('SELECT * FROM requests WHERE id=?',(rid,)).fetchone()
        if row is None:
            raise Denied('unknown request')
        return row

    def inventory(self):
        return dict(self.db.execute('SELECT * FROM inventory WHERE id=?',('synthetic-store',)).fetchone())

    @audit_denials('submit', has_request=False)
    def submit(self, days, *, session=None):
        principal = self._authorize(session, 'submit')
        if type(days) is not int or not -(2**63) <= days < 2**63:
            raise Denied('requested days must be integer')
        rid = str(uuid.uuid4())
        with self.tx():
            self.db.execute('INSERT INTO requests(id,requested_days,status) VALUES(?,?,?)',(rid,days,'submitted'))
            self._event(rid,'submitted',{'days':days,'principal':principal})
        return rid

    def _policy(self, request, rec, inventory):
        if type(rec.retention_days) is not int or rec.retention_days != request['requested_days']:
            raise Denied('recommendation differs from request')
        if not 30 <= rec.retention_days <= 90:
            raise Denied('retention outside synthetic 30–90 day policy')
        if type(rec.evidence_id) is not str or rec.evidence_id != inventory['id'] or type(rec.evidence_revision) is not int or rec.evidence_revision != inventory['revision']:
            raise Denied('missing or stale evidence')
        if type(rec.rationale) is not str or not rec.rationale.strip() or len(rec.rationale)>500:
            raise Denied('invalid rationale')

    @audit_denials('propose')
    def propose(self, rid, response=_DEFAULT_RESPONSE, *, session=None):
        self._authorize(session, 'propose')
        initial = self._row(rid)
        if initial['status'] in ('executed','rejected'):
            raise Denied('terminal request')
        snapshot = self.inventory()
        if response is _DEFAULT_RESPONSE:
            response = json.dumps(FakeModel().recommend(initial['requested_days'], snapshot).__dict__).encode()
        if response is None:
            with self.tx():
                row = self._row(rid)
                if row['status'] != initial['status'] or row['version'] != initial['version']:
                    raise Denied('concurrent recommendation revision')
                self._event(rid,'model_failed',{'reason':'provider_unavailable'})
            raise Denied('provider unavailable')
        rec = parse_response(response)
        with self.tx():
            row = self._row(rid)
            if row['status'] in ('executed','rejected'):
                raise Denied('terminal request')
            if row['version'] != initial['version'] or row['status'] != initial['status']:
                raise Denied('concurrent recommendation revision')
            self._policy(row,rec,self.inventory())
            ver = row['version']+1
            payload = json.dumps(rec.__dict__,sort_keys=True,separators=(',',':'),ensure_ascii=False)
            digest = hashlib.sha256(f'{rid}:{ver}:{POLICY_VERSION}:{payload}'.encode()).hexdigest()
            self.db.execute('UPDATE requests SET version=?,recommendation=?,digest=?,status=?,reviewer=NULL,approval_digest=NULL WHERE id=?',
                            (ver,payload,digest,'proposed',rid))
            self._event(rid,'proposed',{'version':ver,'digest':digest,'policy':POLICY_VERSION,'recommendation':rec.__dict__})
        return digest

    def _current_recommendation(self, row):
        try:
            payload = row['recommendation']
            rec = parse_response(payload.encode('utf-8'))
            expected = hashlib.sha256(f"{row['id']}:{row['version']}:{POLICY_VERSION}:{payload}".encode()).hexdigest()
            if row['digest'] != expected:
                raise Denied('recommendation integrity or policy version mismatch')
            return rec
        except (TypeError, ValueError, KeyError, AttributeError) as exc:
            raise Denied('invalid persisted recommendation') from exc

    @audit_denials('decide')
    def decide(self,rid,digest,approve, *, session=None):
        reviewer = self._authorize(session, 'decide')
        if type(approve) is not bool or type(digest) is not str or len(digest) != 64:
            raise Denied('invalid decision')
        with self.tx():
            row = self._row(rid)
            if row['status']!='proposed' or row['digest']!=digest:
                raise Denied('no current matching recommendation')
            status = 'approved' if approve else 'rejected'
            rec = self._current_recommendation(row)
            if approve:
                self._policy(row,rec,self.inventory())
            self.db.execute('UPDATE requests SET status=?,reviewer=?,approval_digest=? WHERE id=?',
                            (status,reviewer,approval_binding(rid,row['version'],digest,reviewer) if approve else None,rid))
            self._event(rid,status,{'reviewer':reviewer,'digest':digest})

    @audit_denials('execute')
    def execute(self,rid,digest, *, session=None):
        principal = self._authorize(session, 'execute')
        if type(digest) is not str or len(digest) != 64:
            raise Denied('invalid digest')
        # Only a synthetic SQLite mutation; transactional authorization and idempotency.
        with self.tx():
            row = self._row(rid)
            if row['status']!='approved' or row['digest']!=digest or row['reviewer']!='reviewer' or row['approval_digest']!=approval_binding(rid,row['version'],digest,row['reviewer']):
                raise Denied('current approval required; replay or stale approval denied')
            rec = self._current_recommendation(row)
            self._policy(row,rec,self.inventory())
            self.db.execute('INSERT INTO actions VALUES(?,?,?)',(rid,digest,rec.retention_days))
            self.db.execute('UPDATE inventory SET days=?,revision=revision+1 WHERE id=?',(rec.retention_days,rec.evidence_id))
            self.db.execute('UPDATE requests SET status=? WHERE id=?',('executed',rid))
            self._event(rid,'executed',{'digest':digest,'days':rec.retention_days,'idempotency_key':rid,'principal':principal})
            result = self.inventory()
        return result

    def events(self,rid):
        return [dict(row) for row in self.db.execute('SELECT * FROM events WHERE request_id=? ORDER BY seq',(rid,))]

if __name__ == '__main__':
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as tmp:
        lab = Lab(Path(tmp)/'demo.db')
        request = lab.submit(60, session=lab.simulated_session('requester'))
        digest = lab.propose(request, session=lab.simulated_session('controller'))
        print('Proposed:',digest)
        answer = input('Approve synthetic change to 60 days? [y/N] ').strip().lower()
        lab.decide(request,digest,answer=='y', session=lab.simulated_session('reviewer'))
        if answer=='y':
            print('Simulated result:',lab.execute(request,digest, session=lab.simulated_session('executor')))
        print(json.dumps(lab.events(request),indent=2))
        lab.close()
