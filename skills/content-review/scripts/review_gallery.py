#!/usr/bin/env python3
"""Build a local, read-only review gallery. Python 3.9+, standard library only.

python review_gallery.py --manifest review.json --output review/index.html
Asset paths are filesystem paths relative to the manifest, not URL-encoded URLs.
Keep the generated HTML and its referenced assets together when moving a review.
"""

import argparse
import base64
import hashlib
import html
import json
import math
import os
from pathlib import Path
import sys
import tempfile
from urllib.parse import quote, urlsplit
from datetime import datetime
from zoneinfo import ZoneInfo
from review_delivery import attach as attach_delivery, lanes as delivery_lanes
from review_readiness import attach as attach_readiness, LABELS as REVIEW_LABELS


REVIEW_STATUSES = {"new", "draft", "needs-review", "revised", "changes-requested"}
PENDING_STATUSES = {"planned", "generating", "in-progress", "blocked", "held"}
STATUSES = REVIEW_STATUSES | PENDING_STATUSES | {"approved"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".svg", ".webp", ".gif", ".avif"}
AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".aac", ".ogg", ".flac"}
VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov", ".m4v"}

STYLE = """
:root { color-scheme:dark; --bg:#101014; --panel:#18181e; --ink:#f3f1f8; --muted:#aaa8b7;
 --line:#303039; --accent:#baa6ff; --soft:#292238; --green:#8cddb4; --mono:ui-monospace,SFMono-Regular,Consolas,monospace; }
* { box-sizing:border-box; } html { scroll-behavior:smooth; scroll-padding-top:24px; }
body { margin:0; background:var(--bg); color:var(--ink); font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }
main { max-width:1540px; margin:auto; padding:24px 28px 56px; }
a { color:var(--accent); text-underline-offset:3px; } a:hover { text-decoration-thickness:2px; }
:focus-visible { outline:3px solid var(--accent); outline-offset:4px; }
.brand { display:flex; align-items:center; gap:9px; font-size:13px; font-weight:650; letter-spacing:-.01em; }
.mark { display:grid; place-items:center; width:25px; height:25px; background:#292035; color:white; border-radius:4px; font-size:13px; }
.round { margin-left:auto; font-size:12px; color:var(--muted); font-weight:450; }
.hero { display:block; margin:15px 0 20px; }
h1 { font-size:clamp(26px,2.8vw,34px); line-height:1.08; letter-spacing:-.045em; margin:0 0 8px; font-weight:700; }
.lede { margin:0; color:var(--muted); max-width:760px; font-size:14px; }
nav { margin-top:16px; display:flex; gap:6px; flex-wrap:wrap; flex-shrink:0; }
nav a { display:flex; gap:9px; align-items:center; text-decoration:none; padding:9px 13px; background:var(--panel); border:1px solid var(--line); border-radius:4px; font-size:12px; color:var(--ink); white-space:nowrap; }
nav a:first-child { background:var(--soft); color:#e1d5ff; border-color:#695180; }
nav b { font-variant-numeric:tabular-nums; opacity:.65; }
.batch-tools { display:flex; flex-wrap:wrap; align-items:center; gap:10px; padding:12px 0; }
.batch-tools button { font:inherit; font-size:13px; padding:9px 13px; border:1px solid var(--line); border-radius:4px; background:var(--panel); color:var(--ink); cursor:pointer; }
.batch-tools button[aria-pressed="true"] { background:#7557bd; border-color:var(--accent); color:white; }
.batch-tools label { flex-wrap:wrap; }
.batch-tools select { max-width:min(440px, calc(100vw - 48px)); border:1px solid var(--line); border-radius:4px; background:var(--panel); padding:9px; }
.toolbar { display:flex; align-items:center; gap:16px; padding:8px 0; border-top:1px solid var(--line); border-bottom:1px solid var(--line); }
label { display:flex; align-items:center; gap:8px; font-size:12px; color:var(--muted); }
select { font:inherit; color:var(--ink); background:transparent; border:0; max-width:260px; padding:5px 22px 5px 2px; }
#count { margin-left:auto; color:var(--muted); font-size:12px; white-space:nowrap; }
.playback-tools { display:flex; flex-wrap:wrap; align-items:center; gap:6px; margin:14px 0 0; }
.playback-tools > span { color:var(--muted); font-size:12px; margin-right:6px; }
.playback-tools button { font:inherit; font-size:12px; min-width:44px; min-height:32px; padding:5px 9px; border:1px solid var(--line); border-radius:4px; background:var(--panel); color:var(--muted); cursor:pointer; }
.playback-tools button:hover { border-color:var(--accent); color:var(--accent); }
.playback-tools button[aria-pressed="true"] { background:var(--soft); border-color:#604477; color:var(--accent); font-weight:650; }
.detail-tools { display:flex; flex-wrap:wrap; align-items:center; gap:7px; margin:14px 0 0; }
.detail-tools > span { font-size:11px; color:var(--muted); margin-right:5px; }
.detail-tools button { font:inherit; font-size:11px; color:var(--muted); background:transparent; border:1px solid var(--line); border-radius:4px; padding:6px 10px; cursor:pointer; }
.detail-tools button:hover { border-color:var(--accent); color:var(--accent); }
.detail-tools button[aria-pressed="true"] { background:var(--soft); border-color:#604477; color:var(--accent); }
.detail-tools button[data-expand]::after { content:" +"; margin-left:4px; }
.detail-tools button[aria-pressed="true"]::after { content:" −"; }
.review-section { margin-top:22px; scroll-margin-top:22px; }
.section-head { display:flex; align-items:baseline; gap:10px; margin-bottom:12px; }
.section-head h2 { font-size:20px; letter-spacing:-.035em; margin:0; }
.section-head span { color:var(--muted); font-size:12px; }
.gallery { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:18px; align-items:start; }
.card { min-width:0; background:var(--panel); border:1px solid var(--line); border-radius:5px; overflow:hidden; box-shadow:0 3px 10px #24233b03; }
.card-head { padding:14px 17px 12px; }
.identity-row { display:flex; flex-wrap:wrap; gap:8px 10px; align-items:center; justify-content:space-between; margin-bottom:7px; }
.identity { display:flex; flex-wrap:wrap; align-items:center; gap:8px; min-width:0; color:var(--muted); font-size:12px; font-weight:550; letter-spacing:.025em; }
.identity a { color:inherit; text-decoration:none; overflow-wrap:anywhere; user-select:all; }
.copy-reference { font:inherit; font-size:11px; letter-spacing:normal; color:var(--accent); background:var(--soft); border:1px solid #604477; border-radius:3px; min-height:32px; padding:5px 9px; cursor:pointer; }
.mark svg { width:26px; height:26px; }
.copy-reference:hover { border-color:var(--accent); }
.copy-reference:disabled { cursor:wait; }
.sr-only { position:absolute; width:1px; height:1px; padding:0; margin:-1px; overflow:hidden; clip-path:inset(50%); white-space:nowrap; border:0; }
.card h3 { font-size:18px; line-height:1.3; letter-spacing:-.025em; margin:0; }
.badge { display:inline-flex; align-items:center; padding:4px 8px; border-radius:3px; background:var(--soft); color:var(--accent); font-size:10px; font-weight:650; flex-shrink:0; max-width:48%; overflow-wrap:anywhere; }
[data-lane="complete"] .badge { background:#18382e; color:var(--green); }
[data-lane="progress"] .badge { background:#403322; color:#e8c180; }
.stage { display:flex; align-items:center; gap:6px; font-size:11px; color:var(--muted); margin:8px 0 0; }
.stage-dot { width:5px; height:5px; border-radius:50%; background:currentColor; flex-shrink:0; }
.previews { padding:0 12px; }
figure { margin:0; min-width:0; }
figcaption { display:flex; justify-content:space-between; gap:8px; font-size:11px; padding:8px 4px 10px; color:var(--muted); }
figcaption a { text-decoration:none; font-weight:600; }
.media { display:flex; align-items:center; justify-content:center; background:#09090f; border-radius:4px; overflow:hidden; }
.media img,.media video { display:block; width:100%; height:460px; max-height:68vh; min-height:230px; object-fit:contain; }
.media audio { width:100%; margin:24px 12px; }
.pending { min-height:190px; display:flex; flex-direction:column; justify-content:center; align-items:center; gap:7px; color:var(--muted); border-radius:4px; background:repeating-linear-gradient(135deg,#211c2a,#211c2a 9px,#292233 9px,#292233 10px); text-align:center; padding:28px; }
.pending strong { font-size:15px; color:var(--ink); } .pending span { font-size:12px; max-width:220px; }
.focus { margin:0 16px 14px; padding:0 0 0 10px; border-left:2px solid #66517e; color:#bfb4d0; font-size:12px; line-height:1.6; }
.focus b { font-weight:650; }
.meta { padding:0 16px 14px; }
details { min-width:0; border-top:1px solid var(--line); }
summary { cursor:pointer; padding:11px 0; font-size:12px; font-weight:550; color:var(--ink); }
summary .hint { float:right; color:var(--muted); font-size:11px; font-weight:400; }
.detail-body { padding:0 0 12px; font-size:12px; color:var(--muted); overflow-wrap:anywhere; }
.detail-body p { margin:0 0 8px; } .detail-body p:last-child { margin-bottom:0; }
.caption,.prompt { white-space:pre-wrap; } .prompt { font-size:12px; line-height:1.65; }
.changes { padding-left:17px; margin:0; } .changes li+li { margin-top:4px; }
.input-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:12px; }
.input-grid .media img,.input-grid .media video { height:150px; min-height:0; }
.input-grid .media audio { margin:12px 4px; }
.input-grid figcaption { display:block; padding:6px 0; } .input-grid figcaption a { display:block; margin-top:3px; }
.generation { padding:10px 0; border-bottom:1px solid var(--line); }
.generation:first-child { padding-top:0; } .generation:last-child { border-bottom:0; padding-bottom:0; }
.generation-head { display:flex; gap:12px; justify-content:space-between; align-items:baseline; color:var(--ink); }
.generation-head strong { font-weight:600; font-size:12px; } .cost { max-width:50%; text-align:right; font-variant-numeric:tabular-nums; font-size:11px; color:var(--accent); }
.generation small { display:block; font-size:11px; margin-top:3px; } .job { font-family:ui-monospace,monospace; font-size:10px; color:var(--muted); }
.generation details { border:0; } .generation summary { padding:7px 0 0; font-size:11px; color:var(--accent); } .generation .prompt { margin-top:7px; }
.compare .media { margin-bottom:8px; } .compare .media video,.compare .media img { height:320px; }
.empty { padding:35px 0; color:var(--muted); }
.balances { font-size:12px; margin-top:18px; } .balances ul { list-style:none; padding:0; display:flex; flex-wrap:wrap; gap:18px; color:var(--muted); }
footer { margin-top:28px; padding-top:16px; border-top:1px solid var(--line); color:var(--muted); font-size:12px; }
[hidden] { display:none!important; }
@media(min-width:1550px) { .media img,.media video { height:490px; } }
@media(max-width:1100px) { .hero { display:block; } nav { margin-top:18px; } .gallery { grid-template-columns:repeat(2,minmax(0,1fr)); } }
@media(max-width:640px) { main { padding:20px 16px 40px; } .hero { margin-top:22px; } .gallery { grid-template-columns:minmax(0,1fr); } .toolbar { flex-wrap:wrap; gap:6px 12px; } label { max-width:100%; } select { max-width:190px; } #count { margin-left:0; width:100%; } .round { max-width:50%; text-align:right; } .media img,.media video { height:470px; max-height:66vh; } }
@media(prefers-reduced-motion:reduce) { html { scroll-behavior:auto; } }
@media(pointer:coarse) { .copy-reference,.playback-tools button { min-height:44px; } }
/* ViewPrinter review desk: compact controls, content-first hierarchy. */
.brand{font-size:11px;color:var(--muted);letter-spacing:.01em}.mark{width:21px;height:21px;background:transparent;border-radius:3px}.mark svg{width:21px;height:21px}.round{font:10px var(--mono)}
.lede{font-size:12px;line-height:1.6}.hero nav{gap:6px}.hero nav a{font-size:11px;padding:6px 9px;border-radius:3px}.hero nav b{font:10px var(--mono);opacity:1;color:var(--muted)}
.review-controls{border:1px solid var(--line);border-radius:5px;background:#15151b;margin-bottom:24px}.batch-row{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:12px 14px;flex-wrap:wrap}.batch-tools{padding:0;gap:5px;min-width:0}.batch-tools button{padding:7px 10px;font-size:11px;min-height:34px;background:#212128}.batch-tools button[aria-pressed=true]{background:var(--soft);border-color:#695180;color:#e1d5ff}.batch-tools select{font-size:11px;padding:7px;max-width:260px;min-width:0;min-height:34px;background:var(--bg)}.batch-picker{min-width:0}.playback-tools{margin:0;gap:2px}.playback-tools>span{font:10px var(--mono);margin-right:6px;color:var(--muted)}.playback-tools button{border-color:transparent;border-radius:3px;background:transparent;min-width:32px;min-height:30px;padding:4px 6px;font:11px var(--mono)}.playback-tools button[aria-pressed=true]{background:var(--soft);border-color:#695180}
.filter-row{display:flex;align-items:center;gap:12px;flex-wrap:wrap;padding:10px 14px;border-top:1px solid var(--line)}.status-tools,.variant-tools{display:flex;align-items:center;gap:12px;flex-wrap:wrap;min-width:0}.filter-row label{font-size:10px;gap:6px;min-width:0;flex-wrap:wrap}.filter-row select{font-size:11px;max-width:230px;border:1px solid var(--line);border-radius:3px;background:var(--bg);padding:6px;min-width:0}.filter-row #count{font:10px var(--mono)}
.advanced-tools{padding:0 14px}.advanced-tools>summary{font-size:11px;color:var(--muted);padding:9px 0}.advanced-tools .hint{font-size:10px}.advanced-body{padding-bottom:12px}.advanced-body .toolbar{border:0;padding:4px 0 9px;gap:18px;flex-wrap:wrap}.advanced-body .toolbar select{font-size:11px;border:1px solid var(--line);padding:5px;background:var(--bg);border-radius:3px}.advanced-body .detail-tools{margin:0;gap:6px}.detail-tools button{font-size:10px;padding:5px 8px}.section-head{border-bottom:1px solid var(--line);padding-bottom:11px;margin-bottom:16px;gap:9px}.section-head h2{font-size:15px;letter-spacing:-.25px;font-weight:600}.section-count{font:10px var(--mono);padding:3px 6px;background:var(--soft);border-radius:3px;color:var(--accent)!important}.review-section{margin-top:24px}.card{box-shadow:none}.card-head{padding:13px 14px}.identity-row{margin-bottom:9px;gap:7px}.identity{font:10px var(--mono);gap:8px;letter-spacing:0}.identity a{color:var(--muted)}.copy-reference{font:10px var(--mono);background:#22202a;border-color:#51415f;color:#cfbaff;min-height:28px;padding:4px 7px}.badge{border-radius:3px;font:9px var(--mono);padding:3px 5px;max-width:48%}.stage{font:10px/1.5 var(--mono);color:var(--muted);margin-top:9px}.card[data-lane=scheduled] .badge{background:#1b3029;color:var(--green)}.card[data-lane=changes-requested] .badge{background:#37232a;color:#f1a4b3}.card[data-lane=production] .badge{background:#322a21;color:#edc48b}.previews{padding:0 10px}.media{border-radius:3px;background:#08080b}.meta{font-size:11px;padding:0 14px 12px}.meta b{font-weight:500;color:var(--muted)}.detail-body{line-height:1.65}.meta summary{padding:10px 0;font-size:11px}.focus{margin-top:2px}.pending{background:#201c28;border:1px dashed #574264}.generation{padding:12px 0}.generation .prompt{font-size:11px}.meta .caption{color:#dfdbe8}.meta h4{font-size:11px;color:var(--ink);margin:14px 0 8px}.detail-tools button{touch-action:manipulation}
@media(min-width:1550px){.media img,.media video{height:510px}}
@media(max-width:1100px){.hero nav{margin-top:12px}.batch-row{gap:10px}.batch-tools select{max-width:260px}.playback-tools{margin-left:0}.gallery{gap:16px}}
@media(max-width:640px){main{padding:20px 14px 40px}.hero{margin:14px 0 18px}.hero nav a{font-size:10px;padding:6px 7px}.hero h1{font-size:28px}.review-controls{margin-bottom:20px}.batch-row{display:block;padding:11px}.batch-tools{gap:5px}.batch-picker{width:100%;margin-top:4px}.batch-picker select{width:100%;max-width:100%}.playback-tools{margin-top:10px;gap:2px}.playback-tools>span{font-size:9px;margin-right:3px}.playback-tools button{min-width:29px;font-size:10px;padding:5px}.filter-row{padding:10px 11px;gap:10px}.filter-row label{width:100%;display:flex;justify-content:space-between;gap:5px}.status-tools,.variant-tools{width:100%;gap:10px}.filter-row select{width:65%;max-width:100%}.filter-row #count{margin:0;width:auto}.advanced-tools{padding:0 11px}.advanced-tools .hint{font-size:9px}.advanced-body .toolbar label{width:100%;justify-content:space-between}.advanced-body .toolbar select{max-width:65%}.round{font-size:9px}.card h3{font-size:18px}.media img,.media video{height:490px;max-height:70vh}.gallery{gap:18px}.section-head{margin-bottom:14px}.card-head{padding:13px 14px}.focus{font-size:12px}.detail-tools>span{width:100%;margin-bottom:3px}}
@media(pointer:coarse){.copy-reference,.playback-tools button,.batch-tools button{min-height:40px}}


.embedded .brand{display:none}.embedded .hero{margin-top:0}
@media(max-width:640px){.playback-tools>span{width:100%;margin:0 0 4px}.playback-tools{gap:3px}.playback-tools button{flex:1;min-width:0}.embedded main{padding-top:18px}}

"""

