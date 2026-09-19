/* =====================================================================
   MCA CareerGrid — App Controller
   ===================================================================== */

const API = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
  ? 'http://localhost:8000/api'
  : 'https://mca-job-portal.onrender.com/api';

let JOBS = [], COMPANIES = [], API_UP = false;
const $ = id => document.getElementById(id);
const qsa = s => document.querySelectorAll(s);

const S = {
  view: 'jobs-view', exp: 'all', search: '', sort: 'newest',
  page: 0, pageSize: 30, total: 0, loading: false,
  cats: new Set(), locs: new Set(), ats: new Set(),
  rocFilter: 'all', mcaSearch: '',
  saved: new Set(JSON.parse(localStorage.getItem('mca_cg_saved') || '[]')),
};

// ── Boot ──────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', async () => {
  showSkeletons();
  await connect();
  await loadData();
  buildFilters();
  bindEvents();
  renderJobs();
  renderCompanies();
  renderPortals();
  renderSaved();
  syncBadge();
});

// ── API ───────────────────────────────────────────────────────────────

async function connect() {
  try {
    const r = await fetch(`${API}/stats`, { signal: AbortSignal.timeout(4000) });
    if (r.ok) {
      API_UP = true;
      applyStats(await r.json());
      setLive(true);
    }
  } catch { setLive(false); }
}

async function loadData() {
  if (API_UP) { await fetchJobs(); await fetchCompanies(); }
  else {
    JOBS = (MCA_DATA.jobs || []).map(j => ({ ...j, apply_url: j.apply_url || j.direct_url || '#' }));
    COMPANIES = MCA_DATA.companies || [];
    applyStats({
      total_jobs: JOBS.length,
      fresher_jobs: JOBS.filter(j => j.exp_level === 'entry_level').length,
      total_companies: COMPANIES.length,
      crawled_companies: COMPANIES.length,
      ats_breakdown: {},
    });
  }
}

async function fetchJobs(append = false) {
  if (S.loading) return; S.loading = true;
  const p = new URLSearchParams({ limit: S.pageSize, offset: S.page * S.pageSize, sort: 'newest' });
  if (S.search) p.set('search', S.search);
  if (S.exp !== 'all') p.set('exp', S.exp);
  try {
    const r = await fetch(`${API}/jobs?${p}`);
    const d = await r.json();
    S.total = d.total;
    JOBS = append ? [...JOBS, ...d.jobs] : d.jobs;
  } catch (e) { console.warn('fetchJobs:', e); }
  S.loading = false;
}

async function fetchCompanies() {
  try {
    const r = await fetch(`${API}/companies?limit=500`);
    COMPANIES = (await r.json()).companies || [];
  } catch { COMPANIES = MCA_DATA.companies || []; }
}

// ── Stats ─────────────────────────────────────────────────────────────

function applyStats(s) {
  const fmt = n => n ? n.toLocaleString('en-IN') : '—';
  const set = (id, v) => { const e = $(id); if (e) e.textContent = v; };
  set('stat-companies', fmt(s.total_companies || s.crawled_companies));
  set('stat-portals',   fmt(s.crawled_companies || s.total_companies));
  set('stat-freshers',  fmt(s.fresher_jobs));
  set('stat-ats',       fmt(Object.keys(s.ats_breakdown || {}).length || 5));
}

function setLive(ok) {
  const dot = document.querySelector('.live-dot');
  const pill = document.querySelector('.live-pill');
  if (dot) dot.style.background = ok ? 'var(--green)' : '#ef4444';
  if (pill) pill.style.color = ok ? 'var(--green)' : '#ef4444';
}

// ── Events ────────────────────────────────────────────────────────────

