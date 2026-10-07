"""Stable format registration and immutable, revisioned contribution snapshots.

Call mutations under the workspace registry lock. Source manifests remain owned by
contributors; derived reviews are replaced as a generation, then published through
one atomic registry record. No remote services are involved.
"""
import copy
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import uuid

import review_workspace as ws


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def project_identity(project):
    config_path = project / '.viewprinter/content-memory/config.json'
    config = ws.read(config_path, {})
    if not config.get('reviewProjectId'):
        config['reviewProjectId'] = str(uuid.uuid4())
        ws.atomic(config_path, config)
    return config['reviewProjectId']


def data_for(source):
    data = ws.read(source.get('snapshot') or source['manifest'])
    if not isinstance(data, dict):
        raise ValueError('Missing accepted contribution: ' + source['manifest'])
    return data


def asset_hashes(data, base):
    result = {}
    for item in data.get('items', []):
        if item.get('src'):
            p = (base / item['src']).resolve()
            if not p.is_file():
                raise ValueError('Missing preview: ' + str(p))
            with p.open('rb') as f:
                h = hashlib.sha256()
                for chunk in iter(lambda: f.read(1024 * 1024), b''): h.update(chunk)
            result[item['id'] + '\x00' + str(item['version'])] = h.hexdigest()
    return result


def contribution(manifest, gallery, owner=None, previous=None, expected=None):
    manifest, gallery = Path(manifest).resolve(), Path(gallery).resolve()
    data = ws.read(manifest)
    if not isinstance(data, dict) or not isinstance(data.get('items'), list):
        raise ValueError('Contribution manifest needs items')
    metadata = data.get('reviewHub', {})
    comparable = copy.deepcopy(data)
    comparable.get('reviewHub', {}).pop('sourceRevision', None)
    signature = digest(comparable)
    hashes = asset_hashes(data, manifest.parent)
    if previous:
        changed = signature != previous.get('digest') or hashes != previous.get('mediaHashes')
        if changed:
            if expected != previous['revision'] and metadata.get('sourceRevision') != previous['revision'] + 1:
                raise ValueError('Contribution changed; refresh its source revision before updating ' + str(manifest))
            for key, sha in hashes.items():
                old = previous.get('mediaHashes', {}).get(key)
                if old and old != sha:
                    raise ValueError('Media changed for an existing item/version; create a new version: ' + key.replace('\x00', ' / v'))
        revision = previous['revision'] + int(changed)
    else:
        if expected not in (None, 0): raise ValueError('New contribution expects source revision 0')
        revision = 1
    source_id = (previous or {}).get('id') or 'source-' + hashlib.sha256(str(manifest).encode()).hexdigest()[:12]
    result = {**(previous or {}), 'id': source_id, 'manifest': str(manifest), 'gallery': str(gallery),
              'owner': owner or metadata.get('owner') or (previous or {}).get('owner') or 'unassigned',
              'revision': revision, 'digest': signature, 'mediaHashes': hashes,
              'addedAt': (previous or {}).get('addedAt') or ws.now()}
    result['_data'] = data
    return result


def rebase_media(item, base):
    result = copy.deepcopy(item)
    for media in (result, result.get('previous', {}), *result.get('inputs', [])):
        for key in ('src', 'poster'):
            # Forward slashes: the gallery reads manifest paths the same way on every system.
            if media.get(key): media[key] = (base / media[key]).resolve().as_posix()
    return result


