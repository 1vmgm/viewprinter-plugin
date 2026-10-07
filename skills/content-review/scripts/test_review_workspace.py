import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import review_workspace as ws
from review_delivery import item_progress, summarize, sync
from review_gallery import build_gallery


class ProgressTests(unittest.TestCase):
    def setUp(self):
        self.item={'id':'A','version':2,'status':'approved','captionStatus':'approved','sha256':'abc',
            'captions':{'instagram':{'caption':'Hello'}},'distribution':{'targets':[
                {'accountId':a,'organizationId':'org','platform':'instagram'} for a in ('one','two')]}}
        self.rows=[{'itemId':'A','version':2,'accountId':a,'organizationId':'org','status':s,
            'caption':'Hello','checkedAt':'2026-10-05T12:00:00Z','mediaSha256':'abc'} for a,s in [('one','published'),('two','scheduled')]]
    def progress(self):return item_progress(self.item,self.rows)
    def test_all_destinations_and_empty_plan(self):
        self.assertEqual(self.progress()['state'],'all-scheduled')
        self.rows[1]['status']='published';self.assertEqual(self.progress()['state'],'all-posted')
        self.item['distribution']={};self.assertNotEqual(self.progress()['state'],'all-posted')
        self.assertNotEqual(summarize({'items':[]},[])['state'],'all-posted')
    def test_cancellation_unknown_org_and_removed_do_not_complete(self):
        for status in ('failed','canceled','unknown','removed'):
            self.rows[1]['status']=status;self.assertNotEqual(self.progress()['state'],'all-posted')
        self.rows[1]['status']='published';self.rows[1]['organizationId']='other'
        self.assertNotEqual(self.progress()['state'],'all-posted')
        self.item['distribution']['targets'][1].update(state='withdrawn',reason='Moved to a different account')
        self.assertEqual(self.progress()['state'],'all-posted')
    def test_copy_title_media_changes_are_visible(self):
        self.item['captions']['instagram']['title']='New title';self.rows[1].update(caption='Old',title='Old title',mediaSha256='old')
        p=self.progress();self.assertEqual(p['copy'],'changed');self.assertIn('media-version-mismatch',p['issues'])
    def test_revised_version_and_new_batch_reset_completion(self):
        self.rows[1]['status']='published'
        m={'items':[self.item]};self.assertEqual(summarize(m,self.rows)['state'],'all-posted')
        changed=copy.deepcopy(self.item);changed['version']=3;m['items']=[changed]
        self.assertNotEqual(summarize(m,self.rows)['state'],'all-posted')
        m['items']=[self.item,changed];self.assertNotEqual(summarize(m,self.rows)['state'],'all-posted')
    def test_receipt_clock_and_complete_removal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);logs=root/'history/publications';logs.mkdir(parents=True)
            link={'postId':'p','accountId':'one','itemId':'A','version':2,'batchId':'b'}
            (logs/'links.jsonl').write_text(json.dumps(link)+'\n', encoding='utf-8')
            out=root/'delivery.json';page=root/'receipt.json'
            d={'observedAt':'2026-10-05T12:00:00Z','posts':[{'post':{'id':'p'},'targets':[{'socialAccountId':'one','status':'published'}]}]}
            page.write_text(json.dumps(d), encoding='utf-8');r=sync(root,[page],out)['placements'][0]
            self.assertEqual(r['checkedAt'],d['observedAt'])
            d['observedAt']='2026-10-01T12:00:00Z';d['posts'][0]['targets'][0]['status']='pending';page.write_text(json.dumps(d), encoding='utf-8')
            self.assertEqual(sync(root,[page],out)['placements'][0]['status'],'published')
            d['observedAt']='2026-10-06T12:00:00Z';d['posts'][0]['targets']=[];page.write_text(json.dumps(d), encoding='utf-8')
            self.assertEqual(sync(root,[page],out)['placements'][0]['status'],'published')
            d['readScope']={'completeTargets':True,'accountFilter':False,'postIds':['p']};page.write_text(json.dumps(d), encoding='utf-8')
            self.assertEqual(sync(root,[page],out)['placements'][0]['status'],'removed')


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name).resolve();self.project=self.root/'project';(self.project/'.viewprinter/content-memory').mkdir(parents=True)
        self.folder=self.project/'format';self.folder.mkdir();self.hub=self.root/'hub'
        self.env=patch.dict(os.environ,{'VIEWPRINTER_REVIEW_ROOT':str(self.hub),'VIEWPRINTER_REVIEW_HUB':'0'});self.env.start();self.addCleanup(self.env.stop)
        (self.folder/'preview.png').write_bytes(b'unchanged-image')
        self.data={'title':'Example','round':1,'reviewHub':{'kind':'social-content','formatId':'ugc'},'batches':[{'id':'new','label':'New'},{'id':'old','label':'Old'}],
            'items':[{'id':x,'version':1,'title':x,'format':'ugc','kind':'image','status':'needs-review','src':'preview.png','batch':b} for x,b in [('A','new'),('B','old')]]}
        self.mf=self.folder/'review.json';self.mf.write_text(json.dumps(self.data), encoding='utf-8');self.gallery=self.folder/'review.html';build_gallery(self.mf,self.gallery)
    def register(self):return ws.register(self.gallery,name='example--product-demo')
    def test_scope_rejection_and_atomic_collision(self):
        self.data.pop('reviewHub');self.mf.write_text(json.dumps(self.data), encoding='utf-8')
        with self.assertRaises(ValueError):self.register()
        self.data['reviewHub']={'kind':'social-content','formatId':'x'};self.data['reviewScope']='product-listing-assets';self.mf.write_text(json.dumps(self.data), encoding='utf-8')
        with self.assertRaises(ValueError):self.register()
    def test_registration_race_has_one_stable_entry(self):
        script='import review_workspace as w;w.register('+repr(str(self.gallery))+',name="example--product-demo")'
        processes=[subprocess.Popen([sys.executable,'-c',script],cwd=Path(ws.__file__).parent,stdout=subprocess.PIPE,stderr=subprocess.PIPE) for _ in range(5)]
        for process in processes:
            _,error=process.communicate(timeout=20);self.assertEqual(process.returncode,0,error)
        self.assertEqual(len(ws.records()),1);self.assertEqual(ws.get('example--product-demo')['revision'],5)
    def test_archive_media_is_immutable_and_revision_conflicts(self):
        entry=self.register();r=ws.get(entry);archived=ws.lifecycle(entry,'archive',r['revision'])
        assets=json.loads(Path(archived['snapshotAssets']).read_text(encoding='utf-8'));self.assertEqual(len(assets),1)
        frozen=Path(next(iter(assets.values()))['path']);(self.folder/'preview.png').write_bytes(b'changed')
        self.assertEqual(frozen.read_bytes(),b'unchanged-image')
        with self.assertRaises(ValueError):ws.lifecycle(entry,'restore',r['revision'])
        ws.lifecycle(entry,'restore',archived['revision']);self.assertEqual(ws.get(entry)['id'],entry)
    def test_batch_archive_restore_and_rearchive(self):
        entry=self.register();r=ws.lifecycle(entry,'archive',batch='old')
        self.assertEqual(ws.describe(ws.get(entry))['summary']['items'],1)
        snapshot=Path(r['snapshotGallery']).read_bytes();ws.lifecycle(r['id'],'restore')
        self.assertEqual(ws.describe(ws.get(entry))['summary']['items'],2)
        self.assertEqual(Path(r['snapshotGallery']).read_bytes(),snapshot)
        ws.lifecycle(entry,'archive',batch='old');self.assertEqual(ws.describe(ws.get(entry))['summary']['items'],1)
    def test_failed_batch_build_preserves_manifest(self):
        entry=self.register();before=self.mf.read_bytes()
        with patch('review_gallery.build_gallery',side_effect=ValueError('bad media')):
            with self.assertRaises(ValueError):ws.lifecycle(entry,'archive',batch='old')
        self.assertEqual(self.mf.read_bytes(),before);self.assertEqual(len(ws.records()),1)
    def test_migration_idempotence_legacy_alias_and_rollback(self):
        old=self.hub/'posted/2020-01-01';old.mkdir(parents=True);(old/'legacy').symlink_to(self.folder)
        live=self.hub/'in-review';live.mkdir();(live/'example').symlink_to(self.folder)
        self.assertEqual(len(ws.migrate()['entries']),2);self.assertEqual(ws.records(),[])
        result=ws.migrate(True);self.assertEqual(len(ws.migrate(True)['entries']),0)
        legacy=ws.get('posted/2020-01-01/legacy');self.assertEqual(legacy['lifecycle'],'archived');self.assertNotEqual(ws.describe(legacy)['progress']['state'],'all-posted')
        self.assertEqual(len(ws.scan()[0]['archived']),1)
        ws.rollback(result['backup']);self.assertEqual(ws.records(),[]);self.assertTrue((live/'example').is_symlink())
    def test_download_scope(self):
        (self.folder/'public.json').write_text('{}', encoding='utf-8');(self.project/'private.json').write_text('{}', encoding='utf-8')
        self.data['downloads']=[{'id':'allowed','title':'Public','path':'public.json'},{'id':'no','title':'No','path':'../private.json'}];self.mf.write_text(json.dumps(self.data), encoding='utf-8')
        entry=self.register();self.assertEqual([d['id'] for d in ws.describe(ws.get(entry))['downloads']],['allowed'])

if __name__=='__main__':unittest.main()