function bindEvents() {
  qsa('.nav-link').forEach(a => a.addEventListener('click', e => {
    e.preventDefault();
    const v = a.dataset.view; if (v) { switchView(v); closeMobileNav(); }
  }));

  $('menu-btn')?.addEventListener('click', () => $('mobile-nav')?.classList.toggle('hidden'));

  qsa('.exp-tab').forEach(btn => btn.addEventListener('click', () => {
    qsa('.exp-tab').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    S.exp = btn.dataset.exp; S.page = 0; refresh();
  }));

  const debouncedSearch = debounce(async () => {
    S.search = $('global-search-input')?.value.trim() || '';
    S.page = 0; await refresh();
  }, 300);
  $('global-search-input')?.addEventListener('input', debouncedSearch);

  $('sort-select')?.addEventListener('change', e => { S.sort = e.target.value; renderJobs(); });

  $('filter-toggle-btn')?.addEventListener('click', () => {
    $('filters-panel')?.classList.toggle('hidden');
  });

  $('mca-search-input')?.addEventListener('input', e => { S.mcaSearch = e.target.value.toLowerCase(); renderCompanies(); });
  $('roc-filter-select')?.addEventListener('change', e => { S.rocFilter = e.target.value; renderCompanies(); });

  $('load-more-btn')?.addEventListener('click', async () => {
    S.page++;
    if (API_UP) { await fetchJobs(true); renderJobs(); }
  });

  $('close-modal-btn')?.addEventListener('click', closeModal);
  $('cin-modal')?.addEventListener('click', e => { if (e.target === $('cin-modal')) closeModal(); });
  document.addEventListener('keydown', e => { if (e.key === 'Escape') closeModal(); });
}

function closeMobileNav() { $('mobile-nav')?.classList.add('hidden'); }
function debounce(fn, ms) { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; }

// ── Views ─────────────────────────────────────────────────────────────