def collect(record, folder):
    """Build from accepted source snapshots, never from another writer's draft."""
    sources = record['sources']
    first = sources[0].get('_data') or data_for(sources[0])
    manifest = copy.deepcopy(first)
    manifest.update(title=record.get('label') or record.get('influencerId') or record['formatId'], round=record['revision'],
                    focus=record.get('brief') or ('Review the latest batch, or browse this influencer’s content and history.' if record.get('kind')=='influencer' else 'Review the latest batch, or browse all content in this format.'),
                    items=[], batches=[], downloads=[], balances=[])
    manifest['reviewHub'] = {'kind': record.get('kind','social-content'), ('influencerId' if record.get('kind')=='influencer' else 'formatId'): record.get('influencerId') or record.get('formatId'),
                            'projectId': record['projectId'], 'entry': record['id'], 'label': manifest['title']}
    manifest['delivery'] = {'snapshot': 'delivery.json', 'timezone': (first.get('delivery') or {}).get('timezone', 'UTC')}
    items, batches, rows, public_downloads = {}, set(), [], []
    row_keys = set()
    receipt_signatures = {}
    for source in sources:
        data = source.get('_data') or data_for(source)
        base = Path(source['manifest']).parent
        snapshot = folder / (source['id'] + '.json')
        ws.atomic(snapshot, data)
        source['snapshot'] = str(snapshot)
        source.pop('_data', None)
        declared = data.get('reviewHub', {})
        source_batches = copy.deepcopy(data.get('batches') or [{'id': source['id'], 'label': declared.get('batchLabel') or declared.get('label') or data.get('title') or source['id']}])
        source['batchIds'] = [b['id'] for b in source_batches]
        for batch in source_batches:
            if batch['id'] in batches: raise ValueError('Batch ID belongs to another contribution: ' + batch['id'])
            batches.add(batch['id'])
            batch['sourceId'] = source['id']
            if batch['id'] in record.get('batchStates', {}): batch['lifecycle'] = record['batchStates'][batch['id']]
        # Registered contributions newest first; each source retains its own batch order.
        manifest['batches'] = source_batches + manifest['batches']
        for raw in data.get('items', []):
            item = rebase_media(raw, base)
            key = item['id']
            if key in items and items[key] != source['id']:
                raise ValueError('Item ID belongs to another contribution: ' + key)
            items[key] = source['id']
            item.setdefault('batch', source_batches[0]['id'])
            item['sourceId'] = source['id']
            item['contributor'] = source['owner']
            item['sourceLabel'] = source.get('variant') or declared.get('label') or data.get('title') or source['owner']
            item['variant'] = raw.get('variant') or source.get('variant') or declared.get('variant') or ''
            manifest['items'].append(item)
        delivery = data.get('delivery') or {}
        if delivery.get('snapshot'):
            receipt_path = (base / delivery['snapshot']).resolve()
            receipt = ws.read(receipt_path)
            if not isinstance(receipt, dict) or not isinstance(receipt.get('placements'), list):
                raise ValueError('Missing scheduling receipt source: ' + str(receipt_path))
            receipt_signatures[str(receipt_path)] = digest(receipt)
            for row in receipt['placements']:
                if row.get('itemId') not in {i['id'] for i in data.get('items', [])}: continue
                signature = digest(row)
                if signature not in row_keys: rows.append(row); row_keys.add(signature)
        for download in data.get('downloads', []):
            p = (base / download.get('path', '')).resolve()
            if p.is_file() and p.is_relative_to(base) and p.suffix.lower() in {'.json','.csv','.zip','.md','.pdf'}:
                public_downloads.append({**download, 'id': (source['id'] + '-' if len(sources)>1 else '') + ws.slug(download['id']), 'path': str(p), 'base': str(base)})
    manifest['batches'].sort(key=lambda b: b.get('createdAt', ''), reverse=True)
    record['publicDownloads'] = public_downloads
    record['receiptSignatures'] = receipt_signatures
    ws.atomic(folder / 'delivery.json', {'placements': rows})
    ws.atomic(folder / 'review.json', manifest)
    return manifest


def publish(record):
    """Prepare a complete generation before the caller swaps the registry pointer."""
    from review_gallery import build_gallery
    folder = Path(record['projectRoot']) / '.viewprinter/content-memory/reviews' / (('influencers/' + record['influencerId']) if record.get('kind')=='influencer' else record['formatId']) / ('r' + str(record['revision']) + '-' + uuid.uuid4().hex[:10])
    folder.mkdir(parents=True)
    candidate = copy.deepcopy(record)
    try:
        collect(candidate, folder)
        build_gallery(folder / 'review.json', folder / 'review.html')
    except Exception:
        shutil.rmtree(folder)
        raise
    candidate.update(manifest=str(folder / 'review.json'), gallery=str(folder / 'review.html'), target=str(folder), updatedAt=ws.now())
    return candidate


