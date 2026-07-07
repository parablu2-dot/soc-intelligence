// SoC Intelligence Dashboard — 프론트엔드 SPA
// v2 Phase 2: 인터랙티브 드릴다운 + 생태계 그래프

'use strict';

// ── 데이터 소스 정의 (config.yaml과 동기화 필요) ────────────────────────────
const DATA_SOURCES = [
  { axis: 'mobile_ap',      company: 'apple' },
  { axis: 'mobile_ap',      company: 'qualcomm' },
  { axis: 'mobile_ap',      company: 'mediatek' },
  { axis: 'mobile_ap',      company: 'unisoc' },
  { axis: 'mobile_ap',      company: 'exynos' },
  { axis: 'mobile_ap',      company: 'googlenews' },  // Phase 4: 축별 뉴스 확장
  { axis: 'hpc_datacenter', company: 'nvidia' },
  { axis: 'hpc_datacenter', company: 'amd' },
  { axis: 'hpc_datacenter', company: 'intel' },
  { axis: 'hpc_datacenter', company: 'hiring' },      // Phase 3: 채용 레이더
  { axis: 'hpc_datacenter', company: 'googlenews' },  // Phase 4: 축별 뉴스 확장
  { axis: 'custom_soc',     company: 'broadcom' },
  { axis: 'custom_soc',     company: 'marvell' },
  { axis: 'custom_soc',     company: 'hyperscaler_inhouse' },
  { axis: 'custom_soc',     company: 'googlenews' },  // Phase 4: 축별 뉴스 확장
  { axis: 'foundry',        company: 'tsmc' },
  { axis: 'foundry',        company: 'samsung_foundry' },
  { axis: 'foundry',        company: 'intel_foundry' },
  { axis: 'foundry',        company: 'globalfoundries' },
  { axis: 'foundry',        company: 'smic' },
  { axis: 'foundry',        company: 'trendforce' },   // Phase 3: 캐파 실소스
  { axis: 'foundry',        company: 'etnews' },       // Phase 3: 한국어 소스
  { axis: 'foundry',        company: 'googlenews' },  // Phase 4: 축별 뉴스 확장
  { axis: 'packaging',      company: 'ase' },
  { axis: 'packaging',      company: 'amkor' },
  { axis: 'packaging',      company: 'jcet' },
  { axis: 'packaging',      company: 'googlenews' },  // Phase 4: 축별 뉴스 확장
];

const DATA_BASE = window.location.pathname.startsWith('/site/') ? '../data' : 'data';

// ── 5축 업체 관계 데이터 (생태계 그래프) ─────────────────────────────────
const _ECO_RELATIONS = [
  // 파운드리 공급 관계
  { from: 'tsmc',            to: 'apple',              type: 'supply',  label: 'A/M칩 파운드리' },
  { from: 'tsmc',            to: 'nvidia',             type: 'supply',  label: '파운드리+CoWoS' },
  { from: 'tsmc',            to: 'amd',                type: 'supply',  label: '파운드리' },
  { from: 'tsmc',            to: 'qualcomm',           type: 'supply',  label: '파운드리' },
  { from: 'tsmc',            to: 'broadcom',           type: 'supply',  label: '파운드리' },
  { from: 'tsmc',            to: 'hyperscaler_inhouse', type: 'supply', label: 'TPU/Trainium' },
  { from: 'tsmc',            to: 'mediatek',           type: 'supply',  label: '파운드리' },
  { from: 'samsung_foundry', to: 'exynos',             type: 'supply',  label: '파운드리(GAA)' },
  { from: 'samsung_foundry', to: 'qualcomm',           type: 'supply',  label: '파운드리(일부)' },
  { from: 'intel_foundry',   to: 'intel',              type: 'supply',  label: '내재화' },
  { from: 'globalfoundries', to: 'qualcomm',           type: 'supply',  label: 'legacy 노드' },
  // 패키징 공급 관계
  { from: 'ase',             to: 'nvidia',             type: 'supply',  label: 'OSAT 패키징' },
  { from: 'ase',             to: 'apple',              type: 'supply',  label: 'OSAT 패키징' },
  { from: 'amkor',           to: 'qualcomm',           type: 'supply',  label: 'OSAT 패키징' },
  { from: 'amkor',           to: 'amd',                type: 'supply',  label: 'OSAT 패키징' },
  // 경쟁 관계
  { from: 'tsmc',            to: 'samsung_foundry',    type: 'compete', label: '파운드리 경쟁' },
  { from: 'tsmc',            to: 'intel_foundry',      type: 'compete', label: '파운드리 경쟁' },
  { from: 'nvidia',          to: 'hyperscaler_inhouse', type: 'compete', label: 'AI 가속기 경쟁' },
  { from: 'apple',           to: 'qualcomm',           type: 'compete', label: 'Mobile AP 경쟁' },
  { from: 'apple',           to: 'mediatek',           type: 'compete', label: 'Mobile AP 경쟁' },
  // 파트너십
  { from: 'tsmc',            to: 'ase',                type: 'partner', label: 'CoWoS 협력' },
];

// 회사 표시명 (긴 슬러그 단축)
const _CO_DISPLAY = {
  hyperscaler_inhouse: 'Hyperscaler',
  samsung_foundry:     'Samsung Fdy',
  intel_foundry:       'Intel Fdy',
  globalfoundries:     'GF',
};
function coLabel(co) { return _CO_DISPLAY[co] || co; }

// 업체 로고 배지 — coLabel 표시명에서 이니셜 자동 파생 (하드코딩 금지)
function _logoInitials(co) {
  const words = coLabel(co).split(/\s+/);
  return words.length >= 2
    ? (words[0][0] + words[1][0]).toUpperCase()
    : coLabel(co).slice(0, 2).toUpperCase();
}
function coLogoBadge(co) {
  return `<span class="logo-badge">${_logoInitials(co)}</span>`;
}

// 크롤러 소스/집계 그룹 — 실제 개별 업체가 아님. 업체 비교 뷰
// (매트릭스·벤치마크 스코어·업체별 전략)에서 제외
const _NON_VENDOR_COMPANIES = ['hiring', 'trendforce', 'etnews', 'hyperscaler_inhouse', 'googlenews'];

// ── 모듈 정의 (v2 Phase 1: 17 → 13) ─────────────────────────────────────
const MODULES = [
  { id: 'today',      label: '오늘의 요약',           icon: '★' },
  { id: 'review',     label: '일일 리뷰 큐',           icon: '☑' },
  { id: 'articles',   label: '기사 (영어/중문/한국어)', icon: '◈' },
  { id: 'foundry',    label: '파운드리 캐파',           icon: '▦' },
  { id: 'ecosystem',  label: 'SoC 생태계·다이나믹스',  icon: '⬡' },
  { id: 'hiring',     label: '인재·채용 레이더',        icon: '⚑' },
  { id: 'metrics',    label: '숫자 대시보드',            icon: '▣' },
  { id: 'workbench',  label: '벤치마크 성능',            icon: '⛭' },
  { id: 'matrix',     label: '공정·패키징 매트릭스',     icon: '⊞' },
  { id: 'categories', label: 'SoC 카테고리',             icon: '⊟' },
  { id: 'competitor', label: '업체별 주요 전략',          icon: '◉' },
  { id: 'channels',   label: '정보 획득 채널',            icon: '⛓' },
  { id: 'control',    label: '크롤링 관제',             icon: '⚙' },
];

// ── 전역 상태 ──────────────────────────────────────────────────────────────
let allSignals = [];
let capacityRecords = [];   // FoundryCapacityRecord[] — Phase 3 backfill
let companySummaries = {};  // {generated_at, summaries: {company: {summary, signal_count, generated_at}}}
let _artSignals = { en: [], zh: [], kr: [] };  // 기사 탭 별 신호 캐시 (서브필터용)
let crawlStatus = [];
let currentModule = 'today';
let reviewedSet = new Set(JSON.parse(localStorage.getItem('reviewed') || '[]'));
let distillationNotes = JSON.parse(localStorage.getItem('distillation_notes') || '[]');
let distillationSummaries = {};  // {"axis||category": {summary, note_count, generated_at}} — 빌드타임 생성
let baselineNotes = [];  // BaselineNote[] — data/baseline/notes/*.md 빌드타임 파싱 (장문 deep-research 노트)
let versionInfo = null;  // data/refined/version.json — 단일 진실원 (version/date/maturity)
let sectorSummaries = {};  // {axis: {summary, item_count, generated_at}} — Phase 3 item 6, 빌드타임 생성
let dailyTop5 = [];  // [{axis, company, headline, url, source, published_date, score}] — Phase 3 item 7

// ── 부트스트랩 ─────────────────────────────────────────────────────────────
async function boot() {
  initTheme();
  renderLayout();
  await loadAllData();
  navigate(location.hash.replace('#', '') || 'today');
  window.addEventListener('resize', () => {
    if (currentModule === 'ecosystem') ecoDrawLines(_ECO_RELATIONS, null);
  });
}

// ── White/Black 테마 토글 ───────────────────────────────────────────────
function initTheme() {
  document.documentElement.dataset.theme = localStorage.getItem('theme') || 'dark';
}
window.toggleTheme = function() {
  const next = document.documentElement.dataset.theme === 'light' ? 'dark' : 'light';
  document.documentElement.dataset.theme = next;
  localStorage.setItem('theme', next);
  const btn = document.getElementById('theme-toggle');
  if (btn) btn.textContent = next === 'light' ? 'Black' : 'White';
};

