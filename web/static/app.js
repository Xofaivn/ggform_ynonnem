// ── Meteor canvas ──────────────────────────────────────────────────────────────
(function () {
  const canvas = document.getElementById('meteor-canvas');
  const ctx = canvas.getContext('2d');
  let W, H;

  function resize() {
    W = canvas.width = window.innerWidth;
    H = canvas.height = window.innerHeight;
  }
  window.addEventListener('resize', resize);
  resize();

  // Stars background
  const STARS = Array.from({ length: 200 }, () => ({
    x: Math.random(),
    y: Math.random(),
    r: Math.random() * 1.2 + 0.2,
    a: Math.random() * 0.6 + 0.2,
  }));

  function drawStars() {
    STARS.forEach(s => {
      ctx.beginPath();
      ctx.arc(s.x * W, s.y * H, s.r, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(255,255,255,${s.a})`;
      ctx.fill();
    });
  }

  // Meteors
  class Meteor {
    constructor(delayed = false) { this.reset(delayed); }
    reset(delayed = false) {
      this.x = Math.random() * W * 1.5 - W * 0.25;
      this.y = Math.random() * H * 0.4 - H * 0.1;
      this.len = Math.random() * 180 + 80;
      this.speed = Math.random() * 6 + 3;
      this.angle = (Math.PI / 4) + (Math.random() - 0.5) * 0.3;
      this.alpha = Math.random() * 0.6 + 0.4;
      this.width = Math.random() * 1.5 + 0.5;
      this.delay = delayed ? Math.random() * 300 : 0;
      this.active = false;
    }
    update() {
      if (this.delay > 0) { this.delay--; return; }
      this.active = true;
      this.x += Math.cos(this.angle) * this.speed;
      this.y += Math.sin(this.angle) * this.speed;
      if (this.x > W + 200 || this.y > H + 200) this.reset(true);
    }
    draw() {
      if (!this.active) return;
      const tx = this.x - Math.cos(this.angle) * this.len;
      const ty = this.y - Math.sin(this.angle) * this.len;
      const grad = ctx.createLinearGradient(tx, ty, this.x, this.y);
      grad.addColorStop(0, `rgba(255,255,255,0)`);
      grad.addColorStop(0.6, `rgba(200,200,255,${this.alpha * 0.4})`);
      grad.addColorStop(1, `rgba(255,255,255,${this.alpha})`);
      ctx.beginPath();
      ctx.moveTo(tx, ty);
      ctx.lineTo(this.x, this.y);
      ctx.strokeStyle = grad;
      ctx.lineWidth = this.width;
      ctx.stroke();
      // Head glow
      ctx.beginPath();
      ctx.arc(this.x, this.y, this.width * 1.2, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(255,255,255,${this.alpha * 0.8})`;
      ctx.fill();
    }
  }

  const meteors = Array.from({ length: 18 }, () => new Meteor(true));

  function frame() {
    ctx.clearRect(0, 0, W, H);
    drawStars();
    meteors.forEach(m => { m.update(); m.draw(); });
    requestAnimationFrame(frame);
  }
  frame();
})();

// ── Rich markup → HTML ─────────────────────────────────────────────────────────
function richToHtml(text) {
  // Strip Rich markup tags, convert some to spans
  const map = {
    'bold': 'log-bold',
    'green': 'log-green',
    'red': 'log-red',
    'yellow': 'log-yellow',
    'cyan': 'log-cyan',
    'dim': 'log-dim',
    'bold cyan': 'log-bold log-cyan',
    'bold green': 'log-bold log-green',
  };
  let out = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');

  // Convert [tag]...[/tag] pairs
  for (const [tag, cls] of Object.entries(map)) {
    const re = new RegExp(`\\[${tag}\\](.*?)\\[\\/${tag.split(' ')[0]}\\]`, 'gs');
    out = out.replace(re, `<span class="${cls}">$1</span>`);
  }
  // Strip remaining [xxx] tags
  out = out.replace(/\[[^\]]+\]/g, '');
  return out;
}

// ── State ──────────────────────────────────────────────────────────────────────
const state = {
  sid: null,
  status: 'idle',
  eventSource: null,
  keywordRules: [],   // [{question_keyword, preferred_answers: [], ratio}]
  textRules: [],      // [{question_keyword, answers: []}]
};

// ── Session init ───────────────────────────────────────────────────────────────
async function initSession() {
  const saved = localStorage.getItem('filler_sid');
  const res = await fetch('/api/session', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ sid: saved }),
  }).then(r => r.json());
  state.sid = res.sid;
  localStorage.setItem('filler_sid', state.sid);
  loadProfilesList();
  loadHistory();
}

