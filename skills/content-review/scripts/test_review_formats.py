import copy
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import unquote
import review_workspace as ws
import review_formats as formats
from review_gallery import build_gallery


class FormatTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name).resolve();self.project=self.base/'project'
        (self.project/'.viewprinter/content-memory').mkdir(parents=True)
        self.env=patch.dict(os.environ,VIEWPRINTER_REVIEW_ROOT=str(self.base/'hub'),VIEWPRINTER_REVIEW_HUB='0')
        self.env.start();self.addCleanup(self.env.stop)
    def source(self,name,item,project=None,format_id='same'):
        p=(project or self.project)/name;p.mkdir(parents=True)
        (p/'image.png').write_bytes(b'picture '+name.encode())
        data={'title':name,'round':1,'reviewHub':{'kind':'social-content','formatId':format_id,'owner':name,'variant':name},'items':[
            {'id':item,'version':1,'title':item,'format':'Hook demo','kind':'image','src':'image.png','status':'needs-review'}]}
        ws.atomic(p/'review.json',data);build_gallery(p/'review.json',p/'review.html');return p
    def data(self,entry):return ws.read(ws.get(entry)['manifest'])
    def test_agents_contribute_to_one_format_and_old_link_selects_source(self):
        a=self.source('a','A');b=self.source('b','B')
        first=ws.register(a,name='project--first');second=ws.register(b,name='project--second')
        self.assertEqual(first,second);self.assertEqual(len(ws.scan()[0]['entries']),1)
        r=ws.get(first);self.assertEqual(ws.get('project--second')['id'],first)
        self.assertEqual(len(r['sources']),2);self.assertIn('project--second',r['aliasSources'])
        d=self.data(first);self.assertEqual({i['id'] for i in d['items']},{'A','B'})
        self.assertEqual({Path(i['src']).read_bytes() for i in d['items']},{b'picture a',b'picture b'})
        self.assertEqual({i['variant'] for i in d['items']},{'a','b'})
    def test_retry_does_not_duplicate_and_different_batch_race_is_safe(self):
        sources=[self.source(str(i),str(i)) for i in range(5)]
        workers=[subprocess.Popen([sys.executable,'-c','import review_workspace as w;w.register('+repr(str(p))+')'],cwd=Path(ws.__file__).parent,stdout=subprocess.PIPE,stderr=subprocess.PIPE) for p in sources]
        for p in workers:
            _,err=p.communicate(timeout=30);self.assertEqual(p.returncode,0,err)
        entries=ws.scan()[0]['entries'];self.assertEqual(len(entries),1);eid=entries[0]['id']
        ws.register(sources[0]);self.assertEqual(len(self.data(eid)['items']),5)
    def test_stale_source_and_changed_media_fail_without_replacing_current_review(self):
        a=self.source('a','A');eid=ws.register(a);record=ws.get(eid)
        data=ws.read(a/'review.json');data['items'][0]['title']='Updated';ws.atomic(a/'review.json',data)
        with self.assertRaisesRegex(ValueError,'source revision'):ws.register(a)
        self.assertEqual(ws.get(eid),record)
        ws.register(a,source_revision=1);self.assertEqual(self.data(eid)['items'][0]['title'],'Updated')
        data['items'][0]['title']='Stale';ws.atomic(a/'review.json',data)
        with self.assertRaises(ValueError):ws.register(a,source_revision=1)
        (a/'image.png').write_bytes(b'new media')
        with self.assertRaisesRegex(ValueError,'new version'):ws.register(a,source_revision=2)
        data['items'][0]['version']=2;ws.atomic(a/'review.json',data);ws.register(a,source_revision=2)
        self.assertEqual(self.data(eid)['items'][0]['version'],2)
    def test_drafts_are_not_accepted_implicitly(self):
        a=self.source('a','A');eid=ws.register(a)
        d=ws.read(a/'review.json');d['items'][0]['title']='Unsubmitted';ws.atomic(a/'review.json',d)
        b=self.source('b','B');ws.register(b)
        self.assertEqual(next(i['title'] for i in self.data(eid)['items'] if i['id']=='A'),'A')
    def test_conflicting_item_or_batch_id_does_not_replace_entry(self):
        a=self.source('a','A');eid=ws.register(a);before=ws.get(eid)
        b=self.source('b','A')
        with self.assertRaisesRegex(ValueError,'Item ID'):ws.register(b)
        self.assertEqual(ws.get(eid),before)
        d=ws.read(b/'review.json');d['items'][0].update(id='B',batch=before['sources'][0]['batchIds'][0]);d['batches']=[{'id':d['items'][0]['batch'],'label':'Colliding'}];ws.atomic(b/'review.json',d)
        with self.assertRaisesRegex(ValueError,'Batch ID'):ws.register(b)
        self.assertEqual(ws.get(eid),before)
    def test_archive_requires_explicit_restore_and_batch_restore_joins_parent(self):
        a=self.source('a','A');b=self.source('b','B');eid=ws.register(a);ws.register(b)
        batch=ws.get(eid)['sources'][0]['batchIds'][0]
        archived=ws.lifecycle(eid,'archive',batch=batch)
        self.assertEqual(ws.describe(ws.get(eid))['summary']['items'],1)
        ws.register(b);self.assertEqual(ws.describe(ws.get(eid))['summary']['items'],1)
        ws.lifecycle(archived['id'],'restore');self.assertEqual(ws.describe(ws.get(eid))['summary']['items'],2)
        ws.lifecycle(eid,'archive')
        with self.assertRaisesRegex(ValueError,'explicitly restore'):ws.register(a)
        ws.lifecycle(eid,'restore');self.assertEqual(ws.get(eid)['id'],eid)
    def test_missing_source_remains_visible(self):
        a=self.source('a','A');eid=ws.register(a);(a/'review.json').unlink()
        view=ws.describe(ws.get(eid));self.assertEqual(view['summary']['items'],1);self.assertTrue(view['sourceErrors'])
    def test_same_names_in_two_projects_do_not_merge(self):
        a=self.source('a','A');first=ws.register(a)
        other=self.base/'other/project';(other/'.viewprinter/content-memory').mkdir(parents=True)
        b=self.source('b','B',other);second=ws.register(b)
        self.assertNotEqual(first,second);self.assertNotEqual(ws.get(first)['projectKey'],ws.get(second)['projectKey'])
    def test_scheduling_receipts_refresh_and_new_content_reopens_review(self):
        a=self.source('a','A');d=ws.read(a/'review.json');d['delivery']={'snapshot':'delivery.json'}
        d['items'][0].update(captionStatus='approved',captions={'instagram':{'caption':'Hi'}},distribution={'targets':[{'organizationId':'o','accountId':'a','platform':'instagram'}]})
        ws.atomic(a/'review.json',d);ws.atomic(a/'delivery.json',{'placements':[]});eid=ws.register(a)
        row={'itemId':'A','version':1,'postId':'p','accountId':'a','organizationId':'o','platform':'instagram','caption':'Hi','status':'scheduled','checkedAt':'2026-10-06T12:00:00Z'}
        ws.atomic(a/'delivery.json',{'placements':[row]})
        view=ws.describe(ws.get(eid));self.assertEqual(view['readiness']['state'],'scheduled')
        b=self.source('b','B');ws.register(b);self.assertEqual(ws.describe(ws.get(eid))['readiness']['state'],'active')
    def test_guidance_optional_and_contained(self):
        a=self.source('a','A');eid=ws.register(a);self.assertEqual(ws.describe(ws.get(eid))['guidance'],[])
        cfg=self.project/'.viewprinter/content-memory/config.json';config=ws.read(cfg)
        guide=self.project/'guide.md';guide.write_text('# Guidance', encoding='utf-8')
        config['contentSkill']='guide.md';ws.atomic(cfg,config)
        self.assertEqual(ws.guidance(ws.get(eid))[0]['path'],str(guide))
        (self.base/'private.md').write_text('private', encoding='utf-8');config['contentSkill']='../private.md';ws.atomic(cfg,config)
        self.assertEqual(ws.guidance(ws.get(eid)),[])
    def test_historical_snapshot_does_not_restore_a_duplicate(self):
        a=self.source('a','A');eid=ws.register(a);r=ws.get(eid)
        old={**r,'id':'historical','lifecycle':'archived','recordType':'historical-review','parentId':eid}
        ws.atomic(ws.registry()/'historical.json',old)
        with self.assertRaisesRegex(ValueError,'current parent'):ws.lifecycle('historical','restore')
        self.assertEqual(len(ws.scan()[0]['entries']),1)
        self.assertIn('historical review',ws.describe(old)['label'])
    def test_reconcile_preserves_receipts_and_links_and_has_guarded_rollback(self):
        a=self.source('a','A',format_id='old-a');b=self.source('b','B',format_id='old-b')
        e1=ws.register(a);e2=ws.register(b);before=copy.deepcopy(ws.records())
        plan={'formats':[{'entries':[e1,e2],'entry':'project--same','formatId':'same','label':'Same'}]}
        dry=formats.reconcile(plan);self.assertTrue(dry['dryRun']);self.assertEqual(ws.records(),before)
        result=formats.reconcile(plan,True);self.assertEqual(len(ws.scan()[0]['entries']),1)
        self.assertEqual(ws.get(e1)['id'],'project--same');self.assertEqual(len(self.data(e2)['items']),2)
        sources=[s['id'] for s in ws.get(e1)['sources']]  # one batch per source, newest first
        self.assertEqual([x['id'] for x in self.data(e1)['batches']],sources[::-1])
        formats.rollback(result['receipt']);self.assertEqual(ws.records(),before)
        result=formats.reconcile(plan,True);ws.register(a)
        with self.assertRaisesRegex(ValueError,'changed after'):formats.rollback(result['receipt'])

    def test_influencer_is_separate_from_format_and_accepts_multiple_agents(self):
        a=self.source('a','A');format_entry=ws.register(a)
        b=self.source('b','B');d=ws.read(b/'review.json');d['reviewHub']={'kind':'influencer','influencerId':'same','label':'Creator'};ws.atomic(b/'review.json',d)
        creator=ws.register(b);self.assertNotEqual(creator,format_entry)
        self.assertEqual(ws.get(creator)['kind'],'influencer');self.assertNotIn('formatId',ws.get(creator))
        c=self.source('c','C');d=ws.read(c/'review.json');d['reviewHub']={'kind':'influencer','influencerId':'same'};ws.atomic(c/'review.json',d)
        self.assertEqual(ws.register(c),creator);self.assertEqual(len(self.data(creator)['items']),2)
        self.assertEqual(ws.describe(ws.get(creator))['readiness']['active'],2)
    def test_multiple_influencers_and_project_isolation(self):
        entries=[]
        for name in ['ada','bea']:
            p=self.source(name,name);d=ws.read(p/'review.json');d['reviewHub']={'kind':'influencer','influencerId':name};ws.atomic(p/'review.json',d);entries.append(ws.register(p))
        self.assertEqual(len(set(entries)),2);self.assertEqual(len(ws.scan()[0]['entries']),2)
    def test_manage_influencer_moves_snapshot_into_own_history(self):
        a=self.source('a','A');eid=ws.register(a);original=ws.get(eid)
        old={**copy.deepcopy(original),'id':'historical','lifecycle':'archived','recordType':'historical-review','parentId':eid,'historyDate':'2026-10-01'}
        old.update(ws.freeze(original));ws.atomic(ws.registry()/'historical.json',old)
        snapshot=Path(old['snapshotGallery']).read_bytes()
        ws.atomic(self.project/'creator.json',{'name':'Creator','description':'Known identity'})
        result=formats.manage_influencer(eid,'creator','creator.json')
        self.assertEqual(result['historyMoved'],1)
        scan=ws.scan()[0];self.assertEqual(scan['archived'],[]);self.assertEqual(len(scan['history']),1)
        self.assertEqual(scan['entries'][0]['history'][0]['id'],'historical')
        self.assertEqual(scan['entries'][0]['influencer']['name'],'Creator')
        self.assertEqual(Path(old['snapshotGallery']).read_bytes(),snapshot)
        self.assertEqual(ws.register(a),eid) # Legacy source keeps joining its managed identity.
        self.assertEqual(ws.get(eid)['kind'],'influencer')
        self.assertEqual(len(self.data(eid)['items']),1)
        ws.lifecycle(eid,'archive')
        self.assertEqual(ws.scan()[0]['archived'][0]['history'][0]['id'],'historical')
        ws.lifecycle(eid,'restore')
        self.assertEqual(ws.scan()[0]['entries'][0]['history'][0]['id'],'historical')
    def test_influencer_profile_cannot_read_outside_project(self):
        a=self.source('a','A');eid=ws.register(a);ws.atomic(self.base/'private.json',{'name':'Private'})
        with self.assertRaises(ValueError):formats.manage_influencer(eid,'creator','../private.json')
        self.assertEqual(ws.get(eid)['kind'],'social-content')

    def shown(self,eid):
        """The bytes the format's review shows for each item: preview, cover and inputs."""
        return {i['id']:[Path(m[k]).read_bytes() for m in (i,*i.get('inputs',[])) for k in ('src','poster') if m.get(k)] for i in self.data(eid)['items']}
    def pictures(self,eid):
        gallery=Path(ws.get(eid)['gallery']);page=gallery.read_text(encoding='utf-8')
        return {(gallery.parent/unquote(u)).resolve().read_bytes() for u in re.findall(r'<img src="([^"]+)"',page)}
    def test_replacing_a_source_file_keeps_the_accepted_preview(self):
        a=self.source('a','A');d=ws.read(a/'review.json')
        (a/'cover.png').write_bytes(b'cover');(a/'still.png').write_bytes(b'still')
        d['items'][0].update(poster='cover.png',inputs=[{'label':'Still','kind':'image','src':'still.png'}]);ws.atomic(a/'review.json',d)
        eid=ws.register(a);accepted=self.shown(eid)['A']
        self.assertEqual(accepted,[b'picture a',b'cover',b'still'])
        for name in ('image.png','cover.png','still.png'):(a/name).write_bytes(b'replaced')
        self.assertEqual(self.shown(eid)['A'],accepted)
        ws.register(self.source('b','B'))  # another contributor's registration rebuilds the format
        self.assertEqual(self.shown(eid)['A'],accepted)
        self.assertEqual(self.pictures(eid),{b'picture a',b'still',b'picture b'})
        with self.assertRaisesRegex(ValueError,'new version'):ws.register(a,source_revision=1)
        (a/'image.png').write_bytes(b'picture a')  # the preview is back; the cover is still replaced
        with self.assertRaisesRegex(ValueError,'Cover changed.*new version'):ws.register(a,source_revision=1)
        self.assertEqual(self.shown(eid)['A'],accepted)
        d['items'][0]['version']=2;ws.atomic(a/'review.json',d);ws.register(a,source_revision=1)
        self.assertEqual(self.shown(eid)['A'],[b'picture a',b'replaced',b'replaced'])
        store=self.project/'.viewprinter/content-memory/reviews/.media';item=self.data(eid)['items'][0]
        for path in (item['src'],item['poster'],item['inputs'][0]['src']):self.assertTrue(Path(path).is_relative_to(store),path)
        self.assertEqual((store/'.gitignore').read_text(encoding='utf-8'),'*\n')
    def legacy(self,eid):
        """Make a record look like one registered by code that did not keep accepted media."""
        r=ws.get(eid);r.pop('generation',None);r.pop('batchesSeen',None)
        for s in r['sources']:
            for key in ('frozenMedia','replacedMedia','coverHashes'):s.pop(key,None)
        ws.atomic(ws.registry()/(eid+'.json'),r)
    def test_upgrade_rebuilds_older_reviews_and_flags_media_replaced_before_it(self):
        a=self.source('a','A');d=ws.read(a/'review.json')
        d['items'][0].update(status='approved',stage='final',captionStatus='approved',captions={'instagram':{'caption':'Hi'}},
                             distribution={'targets':[{'organizationId':'o','accountId':'x','platform':'instagram'}]})
        ws.atomic(a/'review.json',d);eid=ws.register(a);ws.register(self.source('b','B'))
        counts=lambda:{k:v for k,v in ws.describe(ws.get(eid))['readiness']['counts'].items() if v}
        self.assertEqual(counts(),{'ready':1,'needs-review':1})
        self.legacy(eid);(a/'image.png').write_bytes(b'replaced')
        rebuilt,failed=formats.upgrade();self.assertEqual((rebuilt,failed),([eid],{}))
        items={i['id']:i for i in self.data(eid)['items']}
        self.assertTrue(items['A'].get('_mediaReplaced'));self.assertFalse(items['B'].get('_mediaReplaced'))
        self.assertIn('Changed after acceptance',Path(ws.get(eid)['gallery']).read_text(encoding='utf-8'))
        self.assertEqual(counts(),{'needs-review':2})
        (a/'image.png').write_bytes(b'again');self.assertEqual(self.shown(eid)['A'],[b'replaced'])
        self.assertEqual(formats.upgrade(),([],{}))
        self.legacy(eid);r=ws.get(eid);Path(r['sources'][1]['snapshot']).unlink();(self.project/'b/review.json').unlink()
        rebuilt,failed=formats.upgrade();self.assertEqual((rebuilt,list(failed)),([],[(eid,r['revision'])]))
        self.assertEqual(formats.upgrade(skip=failed),([],{}))
    def test_new_batches_lead_even_when_older_batches_are_dated(self):
        def batch(path,identity,item=None,**fields):
            """Declare a batch newest first; it holds the source's first item, or a new one."""
            d=ws.read(path/'review.json');d.setdefault('batches',[]).insert(0,{'id':identity,'label':identity,**fields})
            if item:d['items'].append(dict(d['items'][0],id=item,batch=identity))
            else:d['items'][0]['batch']=identity
            ws.atomic(path/'review.json',d)
        a=self.source('a','A');batch(a,'september',createdAt='2026-09-01T10:00:00Z');eid=ws.register(a)
        b=self.source('b','B');batch(b,'newer');ws.register(b)
        order=lambda:[x['id'] for x in self.data(eid)['batches']]
        self.assertEqual(order(),['newer','september'])
        batch(a,'latest','A2');ws.register(a,source_revision=1)  # the first contributor's new batch
        self.assertEqual(order(),['latest','newer','september'])
        batch(a,'east','A3',createdAt='2026-09-01T12:00:00+05:00');ws.register(a,source_revision=2)  # 07:00 UTC
        self.assertEqual(order(),['latest','newer','september','east'])
        gallery=Path(ws.get(eid)['gallery']).read_text(encoding='utf-8')
        self.assertIn('data-batch-view="latest" aria-pressed="true"',gallery)
        # Older records kept no arrival times: their batches date from each contributor's first
        # registration, and a declared time still wins.
        self.legacy(eid);formats.upgrade();self.assertEqual(order(),['newer','latest','september','east'])
        batch(b,'today','B2');ws.register(b,source_revision=1);self.assertEqual(order()[0],'today')

if __name__=='__main__':unittest.main()