function switchView(id) {
  S.view = id;
  qsa('.view').forEach(v => v.classList.toggle('active', v.id === id));
  qsa('.nav-link').forEach(a => a.classList.toggle('active', a.dataset.view === id));
  if (id === 'saved-view') renderSaved();
  if (id === 'companies-view') renderCompanies();
  if (id === 'ats-view') renderPortals();
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

// ── Filters ───────────────────────────────────────────────────────────

function buildFilters() {
  const all = JOBS.length ? JOBS : (MCA_DATA?.jobs || []);
  const cats = [...new Set(all.map(j => j.department || j.category).filter(Boolean))];
  const locs = ['Bengaluru', 'Mumbai', 'Delhi', 'Hyderabad', 'Pune', 'Chennai', 'Gurugram', 'Remote'];
  const atsL = [...new Set(all.map(j => j.ats).filter(Boolean))];

  buildChipList('category-filter-list', cats, v => {
    if (S.cats.has(v)) S.cats.delete(v); else S.cats.add(v); renderJobs();
  });
  buildChipList('location-filter-list', locs, v => {
    if (S.locs.has(v)) S.locs.delete(v); else S.locs.add(v); renderJobs();
  });
  buildChipList('ats-filter-list', atsL, v => {
    if (S.ats.has(v)) S.ats.delete(v); else S.ats.add(v); refresh();
  });
}

function buildChipList(id, items, onClick) {
  const el = $(id); if (!el) return;
  el.innerHTML = items.map(item => `<button class="filter-chip" data-val="${item}">${item}</button>`).join('');
  el.querySelectorAll('.filter-chip').forEach(chip => chip.addEventListener('click', () => {
    chip.classList.toggle('active');
    onClick(chip.dataset.val);
  }));
}

// ── Refresh ───────────────────────────────────────────────────────────

async function refresh() {
  if (API_UP) { showSkeletons(); await fetchJobs(); }
  renderJobs();
}

function showSkeletons() {
  const g = $('jobs-cards-grid'); if (!g) return;
  g.innerHTML = Array(6).fill('<div class="skeleton-card"></div>').join('');
  $('load-more-wrap')?.classList.add('hidden');
}

// ── Render Jobs ───────────────────────────────────────────────────────

function renderJobs() {
  const grid = $('jobs-cards-grid'); if (!grid) return;
  let jobs = [...JOBS];

  if (!API_UP) {
    if (S.exp !== 'all') jobs = jobs.filter(j => j.exp_level === S.exp);
    if (S.search) {
      const q = S.search.toLowerCase();
      jobs = jobs.filter(j =>
        [j.title, j.company_name, j.brand, j.company_cin, ...(j.skills||[])].join(' ').toLowerCase().includes(q)
      );
    }
    jobs.sort((a, b) => {
      const da = a.first_seen || a.posted_date || '';
      const db = b.first_seen || b.posted_date || '';
      return db.localeCompare(da);
    });
  }

  if (S.cats.size) jobs = jobs.filter(j => S.cats.has(j.department || j.category));
  if (S.locs.size) jobs = jobs.filter(j => [...S.locs].some(l => (j.location||'').toLowerCase().includes(l.toLowerCase())));

  // Sort
  if (S.sort === 'company') jobs.sort((a,b) => (a.brand||a.company_name||'').localeCompare(b.brand||b.company_name||''));
  if (S.sort === 'exp-asc') jobs.sort((a,b) => (a.exp_years||0)-(b.exp_years||0));
  if (S.sort === 'exp-desc') jobs.sort((a,b) => (b.exp_years||0)-(a.exp_years||0));

  const total = API_UP ? S.total : jobs.length;
  $('jobs-results-count').textContent = jobs.length
    ? `Showing ${jobs.length.toLocaleString('en-IN')}${API_UP && total > jobs.length ? ' of ' + total.toLocaleString('en-IN') : ''} jobs`
    : 'No jobs found';

  // Update stat
  const sj = $('stat-freshers');
  if (sj && jobs.length) sj.textContent = jobs.filter(j => j.exp_level === 'entry_level').length.toLocaleString('en-IN');

  if (!jobs.length) {
    grid.innerHTML = `<div class="empty-state">
      <i class="fa-solid fa-briefcase"></i>
      <h3>No jobs found</h3>
      <p>Try a different search or filter.</p>
    </div>`;
    $('load-more-wrap')?.classList.add('hidden');
    return;
  }

  grid.innerHTML = jobs.map(jobCard).join('');
  bindCardEvents();

  const lmw = $('load-more-wrap');
  if (API_UP && JOBS.length < S.total) lmw?.classList.remove('hidden');
  else lmw?.classList.add('hidden');
}

// ── Job Card ──────────────────────────────────────────────────────────

function timeAgo(dateStr) {
  if (!dateStr) return '';
  const diff = Math.floor((Date.now() - new Date(dateStr).getTime()) / 86400000);
  if (diff <= 0) return 'Today';
  if (diff === 1) return 'Yesterday';
  if (diff < 7) return `${diff}d ago`;
  if (diff < 30) return `${Math.floor(diff/7)}w ago`;
  return `${Math.floor(diff/30)}mo ago`;
}

function jobCard(j) {
  const saved   = S.saved.has(j.id);
  const brand   = j.brand || j.company_name || '';
  const initials = brand.split(/[\s&]+/).filter(Boolean).map(w => w[0]).join('').slice(0,2).toUpperCase();
  const apply   = j.apply_url || j.direct_url || '#';
  const cin     = j.company_cin || '';
  const skills  = (j.skills || []).slice(0, 5);
  const isFresh = j.exp_level === 'entry_level';
  const isSenior = j.exp_level === 'experienced';
  const expClass = isFresh ? 'badge-fresher' : isSenior ? 'badge-senior' : 'badge-mid';
  const expLabel = isFresh ? 'Fresher · 0-2 Yrs' : isSenior ? 'Senior · 5+ Yrs' : 'Mid · 2-5 Yrs';
  const dept = j.department || j.category || '';
  const desc = (j.description || '').replace(/<[^>]+>/g,' ').trim().slice(0, 180);
  const date = timeAgo(j.first_seen || j.posted_date);

  return `
<div class="job-card">
  <div class="card-body">
    <div class="card-top-row">
      <div class="company-badge">${initials}</div>
      <div class="card-top-right">
        <button class="btn-bk${saved?' saved':''}" data-id="${j.id}" title="Bookmark">
          <i class="fa-${saved?'solid':'regular'} fa-bookmark"></i>
        </button>
      </div>
    </div>

    <div class="company-name-row">
      <span class="co-name">${brand}</span>
      ${cin ? `<span class="cin-tag" onclick="openModal('${cin}')" title="View MCA record">${cin}</span>` : ''}
    </div>

    <div class="job-title">${j.title}</div>

    <div class="badges-row">
      <span class="badge ${expClass}">${expLabel}</span>
      ${j.location ? `<span class="badge badge-loc"><i class="fa-solid fa-location-dot"></i> ${j.location}</span>` : ''}
      ${j.ats ? `<span class="badge badge-ats">${j.ats}</span>` : ''}
      ${dept ? `<span class="badge badge-dept">${dept}</span>` : ''}
    </div>

    ${desc ? `<div class="job-desc">${desc}</div>` : ''}

    ${skills.length ? `<div class="skills-row">${skills.map(s => `<span class="skill">${s}</span>`).join('')}</div>` : ''}
  </div>

  <div class="card-foot">
    <span class="card-date">${date ? date + ' · ' : ''}Not disclosed</span>
    <a href="${apply}" target="_blank" rel="noopener" class="btn-apply">
      Apply Direct <i class="fa-solid fa-arrow-up-right-from-square" style="font-size:.7rem"></i>
    </a>
  </div>
</div>`;
}

function bindCardEvents() {
  qsa('.btn-bk').forEach(btn => btn.addEventListener('click', e => {
    e.stopPropagation();
    const id = btn.dataset.id;
    if (S.saved.has(id)) S.saved.delete(id); else { S.saved.add(id); showToast('Saved!'); }
    localStorage.setItem('mca_cg_saved', JSON.stringify([...S.saved]));
    syncBadge();
    btn.classList.toggle('saved', S.saved.has(id));
    btn.querySelector('i').className = `fa-${S.saved.has(id)?'solid':'regular'} fa-bookmark`;
    if (S.view === 'saved-view') renderSaved();
  }));
}

function syncBadge() { const e = $('saved-count'); if (e) e.textContent = S.saved.size; }

// ── MCA Table ─────────────────────────────────────────────────────────

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

  if (!list.length) { tbody.innerHTML = `<tr><td colspan="9" class="loading-cell">No companies found.</td></tr>`; return; }

  tbody.innerHTML = list.map(c => `
    <tr>
      <td><span class="td-cin">${c.cin||'—'}</span></td>
      <td><div class="td-name">${c.legal_name||c.name||'—'}</div><div class="td-brand">${c.brand||''}</div></td>
      <td>${c.roc||'—'}</td>
      <td>${c.incorporated||'—'}</td>
      <td style="font-family:var(--mono);font-size:.75rem;color:var(--green)">${c.capital||'—'}</td>
      <td><a href="${c.career_url||'#'}" target="_blank" class="td-link">${c.domain||''}/careers ↗</a></td>
      <td><span class="td-ats">${c.ats||'—'}</span></td>
      <td><span class="td-jobs">${c.jobs_found > 0 ? c.jobs_found : '—'}</span></td>
      <td><button class="btn-inspect" onclick="openModal('${c.cin||''}')">Inspect</button></td>
    </tr>`).join('');
}

