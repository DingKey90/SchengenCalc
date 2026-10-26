// Schengen 90/180 calculator. Page-specific strings come from window.SC (injected by build.py).
(function () {
'use strict';

const SC = window.SC;
const T = SC.t;
const LIMIT = 90, WINDOW = 180, DAY = 86400000;
const STORE_KEY = 'schengen-trips-v1';
const $ = id => document.getElementById(id);
const fill = (s, vars) => s.replace(/\{(\w+)\}/g, (_, k) => vars[k]);

// ── Dates as integer day numbers (days since 1970-01-01 UTC) — immune to DST/timezone drift ──
const ISO_RE = /^\d{4}-\d{2}-\d{2}$/;
const toDay = s => {
  if (!s || !ISO_RE.test(s)) return null;
  const [y, m, d] = s.split('-').map(Number);
  const n = Date.UTC(y, m - 1, d) / DAY;
  return Number.isFinite(n) ? n : null;
};
const toIso = n => new Date(n * DAY).toISOString().slice(0, 10);
const fmt = n => n == null ? '—' : new Date(n * DAY).toLocaleDateString(SC.locale,
  { timeZone: 'UTC', day: 'numeric', month: 'short', year: 'numeric' });
const todayDay = () => { const d = new Date(); return Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()) / DAY; };

// ── Core rule ──
const isValid = t => t.entry != null && t.exit != null && t.exit >= t.entry;

function daySet(list, upTo = Infinity) {
  const s = new Set();
  for (const t of list) {
    if (!isValid(t)) continue;
    for (let d = t.entry; d <= Math.min(t.exit, upTo); d++) s.add(d);
  }
  return s;
}

// Days spent in the 180-day window ending on (and including) day d
function countWindow(set, d) {
  let n = 0;
  for (let x = d - WINDOW + 1; x <= d; x++) if (set.has(x)) n++;
  return n;
}

// Latest day you can stay until if you are present every day from `start`, given days already in `set`
function latestStay(set, start) {
  const s = new Set(set);
  for (let x = start; x < start + WINDOW + 1; x++) {
    s.add(x);
    if (countWindow(s, x) > LIMIT) return x - 1;
  }
  return null;
}

// ── State ──
let trips = [], tid = 0;

function save() {
  try {
    localStorage.setItem(STORE_KEY, JSON.stringify(trips.map(t => [
      t.entry == null ? '' : toIso(t.entry), t.exit == null ? '' : toIso(t.exit)])));
  } catch (e) { /* storage unavailable — calculator still works */ }
}

function load() {
  const p = new URLSearchParams(location.search);
  // Old links used ?lang=xx on the English page — send them to the language page
  const l = p.get('lang');
  if (SC.lang === 'en' && l && SC.langPaths[l] && l !== 'en') {
    p.delete('lang');
    const q = p.toString();
    location.replace(SC.langPaths[l] + (q ? '?' + q : ''));
    return false;
  }
  let pairs = null;
  const tp = p.get('trips');
  if (tp) pairs = tp.split(',').map(x => x.split('_'));
  else {
    try { pairs = JSON.parse(localStorage.getItem(STORE_KEY) || 'null'); } catch (e) { pairs = null; }
  }
  if (Array.isArray(pairs)) {
    for (const pr of pairs) {
      if (!Array.isArray(pr)) continue;
      const entry = toDay(pr[0]), exit = toDay(pr[1]);
      if (entry != null || exit != null) trips.push({ id: ++tid, entry, exit });
    }
  }
  if (tp) save();
  return true;
}

function addTrip() { trips.push({ id: ++tid, entry: null, exit: null }); save(); render(); }
function removeTrip(id) { trips = trips.filter(t => t.id !== id); save(); render(); }
function updateTrip(id, field, val) {
  const t = trips.find(t => t.id === id); if (!t) return;
  t[field] = toDay(val);
  if (t.entry != null && t.exit != null && t.exit < t.entry) {
    if (field === 'entry') t.exit = t.entry; else t.entry = t.exit;
  }
  save(); render();
}

// ── Trip list ──
function analyseTrips(today) {
  const full = daySet(trips);
  const valid = trips.filter(isValid);
  const info = {};
  for (const t of trips) {
    const r = { overlap: false, over: 0, overOn: null, future: t.entry != null && t.entry > today };
    if (isValid(t)) {
      r.overlap = valid.some(o => o.id !== t.id && t.entry <= o.exit && o.entry <= t.exit);
      for (let d = t.entry; d <= t.exit; d++) {
        const c = countWindow(full, d);
        if (c > LIMIT && r.overOn == null) r.overOn = d;
        if (c - LIMIT > r.over) r.over = c - LIMIT;
      }
    }
    info[t.id] = r;
  }
  return info;
}

function renderTrips(today) {
  const list = $('tripsList');
  if (!trips.length) {
    list.innerHTML = `<div class="empty-state"><div class="big">✈</div><span>${T.empty_trips}</span></div>`;
    return;
  }
  const info = analyseTrips(today);
  list.innerHTML = '';
  for (const t of trips) {
    const r = info[t.id];
    const row = document.createElement('div');
    row.className = 'trip-row' + (r.over ? ' over' : r.overlap ? ' overlap' : '') + (r.future ? ' future' : '');
    let msg = '';
    if (r.over) msg = `<div class="trip-msg danger">✕ ${fill(T.msg_over, { n: r.over, date: fmt(r.overOn) })}</div>`;
    else if (r.overlap) msg = `<div class="trip-msg warn">⚠ ${T.msg_overlap}</div>`;
    else if (r.future) msg = `<div class="trip-msg muted">${T.msg_future}</div>`;
    let badge = '—', color = 'var(--muted)';
    if (isValid(t)) {
      const d = t.exit - t.entry + 1;
      badge = d + T.ds;
      color = r.over ? 'var(--danger)' : r.overlap ? 'var(--warn)' : 'var(--ok)';
    }
    row.innerHTML = `<div><label for="en-${t.id}">${T.label_entry}</label>
        <input type="date" id="en-${t.id}" value="${t.entry != null ? toIso(t.entry) : ''}" data-id="${t.id}" data-f="entry"></div>
      <div><label for="ex-${t.id}">${T.label_exit}</label>
        <input type="date" id="ex-${t.id}" value="${t.exit != null ? toIso(t.exit) : ''}" data-id="${t.id}" data-f="exit"></div>
      <div class="trip-days-badge" style="color:${color}">${badge}</div>
      <button class="remove-btn" type="button" data-remove="${t.id}" aria-label="${T.remove}" title="${T.remove}">×</button>
      ${msg}`;
    list.appendChild(row);
  }
}

// ── Status ──
function renderStatus(today) {
  const past = daySet(trips, today);
  const used = countWindow(past, today), left = Math.max(0, LIMIT - used);
  const tone = used > LIMIT ? 'var(--danger)' : used >= 75 ? 'var(--warn)' : 'var(--ok)';

  const circ = 295, ring = $('ringFill');
  ring.style.strokeDashoffset = circ - Math.min(used / LIMIT, 1) * circ;
  ring.style.stroke = tone;
  const dl = $('daysLeft');
  dl.textContent = used > LIMIT ? '−' + (used - LIMIT) : left;
  dl.style.color = used > LIMIT ? 'var(--danger)' : used >= 75 ? 'var(--warn)' : 'var(--text)';
  $('daysUsed').textContent = used + ' / ' + LIMIT;
  $('daysUsed').style.color = tone;

  // Must exit by — only meaningful while inside Schengen today
  const inNow = trips.some(t => isValid(t) && t.entry <= today && t.exit >= today);
  const mEl = $('mustExit');
  if (inNow) {
    const before = new Set([...past].filter(d => d < today));
    const last = latestStay(before, today);
    if (last == null || last < today) { mEl.textContent = T.leave_now; mEl.style.color = 'var(--danger)'; }
    else { mEl.textContent = fmt(last); mEl.style.color = 'var(--warn)'; }
  } else { mEl.textContent = T.not_inside; mEl.style.color = 'var(--muted)'; }

  // Earliest re-entry if you leave (or are outside) today
  const re = $('reentry');
  if (used < LIMIT) { re.textContent = T.now_lbl; re.style.color = 'var(--ok)'; }
  else {
    let d = today + 1;
    while (countWindow(past, d) >= LIMIT && d < today + WINDOW + 1) d++;
    re.textContent = fmt(d); re.style.color = 'var(--warn)';
  }

  $('alertOk').classList.toggle('show', used > 0 && used < 75);
  $('alertWarn').classList.toggle('show', used >= 75 && used <= LIMIT);
  $('alertDanger').classList.toggle('show', used > LIMIT);
}

// ── Timeline (last 180 days) ──
function renderTimeline(today) {
  const card = $('timelineCard'), con = $('timeline');
  const wStart = today - WINDOW + 1;
  const shown = trips.filter(t => isValid(t) && t.exit >= wStart && t.entry <= today);
  if (!shown.length) { card.style.display = 'none'; return; }
  card.style.display = 'block';
  con.innerHTML = '';
  for (const t of shown) {
    const s = Math.max(t.entry, wStart), e = Math.min(t.exit, today);
    const lp = (s - wStart) / WINDOW * 100, wp = (e - s + 1) / WINDOW * 100;
    const bar = document.createElement('div');
    bar.className = 'timeline-bar';
    bar.style.cssText = `left:${lp}%;width:${Math.max(wp, .5)}%;background:var(--ok);opacity:.85`;
    bar.title = `${fmt(t.entry)} → ${fmt(t.exit)}`;
    if (wp > 5) bar.innerHTML = `<span class="timeline-bar-label">${e - s + 1}${T.ds}</span>`;
    con.appendChild(bar);
  }
  const m = document.createElement('div');
  m.style.cssText = 'position:absolute;right:0;top:0;width:2px;height:100%;background:rgba(232,213,163,.55);z-index:5';
  con.appendChild(m);
  $('axisStart').textContent = fmt(wStart);
  $('axisEnd').textContent = fmt(today);
}

// ── Planner ──
function calcProjection() {
  const entry = toDay($('projEntry').value), exit = toDay($('projExit').value);
  const res = $('projResult');
  if (entry == null) { res.classList.remove('show'); return; }
  const set = daySet(trips);
  if (exit == null || exit < entry) {
    // Only an entry date: how long could I stay?
    const last = latestStay(set, entry);
    res.innerHTML = last == null || last < entry
      ? `<span style="color:var(--danger)">${T.proj_none}</span>`
      : `<span style="color:var(--ok)">${fill(T.proj_maxstay, { date: fmt(last), n: last - entry + 1 })}</span>`;
    res.classList.add('show');
    return;
  }
  for (let d = entry; d <= exit; d++) set.add(d);
  let maxU = 0;
  for (let d = entry; d <= exit; d++) maxU = Math.max(maxU, countWindow(set, d));
  const over = maxU - LIMIT, dur = exit - entry + 1;
  const head = over > 0
    ? `<span style="color:var(--danger)">${fill(T.proj_over, { n: over })}</span><br>`
    : `<span style="color:var(--ok)">${T.proj_ok}</span><br>`;
  res.innerHTML = head + `<span style="color:var(--muted)">${T.proj_dur}: ${dur}${T.ds} &nbsp;·&nbsp; ${T.proj_max}: ${maxU}/${LIMIT} &nbsp;·&nbsp; ${T.proj_rem}: ${Math.max(0, LIMIT - maxU)}${T.ds}</span>`;
  res.classList.add('show');
}

// ── Share ──
function buildShareUrl() {
  const valid = trips.filter(isValid);
  const el = $('shareUrl'), btn = $('copyBtn');
  if (!valid.length) { el.textContent = T.share_ph; btn.disabled = true; return; }
  btn.disabled = false;
  const enc = valid.map(t => toIso(t.entry) + '_' + toIso(t.exit)).join(',');
  el.textContent = location.origin + location.pathname + '?trips=' + encodeURIComponent(enc);
}

function copyShare() {
  navigator.clipboard.writeText($('shareUrl').textContent).then(() => {
    const t = $('copyToast');
    t.style.opacity = '1'; setTimeout(() => t.style.opacity = '0', 2000);
  });
}

function render() {
  const today = todayDay();
  renderTrips(today);
  renderStatus(today);
  renderTimeline(today);
  calcProjection();
  buildShareUrl();
}

// ── Wire up ──
$('addTrip').addEventListener('click', addTrip);
$('copyBtn').addEventListener('click', copyShare);
$('projEntry').addEventListener('input', calcProjection);
$('projExit').addEventListener('input', calcProjection);
$('tripsList').addEventListener('change', e => {
  const el = e.target;
  if (el.dataset.id) updateTrip(+el.dataset.id, el.dataset.f, el.value);
});
$('tripsList').addEventListener('click', e => {
  const id = e.target.dataset && e.target.dataset.remove;
  if (id) removeTrip(+id);
});

if (load()) render();

// Exposed for tests
window.SchengenCore = { toDay, toIso, daySet, countWindow, latestStay };
})();