SCRIPT = """
'use strict';
document.documentElement.classList.toggle('embedded',window.self!==window.top);
const videos = Array.from(document.querySelectorAll('video,audio'));
const speedButtons = Array.from(document.querySelectorAll('[data-playback-speed]'));
let playbackSpeed = 1;
function applyPlaybackSpeed(media) {
  media.defaultPlaybackRate=playbackSpeed;
  media.playbackRate=playbackSpeed;
  if ('preservesPitch' in media) media.preservesPitch=true;
}
speedButtons.forEach(button => button.addEventListener('click', () => {
  playbackSpeed=Number(button.dataset.playbackSpeed);
  videos.forEach(applyPlaybackSpeed);
  speedButtons.forEach(option=>option.setAttribute('aria-pressed',String(Number(option.dataset.playbackSpeed)===playbackSpeed)));
}));
videos.forEach(media => {
  applyPlaybackSpeed(media);
  media.addEventListener('loadedmetadata',()=>applyPlaybackSpeed(media));
});
document.addEventListener('play', event => {
  if (['VIDEO','AUDIO'].includes(event.target.tagName)) {
    applyPlaybackSpeed(event.target);
    videos.forEach(video => { if (video !== event.target) video.pause(); });
  }
}, true);
document.querySelectorAll('video').forEach(video => {
  video.addEventListener('loadedmetadata', () => {
    if (!video.hasAttribute('poster') && video.paused && !video.played.length && video.duration > 0) {
      video.currentTime = Math.min(0.05, video.duration / 2);
    }
  }, { once: true });
});
if ('IntersectionObserver' in window) {
  const previews = new IntersectionObserver(entries => {
    entries.forEach(({target,isIntersecting}) => {
      if (isIntersecting && !target.closest('[hidden]')) { target.preload='metadata';previews.unobserve(target); }
    });
  }, {rootMargin:'180px'});
  document.querySelectorAll('.previews video,.previews audio').forEach(v=>previews.observe(v));
}
const copyTimers = new WeakMap();
function copySelectedReference(button) {
  const selection=window.getSelection();
  const saved=Array.from({length:selection.rangeCount},(_,i)=>selection.getRangeAt(i).cloneRange());
  const range=document.createRange();
  range.selectNodeContents(button.dataset.copyText !== undefined ? button.closest('section').querySelector('.caption') : button.closest('.identity').querySelector('a'));
  selection.removeAllRanges();
  selection.addRange(range);
  let copied=false;
  try { copied=document.execCommand('copy'); } catch (_) { /* Keep the ID selected for manual copy. */ }
  if (copied) {
    selection.removeAllRanges();
    saved.forEach(previous=>selection.addRange(previous));
  }
  return copied;
}
document.querySelectorAll('[data-copy-reference],[data-copy-text]').forEach(button => {
  button.addEventListener('click', async () => {
    const reference=button.dataset.copyReference || button.dataset.copyText;
    const originalLabel=button.dataset.originalLabel || button.textContent;button.dataset.originalLabel=originalLabel;
    const status=document.getElementById('copy-status');
    const restoreFocus=document.activeElement===button;
    clearTimeout(copyTimers.get(button));
    button.disabled=true;
    let copied=false;
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(reference);
        copied=true;
      }
    } catch (_) { /* Local files or browser permissions may require selection copy. */ }
    if (!copied) copied=copySelectedReference(button);
    button.disabled=false;
    if (restoreFocus) button.focus({preventScroll:true});
    button.textContent=copied ? 'Copied' : originalLabel;
    status.textContent=copied ? `Copied ${reference}` : `ID ${reference} selected. Press Command+C or Ctrl+C to copy.`;
    button.title=copied ? `Copied ${reference}` : status.textContent;
    copyTimers.set(button,setTimeout(()=>{
      button.textContent=originalLabel;
      button.title=`Copy reference ${reference}`;
    },1800));
  });
});
const statusFilter = document.getElementById('status-filter');
const formatFilter = document.getElementById('format-filter');
const cards = Array.from(document.querySelectorAll('.card'));
const batchFilter = document.getElementById('batch-filter');
const batchButtons = Array.from(document.querySelectorAll('[data-batch-view]'));
const deliveryFilter = document.getElementById('delivery-filter');
const variantFilter = document.getElementById('variant-filter');
const sourceFilter = document.getElementById('source-filter');
variantFilter?.addEventListener('change', filterCards);
sourceFilter?.addEventListener('change', filterCards);
deliveryFilter?.addEventListener('change', filterCards);
function filterCards() {
  let shown = 0;
  cards.forEach(card => {
    const visible = (!variantFilter?.value || card.dataset.variant === variantFilter.value) &&
      (!sourceFilter?.value || card.dataset.source === sourceFilter.value) &&
      (!batchFilter?.value || card.dataset.batch === batchFilter.value) &&
      (!statusFilter.value || card.dataset.status === statusFilter.value) &&
      (!formatFilter.value || card.dataset.format === formatFilter.value) &&
      (!deliveryFilter?.value || (card.dataset.delivery || '').split(' ').includes(deliveryFilter.value));
    card.hidden = !visible;
    if (visible) shown += 1;
    else card.querySelectorAll('video,audio').forEach(video => video.pause());
  });
  document.querySelectorAll('.review-section').forEach(section => {
    const count=section.querySelectorAll('.card:not([hidden])').length;
    section.hidden=count===0;
    section.querySelector('.section-count').textContent=count;
    const link=document.querySelector('nav a[href="#'+section.id+'"]');
    if (link) { link.hidden=count===0; link.querySelector('b').textContent=count; }
  });
  document.getElementById('count').textContent = `${shown} of ${cards.length} items`;
  document.getElementById('empty').hidden = shown !== 0;
  batchButtons.forEach(button => button.setAttribute('aria-pressed', String(button.dataset.batchView === batchFilter?.value)));
  if (deliveryFilter) Array.from(deliveryFilter.options).forEach(option => {
    const total=cards.filter(card => (!batchFilter?.value || card.dataset.batch===batchFilter.value) &&
      (!option.value || (card.dataset.delivery || '').split(' ').includes(option.value))).length;
    option.textContent=option.dataset.label+' ('+total+')';
  });
}
function selectBatch(value) {
  if (batchFilter) batchFilter.value=value;
  statusFilter.value='';
  formatFilter.value='';
  filterCards();
}
batchFilter?.addEventListener('change', () => selectBatch(batchFilter.value));
batchButtons.forEach(button => button.addEventListener('click', () => selectBatch(button.dataset.batchView)));
function revealLinkedCard() {
  let anchor;
  try { anchor=decodeURIComponent(location.hash.slice(1)); } catch (_) { return; }
  const card=document.getElementById(anchor);
  if (!card?.classList.contains('card')) return;
  if (deliveryFilter) deliveryFilter.value='';
  selectBatch(card.dataset.batch || '');
  requestAnimationFrame(() => card.scrollIntoView({block:'start'}));
}
window.addEventListener('hashchange', revealLinkedCard);
statusFilter.addEventListener('change', filterCards);
formatFilter.addEventListener('change', filterCards);
const detailButtons = Array.from(document.querySelectorAll('[data-expand]'));
function disclosureTargets(kind) {
  return Array.from(document.querySelectorAll(kind === 'all' ? '.card details' : '.card details[data-detail="'+kind+'"]'));
}
function syncDetailButtons() {
  detailButtons.forEach(button => {
    const targets=disclosureTargets(button.dataset.expand);
    button.setAttribute('aria-pressed', String(targets.length>0 && targets.every(d=>d.open)));
  });
}
function setDetails(targets, open) {
  targets.forEach(detail => {
    detail.open=open;
    if (open) {
      let parent=detail.parentElement.closest('details');
      while (parent) { parent.open=true; parent=parent.parentElement.closest('details'); }
    } else {
      detail.querySelectorAll('video,audio').forEach(media=>media.pause());
    }
  });
  syncDetailButtons();
}
detailButtons.forEach(button => button.addEventListener('click', () => {
  const targets=disclosureTargets(button.dataset.expand);
  setDetails(targets, !targets.every(detail=>detail.open));
}));
document.querySelector('[data-collapse-all]')?.addEventListener('click',()=>setDetails(disclosureTargets('all'),false));
document.querySelectorAll('details').forEach(details => {
  details.addEventListener('toggle', () => {
    if (!details.open) details.querySelectorAll('video,audio').forEach(video => video.pause());
    syncDetailButtons();
  });
});
filterCards();
revealLinkedCard();
"""


