(function initMeteorCanvas() {
  const canvas = document.getElementById("meteor-canvas");
  const ctx = canvas.getContext("2d");
  let width = 0;
  let height = 0;

  function resize() {
    width = canvas.width = window.innerWidth;
    height = canvas.height = window.innerHeight;
  }

  window.addEventListener("resize", resize);
  resize();

  const stars = Array.from({ length: 200 }, () => ({
    x: Math.random(),
    y: Math.random(),
    r: Math.random() * 1.2 + 0.2,
    a: Math.random() * 0.6 + 0.2,
  }));

  class Meteor {
    constructor(delayed = false) {
      this.reset(delayed);
    }

    reset(delayed = false) {
      this.x = Math.random() * width * 1.5 - width * 0.25;
      this.y = Math.random() * height * 0.4 - height * 0.1;
      this.len = Math.random() * 180 + 80;
      this.speed = Math.random() * 6 + 3;
      this.angle = Math.PI / 4 + (Math.random() - 0.5) * 0.3;
      this.alpha = Math.random() * 0.6 + 0.4;
      this.lineWidth = Math.random() * 1.5 + 0.5;
      this.delay = delayed ? Math.random() * 300 : 0;
      this.active = false;
    }

    update() {
      if (this.delay > 0) {
        this.delay -= 1;
        return;
      }
      this.active = true;
      this.x += Math.cos(this.angle) * this.speed;
      this.y += Math.sin(this.angle) * this.speed;
      if (this.x > width + 200 || this.y > height + 200) {
        this.reset(true);
      }
    }

    draw() {
      if (!this.active) {
        return;
      }
      const tailX = this.x - Math.cos(this.angle) * this.len;
      const tailY = this.y - Math.sin(this.angle) * this.len;
      const gradient = ctx.createLinearGradient(tailX, tailY, this.x, this.y);
      gradient.addColorStop(0, "rgba(255,255,255,0)");
      gradient.addColorStop(0.6, `rgba(200,200,255,${this.alpha * 0.4})`);
      gradient.addColorStop(1, `rgba(255,255,255,${this.alpha})`);
      ctx.beginPath();
      ctx.moveTo(tailX, tailY);
      ctx.lineTo(this.x, this.y);
      ctx.strokeStyle = gradient;
      ctx.lineWidth = this.lineWidth;
      ctx.stroke();
      ctx.beginPath();
      ctx.arc(this.x, this.y, this.lineWidth * 1.2, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(255,255,255,${this.alpha * 0.8})`;
      ctx.fill();
    }
  }

  function drawStars() {
    stars.forEach((star) => {
      ctx.beginPath();
      ctx.arc(star.x * width, star.y * height, star.r, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(255,255,255,${star.a})`;
      ctx.fill();
    });
  }

  const meteors = Array.from({ length: 18 }, () => new Meteor(true));

  function frame() {
    ctx.clearRect(0, 0, width, height);
    drawStars();
    meteors.forEach((meteor) => {
      meteor.update();
      meteor.draw();
    });
    requestAnimationFrame(frame);
  }

  frame();
})();

function richToHtml(text) {
  const classes = {
    bold: "log-bold",
    green: "log-green",
    red: "log-red",
    yellow: "log-yellow",
    cyan: "log-cyan",
    dim: "log-dim",
  };

  let output = String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  output = output.replace(/\[(bold|green|red|yellow|cyan|dim)\](.*?)\[\/\1\]/gs, (_, tag, inner) => {
    return `<span class="${classes[tag]}">${inner}</span>`;
  });

  output = output.replace(/\[bold cyan\](.*?)\[\/bold cyan\]/gs, '<span class="log-bold log-cyan">$1</span>');
  output = output.replace(/\[bold green\](.*?)\[\/bold green\]/gs, '<span class="log-bold log-green">$1</span>');
  output = output.replace(/\[[^\]]+\]/g, "");
  return output;
}

const state = {
  sid: null,
  token: localStorage.getItem("filler_token"),
  user: null,
  status: "idle",
  eventSource: null,
  progressTimer: null,
  finishHandled: false,
  keywordRules: [],
  textRules: [],
  lastProgress: { success: 0, fail: 0, total: 0 },
};