def refresh_receipts(record):
    if record.get('lifecycle') != 'active' or not record.get('sources'): return record
    changed = any(digest(ws.read(p)) != sha for p, sha in record.get('receiptSignatures', {}).items())
    if not changed: return record
    with ws.lock():
        fresh = ws.get(record['id'])
        if fresh['revision'] != record['revision']: return fresh
        candidate = copy.deepcopy(fresh); candidate['revision'] += 1
        candidate = publish(candidate)
        ws.atomic(ws.registry() / (candidate['id'] + '.json'), candidate)
        shortcut(candidate)
        return candidate


def shortcut(record):
    link = ws.root() / 'in-review' / record['id']
    if link.exists() and not link.is_symlink(): return
    link.parent.mkdir(parents=True, exist_ok=True)
    temp = link.parent / ('.' + link.name + '-' + uuid.uuid4().hex)
    # The registry is the record; the shortcut is a convenience. Windows refuses links
    # without Developer Mode, and won't replace a link to a folder in place.
    try:
        temp.symlink_to(Path(record['gallery']).parent, target_is_directory=True)
        try:
            os.replace(temp, link)
        except PermissionError:
            ws.drop_shortcut(link)
            os.replace(temp, link)
    except OSError:
        ws.drop_shortcut(temp)


def register(project, gallery, manifest, identity, name=None, owner=None, groups=None, source_revision=None, revision=None, kind="social-content"):
    project, gallery, manifest = Path(project), Path(gallery), Path(manifest)
    if ws.slug(identity) != identity: raise ValueError('Format ID must be a stable lowercase slug')
    with ws.lock():
        project_key = project_identity(project)
        all_records = ws.records()
        data = ws.read(manifest, {}); declared = data.get('reviewHub', {})
        if not manifest.is_relative_to(project):raise ValueError('Contribution must belong to this project')
        if any(r.get('projectKey')==project_key and Path(r['projectRoot']).resolve()!=project and r.get('lifecycle')=='active' for r in all_records):raise ValueError('Project identity is used by another folder; explicitly reconcile the moved or cloned project')
        candidates = [r for r in all_records if r.get('kind') == kind and not r.get('batchId') and r.get('recordType') != 'historical-review' and r.get('lifecycle') in {'active','archived'}
                      and (r.get('projectKey') == project_key or Path(r['projectRoot']).resolve() == project)]
        path_match = next((r for r in candidates if str(manifest) == r.get('manifest') or any(s['manifest'] == str(manifest) for s in r.get('sources', []))), None)
        if path_match and identity in path_match.get('formatAliases', []): identity = path_match.get('influencerId') or path_match['formatId']
        if path_match and (path_match.get('influencerId') or path_match.get('formatId')) != identity:
            raise ValueError('Existing source has another format ID; use explicit reconcile migration')
        matches = [r for r in candidates if (r.get('influencerId') or r.get('formatId')) == identity]
        if len(matches) > 1: raise ValueError('Duplicate legacy format registrations; reconcile them first')
        existing = matches[0] if matches else None
        if existing and existing.get('lifecycle') == 'archived': raise ValueError('Format is archived; explicitly restore it before adding content')
        if existing and str(manifest) == existing.get('manifest') and existing.get('sources'):
            raise ValueError('Generated format index is read-only; edit and register the owned source manifest')
        if revision is not None and revision != (existing or {}).get('revision', 0): raise ValueError('Review changed; refresh its revision')
        entry = (existing or {}).get('id') or name or declared.get('entry') or ws.slug(project.name + '--' + identity)
        occupied = [r for r in all_records if r is not existing and (r['id'] == entry or entry in r.get('aliases', []))]
        if occupied and not name and not declared.get('entry'): entry += '-' + project_key[:8]
        elif occupied: raise ValueError('Entry ID belongs to another review')
        if ws.slug(entry) != entry: raise ValueError('Invalid entry ID')
        record = copy.deepcopy(existing) if existing else {'schemaVersion':3, 'id':entry, 'createdAt':ws.now(), 'revision':0, 'lifecycle':'active', 'aliases':[]}
        if existing and not record.get('sources'):
            record['sources'] = [contribution(existing['manifest'], existing['gallery'], existing.get('owner'))]
        source = next((s for s in record.get('sources', []) if s['manifest'] == str(manifest)), None)
        incoming = contribution(manifest, gallery, owner, source, source_revision)
        if source: record['sources'][record['sources'].index(source)] = incoming
        else: record.setdefault('sources', []).append(incoming)
        record.update(kind=kind, recordType='influencer' if kind=='influencer' else 'format', projectRoot=str(project), projectKey=project_key,
                      projectId=(existing or {}).get('projectId') or declared.get('projectId') or project.name,
                      revision=record['revision']+1, owner=(existing or {}).get('owner') or owner or declared.get('owner') or 'unassigned')
        record['influencerId' if kind=='influencer' else 'formatId']=identity
        if kind=='influencer':record.pop('formatId',None)
        label=re.sub(r'^\s*THIS SESSION\s*[—–-]\s*','',data.get('title') or identity,flags=re.I)
        label=re.sub(r'^'+re.escape(project.name.replace('-',' '))+r'\s*[:·—-]\s*','',label,flags=re.I)
        record.setdefault('label', declared.get('label') or label)
        for field in ('recipeRef', 'brief', 'influencerRef'):
            if declared.get(field) and not record.get(field): record[field] = declared[field]
        record['accountGroups'] = sorted(set(record.get('accountGroups', []) + (groups if groups is not None else declared.get('accountGroups', []))))
        alias = name or declared.get('entry')
        if alias and alias != entry and alias not in record['aliases']:
            if any(r['id'] == alias or alias in r.get('aliases', []) for r in all_records): raise ValueError('Alias belongs to another review')
            record['aliases'].append(alias)
            record.setdefault('aliasSources', {})[alias] = incoming['id']
        record = publish(record)
        ws.atomic(ws.registry() / (entry + '.json'), record)
        shortcut(record)
        return entry


