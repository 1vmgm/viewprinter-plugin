"""Typed local review registry, reversible lifecycle and manifest summaries."""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import html
import json
import os
from pathlib import Path, PurePath
import re
import shutil
import tempfile
from urllib.parse import quote, unquote, urlsplit
from review_delivery import summarize

SCHEMA_VERSION = 3
KINDS = {'social-content', 'influencer', 'account-group'}
CONTENT_KINDS = {'social-content','influencer'}
MEDIA = {'.png','.jpg','.jpeg','.gif','.webp','.avif','.svg','.mp4','.m4v','.mov','.webm','.mp3','.m4a','.aac','.wav','.ogg','.flac','.woff','.woff2','.ttf','.otf','.pdf','.vtt','.css','.js'}
LINK_RE = re.compile(r'''\b(src|href|poster)=(['"])(.*?)\2''', re.I)


def now(): return datetime.now(timezone.utc).isoformat()
def root(): return Path(os.environ.get('VIEWPRINTER_REVIEW_ROOT') or Path.home()/'ViewPrinter').expanduser()
def registry(): return root()/'.hub'/'entries'
def slug(value): return re.sub(r'[^a-z0-9._-]+','-',value.lower()).strip('-.') or 'review'
def read(path, default=None):
    try: return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError): return default
def file_url(path):
    """The hub URL for a local file: /files/ and its absolute path with forward slashes, so a
    Windows drive path (C:/...) travels the same way a POSIX one does."""
    path=path if isinstance(path,PurePath) else Path(path)
    return '/files/'+quote(path.as_posix().lstrip('/'))
def url_path(rest):
    """The local path a /files/ URL names, given the part after /files/, or None. Only a
    drive path on Windows: a network path (\\\\host\\share) would make Windows contact that host."""
    rest=unquote(rest)
    if os.name=='nt':
        return os.path.normpath(rest) if re.match(r'[A-Za-z]:[\\/]',rest) else None
    return None if rest.startswith(('/','\\')) else os.path.normpath('/'+rest)
def broad(folder):
    """A home folder, a folder above one, or a drive root: too broad to be a project."""
    folder=Path(folder)
    try:home=Path.home().resolve()
    except RuntimeError:return folder==folder.parent
    return folder==folder.parent or folder==home or folder in home.parents
def shortcut(link, folder):
    """A convenience link in ~/ViewPrinter/in-review. The registry is the record; where links
    are not allowed (Windows without Developer Mode) there is simply no shortcut."""
    try:link.parent.mkdir(parents=True,exist_ok=True);link.symlink_to(folder,target_is_directory=True)
    except OSError:pass
def drop_shortcut(link):
    """Remove a shortcut link. Windows removes a link to a folder with rmdir."""
    for remove in (os.unlink,os.rmdir):
        try:remove(link);return
        except FileNotFoundError:return
        except OSError:continue
def served_root(record):
    """The folder whose media the hub may serve for a review: its ViewPrinter project, or for
    work outside a project only the review's own folder. Older records stored the folder's parent
    here, which could be a home directory, so a stored root counts only if it is a project."""
    project=Path(record['projectRoot'])
    if broad(project) or not (project/'.viewprinter'/'content-memory').is_dir():return record['target']
    return str(project)

