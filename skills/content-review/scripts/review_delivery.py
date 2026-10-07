"""Exact-version delivery receipts and conservative, destination-aware progress."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import re
from pathlib import Path
import sys

SCHEDULED = {'scheduled', 'queued', 'publishing', 'processing'}
RETIRED = {'removed', 'withdrawn'}

def iso(text):
    """datetime.fromisoformat with a Z suffix and any number of fractional digits, which it
    accepts only from Python 3.11."""
    text = text.replace('Z', '+00:00')
    text = re.sub(r'(\d{2}:\d{2}:\d{2}),(\d+)', r'\1.\2', text, count=1)  # a comma fraction
    text = re.sub(r'([+-]\d{2})(\d{2})$', r'\1:\2', text)  # a +0000 offset
    text = re.sub(r'\.(\d+)', lambda match: '.' + (match.group(1) + '000000')[:6], text, count=1)
    return datetime.fromisoformat(text)


def timestamp(value):
    try:
        return iso(value).timestamp()
    except (AttributeError, TypeError, ValueError):
        return 0


def sync(memory, pages, output):
    links = {}
    for path in sorted((memory / 'history/publications').glob('*.jsonl')):
        for line in path.read_text(encoding='utf-8').splitlines():
            if line.strip():
                row = json.loads(line); key = (row['postId'], row['accountId'])
                if key in links and any(str(links[key].get(k)) != str(row.get(k)) for k in ('itemId', 'version', 'batchId')):
                    raise ValueError('Conflicting publication links: ' + str(key))
                links[key] = row
    result = json.loads(output.read_text(encoding='utf-8')) if output.exists() else {'placements': []}
    from review_readiness import remember
    placements = {(r['postId'], r['accountId']): r for r in result['placements']}
    for row in placements.values(): remember(row)
    now = datetime.now(timezone.utc).isoformat()
    for key, link in links.items():
        placements.setdefault(key, {**{k: link.get(k) for k in ('postId', 'accountId', 'itemId', 'version', 'batchId')}, 'status': 'unknown'})
    for path in pages:
        envelope = json.loads(path.read_text(encoding='utf-8')); data = envelope.get('structuredContent', envelope)
        if not isinstance(data.get('posts'), list):
            raise ValueError('Expected saved posts_list object: ' + str(path))
        observed = envelope.get('observedAt') or envelope.get('checkedAt') or data.get('observedAt') or data.get('checkedAt')
        clock_source = 'receipt' if observed else 'source-file-mtime'
        observed = observed or datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()
        if not timestamp(observed):
            raise ValueError('Invalid receipt observation timestamp')
        scope = envelope.get('readScope', {})
        authoritative = scope.get('completeTargets') is True and scope.get('accountFilter') is False
        for entry in data['posts']:
            post = entry['post']; seen = set()
            for target in entry.get('targets', []):
                account = target.get('account') or {}
                key = (post['id'], target.get('socialAccountId') or account.get('id')); seen.add(key)
                if key not in links or timestamp(placements[key].get('checkedAt')) > timestamp(observed):
                    continue
                status = raw_status = target.get('status', 'unknown')
                if status == 'pending' and post.get('status') == 'draft': status = 'draft'
                if status == 'pending' and post.get('status') == 'scheduled' and post.get('scheduledAt'): status = 'scheduled'
                row = placements[key]
                row.update(status=status, targetStatus=raw_status, platform=account.get('platform') or row.get('platform'),
                    organizationId=account.get('organizationId') or post.get('organizationId') or row.get('organizationId'),
                    accountName=account.get('handle') or account.get('username') or account.get('name') or row.get('accountName') or key[1],
                    scheduledAt=post.get('scheduledAt'), publishedAt=target.get('publishedAt') or target.get('postedAt'),
                    url=target.get('externalUrl') or target.get('url') or target.get('postUrl') or target.get('platformPostUrl'),
                    checkedAt=observed, importedAt=now, observationSource=clock_source)
                if 'caption' in post or 'content' in post:
                    row['caption'] = target.get('caption', target.get('content', post.get('caption', post.get('content'))))
                if 'title' in target: row['title'] = target['title']
                for field in ('mediaSha256', 'copyRevision'):
                    if field in entry: row[field] = entry[field]
                # Successful new scheduling/copy amendments replace the accepted handoff;
                # later failures/publication states retain the prior receipt.
                if status in SCHEDULED or status == 'published':
                    row.pop('handoff', None)
                    remember(row)
            if authoritative and post['id'] in scope.get('postIds', []):
                for key, row in placements.items():
                    if key[0] == post['id'] and key not in seen and timestamp(row.get('checkedAt')) <= timestamp(observed):
                        row.update(status='removed', checkedAt=observed, importedAt=now,
                            removalEvidence={'kind':'complete-unfiltered-post-read','postId':post['id'],'observedAt':observed})
    result = {'updatedAt': now, 'placements': list(placements.values())}
    output.parent.mkdir(parents=True, exist_ok=True)
    from review_gallery import write_atomically
    write_atomically(output, (json.dumps(result, indent=2) + '\n').encode())
    return result


def attach(manifest, base):
    config = manifest.get('delivery')
    if not config: return
    snapshot = json.loads((base / config['snapshot']).resolve().read_text(encoding='utf-8'))
    for item in manifest['items']:
        item['_placements'] = rows_for(item, snapshot['placements'])
        item['_deliveryTimezone'] = config.get('timezone', 'UTC')
        item['_progress'] = item_progress(item, item['_placements'])


def rows_for(item, rows):
    return [r for r in rows if r.get('itemId') == item['id'] and str(r.get('version')) == str(item['version'])]


def lanes(rows):
    states = {r.get('status', 'unknown') for r in rows}
    result = []
    if states & {'published'}: result.append('posted')
    if states & SCHEDULED: result.append('scheduled')
    if states - {'published', *SCHEDULED, 'draft', 'canceled', 'cancelled', *RETIRED}: result.append('attention')
    return result or ['unscheduled']


def native_copy(item):
    """Read structured native copy; retain legacy text as unstructured, not approved."""
    result = {}
    for platform, value in (item.get('captions') or {}).items():
        if isinstance(value, str): result[platform] = {'caption': value}
        elif isinstance(value, dict): result[platform] = value
    return result


def item_progress(item, rows):
    plan = item.get('distribution') or {}
    if plan.get('status') == 'excluded' and plan.get('reason'):
        return {'state':'excluded','required':0,'published':0,'scheduled':0,'attention':False,'copy':'not-required','issues':[]}
    targets = plan.get('targets')
    known = isinstance(targets, list) and bool(targets)
    required = [t for t in (targets or []) if not (t.get('state') == 'withdrawn' and t.get('reason'))]
    known = known and bool(required) and all(t.get('accountId') and t.get('organizationId') for t in required)
    issue = []; counts = Counter(); copy = native_copy(item)
    missing_copy = False; unverified_copy = False; mismatch = False
    for target in required:
        candidates = [r for r in rows if r.get('accountId') == target.get('accountId') and
            r.get('organizationId') == target.get('organizationId') and r.get('status') not in RETIRED]
        # A successful earlier publication fulfils this destination, unless its source is marked removed.
        published = [r for r in candidates if r.get('status') == 'published']
        row = max(published or candidates, key=lambda r: timestamp(r.get('checkedAt')), default={})
        state = row.get('status', 'unscheduled')
        if row.get('mediaSha256') and item.get('sha256') and row['mediaSha256'] != item['sha256']:
            state='media-version-mismatch';issue.append(state)
        counts[state] += 1
        if state in {'failed','unknown','canceled','cancelled'}: issue.append(state + ': ' + str(target.get('accountId')))
        native = (item.get('captionsByAccount') or {}).get(target.get('accountId')) or copy.get(target.get('platform'), {})
        if isinstance(native, str): native = {'caption': native}
        if not str(native.get('caption', '')).strip(): missing_copy = True
        if row.get('status') in SCHEDULED or row.get('status') == 'published':
            if 'caption' not in row: unverified_copy = True
            elif native.get('caption') is not None and native['caption'] != row['caption']: mismatch = True
            if native.get('title') is not None:
                if 'title' not in row: unverified_copy = True
                elif native['title'] != row['title']: mismatch = True
            if row.get('mediaSha256') and item.get('sha256') and row['mediaSha256'] != item['sha256']: issue.append('media-version-mismatch')
    actual = Counter(r.get('status') for r in rows if r.get('status') not in RETIRED)
    p = counts['published']; s = sum(counts[x] for x in SCHEDULED)
    if known and p == len(required): state = 'all-posted'
    elif known and p+s == len(required): state = 'all-scheduled'
    elif actual['published'] or p: state = 'some-posted'
    elif s or any(actual[x] for x in SCHEDULED): state = 'partly-scheduled'
    elif rows or known: state = 'not-posted'
    else: state = 'plan-needed'
    if mismatch: issue.append('scheduled-copy-differs')
    if missing_copy: copy_state = 'missing'
    elif mismatch: copy_state = 'changed'
    elif not known: copy_state = 'unverified'
    elif item.get('captionStatus') not in {'approved','finalized'}: copy_state = 'needs-review'
    elif unverified_copy: copy_state = 'approved-unverified'
    else: copy_state = 'ready'
    if not known: issue.append('destination-plan-unverified')
    return {'state':state,'planKnown':known,'required':len(required),'published':p,'scheduled':s,
        'actualPublished':actual['published'],'actualScheduled':sum(actual[x] for x in SCHEDULED),
        'attention':bool(issue),'copy':copy_state,'issues':issue,
        'checkedAt': min((r['checkedAt'] for r in rows if r.get('checkedAt')), key=timestamp, default=None)}


def summarize(manifest, placements):
    archived_batches = {b['id'] for b in manifest.get('batches', []) if b.get('lifecycle') == 'archived'}
    items = [i for i in manifest.get('items', []) if i.get('batch') not in archived_batches]
    progress = [item_progress(i, rows_for(i, placements)) for i in items]
    included = [p for p in progress if p['state'] != 'excluded']
    states = Counter(p['state'] for p in included)
    if included and states['all-posted'] == len(included): state = 'all-posted'
    elif included and states['all-posted']+states['all-scheduled'] == len(included): state = 'all-scheduled'
    elif any(p.get('actualPublished', 0) for p in included): state = 'some-posted'
    elif any(p.get('actualScheduled', 0) for p in included): state = 'partly-scheduled'
    elif any(not p.get('planKnown') for p in included): state = 'plan-needed'
    else: state = 'not-posted'
    labels = {'all-posted':'All posted','all-scheduled':'All scheduled','some-posted':'Some posted',
        'partly-scheduled':'Partly scheduled','plan-needed':'Plan needed','not-posted':'No posts yet'}
    creative = Counter(i.get('status', 'unknown') for i in items)
    return {'state':state,'label':labels[state],'items':len(items),'included':len(included),'excluded':len(progress)-len(included),
        'fullyPosted':states['all-posted'],'fullyScheduled':states['all-scheduled'],
        'requiredPlacements':sum(p['required'] for p in included),'publishedPlacements':sum(p['published'] for p in included),
        'scheduledPlacements':sum(p['scheduled'] for p in included),'unverifiedPlans':sum(not p.get('planKnown') for p in included),
        'attention':sum(p['attention'] for p in included),'copy':dict(Counter(p['copy'] for p in included)),
        'creative':dict(creative),'checkedAt':min((p['checkedAt'] for p in included if p.get('checkedAt')), key=timestamp, default=None)}


if __name__ == '__main__':
    # Agents read this through a pipe, which on Windows defaults to the system code page.
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors=stream.errors)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--memory', type=Path, required=True)
    parser.add_argument('--posts', type=Path, action='append', default=[])
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); sync(args.memory, args.posts, args.output)