def reconcile(plan, apply=False):
    """Explicit mappings only. Prepare all generations before publishing any mapping."""
    with ws.lock():
        before = ws.records(); pending = []; retired = []; changes = []
        seen = set()
        for mapping in plan['formats']:
            originals = [ws.get(e) for e in mapping['entries']]
            if any(r['id'] in seen for r in originals): raise ValueError('Entry mapped twice')
            seen.update(r['id'] for r in originals)
            if any(r.get('lifecycle') != 'active' or r.get('batchId') or r.get('recordType') == 'historical-review' for r in originals): raise ValueError('Only current formats can be reconciled')
            projects = {str(Path(r['projectRoot']).resolve()) for r in originals}
            if len(projects) != 1: raise ValueError('Cannot merge different projects')
            project = Path(projects.pop()); identity = mapping['formatId']; entry = mapping.get('entry') or originals[0]['id']
            if ws.slug(identity) != identity or ws.slug(entry) != entry: raise ValueError('Invalid identity')
            if any(r['id'] == entry and r['id'] not in seen for r in before): raise ValueError('Entry collision')
            record = copy.deepcopy(originals[0]); record.update(id=entry, formatId=identity, label=mapping['label'], recordType='format', schemaVersion=3,
                projectKey=project_identity(project) if apply else ws.read(project/'.viewprinter/content-memory/config.json',{}).get('reviewProjectId'), sources=[], aliases=[], aliasSources={}, revision=max(r['revision'] for r in originals)+1)
            record['formatAliases'] = sorted({r['formatId'] for r in originals if r['formatId'] != identity})
            record['accountGroups'] = sorted({g for r in originals for g in r.get('accountGroups', [])})
            record.update({k:mapping[k] for k in ('recipeRef','brief') if k in mapping})
            for original in originals:
                sources = copy.deepcopy(original.get('sources')) or [contribution(original['manifest'], original['gallery'], original.get('owner'))]
                for source in sources:
                    if mapping.get('variants', {}).get(original['id']):
                        source['variant'] = mapping['variants'][original['id']]
                    record['sources'].append(source)
                for alias in [original['id'], *original.get('aliases', [])]:
                    if alias != entry:
                        record['aliases'].append(alias)
                        if len(sources) == 1: record['aliasSources'][alias] = sources[0]['id']
                if original['id'] != entry:
                    retired.append({**original, 'lifecycle':'merged', 'parentId':entry, 'revision':original['revision']+1, 'updatedAt':ws.now()})
            count = sum(len((s.get('_data') or data_for(s)).get('items', [])) for s in record['sources'])
            changes.append({'entry':entry, 'formatId':identity, 'sources':len(record['sources']), 'items':count, 'aliases':record['aliases']})
            if apply: pending.append(publish(record))
        historical=[]
        for mapping in plan.get('history',[]):
            original=ws.get(mapping['entry'])
            if original.get('lifecycle')!='archived' or not (original.get('archive',{}).get('legacy') or original.get('recordType')=='historical-review'):
                raise ValueError('Only legacy snapshots can be classified as historical reviews')
            parent=next((r for r in pending if r['id']==mapping['parentId']),None) or ws.get(mapping['parentId'])
            historical.append({**original,'recordType':'historical-review','parentId':parent['id'],'formatId':parent['formatId'],
                'label':mapping['label'],'historyDate':mapping.get('date'),'revision':original['revision']+1,'updatedAt':ws.now()})
        if not apply: return {'dryRun':True, 'formats':changes, 'historicalReviews':[r['id'] for r in historical]}
        folder = ws.root() / '.hub/migrations' / ('formats-' + uuid.uuid4().hex)
        ws.atomic(folder / 'before.json', {'records':before})
        for record in [*retired, *pending, *historical]: ws.atomic(ws.registry() / (record['id'] + '.json'), record)
        for record in pending:shortcut(record)
        ws.atomic(folder / 'after.json', {'records':ws.records()})
        return {'dryRun':False, 'formats':changes, 'receipt':str(folder), 'historicalReviews':[r['id'] for r in historical], 'remoteChanges':False}