function $(id) {
  return document.getElementById(id);
}

function escHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

async function parseJsonResponse(response) {
  let data = null;
  try {
    data = await response.json();
  } catch (_) {
    data = null;
  }
  if (!response.ok) {
    const message = data?.detail || data?.message || `HTTP ${response.status}`;
    throw new Error(message);
  }
  return data;
}

async function authFetch(url, options = {}) {
  const headers = {
    Authorization: `Bearer ${state.token}`,
    ...options.headers,
  };
  if (options.body && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }
  const response = await fetch(url, { ...options, headers });
  if (response.status === 401) {
    logout();
    throw new Error("Phiên đăng nhập đã hết hạn");
  }
  return response;
}

function showLogin(error = "") {
  $("login-screen").hidden = false;
  $("app").hidden = true;
  $("login-error").hidden = !error;
  $("login-error").textContent = error;
}

function showApp() {
  $("login-screen").hidden = true;
  $("app").hidden = false;
}

function setStatus(status) {
  state.status = status;
  const badge = $("status-badge");
  const icons = {
    idle: "○",
    running: "●",
    done: "✓",
    stopped: "⏹",
    error: "✗",
  };
  const labels = {
    idle: "Chờ",
    running: "Đang chạy",
    done: "Xong",
    stopped: "Đã dừng",
    error: "Lỗi",
  };

  badge.className = `status-badge status-${status}`;
  badge.innerHTML = `<span ${status === "running" ? 'class="pulse"' : ""}>${icons[status]}</span> ${labels[status]}`;

  $("btn-start").disabled = status === "running" || isQuotaBlocked();
  $("btn-stop").disabled = status !== "running";
}

function isQuotaBlocked() {
  return Boolean(state.user && state.user.role !== "admin" && state.user.quota_remaining !== null && state.user.quota_remaining <= 0);
}

function updateUserSummary() {
  if (!state.user) {
    $("user-summary").textContent = "Chưa đăng nhập";
    return;
  }
  const quotaLabel = state.user.quota_remaining === null ? "∞" : `${state.user.quota_remaining} lượt`;
  const role = state.user.role === "admin" ? "admin" : "user";
  $("user-summary").textContent = `👤 ${state.user.username} · ${role} · còn ${quotaLabel}`;
  $("tab-admin-btn").hidden = state.user.role !== "admin";
  syncQuotaNotice();
  setStatus(state.status);
}

function syncQuotaNotice() {
  if (isQuotaBlocked()) {
    $("quota-notice").hidden = false;
    $("quota-notice").textContent = "Hết quota. Liên hệ admin để được cấp thêm.";
  } else {
    $("quota-notice").hidden = true;
    $("quota-notice").textContent = "";
  }
}

function clearLog() {
  $("log-panel").innerHTML = "";
}

function appendLog(message) {
  const line = document.createElement("div");
  line.className = "log-line";
  line.innerHTML = richToHtml(message);
  $("log-panel").appendChild(line);
  $("log-panel").scrollTop = $("log-panel").scrollHeight;
}

