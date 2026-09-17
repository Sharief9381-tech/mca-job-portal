/* ==========================================================================
   MCA CAREERS — APP CONTROLLER
   Pulls live data from FastAPI (port 8000), falls back to MCA_DATA mock.
   ========================================================================== */

// Points to Render backend when live, localhost when running locally
const API = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
  ? 'http://localhost:8000/api'
  : 'https://mca-job-portal.onrender.com/api';
let JOBS = [], COMPANIES = [], API_UP = false;

const $ = id => document.getElementById(id);
const qs = sel => document.querySelector(sel);
const qsa = sel => document.querySelectorAll(sel);

/* ── State ── */
const S = {
  view:        'jobs-view',
  exp:         'all',
  search:      '',
  cats:        new Set(),
  locs:        new Set(),
  ats:         new Set(),
  mcaClass:    'all',
  sort:        'newest',
  expMax:      12,
  rocFilter:   'all',
  mcaSearch:   '',
  page:        0,
  pageSize:    30,
  total:       0,
  loading:     false,
  saved:       new Set(JSON.parse(localStorage.getItem('mca_saved') || '[]')),
};

/* ════════════════════════════════════════
   BOOT
════════════════════════════════════════ */
document.addEventListener('DOMContentLoaded', async () => {
  showSkeletons();
  await connectAPI();
  await loadData();
  buildFilters();
  bindEvents();
  renderJobs();
  renderCompanies();
  renderPortals();
  renderSaved();
  syncBookmarkBadge();
});

/* ════════════════════════════════════════
   API
════════════════════════════════════════ */
async function connectAPI() {
  try {
    const r = await fetch(`${API}/stats`, { signal: AbortSignal.timeout(3000) });
    if (r.ok) {
      API_UP = true;
      const stats = await r.json();
      applyStats(stats);
      statusBadge(true);
    }
  } catch {
    API_UP = false;
    statusBadge(false);
  }
}

async function loadData() {
  if (API_UP) {
    await fetchJobs();
    await fetchCompanies();
  } else {
    JOBS = (MCA_DATA.jobs || []).map(j => ({ ...j, apply_url: j.direct_url || '#' }));
    COMPANIES = MCA_DATA.companies || [];
  }
}

async function fetchJobs(append = false) {
  if (S.loading) return;
  S.loading = true;
  const p = new URLSearchParams({ limit: S.pageSize, offset: S.page * S.pageSize });
  if (S.search) p.set('search', S.search);
  if (S.exp !== 'all') p.set('exp', S.exp);
  if (S.ats.size === 1) p.set('ats', [...S.ats][0]);
  try {
    const r = await fetch(`${API}/jobs?${p}`);
    const d = await r.json();
    S.total = d.total;
    JOBS = append ? [...JOBS, ...d.jobs] : d.jobs;
  } catch (e) { console.warn('[API] jobs:', e); }
  S.loading = false;
}

async function fetchCompanies() {
  try {
    const r = await fetch(`${API}/companies?limit=500`);
    const d = await r.json();
    COMPANIES = d.companies || [];
  } catch { COMPANIES = MCA_DATA.companies || []; }
}

/* ════════════════════════════════════════
   STATS / BADGES
════════════════════════════════════════ */
function applyStats(s) {
  const set = (id, v) => { const el = $(id); if (el) el.textContent = v; };
  set('stat-companies', (s.total_companies || 0).toLocaleString('en-IN') + '+');
  set('stat-portals',   (s.crawled_companies || 0).toLocaleString('en-IN') + '+');
  set('stat-freshers',  (s.fresher_jobs || 0).toLocaleString('en-IN') + '+');
  set('stat-ats',       Object.keys(s.ats_breakdown || {}).length + '+');
}