def escaped(value):
    return html.escape(str(value), quote=True)


def required_text(obj, name, context):
    value = obj.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{context}.{name} must be a nonempty string")
    return value


def version_text(value, context):
    if isinstance(value, bool) or not isinstance(value, (str, int)) or not str(value).strip():
        raise ValueError(f"{context} must be a nonempty string or integer")
    return str(value)


def asset_path(raw, base, context, kind):
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError(f"{context} must be a local filesystem path")
    if any(ord(char) < 32 for char in raw) or "\\" in raw:
        raise ValueError(f"{context} contains invalid path characters; use forward slashes")
    # Require filesystem paths, not URLs (including file:, data:, and protocol-relative URLs).
    if urlsplit(raw).scheme or raw.startswith("//"):
        raise ValueError(f"{context} must be local; asset URLs are not allowed")
    path = (base / raw).resolve()
    if not path.is_file():
        raise ValueError(f"{context}: asset does not exist: {path}")
    allowed = {"video": VIDEO_EXTENSIONS, "image": IMAGE_EXTENSIONS, "audio": AUDIO_EXTENSIONS}[kind]
    if path.suffix.lower() not in allowed:
        raise ValueError(f"{context}: unsupported {kind} extension {path.suffix!r}")
    return path


def prepare_batches(manifest):
    batches = manifest.get("batches", [])
    if not isinstance(batches, list):
        raise ValueError("manifest.batches must be a list ordered newest first")
    result, seen = [], set()
    for index, raw in enumerate(batches):
        context = f"batches[{index}]"
        if not isinstance(raw, dict):
            raise ValueError(f"{context} must be an object")
        batch = {key: required_text(raw, key, context) for key in ("id", "label")}
        if batch["id"] in seen:
            raise ValueError(f"duplicate batch id: {batch['id']}")
        seen.add(batch["id"])
        result.append(batch)
    return result


