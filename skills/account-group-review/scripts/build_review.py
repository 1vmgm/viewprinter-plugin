#!/usr/bin/env python3
"""Render a local, read-only account group handoff. Standard library only."""
import argparse
import base64
import hashlib
import html
import json
import os
from pathlib import Path
import tempfile
from datetime import datetime
from zoneinfo import ZoneInfo
from urllib.parse import urlparse, quote


def esc(value):
    return html.escape(str(value), quote=True)


def href(value):
    value = str(value)
    parsed = urlparse(value)
    if parsed.scheme and parsed.scheme not in ('http', 'https'):
        raise ValueError('Unsupported link scheme')
    if value.startswith('//') or any(ord(c) < 32 for c in value) or '\\' in value:
        raise ValueError('Invalid link')
    return esc(value)


def link(title, url, download=False):
    return f'<a {"download" if download else ""} href="{href(url)}">{esc(title)}</a>'



def manifest_download(manifest, data=None):
    # The shared review hub intentionally does not serve arbitrary JSON files.
    # Embed only this reviewed, public-facing manifest; keep the allowlist intact.
    payload = base64.b64encode(json.dumps(data, indent=2).encode() if data else manifest.read_bytes()).decode('ascii')
    return (f'<a download="{esc(manifest.name)}" '
            f'href="data:application/json;base64,{payload}">Download group brief</a>')



def featured_art(asset):
    full = f'<img class="featured-art" src="{href(asset["src"])}" alt="{esc(asset["title"])}">'
    crop = asset.get('cropPreview')
    if not crop:
        return full
    x,y,w,h,sw,sh = [float(crop[k]) for k in ('x','y','width','height','sourceWidth','sourceHeight')]
    if not (0 <= x < sw and 0 <= y < sh and 0 < w <= sw-x and 0 < h <= sh-y):
        raise ValueError('Invalid crop preview: ' + asset['id'])
    style = f'position:relative;overflow:hidden;aspect-ratio:{w}/{h};border-radius:10px;margin:16px 0'
    image_style = f'position:absolute;max-width:none;width:{sw/w*100}%;height:{sh/h*100}%;left:{-x/w*100}%;top:{-y/h*100}%'
    return (f'<p class="muted">{esc(crop.get("label","Platform crop · local simulation"))}</p>'
            f'<div class="crop-preview" style="{style}"><img style="{image_style}" src="{href(asset["src"])}" alt="{esc(asset["title"])}"></div>'
            f'<details><summary>Full upload artwork</summary>{full}</details>')


def copy_field(label, value, note=''):
    if value is None:
        return f'<div class="field"><b>{esc(label)}</b><p class="muted">Not observed</p></div>'
    if value == '':
        return f'<div class="field"><b>{esc(label)}</b><p class="muted">Not set</p></div>'
    return (f'<div class="field"><div class="field-head"><b>{esc(label)}</b>'
            f'<button data-copy="{esc(value)}" aria-label="Copy {esc(label)}">Copy</button></div>'
            f'<pre>{esc(value)}</pre>' + (f'<small>{esc(note)}</small>' if note else '') + '</div>')


def listing(values):
    return '<ul>' + ''.join(f'<li>{esc(v)}</li>' for v in values) + '</ul>'


def date_label(d):
    raw = d['checkedAt']
    if 'T' not in raw:
        return raw
    observed = datetime.fromisoformat(raw.replace('Z', '+00:00'))
    if observed.tzinfo:
        observed = observed.astimezone(ZoneInfo(d.get('timezone', 'UTC')))
    return observed.strftime('%b %d, %Y · %I:%M %p %Z')