function statusBadge(ok) {
  const old = document.getElementById('api-badge');
  if (old) old.remove();
  const b = document.createElement('div');
  b.id = 'api-badge';
  b.style.cssText = `position:fixed;bottom:20px;right:20px;z-index:999;padding:8px 14px;
    border-radius:99px;font-size:0.75rem;font-weight:600;display:flex;align-items:center;gap:6px;
    background:${ok ? 'rgba(52,211,153,0.12)' : 'rgba(251,113,133,0.12)'};
    border:1px solid ${ok ? 'rgba(52,211,153,0.3)' : 'rgba(251,113,133,0.3)'};
    color:${ok ? '#34d399' : '#fb7185'};font-family:Inter,sans-serif;`;
  b.innerHTML = ok
    ? '<i class="fa-solid fa-circle-check"></i> Live API Connected'
    : '<i class="fa-solid fa-circle-xmark"></i> Mock Data · Start api/server.py';
  document.body.appendChild(b);
}

/* ════════════════════════════════════════
   EVENT BINDINGS
════════════════════════════════════════ */
function bindEvents() {
  /* nav tabs */
  qsa('.nav-tab').forEach(btn => btn.addEventListener('click', () => {
    const v = btn.dataset.view;
    if (v) { switchView(v); closeMobileNav(); }
  }));

  /* mobile menu */
  const menuBtn = $('menu-btn'), mobileNav = $('mobile-nav');
  menuBtn?.addEventListener('click', () => mobileNav?.classList.toggle('open'));

  /* experience tabs */
  qsa('.exp-tab').forEach(t => t.addEventListener('click', () => {
    qsa('.exp-tab').forEach(x => x.classList.remove('active'));
    t.classList.add('active');
    S.exp = t.dataset.exp;
    S.page = 0;
    refresh();
  }));

  /* search */
  $('search-btn')?.addEventListener('click', doSearch);
  $('global-search-input')?.addEventListener('keydown', e => { if (e.key === 'Enter') doSearch(); });

  /* slider */
  $('exp-slider')?.addEventListener('input', e => {
    const v = +e.target.value;
    S.expMax = v;
    $('exp-val-display').textContent = v >= 12 ? 'Any' : `≤ ${v} yr`;
    renderJobs();
  });

  /* sort */
  $('sort-select')?.addEventListener('change', e => { S.sort = e.target.value; renderJobs(); });

  /* reset */
  $('reset-filters-btn')?.addEventListener('click', resetFilters);

  /* mca directory */
  $('mca-search-input')?.addEventListener('input', e => { S.mcaSearch = e.target.value.toLowerCase(); renderCompanies(); });
  $('roc-filter-select')?.addEventListener('change', e => { S.rocFilter = e.target.value; renderCompanies(); });

  /* filter toggle (mobile) */
  $('filter-toggle-btn')?.addEventListener('click', () => {
    $('sidebar')?.classList.toggle('open');
  });

  /* load more */
  $('load-more-btn')?.addEventListener('click', async () => {
    S.page++;
    if (API_UP) {
      await fetchJobs(true);
      renderJobs();
    }
  });

  /* resolver */
  $('run-resolver-btn')?.addEventListener('click', runResolver);

  /* modal */
  $('close-modal-btn')?.addEventListener('click', closeModal);
  $('cin-modal')?.addEventListener('click', e => { if (e.target === $('cin-modal')) closeModal(); });

  /* escape key */
  document.addEventListener('keydown', e => { if (e.key === 'Escape') closeModal(); });
}

function closeMobileNav() { $('mobile-nav')?.classList.remove('open'); }