def prepare_manifest(manifest, base):
    if not isinstance(manifest, dict):
        raise ValueError("manifest must be an object")
    title = required_text(manifest, "title", "manifest")
    review_round = version_text(manifest.get("round"), "manifest.round")
    raw_items = manifest.get("items")
    if not isinstance(raw_items, list):
        raise ValueError("manifest.items must be a list")
    batches = prepare_batches(manifest)
    batch_order = {batch["id"]: index for index, batch in enumerate(batches)}
    items, seen = [], set()
    for index, raw in enumerate(raw_items):
        context = f"items[{index}]"
        if not isinstance(raw, dict):
            raise ValueError(f"{context} must be an object")
        item = {key: required_text(raw, key, context) for key in ("id", "title", "format", "status")}
        if item["status"].casefold() not in STATUSES:
            raise ValueError(f"{context}.status {item['status']!r} is not one of {', '.join(sorted(STATUSES))}; "
                             "leave rejected or withdrawn items out of the review")
        if batches:
            item["batch"] = required_text(raw, "batch", context)
            if item["batch"] not in batch_order:
                raise ValueError(f"{context}.batch must reference a declared batch")
        elif "batch" in raw:
            raise ValueError(f"{context}.batch requires manifest.batches")
        item["version"] = version_text(raw.get("version"), f"{context}.version")
        item['_placements'] = raw.get('_placements', [])
        item['_progress'] = raw.get('_progress', {})
        item['_readiness'] = raw.get('_readiness', {})
        item['captions'] = raw.get('captions', {})
        for field in ('variant','sourceId','contributor','sourceLabel'): item[field] = raw.get(field, '')
        item['_deliveryTimezone'] = raw.get('_deliveryTimezone', 'UTC')
        identity = (item["id"], item["version"])
        if identity in seen:
            raise ValueError(f"duplicate id/version: {identity!r}")
        seen.add(identity)
        if raw.get("src"):
            prepare_media(raw, item, base, context)
        elif item["status"].casefold() in PENDING_STATUSES:
            item["kind"] = "pending"
        else:
            raise ValueError(f"{context}.src required for reviewable or approved content")
        item["stage"] = raw.get("stage", "unspecified")
        if not isinstance(item["stage"], str) or item["stage"] not in STAGES:
            raise ValueError(f"{context}.stage must be one of {list(STAGES)}")
        for field in ("reviewFocus", "nextStep"):
            item[field] = raw.get(field, "")
            if not isinstance(item[field], str):
                raise ValueError(f"{context}.{field} must be a string")
        item["inputs"] = []
        inputs = raw.get("inputs", [])
        if not isinstance(inputs, list):
            raise ValueError(f"{context}.inputs must be a list")
        for i, source in enumerate(inputs):
            if not isinstance(source, dict):
                raise ValueError(f"{context}.inputs[{i}] must be an object")
            target = {"label": required_text(source, "label", context)}
            prepare_media(source, target, base, f"{context}.inputs[{i}]")
            item["inputs"].append(target)
        item["generation"] = prepare_generation(raw.get("generation", []), context)
        if "previous" in raw:
            previous = raw["previous"]
            if not isinstance(previous, dict):
                raise ValueError(f"{context}.previous must be an object")
            item["previous"] = {"version": version_text(previous.get("version"), f"{context}.previous.version")}
            prepare_media(previous, item["previous"], base, f"{context}.previous")
        changes = raw.get("changes", [])
        if not isinstance(changes, list) or any(not isinstance(note, str) for note in changes):
            raise ValueError(f"{context}.changes must be a list of strings")
        item["changes"] = changes
        caption = raw.get("caption", "")
        if not isinstance(caption, str):
            raise ValueError(f"{context}.caption must be a string")
        item["caption"] = caption
        items.append(item)
    if batches:
        if set(batch_order) != {item["batch"] for item in items}:
            raise ValueError("each declared batch must contain at least one item")
        # Batch recency wins over revision status; retain editorial order within a batch.
        items.sort(key=lambda item: batch_order[item["batch"]])
    else:
        # Preserve the existing ordering for legacy single-batch manifests.
        items.sort(key=lambda item: not (item["status"].casefold() == "revised" or item.get("previous") or item["changes"]))
    return title, review_round, items