CSS = '''
:root{color-scheme:dark;font:16px/1.55 system-ui,sans-serif;color:#eeebf6;background:#101018;--blue:#b99cff}
*{box-sizing:border-box}body{margin:0}main{max-width:1180px;margin:auto;padding:42px 24px 70px}
h1{font-size:clamp(32px,5vw,56px);line-height:1.06;letter-spacing:-1.6px;margin:14px 0 20px}
h2{font-size:25px;line-height:1.2}h3{font-size:19px}p{max-width:85ch}a{color:#c7a9ff;overflow-wrap:anywhere}
button,.pill{border:1px solid #44374f;background:#211b2b;border-radius:7px;padding:9px 12px;color:#e0cffa}
button{cursor:pointer;font:inherit;font-size:13px}button:hover{background:#362542}button:focus-visible,a:focus-visible,summary:focus-visible{outline:3px solid #c3a4ff;outline-offset:3px}
header{margin-bottom:30px}.eyebrow{font-size:12px;letter-spacing:1.7px;text-transform:uppercase;color:#b0a0c4}
.status{padding:15px 18px;background:#2b2138;border-radius:10px}.muted,small{color:#b6a8c7}small{font-size:12px;display:block}
nav{display:flex;gap:9px;flex-wrap:wrap;margin:22px 0}nav a{text-decoration:none}
.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:22px}.panel,.account{background:#1a1622;border:1px solid #3c3048;border-radius:16px;padding:24px;margin-bottom:22px;min-width:0}
.account{margin:0;scroll-margin-top:18px}.account-head{display:flex;align-items:center;gap:16px}.avatar{width:74px;height:74px;border-radius:50%;object-fit:cover;background:#241c2f}
.ref{display:flex;gap:12px;align-items:center;font:12px ui-monospace,monospace;margin-bottom:20px}.ref button{margin-left:auto}
.badge{font-size:12px;background:#352843;border-radius:5px;padding:4px 7px;display:inline-block}
.field{margin:20px 0}.field-head{display:flex;justify-content:space-between;gap:10px;align-items:center}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:inherit;background:#241d2e;padding:13px;border-radius:8px;margin:8px 0}
details{border-top:1px solid #40324a;padding:14px 0;margin-top:16px}summary{cursor:pointer;font-weight:650}
.asset-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(235px,1fr));gap:24px}.asset img{display:block;width:100%;max-height:290px;object-fit:contain;background:#15101e;border:1px solid #3e314a;border-radius:10px;margin:12px 0}
.asset.avatar-asset img{height:145px;width:145px;border-radius:50%}.asset h3{margin:10px 0}.asset a{display:inline-block;margin:7px 12px 7px 0}
.featured-art{width:100%;display:block;border-radius:10px;margin:16px 0}.featured-meta{display:flex;gap:14px;align-items:center;flex-wrap:wrap}.featured-meta button{margin-left:auto}
.application-status{border-left:4px solid #7ecaa5;padding:12px 15px;background:#193429;border-radius:6px}.feature{margin:17px 0;padding:13px;background:#241d2e;border-radius:9px}.feature p{margin:7px 0}.feature b{display:block}
.source{margin:18px 0}.source p{margin:5px 0}.links{display:flex;gap:15px;flex-wrap:wrap}.notice{border-left:4px solid #d9a44e;padding-left:14px}
#copy-status{position:fixed;bottom:16px;left:16px;right:16px;max-width:700px;padding:12px 16px;border-radius:8px;background:#3b2950;color:white;z-index:10}#copy-status:empty{display:none}
@media(max-width:720px){main{padding:24px 14px 70px}.grid{grid-template-columns:1fr}.panel,.account{padding:20px}h1{letter-spacing:-.8px}.field-head button{flex:none}.asset-grid{grid-template-columns:1fr}}
'''

JS = '''
document.addEventListener('click',async e=>{
const b=e.target.closest('[data-copy]');if(!b)return;
const text=b.dataset.copy,status=document.querySelector('#copy-status');let ok=false;
try{await navigator.clipboard.writeText(text);ok=true}catch(_){
 const t=document.createElement('textarea');t.value=text;t.setAttribute('aria-label','Text to copy');document.body.append(t);t.select();
 try{ok=document.execCommand('copy')}catch(_){}t.remove();
}
status.textContent=ok?'Copied.':'Copy unavailable. Select the visible text and copy it manually.';
if(ok){const old=b.textContent;b.textContent='Copied';setTimeout(()=>b.textContent=old,1400)}
});
'''