function exportLog() {
  const lines = Array.from(document.querySelectorAll("#log-panel .log-line")).map((node) => node.innerText);
  const blob = new Blob([lines.join("\n")], { type: "text/plain" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = `form-filler-log-${new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-")}.txt`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(link.href);
}

function buildConfig() {
  return {
    form_url: $("form_url").value.trim(),
    n_submissions: parseInt($("n_submissions").value, 10) || 1,
    headless: $("headless").checked,
    form_language: $("form_language").value,
    randomization_level: parseInt($("randomization_level").value, 10) || 3,
    rating_direction: $("rating_direction").value,
    delay_min: parseFloat($("delay_min").value) || 0,
    delay_max: parseFloat($("delay_max").value) || 0,
    no_submit: $("no_submit").checked,
    date_start: $("date_start").value || "2020-01-01",
    date_end: $("date_end").value || "2024-12-31",
    keyword_rules: state.keywordRules,
    text_rules: state.textRules,
    avoid_answers: $("avoid_answers").value.split(",").map((item) => item.trim()).filter(Boolean),
  };
}

function loadConfigIntoForm(config) {
  $("form_url").value = config.form_url || "";
  $("n_submissions").value = config.n_submissions || 1;
  $("headless").checked = Boolean(config.headless);
  $("form_language").value = config.form_language || "auto";
  $("randomization_level").value = config.randomization_level || 3;
  $("randomization_level_val").textContent = $("randomization_level").value;
  $("rating_direction").value = config.rating_direction || "positive";
  $("delay_min").value = config.delay_min ?? 1;
  $("delay_max").value = config.delay_max ?? 3;
  $("no_submit").checked = Boolean(config.no_submit);
  $("date_start").value = config.date_start || "2020-01-01";
  $("date_end").value = config.date_end || "2024-12-31";
  $("avoid_answers").value = (config.avoid_answers || []).join(", ");
  state.keywordRules = config.keyword_rules || [];
  state.textRules = config.text_rules || [];
  renderKeywordRules();
  renderTextRules();
}

function resetConfig() {
  $("form_url").value = "";
  $("n_submissions").value = 2;
  $("headless").checked = false;
  $("form_language").value = "auto";
  $("randomization_level").value = 3;
  $("randomization_level_val").textContent = "3";
  $("rating_direction").value = "positive";
  $("delay_min").value = 1;
  $("delay_max").value = 3;
  $("no_submit").checked = false;
  $("date_start").value = "2020-01-01";
  $("date_end").value = "2024-12-31";
  $("avoid_answers").value = "";
  state.keywordRules = [];
  state.textRules = [];
  renderKeywordRules();
  renderTextRules();
}

function setActiveTab(tabName) {
  document.querySelectorAll(".tab-btn").forEach((button) => {
    button.classList.toggle("active", button.dataset.tab === tabName);
  });
  document.querySelectorAll(".tab-pane").forEach((pane) => {
    pane.classList.toggle("active", pane.id === `tab-${tabName}`);
  });
}

function renderKeywordRules() {
  const list = $("kw-rule-list");
  list.innerHTML = "";
  state.keywordRules.forEach((rule, index) => {
    const chip = document.createElement("div");
    chip.className = "rule-chip";
    chip.innerHTML = `
      <span class="rule-chip-label">
        <span class="kw">${escHtml(rule.question_keyword)}</span>
        → ${escHtml(rule.preferred_answers.join(", "))}
        <span class="ratio">(${Math.round(rule.ratio * 100)}%)</span>
      </span>
    `;
    const button = document.createElement("button");
    button.className = "rule-chip-del";
    button.type = "button";
    button.textContent = "✕";
    button.addEventListener("click", () => {
      state.keywordRules.splice(index, 1);
      renderKeywordRules();
    });
    chip.appendChild(button);
    list.appendChild(chip);
  });
}

function renderTextRules() {
  const list = $("txt-rule-list");
  list.innerHTML = "";
  state.textRules.forEach((rule, index) => {
    const chip = document.createElement("div");
    chip.className = "rule-chip";
    chip.innerHTML = `
      <span class="rule-chip-label">
        <span class="kw">${escHtml(rule.question_keyword)}</span>
        - ${rule.answers.length} đoạn văn
      </span>
    `;
    const button = document.createElement("button");
    button.className = "rule-chip-del";
    button.type = "button";
    button.textContent = "✕";
    button.addEventListener("click", () => {
      state.textRules.splice(index, 1);
      renderTextRules();
    });
    chip.appendChild(button);
    list.appendChild(chip);
  });
}

function resetKeywordForm() {
  $("kw-keyword").value = "";
  $("kw-answers").value = "";
  $("kw-ratio").value = "1.0";
}

function resetTextForm() {
  $("txt-keyword").value = "";
  $("txt-answers").value = "";
}

async function login() {
  const username = $("login-username").value.trim();
  const password = $("login-password").value;
  $("login-error").hidden = true;

  try {
    const response = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    const data = await parseJsonResponse(response);
    state.token = data.token;
    state.user = data.user;
    localStorage.setItem("filler_token", state.token);
    showApp();
    updateUserSummary();
    await initSession();
    await loadProfilesList();
    await loadHistory();
    if (state.user.role === "admin") {
      await loadAdminUsers();
    }
    if ("Notification" in window && Notification.permission === "default") {
      Notification.requestPermission().catch(() => {});
    }
  } catch (error) {
    showLogin(error.message || "Đăng nhập thất bại");
  }
}

function closeRunningChannels() {
  if (state.eventSource) {
    state.eventSource.close();
    state.eventSource = null;
  }
  if (state.progressTimer) {
    clearInterval(state.progressTimer);
    state.progressTimer = null;
  }
}

function logout() {
  closeRunningChannels();
  localStorage.removeItem("filler_token");
  localStorage.removeItem("filler_sid");
  state.sid = null;
  state.token = null;
  state.user = null;
  state.finishHandled = false;
  state.lastProgress = { success: 0, fail: 0, total: 0 };
  setStatus("idle");
  updateProgress({ success: 0, fail: 0, total: 0 }, false);
  showLogin();
}

async function refreshMe() {
  const response = await authFetch("/api/me");
  state.user = await parseJsonResponse(response);
  updateUserSummary();
  return state.user;
}

async function initSession() {
  const savedSid = localStorage.getItem("filler_sid");
  const response = await authFetch("/api/session", {
    method: "POST",
    body: JSON.stringify({ sid: savedSid }),
  });
  const data = await parseJsonResponse(response);
  state.sid = data.sid;
  localStorage.setItem("filler_sid", state.sid);
}

function updateProgress(progress, visible = true) {
  state.lastProgress = progress || { success: 0, fail: 0, total: 0 };
  $("progress-bar-wrap").hidden = !visible || !progress || !progress.total;
  if (!visible || !progress || !progress.total) {
    $("progress-fill").style.width = "0%";
    $("progress-label").textContent = "0 / 0 - 0%";
    return;
  }

  const done = (progress.success || 0) + (progress.fail || 0);
  const total = progress.total || 0;
  const percent = total ? Math.round((done / total) * 100) : 0;
  $("progress-fill").style.width = `${percent}%`;
  $("progress-label").textContent = `${done} / ${total} - ${percent}%`;
}

function notifyDone(success, fail) {
  try {
    const AudioCtor = window.AudioContext || window.webkitAudioContext;
    if (AudioCtor) {
      const ctx = new AudioCtor();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.frequency.value = 880;
      gain.gain.value = 0.05;
      osc.start();
      osc.stop(ctx.currentTime + 0.15);
    }
  } catch (_) {
  }

  if ("Notification" in window && Notification.permission === "granted") {
    new Notification("Form Auto-Filler xong!", {
      body: `✅ ${success} thành công  ❌ ${fail} thất bại`,
    });
  }
}

async function handleRunFinished(status) {
  if (state.finishHandled) {
    return;
  }
  state.finishHandled = true;
  closeRunningChannels();
  setStatus(status);
  await refreshMe().catch(() => {});
  await loadHistory().catch(() => {});
  notifyDone(state.lastProgress.success || 0, state.lastProgress.fail || 0);
}

async function pollStatus() {
  if (!state.sid) {
    return;
  }
  try {
    const response = await authFetch(`/api/status/${state.sid}`);
    const data = await parseJsonResponse(response);
    updateProgress(data.progress, data.status === "running" || (data.progress?.total || 0) > 0);
    if (data.status && data.status !== "running" && state.status === "running") {
      await handleRunFinished(data.status);
    }
  } catch (_) {
  }
}

function startProgressPolling() {
  if (state.progressTimer) {
    clearInterval(state.progressTimer);
  }
  state.progressTimer = setInterval(pollStatus, 1000);
}

function openStream() {
  if (state.eventSource) {
    state.eventSource.close();
  }
  state.eventSource = new EventSource(`/api/stream/${state.sid}?token=${encodeURIComponent(state.token)}`);
  state.eventSource.onmessage = async (event) => {
    const data = JSON.parse(event.data);
    if (data.msg === "__DONE__") {
      if (state.eventSource) {
        state.eventSource.close();
        state.eventSource = null;
      }
      await pollStatus();
      return;
    }
    appendLog(data.msg);
  };
  state.eventSource.onerror = () => {
    if (state.eventSource) {
      state.eventSource.close();
      state.eventSource = null;
    }
  };
}

async function startRun() {
  if (!state.sid) {
    await initSession();
  }
  if (isQuotaBlocked()) {
    syncQuotaNotice();
    return;
  }

  const config = buildConfig();
  if (!config.form_url) {
    alert("Vui lòng nhập Form URL");
    return;
  }

  if ("Notification" in window && Notification.permission === "default") {
    Notification.requestPermission().catch(() => {});
  }

  state.finishHandled = false;
  clearLog();
  appendLog("[dim]▶ Bắt đầu...[/dim]");
  updateProgress({ success: 0, fail: 0, total: config.n_submissions }, true);
  setStatus("running");

  try {
    const response = await authFetch(`/api/run/${state.sid}`, {
      method: "POST",
      body: JSON.stringify(config),
    });
    const data = await parseJsonResponse(response);
    updateProgress({ success: 0, fail: 0, total: data.effective_submissions || config.n_submissions }, true);
    openStream();
    startProgressPolling();
  } catch (error) {
    setStatus("error");
    appendLog(`[red]❌ ${error.message}[/red]`);
  }
}

async function stopRun() {
  if (!state.sid) {
    return;
  }
  try {
    await authFetch(`/api/stop/${state.sid}`, { method: "POST" });
    setStatus("stopped");
  } catch (error) {
    appendLog(`[red]❌ ${error.message}[/red]`);
  } finally {
    closeRunningChannels();
  }
}

async function loadProfilesList() {
  const response = await authFetch("/api/profiles");
  const data = await parseJsonResponse(response);
  const list = $("profile-list");
  list.innerHTML = "";
  if (!data.profiles.length) {
    list.innerHTML = '<div class="empty-state">Chưa có profile nào</div>';
    return;
  }

  data.profiles.forEach((name) => {
    const item = document.createElement("div");
    item.className = "profile-item";
    item.innerHTML = `<span class="profile-name">📁 ${escHtml(name)}</span>`;

    const actions = document.createElement("div");
    actions.className = "profile-actions";

    const loadBtn = document.createElement("button");
    loadBtn.className = "btn btn-ghost btn-sm";
    loadBtn.textContent = "Load";
    loadBtn.addEventListener("click", async () => {
      const res = await authFetch(`/api/profiles/${encodeURIComponent(name)}`);
      const cfg = await parseJsonResponse(res);
      loadConfigIntoForm(cfg);
      setActiveTab("config");
    });

    const deleteBtn = document.createElement("button");
    deleteBtn.className = "btn btn-danger btn-sm";
    deleteBtn.textContent = "Xóa";
    deleteBtn.addEventListener("click", async () => {
      if (!confirm(`Xóa profile "${name}"?`)) {
        return;
      }
      await authFetch(`/api/profiles/${encodeURIComponent(name)}`, { method: "DELETE" });
      await loadProfilesList();
    });

    actions.appendChild(loadBtn);
    actions.appendChild(deleteBtn);
    item.appendChild(actions);
    list.appendChild(item);
  });
}

async function loadHistory() {
  if (!state.sid) {
    return;
  }
  const response = await authFetch(`/api/history/${state.sid}`);
  const data = await parseJsonResponse(response);
  const container = $("history-list");
  container.innerHTML = "";
  if (!data.history.length) {
    container.innerHTML = '<div class="empty-state">Chưa có lần chạy nào</div>';
    return;
  }

  [...data.history].reverse().forEach((run) => {
    const item = document.createElement("div");
    item.className = "history-item";
    const logsHtml = run.logs.map((line) => `<div class="log-line">${richToHtml(line)}</div>`).join("");
    item.innerHTML = `
      <div class="history-meta">
        <span class="history-time">${escHtml(run.time)}</span>
        <span class="history-url" title="${escHtml(run.url)}">${escHtml(run.url)}</span>
        <div class="history-stats">
          <span class="stat-ok">✓ ${run.success}</span>
          <span class="stat-fail">✗ ${run.fail}</span>
          <span class="log-dim">/ ${run.n_submissions}</span>
        </div>
      </div>
      <div class="history-logs">${logsHtml}</div>
    `;
    item.addEventListener("click", () => item.classList.toggle("expanded"));
    container.appendChild(item);
  });
}

async function loadAdminUsers(query = "") {
  if (!state.user || state.user.role !== "admin") {
    return;
  }
  const search = query.trim();
  const qs = search ? `?q=${encodeURIComponent(search)}` : "";
  const response = await authFetch(`/api/admin/users${qs}`);
  const data = await parseJsonResponse(response);
  const list = $("admin-user-list");
  list.innerHTML = "";
  if (!data.users.length) {
    list.innerHTML = '<div class="empty-state">Không tìm thấy user</div>';
    return;
  }

  data.users.forEach((user) => {
    const card = document.createElement("div");
    card.className = "admin-user-card";

    const quotaValue = user.quota_remaining === null ? "" : user.quota_remaining;
    card.innerHTML = `
      <div class="admin-user-main">
        <span class="admin-user-name">${escHtml(user.username)}</span>
        <span class="admin-user-meta">
          role=${escHtml(user.role)} · quota=${user.quota_remaining === null ? "∞" : user.quota_remaining} · submitted=${user.total_submitted}
        </span>
      </div>
    `;

    const actions = document.createElement("div");
    actions.className = "admin-actions";

    const quotaEditor = document.createElement("div");
    quotaEditor.className = "quota-editor";

    const input = document.createElement("input");
    input.type = "number";
    input.min = "0";
    input.placeholder = "Quota";
    input.value = quotaValue;

    const saveBtn = document.createElement("button");
    saveBtn.className = "btn btn-ghost btn-sm";
    saveBtn.textContent = "Set quota";
    saveBtn.addEventListener("click", async () => {
      await authFetch(`/api/admin/users/${user.id}`, {
        method: "PUT",
        body: JSON.stringify({ quota: input.value.trim() }),
      });
      await loadAdminUsers($("admin-search").value);
    });

    quotaEditor.appendChild(input);
    quotaEditor.appendChild(saveBtn);
    actions.appendChild(quotaEditor);

    if (user.role !== "admin") {
      const deleteBtn = document.createElement("button");
      deleteBtn.className = "btn btn-danger btn-sm";
      deleteBtn.textContent = "Xóa";
      deleteBtn.addEventListener("click", async () => {
        if (!confirm(`Xóa user "${user.username}"?`)) {
          return;
        }
        await authFetch(`/api/admin/users/${user.id}`, { method: "DELETE" });
        await loadAdminUsers($("admin-search").value);
      });
      actions.appendChild(deleteBtn);
    }

    card.appendChild(actions);
    list.appendChild(card);
  });
}

async function createAdminUser() {
  const username = $("admin-new-username").value.trim();
  const password = $("admin-new-password").value;
  const quota = $("admin-new-quota").value;
  if (!username || !password) {
    alert("Cần nhập username và password");
    return;
  }

  await authFetch("/api/admin/users", {
    method: "POST",
    body: JSON.stringify({ username, password, quota }),
  }).then(parseJsonResponse);

  $("admin-new-username").value = "";
  $("admin-new-password").value = "";
  $("admin-new-quota").value = "10";
  await loadAdminUsers($("admin-search").value);
}

function bindEvents() {
  document.querySelectorAll(".tab-btn").forEach((button) => {
    button.addEventListener("click", async () => {
      setActiveTab(button.dataset.tab);
      if (button.dataset.tab === "profiles") {
        await loadProfilesList();
      }
      if (button.dataset.tab === "history") {
        await loadHistory();
      }
      if (button.dataset.tab === "admin") {
        await loadAdminUsers($("admin-search").value);
      }
    });
  });

  document.querySelectorAll('input[type="range"]').forEach((slider) => {
    const display = $(`${slider.id}_val`);
    if (display) {
      display.textContent = slider.value;
      slider.addEventListener("input", () => {
        display.textContent = slider.value;
      });
    }
  });

  $("btn-login").addEventListener("click", login);
  $("login-password").addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      login();
    }
  });
  $("btn-logout").addEventListener("click", logout);

  $("btn-start").addEventListener("click", startRun);
  $("btn-stop").addEventListener("click", stopRun);
  $("btn-clear-log").addEventListener("click", clearLog);
  $("btn-export-log").addEventListener("click", exportLog);
  $("btn-reset-config").addEventListener("click", () => {
    if (confirm("Reset toàn bộ config về mặc định?")) {
      resetConfig();
    }
  });

  $("btn-add-kw").addEventListener("click", () => {
    $("kw-form").hidden = false;
  });
  $("btn-kw-cancel").addEventListener("click", () => {
    $("kw-form").hidden = true;
    resetKeywordForm();
  });
  $("btn-kw-save").addEventListener("click", () => {
    const keyword = $("kw-keyword").value.trim();
    const answers = $("kw-answers").value.split(",").map((item) => item.trim()).filter(Boolean);
    const ratio = Math.min(1, Math.max(0, parseFloat($("kw-ratio").value) || 1));
    if (!keyword || !answers.length) {
      alert("Cần nhập keyword và preferred answers");
      return;
    }
    state.keywordRules.push({ question_keyword: keyword, preferred_answers: answers, ratio });
    renderKeywordRules();
    resetKeywordForm();
    $("kw-form").hidden = true;
  });

  $("btn-add-txt").addEventListener("click", () => {
    $("txt-form").hidden = false;
  });
  $("btn-txt-cancel").addEventListener("click", () => {
    $("txt-form").hidden = true;
    resetTextForm();
  });
  $("btn-txt-save").addEventListener("click", () => {
    const keyword = $("txt-keyword").value.trim();
    const raw = $("txt-answers").value.trim();
    const answers = raw.split("\n---\n").map((item) => item.trim()).filter(Boolean);
    if (!answers.length && raw) {
      answers.push(raw);
    }
    if (!keyword || !answers.length) {
      alert("Cần nhập keyword và ít nhất 1 đoạn văn");
      return;
    }
    state.textRules.push({ question_keyword: keyword, answers });
    renderTextRules();
    resetTextForm();
    $("txt-form").hidden = true;
  });

  $("btn-save-profile").addEventListener("click", () => {
    $("save-modal").classList.add("open");
    $("profile-name-input").value = "";
    $("profile-name-input").focus();
  });
  $("btn-modal-cancel").addEventListener("click", () => {
    $("save-modal").classList.remove("open");
  });
  $("btn-modal-save").addEventListener("click", async () => {
    const name = $("profile-name-input").value.trim().replace(/\s+/g, "_");
    if (!name) {
      alert("Nhập tên profile");
      return;
    }
    await authFetch(`/api/profiles/${encodeURIComponent(name)}`, {
      method: "POST",
      body: JSON.stringify(buildConfig()),
    }).then(parseJsonResponse);
    $("save-modal").classList.remove("open");
    await loadProfilesList();
  });

  $("btn-refresh-profiles").addEventListener("click", loadProfilesList);
  $("btn-refresh-history").addEventListener("click", loadHistory);
  $("btn-admin-search").addEventListener("click", () => loadAdminUsers($("admin-search").value));
  $("btn-admin-refresh").addEventListener("click", () => loadAdminUsers($("admin-search").value));
  $("admin-search").addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      loadAdminUsers($("admin-search").value);
    }
  });
  $("btn-admin-create").addEventListener("click", createAdminUser);
}

async function boot() {
  bindEvents();
  renderKeywordRules();
  renderTextRules();
  setStatus("idle");
  updateProgress({ success: 0, fail: 0, total: 0 }, false);

  if (!state.token) {
    showLogin();
    return;
  }

  try {
    await refreshMe();
    showApp();
    await initSession();
    await loadProfilesList();
    await loadHistory();
    if (state.user.role === "admin") {
      await loadAdminUsers();
    }
  } catch (_) {
    logout();
  }
}

window.addEventListener("DOMContentLoaded", boot);