async function loadAllData() {
  // 신호 데이터 로드
  const loads = DATA_SOURCES.map(async ({ axis, company }) => {
    const path = `${DATA_BASE}/refined/${axis}/${company}.json`;
    try {
      const resp = await fetch(path);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      crawlStatus.push({ axis, company, count: data.length, ok: true });
      return data;
    } catch {
      crawlStatus.push({ axis, company, count: 0, ok: false });
      return [];
    }
  });
  // capacity_records.json 병렬 로드 (Phase 3 backfill)
  const capLoad = fetch(`${DATA_BASE}/refined/foundry/capacity_records.json`)
    .then(r => r.ok ? r.json() : [])
    .catch(() => []);
  const sumLoad = fetch(`${DATA_BASE}/refined/company_summaries.json`)
    .then(r => r.ok ? r.json() : {})
    .catch(() => {});
  const distLoad = fetch(`${DATA_BASE}/refined/distillation_summaries.json`)
    .then(r => r.ok ? r.json() : {})
    .catch(() => ({}));
  const baselineNotesLoad = fetch(`${DATA_BASE}/refined/baseline_notes.json`)
    .then(r => r.ok ? r.json() : {})
    .catch(() => ({}));
  const versionLoad = fetch(`${DATA_BASE}/refined/version.json`)
    .then(r => r.ok ? r.json() : null)
    .catch(() => null);
  const sectorSumLoad = fetch(`${DATA_BASE}/refined/sector_summaries.json`)
    .then(r => r.ok ? r.json() : null)
    .catch(() => null);
  const top5Load = fetch(`${DATA_BASE}/refined/daily_top5.json`)
    .then(r => r.ok ? r.json() : null)
    .catch(() => null);

  const [results, capData, sumData, distData, baselineNotesData, versionData, sectorSumData, top5Data] =
    await Promise.all([Promise.all(loads), capLoad, sumLoad, distLoad, baselineNotesLoad, versionLoad, sectorSumLoad, top5Load]);
  allSignals = results.flat().sort((a, b) => b.published_date.localeCompare(a.published_date));
  capacityRecords = capData;
  companySummaries = sumData || {};
  distillationSummaries = distData?.summaries || {};
  baselineNotes = baselineNotesData?.notes || [];
  versionInfo = versionData;
  sectorSummaries = sectorSumData?.sectors || {};
  dailyTop5 = top5Data?.top5 || [];
  document.getElementById('crawl-time').textContent =
    `신호 ${allSignals.length}건 · 캐파 ${capacityRecords.length}건 · ${new Date().toLocaleString('ko-KR')}`;
  document.getElementById('update-time').textContent =
    `News 최근 갱신: ${allSignals[0]?.published_date || '–'}`;
  const footerEl = document.getElementById('version-info');
  if (footerEl) {
    footerEl.textContent = versionInfo
      ? `v${versionInfo.version} · ${versionInfo.date}`
      : '';
  }
}

// ── 레이아웃 렌더 ─────────────────────────────────────────────────────────
function renderLayout() {
  document.body.innerHTML = `
    <header>
      <h1>SoC Intelligence</h1>
      <span class="update-time" id="update-time">News 최근 갱신 확인 중...</span>
      <button class="theme-toggle-btn" id="theme-toggle" onclick="toggleTheme()">${document.documentElement.dataset.theme === 'light' ? 'Black' : 'White'}</button>
      <span class="crawl-time" id="crawl-time">로딩 중...</span>
    </header>
    <div class="layout">
      <nav id="sidebar">${renderNav()}</nav>
      <main id="content"></main>
    </div>
    <footer id="app-footer"><span id="version-info"></span></footer>`;

  document.getElementById('sidebar').addEventListener('click', e => {
    const a = e.target.closest('a[data-mod]');
    if (a) { e.preventDefault(); navigate(a.dataset.mod); }
  });
  window.addEventListener('hashchange', () => navigate(location.hash.replace('#', '')));
}

function renderNav() {
  return MODULES.map(m =>
    `<a href="#${m.id}" data-mod="${m.id}">
       <span>${m.icon}</span>
       <span class="nav-label">${m.label}</span>
     </a>`
  ).join('');
}

// ── 라우팅 ────────────────────────────────────────────────────────────────
function navigate(id) {
  currentModule = MODULES.find(m => m.id === id) ? id : 'today';
  location.hash = currentModule;
  document.querySelectorAll('nav a').forEach(a =>
    a.classList.toggle('active', a.dataset.mod === currentModule)
  );
  document.getElementById('content').innerHTML = renderModule(currentModule);
  attachHandlers(currentModule);
}

function renderModule(id) {
  switch (id) {
    case 'today':      return modToday();
    case 'review':     return modReview();
    case 'control':    return modControl();
    case 'foundry':    return modFoundry();
    case 'articles':   return modArticles();
    case 'ecosystem':  return modEcosystem();
    case 'hiring':     return modHiring();
    case 'metrics':    return modMetrics();
    case 'workbench':  return modWorkbench();
    case 'matrix':     return modMatrix();
    case 'categories': return modCategories();
    case 'competitor': return modCompetitor();
    case 'channels':   return modChannels();
    default: return '<p>알 수 없는 모듈</p>';
  }
}

// ── 공통 렌더 헬퍼 ────────────────────────────────────────────────────────
function axisLabel(axis) {
  return {
    mobile_ap: 'Mobile AP',
    hpc_datacenter: 'HPC·DC',
    custom_soc: 'Custom SoC',
    foundry: 'Foundry',
    packaging: 'Packaging',
  }[axis] || axis;
}

function chipAxis(axis) {
  return `<span class="chip chip-axis-${axis}">${axisLabel(axis)}</span>`;
}

function chipCat(cat) {
  const labels = { news: '뉴스', process: '공정', packaging: '패키징', price: '가격', hiring: '채용' };
  return `<span class="chip chip-cat-${cat}">${labels[cat] || cat}</span>`;
}

function chipTags(tags) {
  if (!tags || !tags.length) return '';
  return tags.map(t => `<span class="chip chip-tag">${t}</span>`).join(' ');
}

function signalCard(s, opts = {}) {
  const reviewed = reviewedSet.has(s.url);
  const isTF = TRENDFORCE_SOURCES.some(c => s.source.includes(c));
  return `
    <div class="signal-card" style="${reviewed ? 'opacity:0.5' : ''}">
      <div class="signal-meta">
        ${chipAxis(s.axis)}
        <span class="chip" style="background:var(--surface2);color:var(--text-muted);display:inline-flex;align-items:center;gap:4px">${coLogoBadge(s.company)}${coLabel(s.company)}</span>
        ${chipCat(s.category)}
        ${isTF ? '<span class="chip" style="background:#e67e00;color:#fff;font-size:10px">TrendForce</span>' : ''}
        ${chipTags(s.tags)}
        ${opts.reviewBtn ? `<button class="filter-btn review-btn" data-url="${s.url}" style="margin-left:auto">${reviewed ? '✓ 완료' : '리뷰 완료'}</button>` : ''}
      </div>
      <div class="signal-headline"><a href="${s.url}" target="_blank" rel="noopener">${s.headline}</a></div>
      <div class="signal-info">
        <span>${s.published_date}</span>
        <span>${s.source}</span>
      </div>
      ${s.summary ? `<div class="signal-summary">${s.summary}</div>` : ''}
    </div>`;
}

function signalList(signals, opts = {}) {
  if (!signals.length) return `<div class="empty"><h3>신호 없음</h3><p>크롤러를 실행해 데이터를 수집하세요.</p></div>`;
  return `<div class="signal-list">${signals.map(s => signalCard(s, opts)).join('')}</div>`;
}

function header(title, desc) {
  return `<div class="module-title">${title}</div><div class="module-desc">${desc}</div>`;
}

// ── 일일 Top-5 (Phase 3 item 7 — 휴리스틱 랭킹, 빌드타임 생성) ──────────────
function _dailyTop5Panel() {
  if (!dailyTop5.length) return '';
  const rows = dailyTop5.map((t, i) => `
    <div style="display:flex;gap:10px;align-items:flex-start;padding:8px 0;${i ? 'border-top:1px solid var(--border)' : ''}">
      <div style="font-size:14px;font-weight:700;color:var(--accent);min-width:18px">${i + 1}</div>
      <div style="flex:1">
        <div style="display:flex;gap:6px;align-items:center;margin-bottom:2px">
          ${chipAxis(t.axis)}
          <span style="font-size:10px;color:var(--text-muted)">${t.source} · ${t.published_date}</span>
        </div>
        <a href="${t.url}" target="_blank" rel="noopener" style="font-size:13px;font-weight:500">${t.headline}</a>
      </div>
    </div>`).join('');
  return `
    <div style="background:var(--surface);border:1px solid var(--border);border-radius:6px;padding:12px 14px;margin-bottom:16px">
      <div style="font-size:11px;font-weight:600;color:var(--accent);margin-bottom:4px">★ 일일 Summary — 중요도 Top 5</div>
      ${rows}
    </div>`;
}