def build(manifest, output):
    base = manifest.parent.resolve()
    if output.parent.resolve() != base:
        raise ValueError('Output must be beside manifest')
    from shared_identity import resolve
    d = resolve(json.loads(manifest.read_text()), base)
    for key in ('id', 'title', 'revision', 'checkedAt', 'status', 'accounts'):
        if key not in d:
            raise ValueError('Missing group field: ' + key)
    if not d['accounts']:
        raise ValueError('Group must contain at least one account')
    assets, refs, ids = {}, set(), set()
    for a in d.get('assets', []):
        if a['id'] in assets:
            raise ValueError('Duplicate asset ID')
        p = (base / a['src']).resolve()
        if not p.is_relative_to(base) or not p.is_file():
            raise ValueError('Asset missing or outside bundle: ' + a['src'])
        if a.get('sha256') and hashlib.sha256(p.read_bytes()).hexdigest() != a['sha256']:
            raise ValueError('Asset hash changed: ' + a['id'])
        assets[a['id']] = a
    cards, nav = [], []
    for a in d['accounts']:
        for key in ('ref', 'accountId', 'organizationId', 'platform', 'url', 'current', 'proposed'):
            if not a.get(key):
                raise ValueError('Missing account field: ' + key)
        identity = (a['organizationId'], a['accountId'])
        if a['ref'] in refs or identity in ids:
            raise ValueError('Duplicate account reference or stable identity')
        refs.add(a['ref']); ids.add(identity)
        p = a['proposed']; current = a['current']
        bio = p.get('bio', '')
        n = len(bio.encode('utf-16-le')) // 2 if p.get('countUnit') == 'utf16' else len(bio)
        if p.get('bioLimit') and n > p['bioLimit']:
            raise ValueError('Bio exceeds declared limit: ' + a['ref'])
        for asset_id in a.get('assetIds', []):
            if asset_id not in assets:
                raise ValueError('Unknown asset: ' + asset_id)
        avatar = next((assets[x] for x in a.get('assetIds', []) if assets[x]['kind'] == 'avatar'), None)
        img = f'<img class="avatar" src="{href(avatar["src"])}" alt="Proposed profile avatar">' if avatar else ''
        ref = f'{a["ref"]} / v{d["revision"]}'
        count_note = f'{n}' + (f' / {p["bioLimit"]}' if p.get('bioLimit') else '') + (' UTF-16 units' if p.get('countUnit') == 'utf16' else ' characters')
        fields = copy_field('Display name', p.get('name')) + copy_field('Bio / description', bio, count_note)
        for key, label in [('linkTitle','Link title'),('website','Website destination')]:
            if key in p: fields += copy_field(label, p[key])
        features = ''.join(f'<div class="feature"><b>{esc(f["label"])}</b><span class="badge">{esc(f["state"])}</span><p>{esc(f.get("requirement", ""))}</p><p>{esc(f.get("action", ""))}</p><small>{esc(f.get("evidence", ""))} · checked {esc(f.get("checkedAt", d["checkedAt"]))}</small></div>' for f in a.get('features', []))
        downloads = ' · '.join(link(assets[x]['title'], assets[x]['src'], True) for x in a.get('assetIds', []))
        observed = ''.join(copy_field(label, current.get(k)) for k,label in [('name','Observed name'),('bio','Observed bio'),('website','Observed website')])
        shared = f'<p class="notice">Shared with: {esc(", ".join(a["sharedWith"]))}</p>' if a.get('sharedWith') else ''
        application = a.get('application', {})
        application_html = (f'<p class="application-status"><strong>{esc(application.get("label",application.get("status","")))}</strong><small>{esc(application.get("note",""))}</small></p>') if application else ''
        card = f'''<article class="account" id="{esc(a['ref'])}" data-account-id="{esc(a['accountId'])}">
<div class="ref"><span>{esc(ref)}</span><button data-copy="{esc(ref)}">Copy ID</button></div>
<div class="account-head">{img}<div><div class="eyebrow">{esc(a['platform'])}</div><h2>{esc(p.get('name',a['ref']))}</h2>{link(a.get('handle',a['url']),a['url'])}</div></div>
<p>{esc(a.get('role',''))}</p>{shared}{application_html}<span class="badge">{esc(a.get('connection',{}).get('summary','Connection not observed'))}</span>
{fields}<p class="muted">{esc(p.get('note',''))}</p><div class="links">{downloads}</div>
<details><summary>Current account & identity</summary>{observed}<small>{esc(current.get('evidence',''))}</small><p>Native type: {esc(a.get('nativeType','unknown'))}</p><p>Account ID: <code>{esc(a['accountId'])}</code></p><p>Workspace: <code>{esc(a['organizationId'])}</code></p></details>
<details><summary>Links & feature requirements</summary>{features}</details>
<details><summary>Application steps</summary>{listing(a.get('actions',[]))}</details></article>'''
        cards.append(card); nav.append(f'<a class="pill" href="#{esc(a["ref"])}">{esc(a["platform"])} · {esc(a["ref"])}</a>')
    asset_cards = []
    for a in assets.values():
        context = ''.join(link(x['title'], x['url']) for x in a.get('reviewLinks', []))
        previous = a.get('previous')
        old = ('<details><summary>Previous version</summary>' + link(previous.get('title','Previous artwork'),previous['src']) + '</details>') if previous else ''
        asset_cards.append(f'<div class="asset {"avatar-asset" if a["kind"]=="avatar" else ""}"><h3>{esc(a["title"])}</h3><span class="badge">{esc(a.get("dimensions",""))}</span><img src="{href(a["src"])}" alt="{esc(a["title"])}"><p>{esc(a.get("note",""))}</p>{link("Download",a["src"],True)}<div class="links">{context}</div>{old}<small>{esc(a.get("provenance",""))}</small></div>')
    featured = []
    for asset_id in d.get('featuredAssets', []):
        if asset_id not in assets:
            raise ValueError('Unknown featured asset: ' + asset_id)
        a = assets[asset_id]
        ref = a.get('ref', asset_id) + ' / v' + str(a.get('version', d['revision']))
        context = ''.join(link(x['title'], x['url']) for x in a.get('reviewLinks', []))
        previous = a.get('previous')
        old = ('<details><summary>Previous version</summary>' + link(previous.get('title','Previous artwork'),previous['src']) + '</details>') if previous else ''
        featured.append(f'<section class="panel" id="featured-{esc(asset_id)}"><div class="featured-meta"><span class="badge">{esc(a.get("status","Needs review"))}</span><span>{esc(ref)}</span><button data-copy="{esc(ref)}">Copy ID</button></div><h2>{esc(a["title"])}</h2>{featured_art(a)}<p>{esc(a.get("reviewFocus",a.get("note","")))}</p><div class="links">{link(a.get("downloadLabel","Download artwork"),a["src"],True)}{context}</div>{old}</section>')
    source_rows = ''.join(f'<div class="source">{link(s["title"],s["url"])}<small>{esc(s.get("status",""))} · checked {esc(s.get("checkedAt",d["checkedAt"]))}</small><p>{esc(s.get("note",""))}</p></div>' for s in d.get('sources',[]))
    content = d.get('content',{})
    content_html = f'<section class="panel"><h2>Content & cadence</h2><p>{esc(content.get("summary",""))}</p>{listing(content.get("notes",[]))}<div class="links">'+''.join(link(x['title'],x['url']) for x in content.get('links',[]))+'</div></section>' if content else ''
    extras = ''.join(f'<section class="panel"><h2>{esc(s["title"])}</h2><p style="white-space:pre-line">{esc(s.get("text",""))}</p>{listing(s.get("items",[]))}</section>' for s in d.get('sections',[]))
    page = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(d['title'])}</title><style>{CSS}</style></head><body><main>