def prepare_media(source, destination, base, context):
    kind = source.get("kind")
    if kind not in ("image", "video", "audio"):
        raise ValueError(f"{context}.kind must be image, video or audio")
    destination["kind"] = kind
    destination["src"] = asset_path(source.get("src"), base, f"{context}.src", kind)
    if "poster" in source:
        destination["poster"] = asset_path(source["poster"], base, f"{context}.poster", "image")


def local_url(path, output):
    # A leading ./ prevents filenames with ':' from being interpreted as URL schemes.
    relative = Path(os.path.relpath(path, output.parent)).as_posix()
    return escaped("./" + quote(relative, safe="/"))


STAGES = {"concept": "Concept", "source": "Source assets", "demo": "Demo capture",
          "edit": "Edit", "final": "Final export", "unspecified": "Stage not recorded"}
LANES = {"review": "Needs review", "progress": "In progress", "complete": "Complete"}


def lane(item):
    if item.get('_readiness'): return item['_readiness']['state']
    status = item["status"].casefold()
    if status == "approved" and item["stage"] == "final":
        return "complete"
    return "review" if status in REVIEW_STATUSES else "progress"


def prepare_generation(records, context):
    if not isinstance(records, list):
        raise ValueError(f"{context}.generation must be a list")
    result = []
    for record in records:
        if not isinstance(record, dict):
            raise ValueError(f"{context}.generation entries must be objects")
        entry = {key: required_text(record, key, context) for key in ("asset", "platform", "model")}
        for field in ("jobId", "prompt", "note"):
            entry[field] = record.get(field, "")
            if not isinstance(entry[field], str):
                raise ValueError(f"{context}.generation.{field} must be a string")
        cost = record.get("cost", {"status": "unknown"})
        if not isinstance(cost, dict) or cost.get("status") not in {"reported", "estimated", "unknown"}:
            raise ValueError(f"{context}.generation.cost status must be reported, estimated or unknown")
        if cost["status"] != "unknown":
            amount = cost.get("amount")
            if isinstance(amount, bool) or not isinstance(amount, (int,float)) or not math.isfinite(amount) or amount < 0:
                raise ValueError(f"{context}.generation.cost amount must be finite and nonnegative")
            required_text(cost, "unit", context)
        entry["cost"] = cost
        result.append(entry)
    return result