// ── 1. 오늘의 요약 (드릴다운) ─────────────────────────────────────────────
function modToday() {
  const yesterday = new Date(Date.now() - 86400000).toISOString().slice(0, 10);
  const recent = allSignals.filter(s => s.published_date >= yesterday);
  const byAxis = {};
  ['mobile_ap','hpc_datacenter','custom_soc','foundry','packaging'].forEach(a => {
    byAxis[a] = recent.filter(s => s.axis === a);
  });
  return `
    ${header('오늘의 요약', `지난 24시간 신호 ${recent.length}건 — 카드 클릭으로 필터`)}
    ${_dailyTop5Panel()}
    <div class="stat-grid">
      ${['mobile_ap','hpc_datacenter','custom_soc','foundry','packaging'].map(a =>
        `<div class="stat-card stat-card-clickable" onclick="todayDrill('axis','${a}',this)">
          <div class="stat-value">${byAxis[a].length}</div>
          <div class="stat-label">${axisLabel(a)}</div>
        </div>`
      ).join('')}
      <div class="stat-card stat-card-clickable" onclick="todayDrill('cat','process',this)">
        <div class="stat-value">${recent.filter(s=>s.category==='process').length}</div>
        <div class="stat-label">공정 노드</div>
      </div>
      <div class="stat-card stat-card-clickable" onclick="todayDrill('cat','price',this)">
        <div class="stat-value">${recent.filter(s=>s.category==='price').length}</div>
        <div class="stat-label">가격</div>
      </div>
    </div>
    <div id="today-list">${signalList(recent.slice(0, 30))}</div>`;
}

// ── Baseline Notes (deep-research 장문 노트, data/baseline/notes/*.md) ───
function _escHtml(s) {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function _mdInline(s) {
  return s
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/\[\[([^\]]+)\]\]/g, '<span class="wikilink">$1</span>');
}