<header><div class="eyebrow">Account group review · revision {esc(d['revision'])}<br>{esc(date_label(d))}</div><h1>{esc(d['title'])}</h1><p>{esc(d.get('focus',''))}</p><p class="status">{esc(d['status'])}</p><nav>{''.join(nav)}</nav></header>
{''.join(featured)}{extras}<section class="grid">{''.join(cards)}</section><section class="panel" style="margin-top:24px"><h2>Profile assets & layout guides</h2><div class="asset-grid">{''.join(asset_cards)}</div></section>{content_html}
<section class="panel"><details><summary>Dated research & remaining checks</summary>{source_rows}</details><p class="muted">Feedback: use the account reference and field in conversation. Proposals, feature eligibility and public application are tracked separately.</p>{manifest_download(manifest,d)}</section>
</main><div id="copy-status" role="status" aria-live="polite"></div><script>{JS}</script></body></html>'''
    with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=base,delete=False) as f:
        f.write(page); temp=Path(f.name)
    os.replace(temp,output)
    return {'accounts':len(cards),'platforms':sorted({a['platform'] for a in d['accounts']}),'assets':len(assets),'output':str(output)}


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    try:
        print(json.dumps(build(args.manifest.resolve(),args.output.resolve())))
    except (ValueError,KeyError,TypeError,OSError) as error:
        parser.exit(1,str(error)+'\n')