def atomic(path, value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    fd,temp=tempfile.mkstemp(prefix='.'+path.name+'.',dir=path.parent)
    try:
        with os.fdopen(fd,'w', encoding='utf-8') as f: json.dump(value,f,indent=2,ensure_ascii=False);f.write('\n');f.flush();os.fsync(f.fileno())
        os.replace(temp,path)
    finally:
        if os.path.exists(temp):os.unlink(temp)

@contextmanager
def lock():
    folder=root()/'.hub';folder.mkdir(parents=True,exist_ok=True)
    with (folder/'registry.lock').open('a+b') as f:
        if os.name=='nt':
            import msvcrt
            f.seek(0);f.write(b'0');f.flush();f.seek(0);msvcrt.locking(f.fileno(),msvcrt.LK_LOCK,1)
        else:
            import fcntl
            fcntl.flock(f,fcntl.LOCK_EX)
        try: yield
        finally:
            if os.name=='nt':f.seek(0);msvcrt.locking(f.fileno(),msvcrt.LK_UNLCK,1)
            else:fcntl.flock(f,fcntl.LOCK_UN)

def project_root(path):
    for p in (path,*path.parents):
        if broad(p):return None  # a home folder is never a project, even one holding memory
        if (p/'.viewprinter/content-memory').is_dir():return p
    return None

def manifest_path(target):
    folder=target if target.is_dir() else target.parent
    for name in ('group.json','review.json','Review.json'):
        p=folder/name
        if p.is_file():return p.resolve()
    return None

def gallery_path(target):
    if target.is_file() and target.suffix.lower() in {'.html','.htm'}:return target
    if not target.is_dir():return None
    pages=[p for p in target.iterdir() if p.is_file() and p.suffix.lower() in {'.html','.htm'}]
    return next((p for p in pages if p.name.lower()=='review.html'),max(pages,key=lambda p:p.stat().st_mtime,default=None))

def records():
    return [d for p in sorted(registry().glob('*.json')) if isinstance(d:=read(p),dict)]

def get(entry):
    all_records=records()
    r=next((r for r in all_records if r['id']==entry),None) or next((r for r in all_records if entry in r.get('aliases',[])),None)
    if r:
        return get(r['parentId']) if r.get('lifecycle')=='merged' else r
    raise ValueError('Unknown review entry: '+entry)

def infer_kind(data):
    if not isinstance(data,dict):return 'unclassified'
    scope=data.get('reviewHub',{}).get('kind') if isinstance(data.get('reviewHub'),dict) else None
    if data.get('reviewScope') in {'external-product-assets','product-listing-assets'} or scope=='external':return 'excluded'
    if (data.get('reviewHub') or {}).get('excluded'):return 'excluded'
    if scope in KINDS:return scope
    if data.get('accounts') and all(a.get('accountId') for a in data['accounts']):return 'account-group'
    formats={str(i.get('format','')).lower() for i in data.get('items',[])}
    if any('app store' in f or 'app-store' in f for f in formats):return 'excluded'
    if data.get('items') and all(i.get('id') and i.get('version') is not None for i in data['items']):return 'social-content'
    return 'unclassified'

def register(target, name=None, kind=None, manifest=None, format_id=None, owner=None, groups=None, require_project=False, source_revision=None, revision=None):
    target=Path(target).expanduser().resolve()
    if not target.exists():raise ValueError('Review target does not exist')
    gallery=gallery_path(target)
    if not gallery:raise ValueError('A review HTML is required')
    project=project_root(target)
    if require_project and project is None:return None
    mf=Path(manifest).expanduser().resolve() if manifest else manifest_path(target)
    data=read(mf) if mf else None
    declared=(data or {}).get('reviewHub',{})
    if not isinstance(declared,dict):declared={}
    existing=next((r for r in records() if r.get('gallery')==str(gallery) and not r.get('batchId') and r.get('lifecycle')!='archived'),None)
    kind=kind or declared.get('kind') or (existing or {}).get('kind')
    if infer_kind(data)=='excluded':raise ValueError('Product-listing assets stay outside the social review workspace')
    if kind not in KINDS:raise ValueError('Registration requires --kind social-content or account-group; use standalone HTML for other work')
    if not mf or not mf.is_file():raise ValueError('A canonical manifest is required')
    if kind=='account-group' and not (data or {}).get('accounts'):raise ValueError('Account group manifest needs accounts')
    if kind in CONTENT_KINDS and 'items' not in (data or {}):raise ValueError('Social content manifest needs items')
    identity=(declared.get('influencerId') if kind=='influencer' else format_id or declared.get('formatId')) or declared.get('groupId') or (data or {}).get('id') or (existing or {}).get('formatId')
    if not identity:raise ValueError('Registration requires a stable --format-id / reviewHub.formatId or group ID')
    prior=next((r for r in records() if r.get('kind')=='influencer' and any(s['manifest']==str(mf) for s in r.get('sources',[]))),None)
    if prior and identity in prior.get('formatAliases',[]):kind='influencer';identity=prior['influencerId']
    if name and slug(name)!=name:raise ValueError('Entry ID must be a safe lowercase slug')
    if kind in CONTENT_KINDS:
        from review_formats import register as register_format
        if project is None: raise ValueError('Social content needs project content memory')
        return register_format(project,gallery,mf,identity,name,owner,groups,source_revision,revision,kind)
    with lock():
        all_records=records();existing=next((r for r in all_records if r.get('gallery')==str(gallery) and not r.get('batchId') and r.get('lifecycle')!='archived'),None)
        entry=(existing or {}).get('id') or name or declared.get('entry') or slug((project or target.parent).name+'--'+gallery.parent.name)
        if slug(entry)!=entry:raise ValueError('Invalid entry ID')
        if any(r['id']==entry and r is not existing for r in all_records):raise ValueError('Entry ID belongs to another review')
        r=existing or {'schemaVersion':SCHEMA_VERSION,'id':entry,'createdAt':now(),'revision':0,'lifecycle':'active','aliases':[]}
        r.update(kind=kind,manifest=str(mf),gallery=str(gallery),target=str(gallery.parent),
            projectRoot=str(project) if project else str(gallery.parent),projectId=declared.get('projectId') or (project or target.parent).name,
            formatId=identity,owner=owner or r.get('owner') or declared.get('owner') or 'unassigned',
            accountGroups=groups if groups is not None else declared.get('accountGroups',r.get('accountGroups',[])),updatedAt=now(),revision=r['revision']+1)
        atomic(registry()/(entry+'.json'),r)
        # Keep Finder shortcuts and old agent paths stable.
        link=root()/'in-review'/entry
        if r['lifecycle']=='active' and not r.get('batchId') and not os.path.lexists(link):
            shortcut(link,gallery.parent)
    return entry


def migrate(apply=False, exclusions=()):
    suggestions=[];backup=None;known={r['id']:r for r in records()}
    paths=list((root()/'in-review').glob('*'))+list((root()/'posted').glob('*/*'))
    for p in paths:
        if not p.is_symlink():continue
        target=p.resolve();gallery=gallery_path(target);mf=manifest_path(target);data=read(mf) if mf else None
        legacy_posted=p.parent.parent.name=='posted'
        eid=slug(p.name if not legacy_posted else 'history-'+p.parent.name+'-'+p.name)
        if eid in known:continue
        kind='excluded' if p.name in exclusions else infer_kind(data)
        proj=project_root(target)
        r={'schemaVersion':SCHEMA_VERSION,'id':eid,'kind':kind,'revision':1,'createdAt':now(),'updatedAt':now(),
           'gallery':str(gallery) if gallery else '', 'target':str(target),'manifest':str(mf) if mf else None,
           'projectRoot':str(proj or target.parent),'projectId':(proj or target.parent).name,
           'formatId':(data or {}).get('id') or p.name,'owner':'legacy-migration','accountGroups':[],
           'lifecycle':'archived' if legacy_posted else 'excluded' if kind=='excluded' else 'active',
           'aliases':['posted/'+p.parent.name+'/'+p.name] if legacy_posted else [],'migrationSource':str(p)}
        if legacy_posted:
            r['recordType']='historical-review'
            r['historyDate']=p.parent.name
            parent=next((x for x in [*known.values(),*suggestions] if x.get('lifecycle')=='active' and x.get('gallery')==str(gallery)),None)
            r['parentId']=parent['id'] if parent else None
            r['archive']={'at':now(),'reason':'Legacy Posted snapshot; current format is not retired','actor':'migration','legacy':True}
        suggestions.append(r)
    if apply:
        with lock():
            backup=root()/'.hub'/'migrations'/datetime.now().strftime('%Y%m%dT%H%M%S%f')
            atomic(backup/'before.json',{'records':records(),'shortcuts':[str(p) for p in paths]})
            for r in suggestions:
                if not (registry()/(r['id']+'.json')).exists():
                    if r['lifecycle']=='archived' and r['gallery'] and r['manifest']:
                        r.update(freeze(r))
                    atomic(registry()/(r['id']+'.json'),r)
    return {'dryRun':not apply,'entries':suggestions,'existing':len(known),'backup':str(backup/'before.json') if backup else None}


def rollback(receipt):
    path=Path(receipt).resolve()
    if not path.is_relative_to((root()/'.hub/migrations').resolve()):raise ValueError('Not a migration receipt')
    before=read(path)
    if not isinstance(before,dict) or 'records' not in before:raise ValueError('Invalid migration receipt')
    with lock():
        old={r['id']:r for r in before['records']};changes=[]
        for r in records():
            if r['id'] not in old:
                if not r.get('migrationSource') or r['revision']!=1:
                    raise ValueError('Workspace changed after migration; cannot roll back over newer work')
                changes.append(r['id'])
        for entry in changes:(registry()/(entry+'.json')).unlink()
    return {'removedRecords':changes,'snapshotsRetained':True}


def clone(source,dest):
    dest.parent.mkdir(parents=True,exist_ok=True)
    if __import__('sys').platform=='darwin':
        import ctypes
        libc=ctypes.CDLL('/usr/lib/libSystem.B.dylib',use_errno=True)
        if libc.clonefile(os.fsencode(source),os.fsencode(dest),0)==0:return
    shutil.copy2(source,dest)


def freeze(record, batch=None):
    """Preserve review bytes plus referenced local media; never hard-link mutable files."""
    mf=Path(record['manifest']);data=read(mf)
    if data is None:raise ValueError('Cannot archive missing manifest')
    if batch:
        data['items']=[i for i in data.get('items',[]) if i.get('batch')==batch]
        if not data['items']:raise ValueError('Batch has no items')
        data['batches']=[{**b,'lifecycle':'active'} for b in data.get('batches',[]) if b['id']==batch]
    folder=root()/'.hub'/'snapshots'/record['id']/datetime.now().strftime('%Y%m%dT%H%M%S%f')
    folder.mkdir(parents=True)
    source=Path(record['gallery'])
    if batch:
        # Render next to the original manifest to preserve its relative inputs.
        from review_gallery import build_gallery
        tmp=mf.parent/('.archive-'+slug(batch)+'.json');out=mf.parent/('.archive-'+slug(batch)+'.html')
        atomic(tmp,data)
        try:build_gallery(tmp,out);text=out.read_text(encoding='utf-8')
        finally:tmp.unlink(missing_ok=True);out.unlink(missing_ok=True)
    else:text=source.read_text(encoding='utf-8')
    sources={};project=Path(record['projectRoot']).resolve()
    def replace(match):
        key,q,value=match.groups();raw=html.unescape(value);parts=urlsplit(raw)
        if parts.scheme or not parts.path or raw.startswith('#'):return match.group(0)
        p=Path(url_path(parts.path[len('/files/'):])) if parts.path.startswith('/files/') else (source.parent/unquote(parts.path)).resolve()
        if not p.is_file() or not p.is_relative_to(project) or p.suffix.lower() not in MEDIA:return match.group(0)
        if str(p) not in sources:
            digest=hashlib.sha256(p.read_bytes()).hexdigest();dest=folder/'media'/(digest+p.suffix.lower())
            if not dest.exists():clone(p,dest)
            sources[str(p)]={'path':str(dest),'sha256':digest}
        url=file_url(sources[str(p)]['path'])
        return key+'='+q+html.escape(url,quote=True)+q
    text=LINK_RE.sub(replace,text)
    (folder/'review.html').write_text(text, encoding='utf-8')
    atomic(folder/'manifest.json',data);atomic(folder/'assets.json',sources)
    return {'snapshotGallery':str(folder/'review.html'),'snapshotManifest':str(folder/'manifest.json'),
            'snapshotAssets':str(folder/'assets.json'),'snapshotBase':str(mf.parent)}


def update_gallery(manifest, data, output):
    from review_gallery import build_gallery, write_atomically
    before=manifest.read_bytes()
    try:
        atomic(manifest,data);build_gallery(manifest,output)
    except Exception:
        write_atomically(manifest,before)
        raise


def lifecycle(entry, action, revision=None, reason='', actor='local-user', batch=None):
    if action not in {'archive','restore'}:raise ValueError('Unknown lifecycle action')
    with lock():
        r=get(entry)
        if revision is not None and int(revision)!=r['revision']:raise ValueError('Review changed; refresh before applying this action')
        if action=='restore' and r.get('recordType')=='historical-review':raise ValueError('Historical reviews cannot create a second format; open the current parent format')
        if batch:
            if action!='archive':raise ValueError('Restore the archived batch entry by its ID')
            original=r;mf=Path(r['manifest']);d=read(mf);b=next((b for b in d.get('batches',[]) if b['id']==batch),None)
            if not b or b.get('lifecycle')=='archived':raise ValueError('Batch not active')
            r={**r,'id':r['id']+'--batch-'+slug(batch),'batchId':batch,'recordType':'batch','parentId':original['id'],'revision':0}
            prior=read(registry()/(r['id']+'.json'))
            if prior and prior['lifecycle']=='archived':raise ValueError('Batch archive already exists; restore or inspect it')
            if prior:r['revision']=prior['revision'];r['history']=prior.get('history',[])
            frozen=freeze(r,batch);r.update(frozen);b['lifecycle']='archived';update_gallery(mf,d,Path(original['gallery']))
            original.setdefault('batchStates',{})[batch]='archived'
            original['revision']+=1;original['updatedAt']=now();atomic(registry()/(original['id']+'.json'),original)
        if action=='archive':
            if r.get('lifecycle')=='archived':return r
            if not batch:r.update(freeze(r))
            r.update(lifecycle='archived',archive={'at':now(),'reason':reason,'actor':actor})
            link=root()/'in-review'/r['id']
            if link.is_symlink():drop_shortcut(link)
        else:
            if r.get('lifecycle')!='archived':raise ValueError('Only archived work can be restored')
            if r.get('batchId'):
                parent=get(r['parentId']);mf=Path(parent['manifest']);d=read(mf)
                b=next((b for b in d.get('batches',[]) if b['id']==r['batchId']),None)
                if not b:raise ValueError('Batch was removed from its parent manifest')
                b['lifecycle']='active';update_gallery(mf,d,Path(parent['gallery']))
                parent.setdefault('batchStates',{})[r['batchId']]='active'
                r['lifecycle']='restored-history';parent['revision']+=1;parent['updatedAt']=now();atomic(registry()/(parent['id']+'.json'),parent)
            else:
                r['lifecycle']='active';link=root()/'in-review'/r['id']
                if not os.path.lexists(link):shortcut(link,Path(r['gallery']).parent)
        r['revision']+=1;r['updatedAt']=now()
        r.setdefault('history',[]).append({'action':action,'at':now(),'reason':reason,'actor':actor, 'snapshotGallery':r.get('snapshotGallery')})
        atomic(registry()/(r['id']+'.json'),r)
    return r


_cache={}
def cached_read(path):
    if not path:return None
    p=Path(path)
    try:key=(str(p),p.stat().st_mtime_ns,p.stat().st_size)
    except OSError:return None
    if key not in _cache:
        _cache.clear() if len(_cache)>256 else None
        _cache[key]=read(p)
    return _cache[key]

def describe(record):
    record=dict(record)
    source_errors=[]
    if record.get('sources') and record['lifecycle']=='active':
        from review_formats import refresh_receipts
        try: record=refresh_receipts(record)
        except (OSError,ValueError) as exc:source_errors.append(str(exc))
        for source in record['sources']:
            if not Path(source['manifest']).is_file():source_errors.append('Source missing: '+source['manifest'])
    archived=record['lifecycle'] in {'archived','history'}
    mf=record.get('snapshotManifest') if archived and record.get('snapshotManifest') else record.get('manifest')
    data=cached_read(mf) or {};snapshot_base=record.get('snapshotBase') if archived else None
    base=Path(snapshot_base or mf or record['target'])
    if not snapshot_base:base=base.parent if mf else base
    gallery=record.get('snapshotGallery') if archived and record.get('snapshotGallery') else record.get('gallery')
    project=record['projectId'];title=data.get('title') or record.get('influencerId') or record.get('formatId')
    label=re.sub(r'^\s*THIS SESSION\s*[—–-]\s*','',title,flags=re.I)
    label=re.sub(r'^'+re.escape(project.replace('-',' '))+r'\s*[:·—-]\s*','',label,flags=re.I)
    label=record.get('label') or (data.get('reviewHub') or {}).get('label') or label
    if record.get('recordType')=='historical-review' and not label.endswith(' — historical review'):label+=' — historical review'
    dates=[]
    for path in [mf,gallery]:
        if path and Path(path).exists():dates.append(Path(path).stat().st_mtime)
    entry={**record,'name':record['id'],'project':project.replace('-',' ').title(),'title':title,'label':label,
        'exists':bool(gallery and Path(gallery).is_file()),'url':file_url(gallery) if gallery else None,
        'updated':max(dates,default=0),'added':0,'summary':None,'thumbnail':None,'platforms':[],'search':label.lower(),
        'batches':[],'downloads':[],'sourceErrors':source_errors,'guidance':guidance(record),'influencer':influencer_profile(record)}
    entry['sources']=[{k:s.get(k) for k in ('id','manifest','owner','revision','batchIds')} for s in record.get('sources',[])]
    if record['kind'] in CONTENT_KINDS:
        config=data.get('delivery') or {};snap=cached_read(base/config.get('snapshot','delivery.json')) or {'placements':[]}
        if config.get('snapshot') and (base/config['snapshot']).exists():entry['updated']=max(entry['updated'],(base/config['snapshot']).stat().st_mtime)
        progress=summarize(data,snap.get('placements',[]));entry['progress']=progress
        from review_readiness import summarize as review_summary
        entry['readiness']=review_summary(data,snap.get('placements',[]))
        from review_gallery import REVIEW_STATUSES,PENDING_STATUSES
        statuses=progress['creative'];entry['summary']={'items':progress['items'],'review':sum(n for s,n in statuses.items() if s in REVIEW_STATUSES),'progress':sum(n for s,n in statuses.items() if s in PENDING_STATUSES),'approved':statuses.get('approved',0)}
        entry['batches']=[{'id':b['id'],'label':b['label'],'lifecycle':b.get('lifecycle','active'),'count':sum(i.get('batch')==b['id'] for i in data.get('items',[]))} for b in data.get('batches',[])]
        items=data.get('items',[]);archived_ids={b['id'] for b in data.get('batches',[]) if b.get('lifecycle')=='archived'}
        active=[i for i in items if i.get('batch') not in archived_ids]
        if active:
            focus=entry['readiness']['nextItem']
            first=next((i for i in active if i['id']==focus.get('id')),active[0]);pic=first.get('poster') or (first.get('src') if first.get('kind')=='image' else None)
            if pic:
                path=str((base/pic).resolve());assets=cached_read(record.get('snapshotAssets')) or {}
                if archived and path in assets:path=assets[path]['path']
                entry['thumbnail']=file_url(path)
        accounts=[t for i in active for t in (i.get('distribution') or {}).get('targets',[])]
        entry['platforms']=sorted({t.get('platform') for t in accounts if t.get('platform')})
        entry['search']=' '.join([label,*[str(i.get(k,'')) for i in active for k in ('id','title','format')],*[b['label'] for b in entry['batches']],*[str(t.get('accountName') or t.get('accountId')) for t in accounts]]).lower()
    elif record['kind']=='account-group':
        import copy
        data=copy.deepcopy(data)
        for account in data.get('accounts',[]):
            if account.get('identityRef'):
                source=(base/account['identityRef']).resolve()
                shared=cached_read(source) if source.is_relative_to(Path(record['projectRoot']).resolve()) else None
                identity=(shared or {}).get('identity',{})
                if all(identity.get(k)==account.get(k) for k in ('accountId','organizationId')):
                    account.update({k:identity[k] for k in ('platform','handle','url') if k in identity})
        entry['accounts']=[{'ref':a.get('ref'),'id':a['accountId'],'organizationId':a.get('organizationId'),'platform':a['platform'],'handle':a.get('handle'),'url':a.get('url'),'sharedWith':a.get('sharedWith',[])} for a in data.get('accounts',[])]
        entry['platforms']=sorted({a['platform'] for a in entry['accounts']})
        entry['status']=data.get('status','Profile review')
        asset=next((a for a in data.get('assets',[]) if a.get('kind')=='avatar'),None)
        if asset:entry['thumbnail']=file_url((base/asset['src']).resolve())
        entry['search']=' '.join([label,*[str(a.get('handle')) for a in entry['accounts']]]).lower()
    for dl in data.get('downloads',[]):
        p=(base/dl['path']).resolve()
        if p.is_relative_to(base.resolve()) and p.is_file() and p.suffix.lower() in {'.json','.csv','.zip','.md','.pdf'}:
            entry['downloads'].append({'id':slug(dl['id']),'title':dl['title'],'path':str(p)})
    for dl in record.get('publicDownloads',[]):
        p=Path(dl['path']).resolve();allowed=Path(dl['base']).resolve()
        if p.is_file() and p.is_relative_to(allowed) and p.is_relative_to(Path(record['projectRoot']).resolve()):entry['downloads'].append(dl)
    return entry


def influencer_profile(record):
    if record.get('kind')!='influencer' or not record.get('influencerRef'):return None
    project=Path(record['projectRoot']).resolve();p=(project/record['influencerRef']).resolve()
    if not p.is_relative_to(project):return None
    profile=cached_read(p) or {}
    result={k:profile[k] for k in ('name','description','voice','identityType','audience') if profile.get(k)}
    if profile.get('avatar'):
        avatar=(project/profile['avatar']).resolve()
        if avatar.is_relative_to(project) and avatar.is_file() and avatar.suffix.lower() in {'.png','.jpg','.jpeg','.webp'}:result['avatar']=file_url(avatar)
    return result


def guidance(record):
    project=Path(record['projectRoot']).resolve()
    config=cached_read(project/'.viewprinter/content-memory/config.json') or {}
    refs=[('project','Project content guidance',config.get('contentSkill')),('format','Influencer guide' if record.get('kind')=='influencer' else 'Format recipe',record.get('recipeRef'))]
    result=[]
    for identity,label,raw in refs:
        if not raw:continue
        path=(project/raw).resolve()
        if path.is_relative_to(project) and path.is_file() and path.suffix.lower()=='.md':result.append({'id':identity,'label':label,'path':str(path)})
    return result


def scan():
    current=[];archived=[];history=[];own=set();projects=set()
    all_records=records()
    for r in all_records:
        for archived_path in [r.get('snapshotGallery'),*[h.get('snapshotGallery') for h in r.get('history',[])]]:
            if archived_path:own.add(str(Path(archived_path).parent))
        if r['lifecycle'] not in {'active','archived','history'} or r['kind']=='excluded':continue
        e=describe(r)
        if r['lifecycle']=='active':e['aliases']=[*e.get('aliases',[]),*[h['id'] for h in all_records if h.get('parentId')==r['id'] and h['lifecycle']=='restored-history']]
        (history if r['lifecycle']=='history' else archived if r['lifecycle']=='archived' else current).append(e)
        own.add(e['target']);projects.add(served_root(r))
        for source in r.get('sources',[]):own.add(str(Path(source['gallery']).parent))
        if r.get('snapshotGallery'):own.add(str(Path(r['snapshotGallery']).parent))
    for e in [*current,*archived]:e['history']=[{'id':h['id'],'label':h['label'],'date':h.get('historyDate')} for h in history if h.get('parentId')==e['id']]
    current.sort(key=lambda e:(e['kind'] not in CONTENT_KINDS,-e['updated'],e['id']))
    archived.sort(key=lambda e:e.get('archive',{}).get('at',''),reverse=True)
    return {'schemaVersion':SCHEMA_VERSION,'root':str(root()),'entries':current,'archived':archived,'history':history,'posted':archived},own,projects
