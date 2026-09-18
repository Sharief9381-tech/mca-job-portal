/* =====================================================================
   INDIA/CAREERS — App Controller
   Fetches live data from Render API, falls back to MCA_DATA mock.
   ===================================================================== */

const API = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
  ? 'http://localhost:8000/api'
  : 'https://mca-job-portal.onrender.com/api';

let JOBS = [], COMPANIES = [], API_UP = false;
const $ = id => document.getElementById(id);
const qsa = s => document.querySelectorAll(s);

const AVATAR_COLORS = ['av-blue','av-green','av-orange','av-purple','av-red','av-teal','av-pink','av-yellow'];
function avatarColor(name) {
  let h = 0;
  for (let c of (name||'')) h = (h * 31 + c.charCodeAt(0)) & 0xffff;
  return AVATAR_COLORS[h % AVATAR_COLORS.length];
}

const S = {
  view: 'jobs-view',
  exp: 'all',
  search: '',
  page: 0,
  pageSize: 30,
  total: 0,
  loading: false,
  saved: new Set(JSON.parse(localStorage.getItem('india_careers_saved') || '[]')),
  rocFilter: 'all',
  mcaSearch: '',
};

// ── Boot ──────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', async () => {
  showSkeletons();
  await connect();
  await loadData();
  bindEvents();
  renderJobs();
  renderCompanies();
  renderPortals();
  renderSaved();
  syncBadge();
});

// ── API ───────────────────────────────────────────────────────────────────

async function connect() {
  try {
    const r = await fetch(`${API}/stats`, { signal: AbortSignal.timeout(4000) });
    if (r.ok) {
      API_UP = true;
      const s = await r.json();
      applyStats(s);
      setLiveStatus(true);
    }
  } catch {
    setLiveStatus(false);
  }
}

async function loadData() {
  if (API_UP) {
    await fetchJobs();
    await fetchCompanies();
  } else {
    JOBS = (MCA_DATA.jobs || []).map(j => ({ ...j, apply_url: j.direct_url || '#' }));
    COMPANIES = MCA_DATA.companies || [];
    applyStats({
      total_jobs: JOBS.length,
      fresher_jobs: JOBS.filter(j => j.exp_level === 'entry_level').length,
      experienced_jobs: JOBS.filter(j => j.exp_level === 'experienced').length,
      total_companies: COMPANIES.length,
      crawled_companies: COMPANIES.length,
      ats_breakdown: {},
    });
  }
}

async function fetchJobs(append = false) {
  if (S.loading) return;
  S.loading = true;
  const p = new URLSearchParams({ limit: S.pageSize, offset: S.page * S.pageSize });
  if (S.search)       p.set('search', S.search);
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
    const d = await r.json();
    COMPANIES = d.companies || [];
  } catch { COMPANIES = MCA_DATA.companies || []; }
}

// ── Stats ─────────────────────────────────────────────────────────────────

function applyStats(s) {
  const set = (id, v) => { const e = $(id); if (e) e.textContent = v; };
  const fmt = n => n ? n.toLocaleString('en-IN') : '—';

  set('hero-jobs',       fmt(s.total_jobs));
  set('stat-companies',  fmt(s.crawled_companies || s.total_companies));
  set('stat-jobs',       fmt(s.total_jobs));
  set('stat-sources',    fmt(Object.keys(s.ats_breakdown || {}).length || 5));
  set('stat-updated',    '2m');
  set('last-updated',    'Just now');
}

function setLiveStatus(ok) {
  const tag = $('data-status');
  if (tag) tag.textContent = ok ? 'UPDATED' : 'OFFLINE';
  const dot = document.querySelector('.live-dot');
  if (dot) dot.style.background = ok ? 'var(--green)' : '#ef4444';
  const sdot = $('status-dot');
  if (sdot) sdot.style.background = ok ? 'var(--green)' : '#ef4444';
  const slabel = $('status-label');
  if (slabel) slabel.textContent = ok ? 'VERIFIED CAREER LINKS' : 'MOCK DATA';
  if (slabel) slabel.style.color = ok ? 'var(--green)' : '#ef4444';
}

// ── Events ────────────────────────────────────────────────────────────────