// ── Portals ───────────────────────────────────────────────────────────

function renderPortals() {
  const grid = $('career-sites-grid'); if (!grid) return;
  const all = COMPANIES.length ? COMPANIES : (MCA_DATA?.companies || []);
  grid.innerHTML = all.slice(0, 80).map(c => `
    <div class="portal-card">
      <div class="pc-brand">${c.brand||c.name}</div>
      <div class="pc-legal">${c.legal_name||c.name}</div>
      <div class="pc-meta">
        <div><i class="fa-solid fa-link"></i> ${c.domain||'—'}</div>
        <div><i class="fa-solid fa-server"></i> ${c.ats||'Custom'}</div>
        ${c.jobs_found ? `<div><i class="fa-solid fa-briefcase"></i> ${c.jobs_found} live jobs</div>` : ''}
      </div>
      <a href="${c.career_url||'#'}" target="_blank" class="btn-primary full">
        Open Career Portal <i class="fa-solid fa-arrow-up-right-from-square"></i>
      </a>
    </div>`).join('');
}

// ── Saved ─────────────────────────────────────────────────────────────

function renderSaved() {
  const grid = $('saved-jobs-grid'); if (!grid) return;
  const all = JOBS.length ? JOBS : (MCA_DATA?.jobs||[]).map(j=>({...j, apply_url:j.apply_url||j.direct_url||'#'}));
  const list = all.filter(j => S.saved.has(j.id));
  if (!list.length) {
    grid.innerHTML = `<div class="empty-state">
      <i class="fa-regular fa-bookmark"></i>
      <h3>No saved jobs yet</h3>
      <p>Click the bookmark icon on any job card.</p>
    </div>`; return;
  }
  grid.innerHTML = list.map(jobCard).join('');
  bindCardEvents();
}