/* ════════════════════════════════════════
   VIEW SWITCHING
════════════════════════════════════════ */
function switchView(id) {
  S.view = id;
  qsa('.view').forEach(v => v.classList.toggle('active', v.id === id));
  qsa('.nav-tab').forEach(b => b.classList.toggle('active', b.dataset.view === id));
  if (id === 'saved-view')     renderSaved();
  if (id === 'companies-view') renderCompanies();
  if (id === 'ats-view')       renderPortals();
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

/* ════════════════════════════════════════
   FILTERS
════════════════════════════════════════ */
function buildFilters() {
  const all = JOBS.length ? JOBS : (MCA_DATA?.jobs || []);
  const cats = [...new Set(all.map(j => j.category || j.department).filter(Boolean))];
  const locs = ['Bengaluru', 'Mumbai', 'Delhi', 'Hyderabad', 'Pune', 'Chennai', 'Gurugram', 'Remote'];
  const atsL = [...new Set(all.map(j => j.ats).filter(Boolean))];

  renderCheckboxGroup('category-filter-list', cats, (v, on) => { on ? S.cats.add(v) : S.cats.delete(v); renderJobs(); });
  renderCheckboxGroup('location-filter-list', locs, (v, on) => { on ? S.locs.add(v) : S.locs.delete(v); renderJobs(); });
  renderCheckboxGroup('ats-filter-list',      atsL, (v, on) => { on ? S.ats.add(v) : S.ats.delete(v); refresh(); });
}

function renderCheckboxGroup(id, items, onChange) {
  const el = $(id); if (!el) return;
  el.innerHTML = items.map(item => `
    <label class="check-item">
      <input type="checkbox" value="${item}"> ${item}
    </label>`).join('');
  el.querySelectorAll('input').forEach(cb =>
    cb.addEventListener('change', () => onChange(cb.value, cb.checked))
  );
}

function resetFilters() {
  S.exp = 'all'; S.expMax = 12; S.search = ''; S.cats.clear(); S.locs.clear(); S.ats.clear(); S.page = 0;
  $('global-search-input').value = '';
  $('exp-slider').value = 12;
  $('exp-val-display').textContent = 'Any';
  qsa('.check-list input').forEach(cb => cb.checked = false);
  qsa('.exp-tab').forEach(t => t.classList.remove('active'));
  qs('.exp-tab[data-exp="all"]')?.classList.add('active');
  refresh();
}

/* ════════════════════════════════════════
   SEARCH
════════════════════════════════════════ */
async function doSearch() {
  S.search = $('global-search-input').value.trim();
  S.page = 0;
  switchView('jobs-view');
  await refresh();
}

async function refresh() {
  if (API_UP) { showSkeletons(); await fetchJobs(); }
  renderJobs();
}

/* ════════════════════════════════════════
   RENDER JOBS
════════════════════════════════════════ */
function renderJobs() {
  const grid = $('jobs-cards-grid'); if (!grid) return;

  let jobs = [...JOBS];

  /* client-side filters (mock mode or extra filters) */
  if (!API_UP) {
    if (S.exp !== 'all') jobs = jobs.filter(j => j.exp_level === S.exp);
    if (S.search) {
      const q = S.search.toLowerCase();
      jobs = jobs.filter(j =>
        [j.title, j.company_name, j.brand, j.company_cin, ...(j.skills || [])].join(' ').toLowerCase().includes(q)
      );
    }
  }

  /* always client-side */
  if (S.cats.size) jobs = jobs.filter(j => S.cats.has(j.category || j.department));
  if (S.locs.size) jobs = jobs.filter(j => [...S.locs].some(l => (j.location || '').toLowerCase().includes(l.toLowerCase())));
  if (!API_UP && S.ats.size) jobs = jobs.filter(j => S.ats.has(j.ats));
  if (S.expMax < 12) jobs = jobs.filter(j => (j.exp_years || 0) <= S.expMax);

  /* sort */
  if (S.sort === 'company')  jobs.sort((a,b) => (a.brand||a.company_name||'').localeCompare(b.brand||b.company_name||''));
  if (S.sort === 'exp-asc')  jobs.sort((a,b) => (a.exp_years||0) - (b.exp_years||0));
  if (S.sort === 'exp-desc') jobs.sort((a,b) => (b.exp_years||0) - (a.exp_years||0));
  if (S.sort === 'newest')   jobs.sort((a,b) => (b.posted_date||'').localeCompare(a.posted_date||''));

  const shown = jobs.length;
  const total = API_UP ? S.total : shown;
  $('jobs-results-count').textContent = shown === 0 ? 'No jobs found' :
    `${shown.toLocaleString('en-IN')}${API_UP && total > shown ? ` of ${total.toLocaleString('en-IN')}` : ''} jobs`;

  if (!shown) {
    grid.innerHTML = `<div class="empty-state">
      <i class="fa-solid fa-briefcase-blank"></i>
      <h3>No jobs match your filters</h3>
      <p>Try a different search term or clear the filters.</p>
    </div>`;
    $('load-more-wrap')?.classList.add('hidden');
    return;
  }

  grid.innerHTML = jobs.map(jobCard).join('');
  bindCardButtons();

  const lmw = $('load-more-wrap');
  if (API_UP && JOBS.length < S.total) lmw?.classList.remove('hidden');
  else lmw?.classList.add('hidden');
}

function jobCard(j) {
  const saved    = S.saved.has(j.id);
  const isFresh  = j.exp_level === 'entry_level';
  const isSenior = j.exp_level === 'experienced';
  const expClass = isFresh ? 'badge-fresher' : isSenior ? 'badge-senior' : 'badge-mid';
  const expIcon  = isFresh ? '🎓' : isSenior ? '💼' : '⚡';
  const expLabel = j.exp_display || (isFresh ? 'Freshers / Entry Level' : isSenior ? 'Experienced' : 'Mid Level');
  const brand    = j.brand || j.company_name || '';
  const apply    = j.apply_url || j.direct_url || '#';
  const cin      = j.company_cin || '';
  const skills   = j.skills || [];
  const desc     = (j.description || '').replace(/<[^>]+>/g,' ').trim().slice(0, 140);
  const dept     = j.department || j.category || '';
  const date     = j.posted_date ? new Date(j.posted_date).toLocaleDateString('en-IN',{day:'numeric',month:'short'}) : '';

  return `
<div class="job-card">
  <div class="job-card-body">
    <div class="card-header-row">
      <div class="company-avatar">${brand.slice(0,2).toUpperCase()}</div>
      <button class="btn-bookmark${saved?' saved':''}" data-id="${j.id}" title="${saved?'Remove bookmark':'Save job'}">
        <i class="fa-${saved?'solid':'regular'} fa-bookmark"></i>
      </button>
    </div>

    <div class="job-title">${j.title}</div>

    <div class="job-company-row">
      <span class="company-name">${brand}</span>
      ${cin ? `<span class="cin-chip" data-cin="${cin}" title="View MCA record">
        <i class="fa-solid fa-building-columns"></i> ${cin.slice(0,11)}…
      </span>` : ''}
    </div>

    <div class="badge-row">
      <span class="badge ${expClass}">${expIcon} ${expLabel}</span>
      ${j.location ? `<span class="badge badge-loc"><i class="fa-solid fa-location-dot"></i> ${j.location}</span>` : ''}
      ${j.ats ? `<span class="badge badge-ats">${j.ats}</span>` : ''}
      ${dept ? `<span class="badge badge-dept">${dept}</span>` : ''}
    </div>

    ${desc ? `<div class="job-desc">${desc}</div>` : ''}

    ${skills.length ? `<div class="skills-row">${skills.slice(0,5).map(s=>`<span class="skill-chip">${s}</span>`).join('')}</div>` : ''}
  </div>

  <div class="job-card-foot">
    <span class="job-meta">${date ? `<i class="fa-regular fa-clock"></i> ${date}` : ''}${j.salary ? (date?' · ':'')+j.salary : ''}</span>
    <a href="${apply}" target="_blank" rel="noopener" class="btn-apply">
      Apply <i class="fa-solid fa-arrow-up-right-from-square" style="font-size:0.7rem"></i>
    </a>
  </div>
</div>`;
}

function bindCardButtons() {
  /* bookmark */
  qsa('.btn-bookmark').forEach(btn => btn.addEventListener('click', e => {
    e.stopPropagation();
    const id = btn.dataset.id;
    if (S.saved.has(id)) S.saved.delete(id);
    else { S.saved.add(id); showToast('Job saved!'); }
    localStorage.setItem('mca_saved', JSON.stringify([...S.saved]));
    syncBookmarkBadge();
    btn.classList.toggle('saved', S.saved.has(id));
    btn.querySelector('i').className = `fa-${S.saved.has(id)?'solid':'regular'} fa-bookmark`;
    if (S.view === 'saved-view') renderSaved();
  }));

  /* CIN chips */
  qsa('.cin-chip').forEach(chip => chip.addEventListener('click', () => openModal(chip.dataset.cin)));
}

function showSkeletons() {
  const g = $('jobs-cards-grid'); if (!g) return;
  g.innerHTML = Array(6).fill('<div class="skeleton-card"></div>').join('');
  $('load-more-wrap')?.classList.add('hidden');
}

/* ════════════════════════════════════════
   COMPANIES TABLE
════════════════════════════════════════ */
function renderCompanies() {
  const tbody = $('mca-table-body'); if (!tbody) return;
  const all = COMPANIES.length ? COMPANIES : (MCA_DATA?.companies || []);

  let list = all.filter(c => {
    if (S.rocFilter !== 'all' && c.roc !== S.rocFilter) return false;
    if (S.mcaSearch) {
      const h = [c.cin, c.legal_name||c.name, c.brand, c.domain].join(' ').toLowerCase();
      if (!h.includes(S.mcaSearch)) return false;
    }
    return true;
  }).slice(0, 300);

  if (!list.length) {
    tbody.innerHTML = `<tr><td colspan="9" class="table-loading">No companies found.</td></tr>`;
    return;
  }

  tbody.innerHTML = list.map(c => `
    <tr>
      <td><span class="cin-mono">${c.cin||'—'}</span></td>
      <td>
        <div class="table-company-name">${c.legal_name||c.name||'—'}</div>
        <div class="table-brand">${c.brand||''}</div>
      </td>
      <td>${c.roc||'—'}</td>
      <td>${c.incorporated||'—'}</td>
      <td style="font-family:var(--font-mono);font-size:0.78rem;color:var(--emerald)">${c.capital||'—'}</td>
      <td>
        <a href="${c.career_url||'#'}" target="_blank" class="table-link">
          ${c.domain||''}/careers <i class="fa-solid fa-up-right-from-square" style="font-size:0.65rem"></i>
        </a>
      </td>
      <td><span class="badge badge-ats">${c.ats||'—'}</span></td>
      <td style="font-family:var(--font-mono);color:var(--cyan)">${c.jobs_found > 0 ? c.jobs_found+' jobs' : '—'}</td>
      <td>
        <button class="btn-inspect" onclick="openModal('${c.cin||''}')">Inspect</button>
      </td>
    </tr>`).join('');
}

/* ════════════════════════════════════════
   PORTALS
════════════════════════════════════════ */
function renderPortals() {
  const grid = $('career-sites-grid'); if (!grid) return;
  const all = COMPANIES.length ? COMPANIES : (MCA_DATA?.companies || []);

  grid.innerHTML = all.slice(0, 60).map(c => `
    <div class="portal-card">
      <div class="portal-card-head">
        <div>
          <div class="portal-company">${c.brand||c.name||'—'}</div>
          <div class="portal-legal">${c.legal_name||c.name||''}</div>
        </div>
        <span class="badge badge-ats">${c.ats||'Custom'}</span>
      </div>
      <div class="portal-info">
        <div><i class="fa-solid fa-link"></i> ${c.domain||'—'}</div>
        <div><i class="fa-solid fa-shield-halved"></i> MCA Verified · ${c.status||'Active'}</div>
        ${c.jobs_found ? `<div><i class="fa-solid fa-briefcase"></i> ${c.jobs_found} live jobs indexed</div>` : ''}
      </div>
      <a href="${c.career_url||'#'}" target="_blank" class="btn-primary">
        Open Career Portal <i class="fa-solid fa-arrow-up-right-from-square"></i>
      </a>
    </div>`).join('');
}

/* ════════════════════════════════════════
   SAVED JOBS
════════════════════════════════════════ */
function renderSaved() {
  const grid = $('saved-jobs-grid'); if (!grid) return;
  const all  = JOBS.length ? JOBS : (MCA_DATA?.jobs||[]).map(j=>({...j,apply_url:j.direct_url||'#'}));
  const list = all.filter(j => S.saved.has(j.id));

  if (!list.length) {
    grid.innerHTML = `<div class="empty-state">
      <i class="fa-regular fa-bookmark"></i>
      <h3>No saved jobs yet</h3>
      <p>Click the bookmark icon on any job card to save it here.</p>
    </div>`;
    return;
  }
  grid.innerHTML = list.map(jobCard).join('');
  bindCardButtons();
}

function syncBookmarkBadge() {
  const el = $('saved-count'); if (el) el.textContent = S.saved.size;
}

/* ════════════════════════════════════════
   CIN MODAL
════════════════════════════════════════ */
window.openModal = function(cin) {
  if (!cin) return;
  const all = COMPANIES.length ? COMPANIES : (MCA_DATA?.companies||[]);
  const c   = all.find(x => x.cin === cin) || {
    cin, legal_name:'MCA REGISTERED ENTITY', brand:'—',
    roc:'—', incorporated:'—', company_class:'—', capital:'—',
    domain:'—', career_url:'#', ats:'—'
  };

  $('modal-company-name').textContent = c.legal_name || c.name || '—';
  $('modal-cin-badge').textContent    = `CIN: ${c.cin}`;
  $('modal-visit-career-btn').href    = c.career_url || '#';

  $('modal-body-content').innerHTML = `
    <div class="modal-info-grid">
      <div class="modal-info-item">
        <div class="modal-info-label">Brand / Trade Name</div>
        <div class="modal-info-value">${c.brand||'—'}</div>
      </div>
      <div class="modal-info-item">
        <div class="modal-info-label">ROC Jurisdiction</div>
        <div class="modal-info-value">${c.roc||'—'}</div>
      </div>
      <div class="modal-info-item">
        <div class="modal-info-label">Incorporated</div>
        <div class="modal-info-value">${c.incorporated||'—'}</div>
      </div>
      <div class="modal-info-item">
        <div class="modal-info-label">Company Class</div>
        <div class="modal-info-value">${c.company_class||'—'} Ltd</div>
      </div>
      <div class="modal-info-item">
        <div class="modal-info-label">Authorized Capital</div>
        <div class="modal-info-value">${c.capital||'—'}</div>
      </div>
      <div class="modal-info-item">
        <div class="modal-info-label">ATS Engine</div>
        <div class="modal-info-value">${c.ats||'Custom'}</div>
      </div>
      ${c.jobs_found ? `<div class="modal-info-item">
        <div class="modal-info-label">Live Jobs Indexed</div>
        <div class="modal-info-value" style="color:var(--cyan)">${c.jobs_found}</div>
      </div>` : ''}
    </div>
    <div class="modal-verify-box">
      <div class="modal-verify-title"><i class="fa-solid fa-circle-check"></i> Career Portal Verified</div>
      <div class="modal-verify-body">
        Direct career URL mapped for <strong>${c.brand||c.name}</strong>.<br>
        Endpoint: <code>${c.career_url||'—'}</code>
      </div>
    </div>`;

  $('cin-modal').classList.remove('hidden');
};

function closeModal() { $('cin-modal')?.classList.add('hidden'); }

/* ════════════════════════════════════════
   RESOLVER
════════════════════════════════════════ */
function runResolver() {
  const raw = $('resolver-input-name').value.trim();
  if (!raw) { showToast('Enter a company name or CIN'); return; }

  const btn = $('run-resolver-btn');
  btn.disabled = true;
  btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Resolving…';

  const all   = COMPANIES.length ? COMPANIES : (MCA_DATA?.companies||[]);
  const q     = raw.toLowerCase();
  const match = all.find(c =>
    (c.legal_name||c.name||'').toLowerCase().includes(q) ||
    (c.brand||'').toLowerCase().includes(q) ||
    (c.cin||'').toLowerCase() === q
  );

  setTimeout(() => {
    btn.disabled = false;
    btn.innerHTML = '<i class="fa-solid fa-robot"></i> Resolve Career Portal';

    const box = $('resolver-result-box');
    box.classList.remove('hidden', 'success', 'estimate');

    if (match) {
      box.classList.add('success');
      box.innerHTML = `
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;flex-wrap:wrap;gap:8px">
          <div>
            <div style="font-weight:700;color:var(--emerald);margin-bottom:2px">
              <i class="fa-solid fa-circle-check"></i> Found in MCA Registry
            </div>
            <div style="font-size:1.05rem;font-weight:700;color:var(--text-1)">${match.brand||match.name}</div>
          </div>
          <span class="badge badge-ats">${match.ats||'Custom'}</span>
        </div>
        <div style="display:grid;gap:8px;font-size:0.9rem;color:var(--text-2)">
          <div><strong>Legal Name:</strong> ${match.legal_name||match.name}</div>
          <div><strong>CIN:</strong> <code style="font-family:var(--font-mono);color:var(--indigo)">${match.cin||'—'}</code></div>
          <div><strong>Domain:</strong> <a href="https://${match.domain}" target="_blank" style="color:var(--cyan)">${match.domain}</a></div>
          <div><strong>Career Portal:</strong> <a href="${match.career_url}" target="_blank" style="color:var(--cyan)">${match.career_url}</a></div>
          ${match.jobs_found ? `<div><strong>Live Jobs:</strong> <span style="color:var(--emerald);font-weight:700">${match.jobs_found} indexed</span></div>` : ''}
        </div>`;
    } else {
      const clean  = raw.replace(/PRIVATE LIMITED|LIMITED|LLP|INDIA/gi,'').trim();
      const domain = $('resolver-input-domain').value.trim() || `${clean.toLowerCase().replace(/\s+/g,'')}.com`;
      box.classList.add('estimate');
      box.innerHTML = `
        <div style="font-weight:700;color:var(--amber);margin-bottom:12px">
          <i class="fa-solid fa-triangle-exclamation"></i> Not yet indexed — estimated result
        </div>
        <div style="display:grid;gap:8px;font-size:0.9rem;color:var(--text-2)">
          <div><strong>Estimated Domain:</strong> <a href="https://${domain}" target="_blank" style="color:var(--cyan)">${domain}</a></div>
          <div><strong>Likely Career URL:</strong> <a href="https://${domain}/careers" target="_blank" style="color:var(--cyan)">${domain}/careers</a></div>
          <div style="margin-top:8px;padding:10px;background:rgba(251,191,36,0.08);border-radius:8px;font-size:0.82rem;color:var(--amber)">
            Run <code>python crawl.py --domain ${domain}</code> to index this company.
          </div>
        </div>`;
    }
  }, 600);
}

/* ════════════════════════════════════════
   TOAST
════════════════════════════════════════ */
let toastTimer;
function showToast(msg) {
  const el = $('toast'); if (!el) return;
  el.textContent = msg;
  el.classList.remove('hidden');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.add('hidden'), 2500);
}