// 아주 가벼운 markdown → HTML 변환. 헤더/굵게/인용/목록/표/구분선만 지원 (풀 CommonMark 아님).
function _mdLite(md) {
  const lines = _escHtml(md).split('\n');
  let html = '';
  let i = 0;
  let inList = false;

  const closeList = () => { if (inList) { html += '</ul>'; inList = false; } };

  const isTableSep = line => /^\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?$/.test(line.trim());

  while (i < lines.length) {
    const line = lines[i];

    if (!line.trim()) { closeList(); i++; continue; }

    const h = line.match(/^(#{1,4})\s+(.*)$/);
    if (h) {
      closeList();
      const level = Math.min(h[1].length + 2, 6); // 문서 h1 → h3 정도로 낮춰 카드 안에서 과하지 않게
      html += `<h${level}>${_mdInline(h[2])}</h${level}>`;
      i++; continue;
    }

    if (line.startsWith('|') && lines[i + 1] && isTableSep(lines[i + 1])) {
      closeList();
      const headCells = line.split('|').slice(1, -1).map(c => c.trim());
      html += '<table class="md-table"><thead><tr>' +
        headCells.map(c => `<th>${_mdInline(c)}</th>`).join('') + '</tr></thead><tbody>';
      i += 2;
      while (i < lines.length && lines[i].trim().startsWith('|')) {
        const cells = lines[i].split('|').slice(1, -1).map(c => c.trim());
        html += '<tr>' + cells.map(c => `<td>${_mdInline(c)}</td>`).join('') + '</tr>';
        i++;
      }
      html += '</tbody></table>';
      continue;
    }

    if (/^-{3,}$/.test(line.trim())) { closeList(); html += '<hr>'; i++; continue; }

    const bq = line.match(/^>\s?(.*)$/);
    if (bq) { closeList(); html += `<blockquote>${_mdInline(bq[1])}</blockquote>`; i++; continue; }

    const li = line.match(/^[-*]\s+(?:\[( |x)\]\s+)?(.*)$/);
    if (li) {
      if (!inList) { html += '<ul>'; inList = true; }
      const checkbox = li[1] !== undefined ? `${li[1] === 'x' ? '☑' : '☐'} ` : '';
      html += `<li>${checkbox}${_mdInline(li[2])}</li>`;
      i++; continue;
    }

    closeList();
    html += `<p>${_mdInline(line)}</p>`;
    i++;
  }
  closeList();
  return html;
}

function _baselineNoteCard(note) {
  const tags = (note.tags || []).map(t => `<span class="chip chip-note">${t}</span>`).join('');
  const statusLabel = note.status ? `<span class="chip chip-note-status">${note.status}</span>` : '';
  return `
    <div class="baseline-note-card">
      <div class="baseline-note-head" onclick="toggleBaselineNote('${note.id}')">
        <div>
          <div class="baseline-note-topic">${note.topic}</div>
          <div class="baseline-note-meta">${note.axis || ''} ${note.date ? '· ' + note.date : ''}</div>
        </div>
        <div>${statusLabel}${tags}</div>
      </div>
      <div id="bn-body-${note.id}" class="baseline-note-body" style="display:none">${_mdLite(note.body_md)}</div>
    </div>`;
}

function _baselineNotesPanel() {
  if (!baselineNotes.length) return '';
  return `
    <div class="baseline-notes-panel">
      <div style="font-size:11px;font-weight:600;color:var(--accent);margin-bottom:8px">
        📥 Baseline Notes — 승격 대기 (dashboard 층, 켜뮤 아님 · ${baselineNotes.length}건)
      </div>
      ${baselineNotes.map(_baselineNoteCard).join('')}
    </div>`;
}

window.toggleBaselineNote = function(id) {
  const el = document.getElementById(`bn-body-${id}`);
  if (el) el.style.display = el.style.display === 'none' ? 'block' : 'none';
};

// ── 2. 일일 리뷰 큐 (5축 + 카테고리 필터 + 1차 증류 코멘트) ───────────────
function _distillationNotePanel(axis, category) {
  const noteKey = `${axis}||${category}`;
  const existing = distillationNotes.filter(n => n.axis === axis && n.category === category);
  const existingHtml = existing.slice(-3).reverse().map(n =>
    `<div style="margin-bottom:6px;padding:6px 8px;background:var(--surface2);border-radius:4px;font-size:11px">
      <span style="color:var(--text-muted)">${n.date}</span>
      <div style="margin-top:2px">${n.comment}</div>
     </div>`
  ).join('') || '<span style="font-size:11px;color:var(--text-muted)">코멘트 없음</span>';

  const catSummary = distillationSummaries[noteKey];
  const summaryHtml = catSummary ? `
    <div style="background:var(--surface2);border-left:2px solid var(--accent);padding:6px 8px;margin-bottom:8px;font-size:12px;line-height:1.5">
      <strong style="color:var(--accent);font-size:10px">◉ 카테고리 요약 (빌드타임 생성 · 메모 ${catSummary.note_count}건)</strong>
      <div style="margin-top:4px">${catSummary.summary}</div>
    </div>` : '';

  return `
    <div class="distillation-panel" data-key="${noteKey}" style="background:var(--surface);border:1px solid var(--border);border-radius:6px;padding:10px 12px;margin-bottom:10px">
      <div style="font-size:11px;font-weight:600;color:var(--accent);margin-bottom:6px">
        ✎ 1차 증류 — ${axisLabel(axis)} / ${category}
      </div>
      ${summaryHtml}
      <div id="notes-${noteKey.replace('||','-')}">${existingHtml}</div>
      <div style="display:flex;gap:6px;margin-top:6px">
        <textarea id="note-input-${noteKey.replace('||','-')}" rows="2"
          placeholder="판단 메모 (append-only, 수정 불가)…"
          style="flex:1;resize:vertical;background:var(--surface2);border:1px solid var(--border);border-radius:4px;padding:4px 6px;color:var(--text);font-size:12px"></textarea>
        <button class="filter-btn"
          onclick="saveNote('${axis}','${category}')"
          style="align-self:flex-end">저장</button>
      </div>
    </div>`;
}

function _reviewGroupedList(signals, activeAxis) {
  if (!signals.length) return signalList([]);
  const cats = ['process','packaging','price','hiring','news'];
  let html = '';
  cats.forEach(cat => {
    const group = signals.filter(s =>
      s.category === cat && (!activeAxis || s.axis === activeAxis)
    );
    if (!group.length) return;
    const groupAxis = activeAxis || group[0].axis;
    html += _distillationNotePanel(groupAxis, cat);
    html += `<div style="margin-bottom:16px">${signalList(group.slice(0, 15), { reviewBtn: true })}</div>`;
  });
  return html || signalList([]);
}

// ── 섹터별 1문단 요약 (Phase 3 item 6 — distill 단계 빌드타임 생성) ─────────
function _sectorSummariesPanel() {
  const axes = ['mobile_ap','hpc_datacenter','custom_soc','foundry','packaging'];
  const present = axes.filter(a => sectorSummaries[a]);
  if (!present.length) return '';
  return `
    <div style="margin-bottom:14px">
      <div style="font-size:11px;font-weight:600;color:var(--accent);margin-bottom:6px">◉ 섹터별 요약 (당일 수집분)</div>
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:8px">
        ${present.map(a => `
          <div style="background:var(--surface);border:1px solid var(--border);border-radius:6px;padding:10px 12px">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px">
              ${chipAxis(a)}
              <span style="font-size:10px;color:var(--text-muted)">${sectorSummaries[a].item_count}건</span>
            </div>
            <div style="font-size:12px;line-height:1.5">${sectorSummaries[a].summary}</div>
          </div>`).join('')}
      </div>
    </div>`;
}

function modReview() {
  const unreviewed = allSignals.filter(s => !reviewedSet.has(s.url));
  const axes = ['mobile_ap','hpc_datacenter','custom_soc','foundry','packaging'];
  return `
    ${header('일일 리뷰', `미완료 ${unreviewed.length}건 · 완료 표시하면 흐려집니다`)}
    ${_baselineNotesPanel()}
    ${_sectorSummariesPanel()}
    <div style="margin-bottom:12px">
      <button class="filter-btn" onclick="exportDistillationNotes()">📥 메모 내보내기 (JSON)</button>
      <span style="font-size:11px;color:var(--text-muted);margin-left:8px">
        data/distillation_notes.json으로 커밋하면 다음 빌드에서 카테고리 요약이 생성됩니다
      </span>
    </div>
    <div class="filters">
      <button class="filter-btn active" onclick="reviewFilter(this,'all')">전체</button>
      ${axes.map(a =>
        `<button class="filter-btn" onclick="reviewFilter(this,'${a}')">${axisLabel(a)}</button>`
      ).join('')}
      <button class="filter-btn" onclick="reviewFilter(this,'process')">공정</button>
      <button class="filter-btn" onclick="reviewFilter(this,'hiring')">채용</button>
      <button class="filter-btn" onclick="reviewFilter(this,'other')">기타</button>
    </div>
    <div id="review-list">${_reviewGroupedList(allSignals.slice(0, 80), null)}</div>`;
}

// ── 3. 크롤링 관제 ────────────────────────────────────────────────────────
function modControl() {
  const rows = crawlStatus.map(s => `
    <tr>
      <td>${axisLabel(s.axis)}</td>
      <td>${s.company}</td>
      <td><span class="channel-status ${s.ok ? 'ok' : 'warn'}">${s.ok ? '✓ OK' : '✗ 실패'}</span></td>
      <td>${s.count}</td>
    </tr>`).join('');
  const ok = crawlStatus.filter(s => s.ok).length;
  return `
    ${header('크롤링 관제', `${ok}/${crawlStatus.length} 소스 정상`)}
    <table>
      <thead><tr><th>축</th><th>회사</th><th>상태</th><th>신호 수</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>`;
}

// ── 4. 파운드리 캐파 ──────────────────────────────────────────────────────
function _capacityTable() {
  if (!capacityRecords.length) {
    return '<div class="empty"><h3>캐파 데이터 없음</h3><p>scripts/backfill_capacity.py를 실행하세요.</p></div>';
  }
  // 노드별로 그룹화 후 최신 데이터 포인트만 표시
  const grouped = {};
  capacityRecords.forEach(r => {
    const key = `${r.company}||${r.node}`;
    if (!grouped[key]) grouped[key] = [];
    grouped[key].push(r);
  });

  // 표시 순서: TSMC → Samsung → Intel → GF
  const ORDER = ['tsmc','samsung_foundry','intel_foundry','globalfoundries','smic'];
  const sortedKeys = Object.keys(grouped).sort((a, b) => {
    const [ca] = a.split('||'); const [cb] = b.split('||');
    return (ORDER.indexOf(ca) - ORDER.indexOf(cb)) || a.localeCompare(b);
  });

  const maxWspm = Math.max(...capacityRecords.map(r => r.wafer_capacity || 0), 1);

  const rows = sortedKeys.map(key => {
    const recs = grouped[key].sort((a, b) => a.month.localeCompare(b.month));
    const [company, node] = key.split('||');
    // 과거 최신 실적
    const hist = recs.filter(r => !r.is_forecast);
    const fc   = recs.filter(r => r.is_forecast);
    const latest = hist[hist.length - 1] || recs[recs.length - 1];
    const latestFc = fc[fc.length - 1];

    const wspm = latest?.wafer_capacity;
    const barPct = wspm ? Math.round(wspm / maxWspm * 100) : 0;
    const price = latest?.price_per_wafer ? `$${(latest.price_per_wafer / 1000).toFixed(1)}K` : '–';
    const yld   = latest?.yield_rate ? `${Math.round(latest.yield_rate * 100)}%` : '–';
    const fcWspm = latestFc?.wafer_capacity;
    const isForecast = !hist.length;

    return `<tr>
      <td>${coLabel(company)}</td>
      <td><strong>${node}</strong></td>
      <td>${latest?.month || '–'} ${isForecast ? '<span class="chip" style="background:var(--orange);color:#fff;font-size:10px">예측</span>' : ''}</td>
      <td>
        <div style="display:flex;align-items:center;gap:6px">
          <div class="bar-track" style="width:90px;display:inline-block">
            <div class="bar-fill" style="width:${barPct}%;background:${isForecast ? 'var(--orange)' : 'var(--accent)'}"></div>
          </div>
          <span style="font-size:12px;color:var(--text-muted)">${wspm ? (wspm/1000).toFixed(0)+'K' : '–'} wspm</span>
        </div>
      </td>
      <td style="color:var(--text-muted);font-size:12px">${price}</td>
      <td style="color:var(--text-muted);font-size:12px">${yld}</td>
      <td style="color:var(--text-muted);font-size:12px">${fcWspm ? (fcWspm/1000).toFixed(0)+'K wspm ('+latestFc.month+')' : '–'}</td>
    </tr>`;
  }).join('');

  return `
    <div style="overflow-x:auto">
    <table>
      <thead>
        <tr>
          <th>파운드리</th><th>노드</th><th>최신 실적</th>
          <th>캐파 (wspm)</th><th>가격/웨이퍼</th><th>수율</th><th>최신 예측</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table></div>
    <p style="font-size:11px;color:var(--text-muted);margin-top:8px">
      출처: TrendForce·Bloomberg·SEMI·Reuters 공개 보고서 추정치. 계약 수치 아님.<br>
      wspm = wafer starts per month. 막대 기준: 최대 ${(maxWspm/1000).toFixed(0)}K wspm (N7 성숙기).
    </p>`;
}

function modFoundry() {
  const foundrySignals = allSignals.filter(s => s.axis === 'foundry' || s.axis === 'packaging');
  const related = allSignals.filter(s => {
    if (s.axis === 'foundry' || s.axis === 'packaging') return false;
    const t = `${s.headline} ${(s.tags||[]).join(' ')}`.toLowerCase();
    return ['tsmc','foundry','wafer','cowos','capacity'].some(k => t.includes(k))
      || ['process','price'].includes(s.category);
  });
  const combined = foundrySignals.concat(related);
  return `
    ${header('파운드리 웨이퍼 캐파·가격 추이',
      `정형 캐파 ${capacityRecords.length}건 · 신호 ${foundrySignals.length}건 + 연관 ${related.length}건`)}
    <h3 style="font-size:13px;margin:0 0 10px;color:var(--accent)">▦ 노드별 캐파 현황 (FoundryCapacityRecord)</h3>
    ${_capacityTable()}
    <h3 style="font-size:13px;margin:24px 0 10px;color:var(--text-muted)">◈ 최신 뉴스 신호</h3>
    <div class="filters">
      <button class="filter-btn active" onclick="filterFoundry(this,'all')">전체</button>
      <button class="filter-btn" onclick="filterFoundry(this,'process')">공정 노드</button>
      <button class="filter-btn" onclick="filterFoundry(this,'packaging')">패키징</button>
      <button class="filter-btn" onclick="filterFoundry(this,'price')">가격</button>
    </div>
    <div id="foundry-list">${signalList(combined.slice(0,50))}</div>`;
}

// ── 5. 기사 ───────────────────────────────────────────────────────────────
const CHINESE_SOURCES    = ['DigiTimes','Unisoc','MediaTek','SMIC','JCET'];
const KOREAN_SOURCES     = ['SK hynix','Samsung Semiconductor','Samsung Foundry','전자신문','ZDNet Korea','디지털타임스'];
const TRENDFORCE_SOURCES = ['TrendForce'];  // EN 탭 내 뱃지 식별용

// 리뷰큐 + 기사 서브필터 공용 정의 (중복 구현 금지)
const _SUBFILTER_ITEMS = [
  ['all', '전체'], ['mobile_ap', 'Mobile AP'], ['hpc_datacenter', 'HPC·DC'],
  ['custom_soc', 'Custom SoC'], ['foundry', 'Foundry'], ['packaging', 'Packaging'],
  ['process', '공정'], ['hiring', '채용'], ['other', '기타'],
];

function _axisSubFilterBar(tabId) {
  return `<div class="filters" style="margin:6px 0 8px;flex-wrap:wrap">
    ${_SUBFILTER_ITEMS.map(([v, l]) =>
      `<button class="filter-btn art-sub-${tabId}${v==='all'?' active':''}"
         style="font-size:11px;padding:2px 8px"
         onclick="articleSubFilter(this,'${tabId}','${v}')">${l}</button>`
    ).join('')}
  </div>`;
}

function modArticles() {
  const kr = allSignals.filter(s =>
    KOREAN_SOURCES.some(c => s.source.includes(c)) ||
    (s.tags && s.tags.includes('KO'))
  );
  const zh = allSignals.filter(s =>
    CHINESE_SOURCES.some(c => s.source.includes(c)) && !kr.includes(s)
  );
  const en = allSignals.filter(s =>
    !CHINESE_SOURCES.some(c => s.source.includes(c)) &&
    !KOREAN_SOURCES.some(c => s.source.includes(c)) &&
    !(s.tags && s.tags.includes('KO'))
  );  // TrendForce → EN 탭 포함 (별도 탭 제거)
  _artSignals = { en, zh, kr };

  return `
    ${header('기사 — 영어권 / 중국어권 / 한국어',
      `영어 ${en.length}건 · 중국어권 ${zh.length}건 · 한국어 ${kr.length}건`)}
    <div class="filters" id="art-lang-tabs">
      <button class="filter-btn active" onclick="switchArticleTab(this,'en')">영어권</button>
      <button class="filter-btn" onclick="switchArticleTab(this,'zh')">중국어권</button>
      <button class="filter-btn" onclick="switchArticleTab(this,'kr')">한국어</button>
    </div>
    <div id="art-tab-en">
      ${_axisSubFilterBar('en')}
      <div id="art-list-en">${signalList(en.slice(0,40))}</div>
    </div>
    <div id="art-tab-zh" style="display:none">
      ${_axisSubFilterBar('zh')}
      <div id="art-list-zh">${signalList(zh.slice(0,40))}</div>
    </div>
    <div id="art-tab-kr" style="display:none">
      ${_axisSubFilterBar('kr')}
      <div id="art-list-kr">
        ${kr.length > 0
          ? signalList(kr.slice(0,40))
          : '<div class="empty"><h3>한국어 소스 수집 중</h3><p>전자신문 RSS 크롤러가 활성화됐습니다. 다음 크롤링 실행 후 확인하세요.</p></div>'
        }
      </div>
    </div>`;
}

// ── 6. SoC 생태계·다이나믹스 (인터랙티브 그래프) ────────────────────────
function modEcosystem() {
  const AXIS_COMPANIES = {
    mobile_ap:      ['apple','qualcomm','mediatek','unisoc','exynos'],
    hpc_datacenter: ['nvidia','amd','intel'],
    custom_soc:     ['broadcom','marvell','hyperscaler_inhouse'],
    foundry:        ['tsmc','samsung_foundry','intel_foundry','globalfoundries','smic'],
    packaging:      ['ase','amkor','jcet'],
  };
  const axes = ['mobile_ap','hpc_datacenter','custom_soc','foundry','packaging'];

  const columns = axes.map(axis =>
    `<div class="eco-column">
      <div class="eco-axis-label">${axisLabel(axis)}</div>
      ${AXIS_COMPANIES[axis].map(co => {
        const cnt = allSignals.filter(s => s.company === co).length;
        return `<div class="eco-node${cnt === 0 ? ' eco-node-empty' : ''}" data-company="${co}" onclick="ecoSelectNode(this,'${co}')">
          <span class="eco-node-logo">${_logoInitials(co)}</span>
          <span class="eco-node-name">${coLabel(co)}</span>
          ${cnt > 0 ? `<span class="eco-node-count">${cnt}</span>` : ''}
        </div>`;
      }).join('')}
    </div>`
  ).join('');

  // 타임라인 (경쟁 다이나믹스)
  const byDate = {};
  allSignals.slice(0,120).forEach(s => {
    if (!byDate[s.published_date]) byDate[s.published_date] = [];
    byDate[s.published_date].push(s);
  });
  const timeline = Object.entries(byDate)
    .sort((a,b) => b[0].localeCompare(a[0])).slice(0,10)
    .map(([d, sigs]) => `
      <div style="margin-bottom:16px">
        <div style="font-size:12px;color:var(--text-muted);margin-bottom:6px;font-weight:600">${d}</div>
        ${signalList(sigs.slice(0,3))}
      </div>`).join('');

  return `
    ${header('SoC 생태계·다이나믹스', '5축 업체 관계도 — 노드 클릭으로 연결 확인')}
    <div style="margin-bottom:10px;font-size:12px;color:var(--text-muted)">
      <span style="color:var(--green)">━━</span> 공급 &nbsp;
      <span style="color:var(--red)">╌╌</span> 경쟁 &nbsp;
      <span style="color:var(--accent)">━━</span> 파트너십
    </div>
    <div class="eco-graph" id="eco-graph">
      <svg class="eco-svg" id="eco-svg" overflow="visible"></svg>
      <div class="eco-columns" id="eco-columns">${columns}</div>
    </div>
    <div id="eco-detail"></div>
    <h3 style="margin:24px 0 10px;font-size:14px">경쟁 다이나믹스 타임라인</h3>
    ${timeline || signalList([])}`;
}

// ECO 업체 슬러그 → 채용 신호 태그 매핑 (config.yaml _SLUG_TO_TAG와 동기화)
const _ECO_TO_HIRING_TAGS = {
  tsmc: ['TSMC'], apple: ['Apple'], nvidia: ['NVIDIA'], amd: ['AMD'],
  qualcomm: ['Qualcomm'], broadcom: ['Broadcom'], mediatek: ['MediaTek'],
  samsung_foundry: ['Samsung Foundry', 'Samsung'], exynos: ['Samsung', 'Exynos'],
  intel: ['Intel'], intel_foundry: ['Intel'], globalfoundries: ['GlobalFoundries', 'GF'],
  smic: ['SMIC'], ase: ['ASE'], amkor: ['Amkor'], jcet: ['JCET'], marvell: ['Marvell'],
  hyperscaler_inhouse: ['Google', 'Amazon', 'Microsoft', 'Meta', 'Hyperscaler'],
};

// ── 7. 인재·채용 레이더 ───────────────────────────────────────────────────
function modHiring() {
  const signals = allSignals.filter(s => s.category === 'hiring');
  const dedicated = signals.filter(s => s.company === 'hiring');
  const incidental = signals.filter(s => s.company !== 'hiring');

  // ECO 업체 전체 (생태계 모듈과 단일 소스)
  const ecoCompanies = [...new Set(_ECO_RELATIONS.flatMap(r => [r.from, r.to]))].sort();
  const ecoGrid = ecoCompanies.map(co => {
    const matchTags = _ECO_TO_HIRING_TAGS[co] || [coLabel(co)];
    const coSigs = dedicated.filter(s =>
      (s.tags || []).some(t => matchTags.some(mt => t.toLowerCase().includes(mt.toLowerCase())))
    );
    return `<div style="background:var(--surface);border:1px solid var(--border);border-radius:6px;padding:8px 10px">
      <div style="font-weight:600;font-size:12px;margin-bottom:4px">${coLabel(co)}</div>
      ${coSigs.length > 0
        ? `<span class="chip chip-cat-hiring" style="font-size:10px">채용신호 ${coSigs.length}건</span>`
        : '<span style="font-size:10px;color:var(--text-muted)">소스 미확보</span>'
      }
    </div>`;
  }).join('');

  const bySource = {};
  signals.forEach(s => {
    if (!bySource[s.source]) bySource[s.source] = 0;
    bySource[s.source]++;
  });
  const sourceChips = Object.entries(bySource)
    .sort((a, b) => b[1] - a[1])
    .map(([src, cnt]) => `<span class="chip chip-tag">${src} (${cnt})</span>`).join(' ');

  return `
    ${header('인재·채용 레이더', `채용 신호 ${signals.length}건 — 전용 ${dedicated.length}건 + 부수탐지 ${incidental.length}건`)}
    <h3 style="font-size:13px;margin:0 0 8px;color:var(--accent)">▦ ECO 업체별 채용 현황</h3>
    <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:8px;margin-bottom:20px">
      ${ecoGrid}
    </div>
    ${signals.length > 0 ? `<div style="margin-bottom:12px;font-size:12px">${sourceChips}</div>` : ''}
    <div class="filters">
      <button class="filter-btn active" onclick="hiringFilter(this,'all')">전체</button>
      <button class="filter-btn" onclick="hiringFilter(this,'dedicated')">채용 레이더</button>
      <button class="filter-btn" onclick="hiringFilter(this,'incidental')">부수 탐지</button>
    </div>
    <div id="hiring-list">${signalList(signals)}</div>`;
}

// ── 8. 숫자 대시보드 ──────────────────────────────────────────────────────
function modMetrics() {
  const total = allSignals.length;
  const cats = ['news','process','packaging','price','hiring'];
  const axes = ['mobile_ap','hpc_datacenter','custom_soc','foundry','packaging'];
  const catCounts = cats.map(c => ({ label: c, count: allSignals.filter(s=>s.category===c).length }));
  const axisCounts = axes.map(a => ({ label: axisLabel(a), count: allSignals.filter(s=>s.axis===a).length }));
  const maxCat = Math.max(...catCounts.map(x=>x.count), 1);
  const maxAxis = Math.max(...axisCounts.map(x=>x.count), 1);

  // 일자별 추이 (최근 14일)
  const days = [...Array(14)].map((_, i) => {
    const d = new Date(Date.now() - (13 - i) * 86400000).toISOString().slice(0, 10);
    return { date: d, count: allSignals.filter(s => s.published_date === d).length };
  });
  const maxDay = Math.max(...days.map(d => d.count), 1);

  // 축 × 카테고리 교차 집계
  const crossRows = axes.map(a => {
    const rowTotal = allSignals.filter(s => s.axis === a).length;
    return `<tr>
      <td>${axisLabel(a)}</td>
      ${cats.map(c => `<td>${allSignals.filter(s => s.axis === a && s.category === c).length}</td>`).join('')}
      <td style="font-weight:600">${rowTotal}</td>
    </tr>`;
  }).join('');
  const colTotals = cats.map(c => allSignals.filter(s => s.category === c).length);

  return `
    ${header('숫자 대시보드', `총 신호 ${total}건`)}
    <div class="stat-grid">
      <div class="stat-card"><div class="stat-value">${total}</div><div class="stat-label">총 신호</div></div>
      ${crawlStatus.filter(s=>s.ok).length > 0
        ? `<div class="stat-card"><div class="stat-value">${crawlStatus.filter(s=>s.ok).length}</div><div class="stat-label">활성 소스</div></div>`
        : ''}
    </div>
    <h3 style="margin:16px 0 10px;font-size:14px">일자별 추이 (최근 14일)</h3>
    <div style="display:flex;align-items:flex-end;gap:4px;height:80px;margin-bottom:20px">
      ${days.map(d => `
        <div style="flex:1;display:flex;flex-direction:column;align-items:center;gap:4px" title="${d.date}: ${d.count}건">
          <div style="width:100%;background:var(--accent);border-radius:2px 2px 0 0;height:${Math.max(2, Math.round(d.count/maxDay*60))}px"></div>
          <span style="font-size:9px;color:var(--text-muted)">${d.date.slice(5)}</span>
        </div>`).join('')}
    </div>
    <h3 style="margin:16px 0 10px;font-size:14px">카테고리별</h3>
    ${catCounts.map(({label,count}) => `
      <div class="bar-row">
        <span class="bar-label">${label}</span>
        <div class="bar-track"><div class="bar-fill" style="width:${Math.round(count/maxCat*100)}%"></div></div>
        <span class="bar-count">${count}</span>
      </div>`).join('')}
    <h3 style="margin:20px 0 10px;font-size:14px">축별</h3>
    ${axisCounts.map(({label,count}) => `
      <div class="bar-row">
        <span class="bar-label">${label}</span>
        <div class="bar-track"><div class="bar-fill" style="width:${Math.round(count/maxAxis*100)}%;background:var(--purple)"></div></div>
        <span class="bar-count">${count}</span>
      </div>`).join('')}
    <h3 style="margin:20px 0 10px;font-size:14px">축 × 카테고리 교차 집계</h3>
    <div style="overflow-x:auto">
    <table>
      <thead><tr><th>축</th>${cats.map(c=>`<th>${c}</th>`).join('')}<th>합계</th></tr></thead>
      <tbody>
        ${crossRows}
        <tr style="font-weight:600">
          <td>합계</td>
          ${colTotals.map(n => `<td>${n}</td>`).join('')}
          <td>${total}</td>
        </tr>
      </tbody>
    </table></div>`;
}

// ── 9. 벤치마크 성능 ──────────────────────────────────────────────────────
function modWorkbench() {
  const companies = [...new Set(allSignals.map(s=>s.company))]
    .filter(co => !_NON_VENDOR_COMPANIES.includes(co));
  const scores = companies.map(co => {
    const sigs = allSignals.filter(s => s.company === co);
    const processScore = sigs.filter(s=>s.category==='process'||s.category==='packaging').length * 2;
    const newsScore = sigs.filter(s=>s.category==='news').length;
    const tagScore = sigs.reduce((acc,s) => acc + (s.tags?.length||0), 0);
    return { co, total: processScore + newsScore + tagScore, count: sigs.length };
  }).sort((a,b) => b.total - a.total);
  const maxScore = scores[0]?.total || 1;
  const scoreRows = scores.map(({ co, total, count }) => `
    <tr>
      <td style="display:flex;align-items:center;gap:6px">${coLogoBadge(co)}${coLabel(co)}</td>
      <td>${count}</td>
      <td>
        <div class="bar-track" style="width:120px;display:inline-block">
          <div class="bar-fill" style="width:${Math.round(total/maxScore*100)}%"></div>
        </div>
        <span style="margin-left:8px;font-size:12px;color:var(--text-muted)">${total}</span>
      </td>
    </tr>`).join('');
  return `
    ${header('벤치마크 성능', '전체 신호 검색·필터 + 회사별 노출도')}
    <div class="filters" style="margin-bottom:12px">
      <input class="search-box" id="wb-search" placeholder="헤드라인·요약 검색..." oninput="wbFilter()">
      <button class="filter-btn active" data-axis="" onclick="wbAxis(this,'')">전체 축</button>
      <button class="filter-btn" data-axis="mobile_ap" onclick="wbAxis(this,'mobile_ap')">Mobile AP</button>
      <button class="filter-btn" data-axis="hpc_datacenter" onclick="wbAxis(this,'hpc_datacenter')">HPC·DC</button>
      <button class="filter-btn" data-axis="custom_soc" onclick="wbAxis(this,'custom_soc')">Custom SoC</button>
      <button class="filter-btn" data-axis="foundry" onclick="wbAxis(this,'foundry')">Foundry</button>
      <button class="filter-btn" data-axis="packaging" onclick="wbAxis(this,'packaging')">Packaging</button>
    </div>
    <div id="wb-list">${signalList(allSignals.slice(0,60))}</div>
    <h3 style="margin:28px 0 6px;font-size:14px">회사별 노출도 스코어</h3>
    <p style="font-size:12px;color:var(--text-muted);margin-bottom:10px">스코어 = (공정·패키징 ×2) + 뉴스 + 태그 합계</p>
    <table>
      <thead><tr><th>회사</th><th>총 신호</th><th>노출도 스코어</th></tr></thead>
      <tbody>${scoreRows}</tbody>
    </table>`;
}

// ── 10. 공정·패키징 매트릭스 (축별 도메인 그룹) ──────────────────────────
function modMatrix() {
  // hiring 신호 제외 (채용 레이더 전용 — 이 모듈에서 미노출)
  const techSignals = allSignals.filter(s => s.category !== 'hiring');
  const techTags = ['2nm','3nm','4nm','5nm','CoWoS','HBM4','HBM3E','HBM','UCIe','chiplet','InFO','3D IC'];
  const axes = ['mobile_ap','hpc_datacenter','custom_soc','foundry','packaging'];

  const matrix = {};       // company -> Set(tags)
  const companyAxis = {};  // company -> axis (최초 신호 기준)
  techSignals.forEach(s => {
    if (!matrix[s.company]) matrix[s.company] = new Set();
    (s.tags || []).forEach(t => matrix[s.company].add(t));
    if (!companyAxis[s.company]) companyAxis[s.company] = s.axis;
  });

  const sections = axes.map(axis => {
    const companies = Object.keys(matrix)
      .filter(co => companyAxis[co] === axis && !_NON_VENDOR_COMPANIES.includes(co))
      .sort((a, b) => matrix[b].size - matrix[a].size);
    if (!companies.length) return '';
    const rows = companies.map(co => `
      <tr>
        <td style="display:flex;align-items:center;gap:6px">${coLogoBadge(co)}${coLabel(co)}</td>
        ${techTags.map(t =>
          `<td class="${matrix[co].has(t) ? 'matrix-cell-yes' : 'matrix-cell-no'}">${matrix[co].has(t) ? '●' : '·'}</td>`
        ).join('')}
        <td style="color:var(--text-muted);font-size:12px">${matrix[co].size}</td>
      </tr>`).join('');
    return `
      <h3 style="margin:20px 0 8px;font-size:13px;color:var(--accent)">${axisLabel(axis)}</h3>
      <div style="overflow-x:auto">
      <table class="matrix-table">
        <thead><tr><th>회사</th>${techTags.map(t=>`<th style="font-size:11px">${t}</th>`).join('')}<th style="font-size:11px">커버리지</th></tr></thead>
        <tbody>${rows}</tbody>
      </table></div>`;
  }).join('');

  return `
    ${header('공정·패키징 매트릭스', '축별 회사 그룹 · 수집된 신호 기준 기술 커버리지')}
    ${sections || '<div class="empty"><h3>신호 없음</h3><p>해당 축의 크롤러를 실행해 데이터를 수집하세요.</p></div>'}`;
}

// ── 11. SoC 카테고리 (5축) ────────────────────────────────────────────────
function modCategories() {
  const axes = ['mobile_ap','hpc_datacenter','custom_soc','foundry','packaging'];
  const activeAxis = window._catActiveAxis || axes[0];
  const cats = ['news','process','packaging','price','hiring'];
  const sigs = allSignals.filter(s => s.axis === activeAxis);
  const sections = cats.map(cat => {
    const catSigs = sigs.filter(s => s.category === cat);
    if (!catSigs.length) return '';
    return `
      <div style="margin-bottom:24px">
        <h3 style="margin-bottom:10px;font-size:14px">${chipCat(cat)} ${catSigs.length}건</h3>
        ${signalList(catSigs.slice(0,10))}
        ${catSigs.length > 10 ? `<p style="color:var(--text-muted);font-size:12px;margin-top:8px">... 외 ${catSigs.length-10}건</p>` : ''}
      </div>`;
  }).join('');
  return `
    ${header('SoC 카테고리 (5축)', '축 선택 후 카테고리별 신호 확인')}
    <div class="filters">
      ${axes.map(a =>
        `<button class="filter-btn ${a===activeAxis?'active':''}" onclick="catAxis(this,'${a}')">${axisLabel(a)}</button>`
      ).join('')}
    </div>
    <div id="cat-content">
      ${sections || '<div class="empty"><h3>신호 없음</h3><p>해당 축의 크롤러를 실행해 데이터를 수집하세요.</p></div>'}
    </div>`;
}

// ── LLM 요약 카드 (modCompetitor + competitorTab 공용) ────────────────────
const _summaryLangCache = {};  // company -> {ko,en,zh} — 빌드타임 사전번역 캐시 (switchSummaryLang 공용)
const _SUMMARY_LANG_LABEL = { ko: '한', en: 'EN', zh: '中' };

function _companySummaryCard(company) {
  const sum = companySummaries.summaries?.[company];
  if (!sum) return '<div style="font-size:11px;color:var(--text-muted);margin-bottom:12px">LLM 요약 없음 — merge_refine.py 실행 후 생성됩니다.</div>';
  const langs = { ko: sum.summary_ko, en: sum.summary_en || sum.summary, zh: sum.summary_zh };
  const available = ['ko','en','zh'].filter(l => langs[l]);
  const defaultLang = available.includes('ko') ? 'ko' : available[0];
  _summaryLangCache[company] = langs;
  const langBtns = available.map(l =>
    `<button class="filter-btn summary-lang-btn${l===defaultLang?' active':''}" data-lang="${l}"
       style="font-size:10px;padding:2px 8px" onclick="switchSummaryLang(this,'${company}')">${_SUMMARY_LANG_LABEL[l]}</button>`
  ).join('');
  return `
    <div class="summary-card" style="background:var(--surface);border:1px solid var(--accent);border-radius:6px;padding:12px 14px;margin-bottom:16px">
      <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:6px;margin-bottom:6px">
        <span style="font-size:11px;font-weight:600;color:var(--accent)">◉ LLM 전략 요약 (빌드타임 생성)</span>
        ${available.length > 1 ? `<span class="summary-lang-bar" style="display:flex;gap:4px">${langBtns}</span>` : ''}
      </div>
      <div class="summary-lang-text" style="font-size:13px;line-height:1.6">${langs[defaultLang]}</div>
      <div style="font-size:10px;color:var(--text-muted);margin-top:8px">
        신호 ${sum.signal_count}건 기준 · ${(sum.generated_at||'').slice(0,10) || '–'}
      </div>
    </div>`;
}

window.switchSummaryLang = function(btn, company) {
  const card = btn.closest('.summary-card');
  card.querySelectorAll('.summary-lang-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  const langs = _summaryLangCache[company];
  const textEl = card.querySelector('.summary-lang-text');
  if (textEl && langs) textEl.textContent = langs[btn.dataset.lang];
};

// ── 12. 업체별 주요 전략 ─────────────────────────────────────────────────
function modCompetitor() {
  // hiring 신호 및 업체 아닌 소스(트렌드포스 등) 제외 — 채용 레이더/기사 전용
  const stratSignals = allSignals.filter(s => s.category !== 'hiring');
  const companies = [...new Set(stratSignals.map(s=>s.company))]
    .filter(co => !_NON_VENDOR_COMPANIES.includes(co));
  const activeCompany = companies[0] || '';
  const tabs = companies.map(co =>
    `<button class="filter-btn ${co===activeCompany?'active':''}" style="display:inline-flex;align-items:center;gap:5px" onclick="competitorTab(this,'${co}')">${coLogoBadge(co)}${coLabel(co)}</button>`
  ).join('');
  const sigs = stratSignals.filter(s => s.company === activeCompany);
  return `
    ${header('업체별 주요 전략', '회사별 상세 신호 (채용 신호 제외)')}
    <div class="filters" id="comp-tabs">${tabs}</div>
    <div id="comp-content">
      ${_companySummaryCard(activeCompany)}
      ${signalList(sigs.slice(0,50))}
    </div>`;
}

// ── 13. 정보 획득 채널 ───────────────────────────────────────────────────
function modChannels() {
  const sourceMap = {};
  allSignals.forEach(s => {
    if (!sourceMap[s.source]) sourceMap[s.source] = 0;
    sourceMap[s.source]++;
  });
  const rows = crawlStatus.map(s => `
    <div class="channel-item">
      ${chipAxis(s.axis)}
      <strong>${s.company}</strong>
      <span class="channel-status ${s.ok ? 'ok' : 'warn'}">${s.ok ? '✓' : '✗'}</span>
      <span style="color:var(--text-muted);font-size:12px">${s.count}건</span>
    </div>`).join('');
  const sourcePart = Object.entries(sourceMap)
    .sort((a,b)=>b[1]-a[1])
    .map(([src,cnt]) => `<tr><td>${src}</td><td>${cnt}</td></tr>`).join('');
  return `
    ${header('정보 획득 채널', '크롤러 현황 및 소스별 신호 분포')}
    <div class="channel-list" style="margin-bottom:24px">${rows}</div>
    <h3 style="margin-bottom:10px;font-size:14px">소스별 신호 수</h3>
    <table>
      <thead><tr><th>소스</th><th>신호 수</th></tr></thead>
      <tbody>${sourcePart}</tbody>
    </table>`;
}

// ── 이벤트 핸들러 ─────────────────────────────────────────────────────────
function attachHandlers(id) {
  if (id === 'review') {
    document.getElementById('review-list')?.addEventListener('click', e => {
      const btn = e.target.closest('.review-btn');
      if (!btn) return;
      const url = btn.dataset.url;
      if (reviewedSet.has(url)) reviewedSet.delete(url);
      else reviewedSet.add(url);
      localStorage.setItem('reviewed', JSON.stringify([...reviewedSet]));
      navigate('review');
    });
  }
  if (id === 'ecosystem') {
    requestAnimationFrame(() => ecoDrawLines(_ECO_RELATIONS, null));
  }
}

// ── 전역 이벤트 함수 ─────────────────────────────────────────────────────
const _AXES = ['mobile_ap','hpc_datacenter','custom_soc','foundry','packaging'];

window.hiringFilter = function(btn, type) {
  document.querySelectorAll('#content .filter-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  const all = allSignals.filter(s => s.category === 'hiring');
  let filtered;
  if (type === 'dedicated') filtered = all.filter(s => s.company === 'hiring');
  else if (type === 'incidental') filtered = all.filter(s => s.company !== 'hiring');
  else filtered = all;
  document.getElementById('hiring-list').innerHTML = signalList(filtered);
};
const _CATS = ['news','process','price','hiring'];  // 'packaging'은 reviewFilter에서 axis와 통합 처리

// 오늘의 요약 드릴다운
window.todayDrill = function(type, value, card) {
  const wasActive = card.classList.contains('active');
  document.querySelectorAll('.stat-card-clickable').forEach(c => c.classList.remove('active'));
  const yesterday = new Date(Date.now() - 86400000).toISOString().slice(0, 10);
  const recent = allSignals.filter(s => s.published_date >= yesterday);
  const list = document.getElementById('today-list');
  if (wasActive) {
    list.innerHTML = signalList(recent.slice(0,30));
    return;
  }
  card.classList.add('active');
  let filtered;
  if (type === 'axis') filtered = recent.filter(s => s.axis === value);
  else if (type === 'cat') filtered = recent.filter(s => s.category === value);
  else filtered = recent;
  list.innerHTML = signalList(filtered.slice(0,30));
};

// 생태계 그래프 SVG 선 그리기
window.ecoDrawLines = function(relations, activeCompany) {
  const svg = document.getElementById('eco-svg');
  const graph = document.getElementById('eco-graph');
  if (!svg || !graph) return;

  const gRect = graph.getBoundingClientRect();
  svg.setAttribute('width', gRect.width);
  svg.setAttribute('height', gRect.height);
  svg.innerHTML = '';

  const COLOR = { supply: '#3fb950', compete: '#f85149', partner: '#58a6ff' };

  relations.forEach(rel => {
    const fromEl = document.querySelector(`[data-company="${rel.from}"]`);
    const toEl   = document.querySelector(`[data-company="${rel.to}"]`);
    if (!fromEl || !toEl) return;

    const fRect = fromEl.getBoundingClientRect();
    const tRect = toEl.getBoundingClientRect();
    const x1 = fRect.left + fRect.width / 2 - gRect.left;
    const y1 = fRect.top  + fRect.height / 2 - gRect.top;
    const x2 = tRect.left + tRect.width / 2 - gRect.left;
    const y2 = tRect.top  + tRect.height / 2 - gRect.top;

    const isActive = activeCompany && (rel.from === activeCompany || rel.to === activeCompany);
    const opacity  = activeCompany ? (isActive ? 0.9 : 0.06) : 0.3;
    const sw = isActive ? 2.5 : 1.5;
    const midX = (x1 + x2) / 2;

    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    path.setAttribute('d', `M${x1},${y1} C${midX},${y1} ${midX},${y2} ${x2},${y2}`);
    path.setAttribute('stroke', COLOR[rel.type] || '#888');
    path.setAttribute('stroke-width', sw);
    path.setAttribute('opacity', opacity);
    path.setAttribute('fill', 'none');
    if (rel.type === 'compete') path.setAttribute('stroke-dasharray', '5,3');
    svg.appendChild(path);
  });
};

// 생태계 그래프 노드 클릭
window.ecoSelectNode = function(node, company) {
  const wasActive = node.classList.contains('active');
  document.querySelectorAll('.eco-node').forEach(n => n.classList.remove('active','highlighted'));
  const detail = document.getElementById('eco-detail');

  if (wasActive) {
    ecoDrawLines(_ECO_RELATIONS, null);
    detail.innerHTML = '';
    return;
  }

  node.classList.add('active');
  const rels = _ECO_RELATIONS.filter(r => r.from === company || r.to === company);
  rels.forEach(rel => {
    const other = rel.from === company ? rel.to : rel.from;
    document.querySelector(`[data-company="${other}"]`)?.classList.add('highlighted');
  });
  ecoDrawLines(_ECO_RELATIONS, company);

  const TYPE_LABEL = { supply: '공급', compete: '경쟁', partner: '파트너십' };
  const TYPE_COLOR = { supply: 'var(--green)', compete: 'var(--red)', partner: 'var(--accent)' };
  const relRows = rels.map(r => {
    const other = r.from === company ? r.to : r.from;
    const dir   = r.from === company ? '→' : '←';
    return `<tr>
      <td><span style="color:${TYPE_COLOR[r.type]||'var(--text-muted)'}">${TYPE_LABEL[r.type]||r.type}</span></td>
      <td>${dir} ${coLabel(other)}</td>
      <td style="color:var(--text-muted)">${r.label}</td>
    </tr>`;
  }).join('');

  const sigs = allSignals.filter(s => s.company === company);
  detail.innerHTML = `
    <div style="display:flex;gap:20px;flex-wrap:wrap;margin-top:16px">
      <div style="flex:1;min-width:220px">
        <h3 style="margin-bottom:10px;font-size:14px">${coLabel(company)} — 연결 관계</h3>
        ${rels.length > 0
          ? `<table><thead><tr><th>유형</th><th>상대방</th><th>설명</th></tr></thead><tbody>${relRows}</tbody></table>`
          : '<p style="color:var(--text-muted)">정의된 관계 없음</p>'
        }
      </div>
      <div style="flex:2;min-width:240px">
        <h3 style="margin-bottom:10px;font-size:14px">${coLabel(company)} 신호 (${sigs.length}건)</h3>
        ${sigs.length > 0 ? signalList(sigs.slice(0,5)) : '<p style="color:var(--text-muted)">수집된 신호 없음</p>'}
      </div>
    </div>`;
};

window.reviewFilter = function(btn, filter) {
  document.querySelectorAll('.filters .filter-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  let sigs;
  if (filter === 'all') {
    sigs = allSignals.slice(0, 80);
  } else if (filter === 'packaging') {
    // Packaging 통합: axis=packaging OR category=packaging
    sigs = allSignals.filter(s => s.axis === 'packaging' || s.category === 'packaging').slice(0, 80);
  } else if (filter === 'other') {
    // 기타 = news 카테고리
    sigs = allSignals.filter(s => s.category === 'news').slice(0, 80);
  } else if (_AXES.includes(filter)) {
    sigs = allSignals.filter(s => s.axis === filter).slice(0, 80);
  } else if (_CATS.includes(filter)) {
    sigs = allSignals.filter(s => s.category === filter).slice(0, 80);
  } else {
    sigs = allSignals.slice(0, 80);
  }

  const activeAxis = _AXES.includes(filter) ? filter : null;
  const activeCat  = (filter === 'other') ? 'news'
                   : _CATS.includes(filter) ? filter : null;
  const el = document.getElementById('review-list');
  if (activeCat) {
    const groupAxis = activeAxis || (sigs[0]?.axis) || 'foundry';
    el.innerHTML = _distillationNotePanel(groupAxis, activeCat)
      + signalList(sigs, { reviewBtn: true });
  } else {
    el.innerHTML = _reviewGroupedList(sigs, activeAxis);
  }
};

window.saveNote = function(axis, category) {
  const key = `${axis}||${category}`.replace('||', '-');
  const input = document.getElementById(`note-input-${key}`);
  if (!input || !input.value.trim()) return;
  const note = {
    id: Date.now().toString(36),
    date: new Date().toISOString().slice(0, 10),
    axis,
    category,
    linked_signal_urls: [],
    comment: input.value.trim(),
  };
  distillationNotes.push(note);
  localStorage.setItem('distillation_notes', JSON.stringify(distillationNotes));
  input.value = '';
  // 패널의 노트 목록만 새로고침
  const notesEl = document.getElementById(`notes-${key}`);
  if (notesEl) {
    const recent = distillationNotes
      .filter(n => n.axis === axis && n.category === category)
      .slice(-3).reverse();
    notesEl.innerHTML = recent.map(n =>
      `<div style="margin-bottom:6px;padding:6px 8px;background:var(--surface2);border-radius:4px;font-size:11px">
        <span style="color:var(--text-muted)">${n.date}</span>
        <div style="margin-top:2px">${n.comment}</div>
       </div>`
    ).join('');
  }
};

window.exportDistillationNotes = function() {
  const blob = new Blob([JSON.stringify(distillationNotes, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'distillation_notes.json';
  a.click();
  URL.revokeObjectURL(url);
};

window.filterFoundry = function(btn, cat) {
  document.querySelectorAll('#content .filter-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  let sigs = allSignals.filter(s => s.axis === 'foundry' || s.axis === 'packaging');
  const related = allSignals.filter(s => {
    if (s.axis === 'foundry' || s.axis === 'packaging') return false;
    const t = `${s.headline} ${(s.tags||[]).join(' ')}`.toLowerCase();
    return ['tsmc','foundry','wafer','cowos','capacity'].some(k => t.includes(k))
      || ['process','price'].includes(s.category);
  });
  let combined = sigs.concat(related);
  if (cat !== 'all') combined = combined.filter(s => s.category === cat);
  document.getElementById('foundry-list').innerHTML = signalList(combined.slice(0,50));
};

window.switchArticleTab = function(btn, tab) {
  document.querySelectorAll('#art-lang-tabs .filter-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  ['en','zh','kr'].forEach(t => {
    const el = document.getElementById(`art-tab-${t}`);
    if (el) el.style.display = t === tab ? '' : 'none';
  });
};

window.articleSubFilter = function(btn, tabId, filter) {
  document.querySelectorAll(`.art-sub-${tabId}`).forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  const base = _artSignals[tabId] || [];
  let sigs;
  if (filter === 'all')             sigs = base;
  else if (filter === 'other')      sigs = base.filter(s => s.category === 'news');
  else if (filter === 'packaging')  sigs = base.filter(s => s.axis === 'packaging' || s.category === 'packaging');
  else if (['mobile_ap','hpc_datacenter','custom_soc','foundry'].includes(filter))
    sigs = base.filter(s => s.axis === filter);
  else sigs = base.filter(s => s.category === filter);
  document.getElementById(`art-list-${tabId}`).innerHTML = signalList(sigs.slice(0,40));
};

window.wbAxis = function(btn, axis) {
  document.querySelectorAll('#content .filters .filter-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  wbFilter(axis);
};

window.wbFilter = function(axisOverride) {
  const q = document.getElementById('wb-search')?.value.toLowerCase() || '';
  const activeBtn = document.querySelector('#content .filters .filter-btn.active');
  const axis = axisOverride !== undefined ? axisOverride : (activeBtn?.dataset.axis || '');
  let sigs = allSignals;
  if (axis) sigs = sigs.filter(s => s.axis === axis);
  if (q) sigs = sigs.filter(s =>
    s.headline.toLowerCase().includes(q) || (s.summary||'').toLowerCase().includes(q)
  );
  document.getElementById('wb-list').innerHTML = signalList(sigs.slice(0,60));
};

window.catAxis = function(btn, axis) {
  window._catActiveAxis = axis;
  document.querySelectorAll('#content .filters .filter-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  const cats = ['news','process','packaging','price','hiring'];
  const sigs = allSignals.filter(s => s.axis === axis);
  const sections = cats.map(cat => {
    const catSigs = sigs.filter(s => s.category === cat);
    if (!catSigs.length) return '';
    return `
      <div style="margin-bottom:24px">
        <h3 style="margin-bottom:10px;font-size:14px">${chipCat(cat)} ${catSigs.length}건</h3>
        ${signalList(catSigs.slice(0,10))}
        ${catSigs.length > 10 ? `<p style="color:var(--text-muted);font-size:12px;margin-top:8px">... 외 ${catSigs.length-10}건</p>` : ''}
      </div>`;
  }).join('');
  document.getElementById('cat-content').innerHTML =
    sections || '<div class="empty"><h3>신호 없음</h3><p>해당 축의 크롤러를 실행해 데이터를 수집하세요.</p></div>';
};

window.competitorTab = function(btn, company) {
  document.querySelectorAll('#comp-tabs .filter-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  const sigs = allSignals.filter(s => s.company === company && s.category !== 'hiring');
  document.getElementById('comp-content').innerHTML =
    _companySummaryCard(company) + signalList(sigs.slice(0,50));
};

// ── 진입점 ────────────────────────────────────────────────────────────────
boot();