// ── Tabs ───────────────────────────────────────────────────────────────────────
document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('tab-' + btn.dataset.tab).classList.add('active');
    if (btn.dataset.tab === 'profiles') loadProfilesList();
    if (btn.dataset.tab === 'history') loadHistory();
  });
});

// ── Slider display ─────────────────────────────────────────────────────────────
document.querySelectorAll('input[type="range"]').forEach(sl => {
  const display = document.getElementById(sl.id + '_val');
  if (display) {
    display.textContent = sl.value;
    sl.addEventListener('input', () => { display.textContent = sl.value; });
  }
});

// ── Run ────────────────────────────────────────────────────────────────────────
document.getElementById('btn-start').addEventListener('click', startRun);
document.getElementById('btn-stop').addEventListener('click', stopRun);

async function startRun() {
  const config = buildConfig();
  if (!config.form_url) { alert('Vui lòng nhập Form URL'); return; }

  setStatus('running');
  clearLog();
  appendLog('[dim]▶ Bắt đầu...[/dim]');

  await fetch(`/api/run/${state.sid}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config),
  });

  openStream();
}

async function stopRun() {
  await fetch(`/api/stop/${state.sid}`, { method: 'POST' });
  setStatus('stopped');
  if (state.eventSource) { state.eventSource.close(); state.eventSource = null; }
}

function openStream() {
  if (state.eventSource) state.eventSource.close();
  state.eventSource = new EventSource(`/api/stream/${state.sid}`);
  state.eventSource.onmessage = (e) => {
    const data = JSON.parse(e.data);
    if (data.msg === '__DONE__') {
      state.eventSource.close();
      state.eventSource = null;
      setStatus(state.status === 'running' ? 'done' : state.status);
      loadHistory();
      return;
    }
    appendLog(data.msg);
  };
  state.eventSource.onerror = () => {
    state.eventSource.close();
    state.eventSource = null;
  };
}

// ── Log panel ──────────────────────────────────────────────────────────────────
function appendLog(msg) {
  const panel = document.getElementById('log-panel');
  const line = document.createElement('div');
  line.className = 'log-line';
  line.innerHTML = richToHtml(msg);
  panel.appendChild(line);
  panel.scrollTop = panel.scrollHeight;
}
function clearLog() {
  document.getElementById('log-panel').innerHTML = '';
}
function exportLog() {
  const lines = document.querySelectorAll('#log-panel .log-line');
  const text = Array.from(lines).map(l => l.innerText).join('\n');
  const blob = new Blob([text], { type: 'text/plain' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `form-filler-log-${new Date().toISOString().slice(0,19).replace(/[:T]/g,'-')}.txt`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(a.href);
}
document.getElementById('btn-clear-log').addEventListener('click', clearLog);
document.getElementById('btn-export-log').addEventListener('click', exportLog);
document.getElementById('btn-reset-config').addEventListener('click', () => {
  if (!confirm('Reset toàn bộ config về mặc định?')) return;
  document.getElementById('form_url').value = '';
  document.getElementById('n_submissions').value = 2;
  document.getElementById('headless').checked = false;
  document.getElementById('form_language').value = 'auto';
  document.getElementById('randomization_level').value = 3;
  document.getElementById('randomization_level_val').textContent = 3;
  document.getElementById('rating_direction').value = 'positive';
  document.getElementById('delay_min').value = 1;
  document.getElementById('delay_max').value = 3;
  document.getElementById('no_submit').checked = false;
  document.getElementById('date_start').value = '2020-01-01';
  document.getElementById('date_end').value = '2024-12-31';
  document.getElementById('avoid_answers').value = '';
  state.keywordRules = [];
  state.textRules = [];
  renderKeywordRules();
  renderTextRules();
});

// ── Status badge ───────────────────────────────────────────────────────────────
function setStatus(s) {
  state.status = s;
  const el = document.getElementById('status-badge');
  const icons = { idle: '○', running: '●', done: '✓', stopped: '⏹', error: '✗' };
  const labels = { idle: 'Chờ', running: 'Đang chạy', done: 'Xong', stopped: 'Đã dừng', error: 'Lỗi' };
  el.className = `status-badge status-${s}`;
  el.innerHTML = `<span ${s === 'running' ? 'class="pulse"' : ''}>${icons[s]}</span> ${labels[s]}`;

  document.getElementById('btn-start').disabled = s === 'running';
  document.getElementById('btn-stop').disabled = s !== 'running';
}

// ── Build config from form ─────────────────────────────────────────────────────
function buildConfig() {
  return {
    form_url: document.getElementById('form_url').value.trim(),
    n_submissions: parseInt(document.getElementById('n_submissions').value) || 1,
    headless: document.getElementById('headless').checked,
    form_language: document.getElementById('form_language').value,
    randomization_level: parseInt(document.getElementById('randomization_level').value),
    rating_direction: document.getElementById('rating_direction').value,
    delay_min: parseFloat(document.getElementById('delay_min').value) || 1,
    delay_max: parseFloat(document.getElementById('delay_max').value) || 3,
    no_submit: document.getElementById('no_submit').checked,
    date_start: document.getElementById('date_start').value || '2020-01-01',
    date_end: document.getElementById('date_end').value || '2024-12-31',
    keyword_rules: state.keywordRules,
    text_rules: state.textRules,
    avoid_answers: document.getElementById('avoid_answers').value
      .split(',').map(s => s.trim()).filter(Boolean),
  };
}

function loadConfigIntoForm(cfg) {
  document.getElementById('form_url').value = cfg.form_url || '';
  document.getElementById('n_submissions').value = cfg.n_submissions || 1;
  document.getElementById('headless').checked = !!cfg.headless;
  document.getElementById('form_language').value = cfg.form_language || 'auto';
  document.getElementById('randomization_level').value = cfg.randomization_level || 3;
  document.getElementById('randomization_level_val').textContent = cfg.randomization_level || 3;
  document.getElementById('rating_direction').value = cfg.rating_direction || 'positive';
  document.getElementById('delay_min').value = cfg.delay_min ?? 1;
  document.getElementById('delay_max').value = cfg.delay_max ?? 3;
  document.getElementById('no_submit').checked = !!cfg.no_submit;
  document.getElementById('date_start').value = cfg.date_start || '2020-01-01';
  document.getElementById('date_end').value = cfg.date_end || '2024-12-31';
  document.getElementById('avoid_answers').value = (cfg.avoid_answers || []).join(', ');

  state.keywordRules = cfg.keyword_rules || [];
  state.textRules = cfg.text_rules || [];
  renderKeywordRules();
  renderTextRules();
}

// ── Keyword rules ──────────────────────────────────────────────────────────────
function renderKeywordRules() {
  const list = document.getElementById('kw-rule-list');
  list.innerHTML = '';
  state.keywordRules.forEach((rule, i) => {
    const chip = document.createElement('div');
    chip.className = 'rule-chip';
    chip.innerHTML = `
      <span class="rule-chip-label">
        <span class="kw">${escHtml(rule.question_keyword)}</span>
        → ${escHtml(rule.preferred_answers.join(', '))}
        <span class="ratio">(${Math.round(rule.ratio * 100)}%)</span>
      </span>
      <button class="rule-chip-del" onclick="deleteKwRule(${i})">✕</button>`;
    list.appendChild(chip);
  });
}

function deleteKwRule(i) {
  state.keywordRules.splice(i, 1);
  renderKeywordRules();
}

document.getElementById('btn-add-kw').addEventListener('click', () => {
  document.getElementById('kw-form').style.display = 'block';
});
document.getElementById('btn-kw-cancel').addEventListener('click', () => {
  document.getElementById('kw-form').style.display = 'none';
  resetKwForm();
});
document.getElementById('btn-kw-save').addEventListener('click', () => {
  const kw = document.getElementById('kw-keyword').value.trim();
  const answers = document.getElementById('kw-answers').value.split(',').map(s => s.trim()).filter(Boolean);
  const ratio = Math.min(1, Math.max(0, parseFloat(document.getElementById('kw-ratio').value) || 1));
  if (!kw || !answers.length) { alert('Cần nhập keyword và preferred answers'); return; }
  state.keywordRules.push({ question_keyword: kw, preferred_answers: answers, ratio });
  renderKeywordRules();
  document.getElementById('kw-form').style.display = 'none';
  resetKwForm();
});
function resetKwForm() {
  document.getElementById('kw-keyword').value = '';
  document.getElementById('kw-answers').value = '';
  document.getElementById('kw-ratio').value = '1.0';
}

// ── Text rules ─────────────────────────────────────────────────────────────────
function renderTextRules() {
  const list = document.getElementById('txt-rule-list');
  list.innerHTML = '';
  state.textRules.forEach((rule, i) => {
    const chip = document.createElement('div');
    chip.className = 'rule-chip';
    chip.innerHTML = `
      <span class="rule-chip-label">
        <span class="kw">${escHtml(rule.question_keyword)}</span>
        — ${rule.answers.length} đoạn văn
      </span>
      <button class="rule-chip-del" onclick="deleteTxtRule(${i})">✕</button>`;
    list.appendChild(chip);
  });
}

function deleteTxtRule(i) {
  state.textRules.splice(i, 1);
  renderTextRules();
}

document.getElementById('btn-add-txt').addEventListener('click', () => {
  document.getElementById('txt-form').style.display = 'block';
});
document.getElementById('btn-txt-cancel').addEventListener('click', () => {
  document.getElementById('txt-form').style.display = 'none';
  resetTxtForm();
});
document.getElementById('btn-txt-save').addEventListener('click', () => {
  const kw = document.getElementById('txt-keyword').value.trim();
  const raw = document.getElementById('txt-answers').value.trim();
  const answers = raw.split('\n---\n').map(s => s.trim()).filter(Boolean);
  if (!answers.length) {
    // fallback: treat whole textarea as one answer
    if (raw) answers.push(raw);
  }
  if (!kw || !answers.length) { alert('Cần nhập keyword và ít nhất 1 đoạn văn'); return; }
  state.textRules.push({ question_keyword: kw, answers });
  renderTextRules();
  document.getElementById('txt-form').style.display = 'none';
  resetTxtForm();
});
function resetTxtForm() {
  document.getElementById('txt-keyword').value = '';
  document.getElementById('txt-answers').value = '';
}

// ── Profiles ───────────────────────────────────────────────────────────────────
async function loadProfilesList() {
  const res = await fetch('/api/profiles').then(r => r.json());
  const list = document.getElementById('profile-list');
  list.innerHTML = '';
  if (!res.profiles.length) {
    list.innerHTML = '<div class="empty-state">Chưa có profile nào</div>';
    return;
  }
  res.profiles.forEach(name => {
    const item = document.createElement('div');
    item.className = 'profile-item';
    item.innerHTML = `
      <span class="profile-name">📁 ${escHtml(name)}</span>
      <div class="profile-actions">
        <button class="btn btn-ghost btn-sm" onclick="loadProfile('${escHtml(name)}')">Load</button>
        <button class="btn btn-danger btn-sm" onclick="deleteProfileItem('${escHtml(name)}')">Xóa</button>
      </div>`;
    list.appendChild(item);
  });
}

async function loadProfile(name) {
  const cfg = await fetch(`/api/profiles/${name}`).then(r => r.json());
  loadConfigIntoForm(cfg);
  // Switch to config tab
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
  document.querySelector('[data-tab="config"]').classList.add('active');
  document.getElementById('tab-config').classList.add('active');
}

async function deleteProfileItem(name) {
  if (!confirm(`Xóa profile "${name}"?`)) return;
  await fetch(`/api/profiles/${name}`, { method: 'DELETE' });
  loadProfilesList();
}

// Save profile modal
document.getElementById('btn-save-profile').addEventListener('click', () => {
  document.getElementById('save-modal').classList.add('open');
  document.getElementById('profile-name-input').value = '';
  document.getElementById('profile-name-input').focus();
});
document.getElementById('btn-modal-cancel').addEventListener('click', () => {
  document.getElementById('save-modal').classList.remove('open');
});
document.getElementById('btn-modal-save').addEventListener('click', async () => {
  const name = document.getElementById('profile-name-input').value.trim().replace(/\s+/g, '_');
  if (!name) { alert('Nhập tên profile'); return; }
  const config = buildConfig();
  await fetch(`/api/profiles/${name}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config),
  });
  document.getElementById('save-modal').classList.remove('open');
  loadProfilesList();
});