function bindEvents() {
  // Sidebar nav
  qsa('.nav-item').forEach(a => a.addEventListener('click', e => {
    e.preventDefault();
    const v = a.dataset.view;
    if (v) switchView(v);
  }));

  // Exp filter tabs
  qsa('.exp-btn').forEach(btn => btn.addEventListener('click', () => {
    qsa('.exp-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    S.exp = btn.dataset.exp;
    S.page = 0;
    refresh();
  }));

  // Search
  $('global-search-input')?.addEventListener('input', debounce(e => {
    S.search = e.target.value.trim();
    S.page = 0;
    refresh();
  }, 300));

  // MCA search
  $('mca-search-input')?.addEventListener('input', e => {
    S.mcaSearch = e.target.value.toLowerCase();
    renderCompanies();
  });
  $('roc-filter-select')?.addEventListener('change', e => {
    S.rocFilter = e.target.value;
    renderCompanies();
  });

  // Load more
  $('load-more-btn')?.addEventListener('click', async () => {
    S.page++;
    if (API_UP) { await fetchJobs(true); renderJobs(); }
  });

  // Resolver
  $('run-resolver-btn')?.addEventListener('click', runResolver);

  // Modal close
  $('close-modal-btn')?.addEventListener('click', closeModal);
  $('cin-modal')?.addEventListener('click', e => { if (e.target === $('cin-modal')) closeModal(); });
  document.addEventListener('keydown', e => { if (e.key === 'Escape') closeModal(); });
}

function debounce(fn, ms) {
  let t;
  return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
}

// ── View switching ────────────────────────────────────────────────────────

function switchView(id) {
  S.view = id;
  qsa('.view').forEach(v => v.classList.toggle('active', v.id === id));
  qsa('.nav-item').forEach(a => a.classList.toggle('active', a.dataset.view === id));
  if (id === 'saved-view')    renderSaved();
  if (id === 'companies-view') renderCompanies();
  if (id === 'ats-view')      renderPortals();
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

// ── Refresh ───────────────────────────────────────────────────────────────

async function refresh() {
  if (API_UP) { showSkeletons(); await fetchJobs(); }
  renderJobs();
}

function showSkeletons() {
  const g = $('jobs-cards-grid'); if (!g) return;
  g.innerHTML = Array(6).fill('<div class="card-skeleton"></div>').join('');
  $('load-more-wrap')?.classList.add('hidden');
}

// ── Render Jobs ───────────────────────────────────────────────────────────

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
  }

  const total = API_UP ? S.total : jobs.length;
  const shown = jobs.length;

  $('jobs-results-count').textContent = shown
    ? `${total.toLocaleString('en-IN')} JOBS`
    : '';
  $('hero-jobs').textContent = total ? total.toLocaleString('en-IN') : '—';
  $('stat-jobs').textContent = total ? total.toLocaleString('en-IN') : '—';

  if (!shown) {
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

function jobCard(j) {
  const saved   = S.saved.has(j.id);
  const brand   = j.brand || j.company_name || '';
  const initials = brand.split(/\s+/).map(w => w[0]).join('').slice(0,2).toUpperCase();
  const avColor = avatarColor(brand);
  const apply   = j.apply_url || j.direct_url || '#';
  const cin     = j.company_cin || '';
  const skills  = (j.skills || []).slice(0, 4);
  const isFresh = j.exp_level === 'entry_level';
  const isSenior = j.exp_level === 'experienced';
  const expClass = isFresh ? 'exp-fresher' : isSenior ? 'exp-senior' : 'exp-mid';
  const expLabel = j.exp_display || (isFresh ? '0–2 yrs' : isSenior ? '5+ yrs' : '2–5 yrs');

  // Posted time
  let timeAgo = '';
  if (j.posted_date) {
    const diff = Math.floor((Date.now() - new Date(j.posted_date).getTime()) / 3600000);
    timeAgo = diff < 1 ? 'Just now' : diff < 24 ? `${diff}h ago` : `${Math.floor(diff/24)}d ago`;
  }

  const source = `${brand} Careers${timeAgo ? ' · ' + timeAgo : ''}`;

  return `
<div class="job-card">
  <div class="card-top">
    <div class="card-header">
      <div class="card-avatar ${avColor}">${initials}</div>
      <div class="card-header-right">
        <button class="btn-bookmark-card ${saved?'saved':''}" data-id="${j.id}" title="Bookmark">
          <i class="fa-${saved?'solid':'regular'} fa-bookmark"></i>
        </button>
      </div>
    </div>
    <div class="card-source">${source}</div>
    <div class="card-title">${j.title}</div>
    <div class="card-meta">
      ${j.location ? `<span class="card-meta-item"><i class="fa-solid fa-location-dot"></i> ${j.location}</span>` : ''}
      <span class="exp-badge ${expClass}">${expLabel}</span>
    </div>
    ${skills.length ? `<div class="card-skills">${skills.map(s => `<span class="skill-tag">${s}</span>`).join('')}</div>` : ''}
  </div>
  <div class="card-bottom">
    ${cin ? `<button class="btn-inspect" onclick="openModal('${cin}')" title="MCA Details">MCA</button>` : ''}
    <a href="${apply}" target="_blank" rel="noopener" class="btn-apply-official">
      Apply on official site <i class="fa-solid fa-arrow-up-right-from-square"></i>
    </a>
  </div>
</div>`;
}

function bindCardEvents() {
  qsa('.btn-bookmark-card').forEach(btn => btn.addEventListener('click', e => {
    e.stopPropagation();
    const id = btn.dataset.id;
    if (S.saved.has(id)) S.saved.delete(id);
    else { S.saved.add(id); showToast('Saved!'); }
    localStorage.setItem('india_careers_saved', JSON.stringify([...S.saved]));
    syncBadge();
    btn.classList.toggle('saved', S.saved.has(id));
    btn.querySelector('i').className = `fa-${S.saved.has(id)?'solid':'regular'} fa-bookmark`;
    if (S.view === 'saved-view') renderSaved();
  }));
}

function syncBadge() {
  const el = $('saved-count'); if (el) el.textContent = S.saved.size;
}

// ── MCA Directory ─────────────────────────────────────────────────────────

function renderCompanies() {
  const tbody = $('mca-table-body'); if (!tbody) return;
  const all = COMPANIES.length ? COMPANIES : (MCA_DATA?.companies || []);

  let list = all.filter(c => {
    if (S.rocFilter !== 'all' && c.roc !== S.rocFilter) return false;
    if (S.mcaSearch) {
      const h = [c.cin, c.legal_name || c.name, c.brand, c.domain].join(' ').toLowerCase();
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
      <td><span class="cin-code">${c.cin || '—'}</span></td>
      <td>
        <div class="company-main">${c.legal_name || c.name || '—'}</div>
        <div class="company-sub">${c.brand || ''}</div>
      </td>
      <td>${c.roc || '—'}</td>
      <td>${c.incorporated || '—'}</td>
      <td style="font-family:var(--font-mono);font-size:0.75rem;color:var(--green)">${c.capital || '—'}</td>
      <td><a href="${c.career_url || '#'}" target="_blank" class="table-link">${c.domain || ''}/careers ↗</a></td>
      <td><span class="ats-pill">${c.ats || '—'}</span></td>
      <td><span class="jobs-count-pill">${c.jobs_found > 0 ? c.jobs_found : '—'}</span></td>
      <td><button class="btn-inspect" onclick="openModal('${c.cin || ''}')">Inspect</button></td>
    </tr>`).join('');
}

// ── ATS Portals ───────────────────────────────────────────────────────────

function renderPortals() {
  const grid = $('career-sites-grid'); if (!grid) return;
  const all = COMPANIES.length ? COMPANIES : (MCA_DATA?.companies || []);

  grid.innerHTML = all.slice(0, 80).map(c => `
    <div class="portal-card">
      <div class="portal-card-brand">${c.brand || c.name}</div>
      <div class="portal-card-legal">${c.legal_name || c.name}</div>
      <div class="portal-card-meta">
        <div><i class="fa-solid fa-link"></i> ${c.domain || '—'}</div>
        <div><i class="fa-solid fa-server"></i> ${c.ats || 'Custom'}</div>
        ${c.jobs_found ? `<div><i class="fa-solid fa-briefcase"></i> ${c.jobs_found} live jobs</div>` : ''}
      </div>
      <a href="${c.career_url || '#'}" target="_blank" class="btn-primary">
        Open Career Portal <i class="fa-solid fa-arrow-up-right-from-square"></i>
      </a>
    </div>`).join('');
}

// ── Saved ─────────────────────────────────────────────────────────────────

function renderSaved() {
  const grid = $('saved-jobs-grid'); if (!grid) return;
  const all = JOBS.length ? JOBS : (MCA_DATA?.jobs || []).map(j => ({...j, apply_url: j.direct_url || '#'}));
  const list = all.filter(j => S.saved.has(j.id));

  if (!list.length) {
    grid.innerHTML = `<div class="empty-state">
      <i class="fa-regular fa-bookmark"></i>
      <h3>No saved jobs yet</h3>
      <p>Click the bookmark icon on a job card to save it here.</p>
    </div>`;
    return;
  }
  grid.innerHTML = list.map(jobCard).join('');
  bindCardEvents();
}

// ── Modal ─────────────────────────────────────────────────────────────────

window.openModal = function(cin) {
  if (!cin) return;
  const all = COMPANIES.length ? COMPANIES : (MCA_DATA?.companies || []);
  const c = all.find(x => x.cin === cin) || {
    cin, legal_name:'MCA REGISTERED ENTITY', brand:'—',
    roc:'—', incorporated:'—', company_class:'—', capital:'—',
    domain:'—', career_url:'#', ats:'—'
  };

  $('modal-company-name').textContent = c.legal_name || c.name || '—';
  $('modal-cin-badge').textContent    = `CIN: ${c.cin}`;
  $('modal-visit-career-btn').href    = c.career_url || '#';

  $('modal-body-content').innerHTML = `
    <div class="modal-info-grid">
      <div><div class="modal-info-label">Brand</div><div class="modal-info-value">${c.brand||'—'}</div></div>
      <div><div class="modal-info-label">ROC</div><div class="modal-info-value">${c.roc||'—'}</div></div>
      <div><div class="modal-info-label">Incorporated</div><div class="modal-info-value">${c.incorporated||'—'}</div></div>
      <div><div class="modal-info-label">Class</div><div class="modal-info-value">${c.company_class||'—'}</div></div>
      <div><div class="modal-info-label">Capital</div><div class="modal-info-value">${c.capital||'—'}</div></div>
      <div><div class="modal-info-label">ATS</div><div class="modal-info-value">${c.ats||'Custom'}</div></div>
      ${c.jobs_found ? `<div><div class="modal-info-label">Live Jobs</div><div class="modal-info-value" style="color:var(--blue)">${c.jobs_found}</div></div>` : ''}
    </div>
    <div class="modal-verify">
      <div class="modal-verify-title"><i class="fa-solid fa-circle-check"></i> MCA Verified</div>
      <div class="modal-verify-body">Career portal mapped for <strong>${c.brand||c.name}</strong> — <code>${c.career_url||'—'}</code></div>
    </div>`;

  $('cin-modal').classList.remove('hidden');
};

function closeModal() { $('cin-modal')?.classList.add('hidden'); }

// ── Resolver ──────────────────────────────────────────────────────────────

function runResolver() {
  const raw = $('resolver-input-name').value.trim();
  if (!raw) { showToast('Enter a company name or CIN'); return; }

  const btn = $('run-resolver-btn');
  btn.disabled = true;
  btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Resolving…';

  const all = COMPANIES.length ? COMPANIES : (MCA_DATA?.companies || []);
  const q = raw.toLowerCase();
  const match = all.find(c =>
    (c.legal_name||c.name||'').toLowerCase().includes(q) ||
    (c.brand||'').toLowerCase().includes(q) ||
    (c.cin||'').toLowerCase() === q
  );

  setTimeout(() => {
    btn.disabled = false;
    btn.innerHTML = '<i class="fa-solid fa-magnifying-glass"></i> Resolve Career Portal';

    const box = $('resolver-result-box');
    box.classList.remove('hidden','success','estimate');

    if (match) {
      box.classList.add('success');
      box.innerHTML = `
        <div style="font-weight:700;color:var(--green);margin-bottom:12px">
          <i class="fa-solid fa-circle-check"></i> Found in MCA Registry — ${match.brand||match.name}
        </div>
        <div style="color:var(--gray-700)">
          <div><strong>Legal Name:</strong> ${match.legal_name||match.name}</div>
          <div><strong>CIN:</strong> <code style="font-family:var(--font-mono);color:var(--blue)">${match.cin||'—'}</code></div>
          <div><strong>Career Portal:</strong> <a href="${match.career_url}" target="_blank" style="color:var(--blue)">${match.career_url}</a></div>
          <div><strong>ATS:</strong> ${match.ats||'Custom'}</div>
          ${match.jobs_found ? `<div><strong>Live Jobs:</strong> <span style="color:var(--green)">${match.jobs_found}</span></div>` : ''}
        </div>`;
    } else {
      const clean = raw.replace(/PRIVATE LIMITED|LIMITED|LLP|INDIA/gi,'').trim();
      const domain = $('resolver-input-domain').value.trim() || `${clean.toLowerCase().replace(/\s+/g,'')}.com`;
      box.classList.add('estimate');
      box.innerHTML = `
        <div style="font-weight:700;color:var(--orange);margin-bottom:12px">
          <i class="fa-solid fa-triangle-exclamation"></i> Not yet indexed — estimated result
        </div>
        <div style="color:var(--gray-700)">
          <div><strong>Estimated Domain:</strong> <a href="https://${domain}" target="_blank" style="color:var(--blue)">${domain}</a></div>
          <div><strong>Likely Career URL:</strong> <a href="https://${domain}/careers" target="_blank" style="color:var(--blue)">${domain}/careers</a></div>
          <div style="margin-top:10px;padding:8px 12px;background:#fff7ed;border-radius:6px;font-size:0.82rem;color:var(--orange)">
            Run <code>python crawl.py --domain ${domain}</code> to index this company.
          </div>
        </div>`;
    }
  }, 500);
}

// ── Toast ─────────────────────────────────────────────────────────────────

let toastTimer;
function showToast(msg) {
  const el = $('toast'); if (!el) return;
  el.textContent = msg;
  el.classList.remove('hidden');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.add('hidden'), 2500);
}