def cost_label(cost):
    if cost["status"] == "unknown":
        return "Cost not reported"
    amount = format(cost["amount"], ".2f" if cost["unit"] == "USD" else ".6g")
    suffix = " · estimated" if cost["status"] == "estimated" else " · reported"
    return amount + " " + cost["unit"] + suffix


DETAIL_KINDS = {"Tools & credits":"tools", "Copy":"copy", "Input assets":"inputs",
                "What changed":"changes", "Previous version":"previous", "Prompt":"prompts"}


def disclosure(title, body, hint="", cls=""):
    category = DETAIL_KINDS.get(title, "other")
    return f'<details class="{cls}" data-detail="{category}"><summary>{escaped(title)}<span class="hint">{escaped(hint)}</span></summary><div class="detail-body">{body}</div></details>'


def render_media(media, title, label, output, preload="metadata"):
    src = local_url(media["src"], output)
    kind = media["kind"]
    if kind == "video":
        poster = f' poster="{local_url(media["poster"], output)}"' if media.get("poster") else ""
        preview = f'<video controls playsinline preload="{preload}" aria-label="{escaped(title)} — {escaped(label)}"{poster}><source src="{src}">Use the file link to play this video.</video>'
    elif kind == "audio":
        preview = f'<audio controls preload="none" aria-label="{escaped(title)} — {escaped(label)}" src="{src}"></audio>'
    else:
        preview = f'<img src="{src}" alt="{escaped(title)} — {escaped(label)}" loading="lazy">'
    return f'<figure><div class="media">{preview}</div><figcaption><span>{escaped(label)}</span><a href="{src}" target="_blank" rel="noopener noreferrer">Open file ↗</a></figcaption></figure>'


def render_card(item, output):
    identity = json.dumps([item["id"], item["version"]], ensure_ascii=True)
    reference = f"{item['id']} / v{item['version']}"
    anchor = "item-" + hashlib.sha256(identity.encode()).hexdigest()[:20]
    if item["kind"] == "pending":
        current = f'<div class="pending"><strong>{escaped(STAGES[item["stage"]])}</strong><span>{escaped(item["nextStep"] or "Output is not ready yet.")}</span></div>'
    else:
        current = render_media(item, item["title"], f'{item["format"]} · v{item["version"]}', output, preload='none')
    details = []
    if item["changes"]:
        notes = "".join(f"<li>{escaped(note)}</li>" for note in item["changes"])
        details.append(disclosure("What changed", f'<ul class="changes">{notes}</ul>', str(len(item["changes"]))))
    if item.get("previous"):
        media = item["previous"]
        details.append(disclosure("Previous version", render_media(media, item["title"], "Previous · v"+media["version"], output, preload="none"), "v"+media["version"], "compare"))
    if item["inputs"]:
        previews = ''.join(render_media(source, item["title"], source["label"], output, preload="none") for source in item["inputs"])
        details.append(disclosure("Input assets", '<div class="input-grid">'+previews+'</div>', str(len(item["inputs"]))))
    if item["generation"]:
        rows = []
        for g in item["generation"]:
            prompt = disclosure("Prompt", '<p class="prompt">'+escaped(g["prompt"])+"</p>") if g["prompt"] else ""
            job = f'<small class="job">Job {escaped(g["jobId"])}</small>' if g["jobId"] else ""
            note = f'<small>{escaped(g["note"])}</small>' if g["note"] else ""
            rows.append(f'<div class="generation"><div class="generation-head"><strong>{escaped(g["asset"])}</strong><span class="cost">{escaped(cost_label(g["cost"]))}</span></div><small>{escaped(g["platform"])} · {escaped(g["model"])}</small>{job}{note}{prompt}</div>')
        platforms = str(len(item['generation'])) + ' assets'
        details.append(disclosure("Tools & credits", ''.join(rows), platforms))
    if item["captions"]:
        blocks = []
        for platform, native in item["captions"].items():
            native = {'caption': native} if isinstance(native, str) else native
            title = f'<p><b>Title</b> {escaped(native["title"])}</p>' if native.get('title') else ''
            copy = native.get('caption', '')
            blocks.append(f'<section><h4>{escaped(platform.title())}</h4>{title}<p class="caption">{escaped(copy)}</p><button type="button" class="copy-reference" data-copy-text="{escaped(copy)}">Copy {escaped(platform.title())} description</button></section>')
        details.append(disclosure("Copy", ''.join(blocks), 'Platform native'))
    elif item["caption"]:
        details.append(disclosure("Copy", f'<p class="caption">{escaped(item["caption"])}</p>'))
    focus = f'<p class="focus"><b>Review:</b> {escaped(item["reviewFocus"])}</p>' if item["reviewFocus"] else ""
    status = item['status'].replace('-', ' ').capitalize()
    placements = item.get('_placements', [])
    delivery = ' '.join(delivery_lanes(placements))
    readiness = item.get('_readiness')
    if readiness:
        status = readiness['label']
        delivery = readiness['state'] + (' active' if readiness.get('active') else '')
        count = readiness['accepted']; required = readiness['required']
        if readiness['state'] == 'scheduled':
            text = 'Scheduling complete · ' + str(count) + ' destinations handed to ViewPrinter'
        elif count:
            text = str(count) + ' of ' + str(required) + ' destinations scheduled'
        else:
            text = readiness['label']
        placement_html = '<div class="meta" style="padding-top:12px"><b>' + escaped(text) + '</b></div>'
    else:
        rows = []
        for placement in placements:
            def stamp(field):
                value = placement.get(field)
                if not value:
                    return ''
                parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
                if parsed.tzinfo is None:
                    raise ValueError('Delivery timestamps require a timezone')
                return parsed.astimezone(ZoneInfo(item['_deliveryTimezone'])).strftime('%b %d, %Y %I:%M %p %Z')
            url = placement.get('url') or ''
            link = f' · <a href="{escaped(url)}" target="_blank" rel="noopener noreferrer">View post</a>' if urlsplit(url).scheme in ('https', 'http') else ''
            when = ('Published ' + stamp('publishedAt')) if placement.get('publishedAt') else ('Scheduled ' + stamp('scheduledAt')) if placement.get('scheduledAt') else 'Time unverified'
            checked = stamp('checkedAt')
            rows.append(f'<p><strong>{escaped(placement.get("platform") or "Platform unverified")} · {escaped(placement.get("accountName") or placement["accountId"])}</strong><br>{escaped(placement.get("status", "unknown"))} · {escaped(when)}{link}<br><small>Checked: {escaped(checked or "not yet verified")}</small></p>')
        placement_html = '<div class="meta" style="padding-top:12px">' + ''.join(rows) + '</div>' if rows else ''
        progress = item.get('_progress') or {}
        if progress:
            issues = ', '.join(progress.get('issues', [])).replace('-', ' ')
            heading = progress.get('state', '').replace('-', ' ').capitalize()
            copy_state = progress.get('copy', 'unverified').replace('-', ' ')
            placement_html = f'<div class="meta" style="padding-top:12px"><b>{escaped(heading)}</b> · Native copy: {escaped(copy_state)}' + (f'<p>{escaped(issues)}</p>' if issues else '') + '</div>' + (disclosure('Delivery receipts', placement_html) if rows else '')
    return f'''<article class="card" id="{anchor}" data-delivery="{delivery}" data-status="{escaped(item['status'])}" data-format="{escaped(item['format'])}" data-lane="{lane(item)}" data-batch="{escaped(item.get('batch', ''))}" data-variant="{escaped(item.get('variant', ''))}" data-source="{escaped(item.get('sourceId', ''))}">
<div class="card-head"><div class="identity-row"><span class="identity"><a href="#{anchor}">{escaped(reference)}</a><button type="button" class="copy-reference" data-copy-reference="{escaped(reference)}" aria-label="Copy reference {escaped(reference)}" title="Copy reference {escaped(reference)}">Copy ID</button></span><span class="badge">{escaped(status)}</span></div><h3>{escaped(item['title'])}</h3><p class="stage"><span class="stage-dot"></span>{escaped(STAGES[item['stage']])}</p></div>
<div class="previews">{current}</div>{focus}{placement_html}<div class="meta">{''.join(details)}</div></article>'''


