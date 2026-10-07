"""The local review ends at verified scheduling, not publication or performance."""
from collections import Counter
from review_delivery import native_copy, rows_for

ACCEPTED = {'scheduled', 'queued', 'publishing', 'processing', 'published'}
LABELS = {'needs-review':'Needs review', 'changes-requested':'Changes requested',
          'needs-copy':'Descriptions to review', 'ready':'Ready to schedule',
          'production':'In production', 'scheduled':'Scheduled', 'excluded':'Excluded'}
ORDER = ['changes-requested', 'needs-review', 'needs-copy', 'ready', 'production']
PENDING = {'planned','generating','in-progress','blocked','held'}


def receipt(row):
    """A durable handoff survives later publication/failure observations."""
    saved = row.get('handoff')
    if isinstance(saved, dict) and saved.get('confirmedAt'):
        return saved
    if row.get('status') not in ACCEPTED or not row.get('postId') or not row.get('checkedAt'):
        return None
    return {k: row[k] for k in ('postId','accountId','organizationId','scheduledAt','caption','title','mediaSha256','copyRevision') if k in row} | {'confirmedAt':row['checkedAt']}


def remember(row):
    """Call before replacing live delivery fields; a receipt is local evidence only."""
    if not row.get('handoff') and (saved := receipt(row)):
        row['handoff'] = saved


def expected_copy(item, target):
    native = (item.get('captionsByAccount') or {}).get(target.get('accountId')) or native_copy(item).get(target.get('platform'), {})
    return {'caption':native} if isinstance(native,str) else native


def item_state(item, rows):
    status = str(item.get('status','')).casefold()
    plan = item.get('distribution') or {}
    if plan.get('status') == 'excluded' and plan.get('reason'):
        return {'state':'excluded','label':LABELS['excluded'],'required':0,'accepted':0,'active':False}
    targets = [t for t in (plan.get('targets') or []) if not (t.get('state')=='withdrawn' and t.get('reason'))]
    known = bool(targets) and all(t.get('organizationId') and t.get('accountId') for t in targets)
    accepted = 0
    mismatch = set()
    for target in targets:
        matches = [receipt(r) for r in rows if r.get('accountId')==target.get('accountId') and r.get('organizationId')==target.get('organizationId')]
        valid = []
        target_issues = set()
        for evidence in filter(None,matches):
            issues = set()
            if evidence.get('mediaSha256') and item.get('sha256') and evidence['mediaSha256']!=item['sha256']:
                issues.add('media')
            native = expected_copy(item,target)
            if any(k in evidence and k in native and evidence[k]!=native[k] for k in ('caption','title')):
                issues.add('copy')
            if evidence.get('copyRevision') is not None and item.get('copyRevision') is not None and str(evidence['copyRevision'])!=str(item['copyRevision']):
                issues.add('copy')
            if not issues:valid.append(evidence)
            target_issues.update(issues)
        if valid:accepted+=1
        else:mismatch.update(target_issues)
    # A file replaced after its version was accepted is no longer what was reviewed.
    if item.get('_mediaReplaced'):mismatch.add('media')
    # Stale creative/copy flags do not reopen a completed exact-version handoff.
    if known and accepted==len(targets):phase='scheduled'
    elif status in PENDING or (status=='approved' and item.get('stage') in {'concept','source','demo','edit'}):phase='production'
    elif status=='changes-requested':phase='changes-requested'
    elif status!='approved' or 'media' in mismatch:phase='needs-review'
    else:
        copies = [expected_copy(item,t) for t in targets] if targets else list(native_copy(item).values())
        copies_ready = bool(copies) and all(str(n.get('caption','')).strip() for n in copies)
        phase='ready' if copies_ready and item.get('captionStatus') in {'approved','finalized'} and not mismatch else 'needs-copy'
    return {'state':phase,'label':LABELS[phase],'required':len(targets),'accepted':accepted,
            'planKnown':known,'active':phase!='scheduled', 'mismatch':sorted(mismatch)}


def attach(manifest, rows):
    for item in manifest.get('items',[]):
        item['_readiness']=item_state(item,rows_for(item,rows))


def summarize(manifest, rows):
    archived={b['id'] for b in manifest.get('batches',[]) if b.get('lifecycle')=='archived'}
    items=[i for i in manifest.get('items',[]) if i.get('batch') not in archived]
    phases=[(i,item_state(i,rows_for(i,rows))) for i in items]
    counts=Counter(p['state'] for _,p in phases)
    included=len(items)-counts['excluded']; active=included-counts['scheduled']
    next_state=next((s for s in ORDER if counts[s]), 'scheduled' if included else 'empty')
    next_item=next((i for i,p in phases if p['state']==next_state),{})
    return {'state':'active' if active else 'scheduled' if included else 'empty',
            'label':'Active' if active else 'Scheduled' if included else 'No active content',
            'items':included,'active':active,'scheduled':counts['scheduled'],'excluded':counts['excluded'],
            'counts':{s:counts[s] for s in LABELS},'nextState':next_state,
            'nextLabel':LABELS.get(next_state,'No active content'),
            'nextItem':{'id':next_item.get('id'),'version':next_item.get('version'),'title':next_item.get('title'),'batch':next_item.get('batch'),
                        'poster':next_item.get('poster') or (next_item.get('src') if next_item.get('kind')=='image' else None)},
            'acceptedPlacements':sum(p['accepted'] for _,p in phases),
            'requiredPlacements':sum(p['required'] for _,p in phases)}
