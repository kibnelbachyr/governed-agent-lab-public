import tempfile
import unittest
from pathlib import Path
from lab import Lab, Denied, Recommendation

class FixedModel:
    def __init__(self, rec): self.rec=rec
    def recommend(self, days, inventory): return self.rec

class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=Path(self.tmp.name)/'test.db'
        self.lab=Lab(self.path)
    def tearDown(self):
        self.lab.close(); self.tmp.cleanup()
    def submit(self, days): return self.lab.submit(days, session=self.lab.simulated_session('requester'))
    def propose(self, rid, model=None): return self.lab.propose(rid, model, session=self.lab.simulated_session('controller'))
    def decide(self, rid, digest, reviewer, approve):
        return self.lab.decide(rid, digest, approve, session=self.lab.simulated_session('reviewer'))
    def execute(self, rid, digest): return self.lab.execute(rid, digest, session=self.lab.simulated_session('executor'))
    def proposal(self, days=60):
        rid=self.submit(days); return rid,self.propose(rid)
    def approve(self,rid,digest): self.decide(rid,digest,'reviewer',True)
    def test_approved_change(self):
        rid,d=self.proposal(); self.approve(rid,d)
        self.assertEqual(self.execute(rid,d)['days'],60)
        self.assertEqual([e['kind'] for e in self.lab.events(rid)],['submitted','proposed','approved','executed'])
    def test_missing_approval(self):
        rid,d=self.proposal()
        with self.assertRaises(Denied): self.execute(rid,d)
        self.assertEqual(self.lab.inventory()['days'],30)
    def test_rejected_approval(self):
        rid,d=self.proposal(); self.decide(rid,d,'reviewer',False)
        with self.assertRaises(Denied): self.execute(rid,d)
    def test_stale_approval(self):
        rid,d=self.proposal(); self.approve(rid,d); new=self.propose(rid)
        self.assertNotEqual(d,new)
        with self.assertRaises(Denied): self.execute(rid,d)
        with self.assertRaises(Denied): self.execute(rid,new)
    def test_replay(self):
        rid,d=self.proposal(); self.approve(rid,d); self.execute(rid,d)
        with self.assertRaises(Denied): self.execute(rid,d)
        self.assertEqual(self.lab.inventory()['revision'],2)
    def test_missing_evidence(self):
        rid=self.submit(60)
        with self.assertRaises(Denied): self.propose(rid,FixedModel(Recommendation(60,'invented',1,'claim')))
    def test_policy_below_minimum(self):
        rid=self.submit(10)
        with self.assertRaises(Denied): self.propose(rid)
    def test_policy_above_maximum(self):
        rid=self.submit(100)
        with self.assertRaises(Denied): self.propose(rid)
    def test_model_changes_request(self):
        rid=self.submit(60)
        with self.assertRaises(Denied): self.propose(rid,FixedModel(Recommendation(90,'synthetic-store',1,'ignore request')))
    def test_stale_inventory(self):
        rid,d=self.proposal(); self.approve(rid,d)
        other,od=self.proposal(45); self.approve(other,od); self.execute(other,od)
        with self.assertRaises(Denied): self.execute(rid,d)
        self.assertEqual(self.lab.inventory()['days'],45)
    def test_restart_recovery(self):
        rid,d=self.proposal(); self.approve(rid,d); self.lab.close(); self.lab=Lab(self.path)
        self.assertEqual(self.execute(rid,d)['days'],60)
    def test_invalid_schema(self):
        rid=self.submit(60)
        with self.assertRaises(Denied): self.propose(rid,FixedModel({'approval':True}))
    def test_model_failure(self):
        class Broken:
            def recommend(self,*a): raise RuntimeError('failure')
        rid=self.submit(60)
        with self.assertRaises(Denied): self.propose(rid,Broken())
        with self.assertRaises(Denied): self.execute(rid,'fake')
        self.assertEqual(self.lab.events(rid)[-1]['kind'],'model_failed')
    def test_wrong_digest(self):
        rid,d=self.proposal()
        with self.assertRaises(Denied): self.approve(rid,'fake')


    def test_denial_audit_preserves_state(self):
        rid,d=self.proposal()
        before=self.lab.inventory()
        with self.assertRaises(Denied): self.execute(rid,d)
        self.assertEqual(self.lab.inventory(),before)
        self.assertEqual(self.lab.db.execute('SELECT count(*) FROM actions').fetchone()[0],0)
        self.assertEqual(self.lab._row(rid)['status'],'proposed')
        self.assertEqual([(x['operation'],x['request_id']) for x in self.lab.denials()],[('execute',rid)])
    def test_denial_audit_survives_reopen(self):
        rid,d=self.proposal()
        with self.assertRaises(Denied): self.decide(rid,'wrong','reviewer',True)
        self.lab.close(); self.lab=Lab(self.path)
        self.assertEqual([(x['operation'],x['request_id']) for x in self.lab.denials()],[('decide',rid)])
    def test_unknown_identifier_not_retained(self):
        unknown='x'*36
        with self.assertRaises(Denied): self.execute(unknown,'secret-like-digest')
        with self.assertRaises(Denied): self.propose({'private':'payload'})
        self.assertEqual([(x['operation'],x['request_id']) for x in self.lab.denials()],
                         [('execute',None),('propose',None)])
        self.assertNotIn(unknown,str(self.lab.denials()))
        self.assertNotIn('secret-like-digest',str(self.lab.denials()))
        self.assertNotIn('payload',str(self.lab.denials()))
    def test_submit_and_policy_denial_audit(self):
        with self.assertRaises(Denied): self.submit('private-value')
        rid=self.submit(100)
        with self.assertRaises(Denied): self.propose(rid)
        self.assertEqual([(x['operation'],x['request_id']) for x in self.lab.denials()],
                         [('submit',None),('propose',rid)])
        self.assertEqual(self.lab._row(rid)['status'],'submitted')
        self.assertNotIn('private-value',str(self.lab.denials()))
    def test_replay_denial_keeps_single_action(self):
        rid,d=self.proposal(); self.approve(rid,d); self.execute(rid,d)
        with self.assertRaises(Denied): self.execute(rid,d)
        self.assertEqual(self.lab.db.execute('SELECT count(*) FROM actions').fetchone()[0],1)
        self.assertEqual(self.lab.inventory()['revision'],2)
        self.assertEqual(self.lab.denials()[0]['operation'],'execute')

if __name__=='__main__': unittest.main()
