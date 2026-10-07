import copy
import json
from pathlib import Path
import tempfile
import unittest
from review_readiness import item_state, summarize, remember
from review_delivery import sync
from review_gallery import build_gallery


class ReviewReadinessTests(unittest.TestCase):
    def setUp(self):
        self.item={'id':'A','version':1,'status':'approved','captionStatus':'approved','sha256':'abc',
            'captions':{'instagram':{'caption':'Native description'}},
            'distribution':{'targets':[{'organizationId':'org','accountId':a,'platform':'instagram'} for a in ['one','two']]}}
        self.rows=[{'itemId':'A','version':1,'postId':'p','organizationId':'org','accountId':a,
            'status':'scheduled','checkedAt':'2026-10-06T12:00:00Z','mediaSha256':'abc','caption':'Native description'} for a in ['one','two']]

    def test_all_targets_complete_at_scheduling_and_never_require_publication(self):
        self.assertEqual(item_state(self.item,self.rows)['state'],'scheduled')
        self.rows.pop();self.assertEqual(item_state(self.item,self.rows)['state'],'ready')
        self.item['distribution']['targets']=[]
        self.assertNotEqual(item_state(self.item,self.rows)['state'],'scheduled')

    def test_review_flags_do_not_reopen_scheduled_items_or_infer_approval(self):
        self.item['status']='needs-review';self.item.pop('captionStatus')
        summary=summarize({'items':[self.item]},self.rows)
        self.assertEqual(summary['counts']['needs-review'],0)
        self.assertEqual(summary['state'],'scheduled')
        self.assertEqual(self.item['status'],'needs-review')

    def test_later_failure_does_not_reopen_an_accepted_handoff(self):
        for row in self.rows:remember(row);row['status']='failed'
        self.assertEqual(item_state(self.item,self.rows)['state'],'scheduled')
        self.rows[0].pop('handoff')
        self.assertEqual(item_state(self.item,self.rows)['state'],'ready')

    def test_new_version_and_new_batch_reactivate_only_new_work(self):
        changed=copy.deepcopy(self.item);changed.update(version=2,status='needs-review',batch='new')
        summary=summarize({'items':[self.item,changed]},self.rows)
        self.assertEqual((summary['state'],summary['active'],summary['scheduled']),('active',1,1))
        summary=summarize({'items':[self.item,changed],'batches':[{'id':'new','lifecycle':'archived'}]},self.rows)
        self.assertEqual(summary['state'],'scheduled')

    def test_copy_changes_and_media_mismatch_need_work(self):
        self.item['captions']['instagram']['caption']='Revised copy'
        self.assertEqual(item_state(self.item,self.rows)['state'],'needs-copy')
        self.item['sha256']='def';self.assertEqual(item_state(self.item,self.rows)['state'],'needs-review')

    def test_excluded_prototype_and_empty_format_not_active_or_scheduled(self):
        self.item['distribution']={'status':'excluded','reason':'Rejected prototype'}
        self.assertEqual(summarize({'items':[self.item]},self.rows)['state'],'empty')
        self.assertEqual(summarize({'items':[]},[])['state'],'empty')

    def test_copy_and_production_are_distinct_next_actions(self):
        self.item.pop('captionStatus')
        self.assertEqual(item_state(self.item,[])['state'],'needs-copy')
        self.item['status']='generating';self.assertEqual(item_state(self.item,[])['state'],'production')
        self.item['status']='changes-requested';self.assertEqual(item_state(self.item,[])['state'],'changes-requested')

    def test_approved_source_is_not_ready_to_schedule(self):
        self.item.update(status='Approved',stage='source')
        self.assertEqual(item_state(self.item,[])['state'],'production')

    def test_import_preserves_original_scheduling_receipt_before_live_update(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);logs=root/'history/publications';logs.mkdir(parents=True)
            (logs/'links.jsonl').write_text(json.dumps({'postId':'p','accountId':'one','itemId':'A','version':1})+'\n', encoding='utf-8')
            output=root/'delivery.json';output.write_text(json.dumps({'placements':self.rows[:1]}), encoding='utf-8')
            page=root/'posts.json';page.write_text(json.dumps({'observedAt':'2026-10-07T12:00:00Z','posts':[{'post':{'id':'p'},'targets':[{'socialAccountId':'one','status':'failed'}]}]}), encoding='utf-8')
            row=sync(root,[page],output)['placements'][0]
            self.assertEqual(row['status'],'failed')
            self.assertEqual(row['handoff']['confirmedAt'],'2026-10-06T12:00:00Z')

    def test_social_gallery_uses_review_stages_and_no_posted_lane(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'p.png').write_bytes(b'image')
            item={**self.item,'format':'UGC','title':'A','kind':'image','src':'p.png'}
            manifest={'title':'Review','round':1,'reviewHub':{'kind':'social-content','formatId':'ugc'},'items':[item], 'delivery':{'snapshot':'delivery.json'}}
            (root/'delivery.json').write_text(json.dumps({'placements':self.rows}), encoding='utf-8')
            (root/'review.json').write_text(json.dumps(manifest), encoding='utf-8');build_gallery(root/'review.json',root/'review.html')
            html=(root/'review.html').read_text(encoding='utf-8')
            self.assertIn('id="section-scheduled"',html)
            self.assertIn('data-delivery="scheduled"',html)
            self.assertNotIn('value="posted"',html)
            self.assertNotIn('Published ',html)

if __name__=='__main__':unittest.main()