def build_gallery(manifest_path, output_path):
    manifest_path = Path(manifest_path).resolve()
    output = Path(output_path).resolve()
    if output.suffix.lower() not in (".html", ".htm"):
        raise ValueError("output must have an .html or .htm extension")
    with manifest_path.open(encoding="utf-8") as handle:
        manifest = json.load(handle)
    archived = {b['id'] for b in manifest.get('batches', []) if b.get('lifecycle') == 'archived'}
    manifest['items'] = [i for i in manifest['items'] if i.get('batch') not in archived]
    manifest['batches'] = [b for b in manifest.get('batches', []) if b['id'] not in archived]
    attach_delivery(manifest, manifest_path.parent)
    is_social = (manifest.get('reviewHub') or {}).get('kind') in {'social-content','influencer'}
    if is_social:
        for raw in manifest.get('items', []):
            attach_readiness({'items':[raw]}, raw.get('_placements', []))
    title, review_round, items = prepare_manifest(manifest, manifest_path.parent)
    focus = manifest.get("focus", "Review by item ID. Send feedback in the conversation.")
    if not isinstance(focus, str):
        raise ValueError("manifest.focus must be a string")
    protected = {manifest_path}
    for item in items:
        for media in (item, item.get("previous", {}), *item["inputs"]):
            protected.update(media[key] for key in ("src", "poster") if key in media)
    if output in protected:
        raise ValueError("output must not overwrite the manifest or a review asset")
    def options(key):
        return "".join(f'<option value="{escaped(value)}">{escaped(value)}</option>' for value in sorted({item[key] for item in items}, key=str.casefold))
    batches = prepare_batches(manifest)
    batch_controls = ""
    if batches:
        latest = batches[0]["id"]
        counts = {batch["id"]: sum(item["batch"] == batch["id"] for item in items) for batch in batches}
        batch_options = ''.join(
            f'<option value="{escaped(batch["id"])}"' + (' selected' if index == 0 else '') +
            f'>{"Latest · " if index == 0 else ""}{escaped(batch["label"])} ({counts[batch["id"]]})</option>'
            for index, batch in enumerate(batches))
        batch_controls = (f'<div class="batch-tools" role="group" aria-label="Choose content batch">'
            f'<button type="button" data-batch-view="{escaped(latest)}" aria-pressed="true">Latest batch · {counts[latest]}</button>'
            f'<button type="button" data-batch-view="" aria-pressed="false">All content · {len(items)}</button>'
            f'<label class="batch-picker" for="batch-filter"><span class="sr-only">Batch</span><select id="batch-filter">{batch_options}'
            f'<option value="">All content ({len(items)})</option></select></label></div>')
    variant_controls = ''
    variants = sorted({i.get('variant') for i in items if i.get('variant')})
    if variants:
        variant_controls += '<label>Variant<select id="variant-filter"><option value="">All variants</option>' + ''.join(f'<option>{escaped(v)}</option>' for v in variants) + '</select></label>'
    sources = {i.get('sourceId'): i.get('sourceLabel') or i.get('contributor') for i in items if i.get('sourceId')}
    if len(sources) > 1:
        variant_controls += '<label>Contribution<select id="source-filter"><option value="">All contributions</option>' + ''.join(f'<option value="{escaped(k)}">{escaped(v)}</option>' for k,v in sources.items()) + '</select></label>'
    if variant_controls: variant_controls = '<div class="variant-tools">' + variant_controls + '</div>'
    sections, links = [], []
    lanes = {k: REVIEW_LABELS[k] for k in ['changes-requested','needs-review','needs-copy','ready','production','scheduled','excluded']} if is_social else LANES
    for key, label in lanes.items():
        group = [item for item in items if lane(item)==key]
        if not group:
            continue
        links.append(f'<a href="#section-{key}">{label}<b>{len(group)}</b></a>')
        sections.append(f'<section class="review-section" id="section-{key}"><div class="section-head"><h2>{label}</h2><span class="section-count">{len(group)}</span></div><div class="gallery">'+''.join(render_card(item,output) for item in group)+'</div></section>')
    balances = manifest.get("balances", [])
    if not isinstance(balances, list):
        raise ValueError("manifest.balances must be a list")
    balance_rows = []
    for balance in balances:
        if not isinstance(balance, dict):
            raise ValueError("balance must be an object")
        platform = required_text(balance, "platform", "balance")
        observed = required_text(balance, "asOf", "balance")
        unit = required_text(balance, "unit", "balance")
        amount = balance.get("amount")
        if isinstance(amount,bool) or not isinstance(amount,(int,float)) or not math.isfinite(amount) or amount<0:
            raise ValueError("balance amount must be finite and nonnegative")
        balance_rows.append(f'<li><strong>{escaped(platform)}</strong> · {escaped(format(amount,".6g"))} {escaped(unit)} remaining<br>As of {escaped(observed)}</li>')
    balance_html = '<div class="balances">'+disclosure('Platform balance snapshots','<ul>'+''.join(balance_rows)+'</ul>')+'</div>' if balances else ''
    available = {
        "tools": any(item["generation"] for item in items),
        "copy": any(item["caption"] or item["captions"] for item in items),
        "inputs": any(item["inputs"] for item in items),
        "changes": any(item["changes"] for item in items),
        "previous": any(item.get("previous") for item in items),
        "prompts": any(g["prompt"] for item in items for g in item["generation"]),
    }
    controls = ''.join(f'<button type="button" data-expand="{key}" aria-pressed="false">{escaped(label)}</button>'
                       for label,key in DETAIL_KINDS.items() if available[key])
    bulk_controls = ('<div class="detail-tools" role="group" aria-label="Expand details across all items"><span>Across all items</span>'+controls+
                     '<button type="button" data-expand="all" aria-pressed="false">All details</button><button type="button" data-collapse-all>Collapse all</button></div>') if controls else ''
    has_playback = any(media.get('kind') in ('video', 'audio') for item in items
                       for media in (item, item.get('previous', {}), *item['inputs']))
    speed_controls = ('<div class="playback-tools" role="group" aria-label="Playback speed for all videos and audio"><span>Playback</span>'+
                      ''.join(f'<button type="button" data-playback-speed="{rate}" aria-pressed="{str(rate == 1).lower()}" aria-label="Play all media at {rate} times speed">{rate}×</button>'
                              for rate in (0.5, 0.75, 1, 1.25, 1.5, 2))+'</div>') if has_playback else ''
    script_hash = base64.b64encode(hashlib.sha256(SCRIPT.encode()).digest()).decode()
    delivery_controls = ''
    if is_social or manifest.get('delivery'):
        choices = [('', 'All content'), ('active', 'Active review'), *REVIEW_LABELS.items()] if is_social else [('', 'All content'), ('unscheduled', 'Unscheduled'), ('scheduled', 'Scheduled'), ('attention', 'Needs attention')]
        delivery_controls = '<div class="status-tools"><label>Review status<select id="delivery-filter">' + ''.join(
            f'<option value="{key}" data-label="{label}">{label}</option>' for key, label in choices) + '</select></label></div>'
    policy = f"default-src 'none'; img-src 'self' file:; media-src 'self' file:; style-src 'unsafe-inline'; script-src 'sha256-{script_hash}'; base-uri 'none'; form-action 'none'"
    mark = (Path(__file__).resolve().parent.parent / 'assets/viewprinter-mark.svg').read_text()
    footer_note = 'Scheduled is the final review step · Delivery is managed in ViewPrinter' if is_social else 'Complete means creative approved, not published'
    document = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="{escaped(policy)}"><title>{escaped(title)}</title><style>{STYLE}</style></head>