// ── History ────────────────────────────────────────────────────────────────────
async function loadHistory() {
  if (!state.sid) return;
  const res = await fetch(`/api/history/${state.sid}`).then(r => r.json());
  const container = document.getElementById('history-list');
  container.innerHTML = '';
  if (!res.history.length) {
    container.innerHTML = '<div class="empty-state">Chưa có lần chạy nào</div>';
    return;
  }
  [...res.history].reverse().forEach((run, i) => {
    const item = document.createElement('div');
    item.className = 'history-item';
    const logsHtml = run.logs.map(l => `<div class="log-line">${richToHtml(l)}</div>`).join('');
    item.innerHTML = `
      <div class="history-meta">
        <span class="history-time">${run.time}</span>
        <span class="history-url" title="${escHtml(run.url)}">${escHtml(run.url)}</span>
        <div class="history-stats">
          <span class="stat-ok">✓ ${run.success}</span>
          <span class="stat-fail">✗ ${run.fail}</span>
          <span style="color:rgba(255,255,255,0.3)">/ ${run.n_submissions}</span>
        </div>
      </div>
      <div class="history-logs">${logsHtml}</div>`;
    item.addEventListener('click', () => item.classList.toggle('expanded'));
    container.appendChild(item);
  });
}

// ── Helpers ────────────────────────────────────────────────────────────────────
function escHtml(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// ── Boot ───────────────────────────────────────────────────────────────────────
setStatus('idle');
initSession();