def rollback(receipt):
    folder = Path(receipt).resolve()
    if not folder.is_relative_to((ws.root() / '.hub/migrations').resolve()): raise ValueError('Not a migration receipt')
    with ws.lock():
        before, after = ws.read(folder / 'before.json'), ws.read(folder / 'after.json')
        if not before or not after: raise ValueError('Incomplete migration receipt')
        if sorted(ws.records(), key=lambda r:r['id']) != sorted(after['records'], key=lambda r:r['id']):
            raise ValueError('Workspace changed after migration; cannot roll back over newer work')
        old = {r['id']:r for r in before['records']}
        for r in ws.records():
            if r['id'] not in old: (ws.registry() / (r['id'] + '.json')).unlink()
        for r in old.values(): ws.atomic(ws.registry() / (r['id'] + '.json'), r)
    return {'restoredRecords':len(old), 'assetsRetained':True}


def manage_influencer(entry, influencer_id, profile_ref, guide_ref=None):
    """Convert an existing active review without renaming its URL or changing media."""
    if ws.slug(influencer_id)!=influencer_id:raise ValueError('Influencer ID must be a stable lowercase slug')
    with ws.lock():
        record=copy.deepcopy(ws.get(entry))
        if record['lifecycle']!='active' or record.get('batchId'):raise ValueError('Restore the current review before managing this influencer')
        for other in ws.records():
            if other['id']!=record['id'] and other.get('kind')=='influencer' and other.get('influencerId')==influencer_id and other['projectRoot']==record['projectRoot']:
                raise ValueError('Influencer already has a review')
        profile=(Path(record['projectRoot'])/profile_ref).resolve()
        if not profile.is_relative_to(Path(record['projectRoot']).resolve()) or not isinstance(ws.read(profile),dict):raise ValueError('Influencer profile must exist inside this project')
        before=copy.deepcopy(record)
        legacy=record.pop('formatId',None)
        record.update(kind='influencer',recordType='influencer',influencerId=influencer_id,influencerRef=profile_ref,revision=record['revision']+1)
        if legacy:record['formatAliases']=sorted(set(record.get('formatAliases',[])+[legacy]))
        if guide_ref:record['recipeRef']=guide_ref
        record=publish(record)
        receipt=ws.root()/'.hub/migrations'/('influencer-'+uuid.uuid4().hex)
        history=[]
        for old in ws.records():
            if old.get('parentId')==entry and old.get('recordType')=='historical-review':
                history.append(old)
        ws.atomic(receipt/'before.json',{'review':before,'history':history})
        ws.atomic(ws.registry()/(entry+'.json'),record)
        for old in history:
            old.update(lifecycle='history',revision=old['revision']+1,updatedAt=ws.now())
            ws.atomic(ws.registry()/(old['id']+'.json'),old)
        shortcut(record)
        return {'entry':entry,'kind':'influencer','influencerId':influencer_id,'historyMoved':len(history),'receipt':str(receipt)}
