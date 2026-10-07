"""Resolve a shared account identity and content-addressed asset copies into a group."""
import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile

IDENTITY_FIELDS = {'organizationId','accountId','platform','handle','url','nativeType','current','proposed','application'}
ASSET_TYPES = {'.png','.jpg','.jpeg','.webp','.svg','.pdf'}


def resolve(data, base):
    base=base.resolve()
    data=copy.deepcopy(data)
    project=next((p for p in (base,*base.parents) if (p/'.viewprinter/content-memory').is_dir()), base)
    for account in data.get('accounts',[]):
        if not account.get('identityRef'):continue
        source=(base/account['identityRef']).resolve()
        if not source.is_relative_to(project):raise ValueError('Shared identity must be inside the project')
        record=json.loads(source.read_text(encoding='utf-8'));identity=record['identity']
        for key in ('organizationId','accountId'):
            if identity.get(key)!=account.get(key):raise ValueError('Shared account identity mismatch: '+key)
        for key in IDENTITY_FIELDS:
            if key in identity:account[key]=identity[key]
        account['identityRevision']=record['revision']
        shared_assets={a['id']:a for a in record.get('assets',[])}
        for asset_id,shared_id in account.get('assetBindings',{}).items():
            asset=next((a for a in data.get('assets',[]) if a['id']==asset_id),None)
            if not asset:raise ValueError('Shared asset binding is missing a group asset')
            shared=shared_assets[shared_id];source_asset=(source.parent/shared['src']).resolve()
            if not source_asset.is_relative_to(project) or source_asset.suffix.lower() not in ASSET_TYPES:
                raise ValueError('Shared asset must be supported media inside the project')
            payload=source_asset.read_bytes();digest=hashlib.sha256(payload).hexdigest()
            if shared.get('sha256')!=digest:raise ValueError('Shared asset hash mismatch')
            target=base/'Assets/shared'/(digest+source_asset.suffix.lower());target.parent.mkdir(parents=True,exist_ok=True)
            if not target.exists():
                fd,tmp=tempfile.mkstemp(dir=target.parent)
                try:
                    with os.fdopen(fd,'wb') as f:f.write(payload)
                    os.replace(tmp,target)
                finally:
                    if os.path.exists(tmp):os.unlink(tmp)
            elif hashlib.sha256(target.read_bytes()).hexdigest()!=digest:
                raise ValueError('Shared asset copy changed unexpectedly')
            asset.update({k:v for k,v in shared.items() if k not in {'id','src'}})
            asset['src']=str(target.relative_to(base));asset['sharedIdentityRevision']=record['revision']
    return data