// ── Modal ─────────────────────────────────────────────────────────────

window.openModal = function(cin) {
  if (!cin) return;
  const all = COMPANIES.length ? COMPANIES : (MCA_DATA?.companies||[]);
  const c = all.find(x => x.cin === cin) || {
    cin, legal_name:'MCA REGISTERED ENTITY', brand:'—', roc:'—',
    incorporated:'—', company_class:'—', capital:'—', domain:'—', career_url:'#', ats:'—'
  };
  $('modal-company-name').textContent = c.legal_name||c.name||'—';
  $('modal-cin-badge').textContent    = `CIN: ${c.cin}`;
  $('modal-visit-career-btn').href    = c.career_url||'#';
  $('modal-body-content').innerHTML   = `
    <div class="modal-grid">
      <div><div class="m-label">Brand</div><div class="m-val">${c.brand||'—'}</div></div>
      <div><div class="m-label">ROC</div><div class="m-val">${c.roc||'—'}</div></div>
      <div><div class="m-label">Incorporated</div><div class="m-val">${c.incorporated||'—'}</div></div>
      <div><div class="m-label">Class</div><div class="m-val">${c.company_class||'—'}</div></div>
      <div><div class="m-label">Capital</div><div class="m-val">${c.capital||'—'}</div></div>
      <div><div class="m-label">ATS</div><div class="m-val">${c.ats||'Custom'}</div></div>
      ${c.jobs_found ? `<div><div class="m-label">Live Jobs</div><div class="m-val" style="color:var(--blue)">${c.jobs_found}</div></div>` : ''}
    </div>
    <div class="modal-verify">
      <div class="modal-verify-title"><i class="fa-solid fa-circle-check"></i> MCA Verified</div>
      <div class="modal-verify-body">Career portal mapped for <strong>${c.brand||c.name}</strong> — <code style="font-family:var(--mono);color:var(--blue);font-size:.75rem">${c.career_url||'—'}</code></div>
    </div>`;
  $('cin-modal').classList.remove('hidden');
};

function closeModal() { $('cin-modal')?.classList.add('hidden'); }

// ── Toast ─────────────────────────────────────────────────────────────

let toastTimer;
function showToast(msg) {
  const el = $('toast'); if (!el) return;
  el.textContent = msg; el.classList.remove('hidden');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.add('hidden'), 2500);
}