<body><main><header><div class="brand"><span class="mark" aria-hidden="true">{mark}</span>ViewPrinter <span class="round">Review room · {escaped(review_round)}</span></div>
<div class="hero"><div><h1>{escaped(title)}</h1><p class="lede">{escaped(focus)}</p></div><nav aria-label="Review sections">{''.join(links)}</nav></div></header>
<div class="review-controls">
<div class="batch-row">{batch_controls}{speed_controls}</div>
<div class="filter-row">{delivery_controls}{variant_controls}<span id="count" role="status" aria-live="polite">{len(items)} items</span></div>
<details class="advanced-tools"><summary>Review tools <span class="hint">Production filters &amp; bulk details</span></summary><div class="advanced-body">
<div class="toolbar"><label for="status-filter">Status<select id="status-filter"><option value="">All statuses</option>{options('status')}</select></label>
<label for="format-filter">Treatment<select id="format-filter"><option value="">All treatments</option>{options('format')}</select></label></div>
{bulk_controls}</div></details></div>{''.join(sections)}<p class="empty" id="empty" hidden>No items match these filters.</p>{balance_html}
<footer>Feedback in the conversation · Approvals belong to the version shown · {footer_note}</footer>
<span id="copy-status" class="sr-only" role="status" aria-live="polite" aria-atomic="true"></span>
</main><script>{SCRIPT}</script></body></html>'''
    write_atomically(output, document.encode("utf-8"))
    return output


def write_atomically(output, data):
    """Replace the gallery whole, so a failed build leaves the previous page intact."""
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix="." + output.name + ".", suffix=".tmp", dir=output.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o644)
        os.replace(temporary, output)
    except BaseException:
        os.unlink(temporary)
        raise


def announce_to_review_hub(output, manifest=None, source_revision=None):
    """Show a gallery built inside a ViewPrinter project as a tab on the review hub.

    The person keeps one hub tab open instead of agents opening a window per gallery.
    VIEWPRINTER_REVIEW_HUB=0 skips this; VIEWPRINTER_REVIEW_AUTOSTART=0 links without
    starting the hub server.
    """
    if os.environ.get("VIEWPRINTER_REVIEW_HUB") == "0":
        return None
    try:
        import review_hub
        if manifest:
            data = json.loads(Path(manifest).read_text())
            metadata = data.get('reviewHub', {})
            if metadata.get('excluded') or metadata.get('kind') not in {'social-content','influencer'}:
                return None
        entry = review_hub.register(output, require_project=True, manifest=manifest, source_revision=source_revision)
        if entry is None:
            return None
        if os.environ.get("VIEWPRINTER_REVIEW_AUTOSTART") != "0":
            review_hub.ensure_server()
        return f"review hub: {entry} is a tab at {review_hub.hub_url(entry)}. {review_hub.HUB_NOTE}"
    except Exception as exc:  # the gallery is already built; the hub is a convenience
        return f"review hub: not updated ({exc})"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-revision", type=int, help="expected registered revision of this source; reread before updating")
    args = parser.parse_args()
    try:
        output = build_gallery(args.manifest, args.output)
    except (OSError, ValueError) as exc:
        print(f"review_gallery: {exc}", file=sys.stderr)
        return 1
    print(output)
    note = announce_to_review_hub(output, args.manifest, args.source_revision)
    if note:
        print(note, file=sys.stderr)
        if "not updated (" in note: return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
