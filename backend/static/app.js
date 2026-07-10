const API = "/api";
const TOKEN_KEY = "vam_token";

const $ = (sel, root = document) => root.querySelector(sel);

const state = {
  token: localStorage.getItem(TOKEN_KEY) || "",
  user: null,
  scenarioId: null,
  jobId: null,
  copyUnlocked: false,
  copyUnlockCost: 5,
  produceCost: 100,
  discussCost: 10,
  scenarioCost: 15,
  refineCost: 35,
  pricing: null,
  lastScenario: null,
};

function setError(el, msg) {
  if (!el) return;
  if (!msg) {
    el.hidden = true;
    el.textContent = "";
    return;
  }
  el.hidden = false;
  el.textContent = msg;
}

function mediaUrl(path) {
  if (!path) return "";
  const sep = path.includes("?") ? "&" : "?";
  const token = state.token ? `access_token=${encodeURIComponent(state.token)}&` : "";
  return `${path}${sep}${token}t=${Date.now()}`;
}

function setWorking(on, text) {
  const overlay = $("#workOverlay");
  if (!overlay) return;
  overlay.hidden = !on;
  if (text) {
    const label = $("#workOverlayText");
    if (label) label.textContent = text;
  }
}

async function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

async function pollJob(jobId, { label } = {}) {
  const terminal = new Set(["completed", "failed"]);
  for (let i = 0; i < 90; i++) {
    const job = await api(`/jobs/${jobId}`);
    renderJob(job, { soft: true });
    const statusLabel = label || "Üretiliyor";
    setWorking(true, `${statusLabel}… (${job.status})`);
    if (terminal.has(job.status)) {
      if (job.status === "failed") {
        throw new Error(job.error_message || "Üretim başarısız");
      }
      return job;
    }
    await sleep(2000);
  }
  throw new Error("Üretim zaman aşımı — işler sayfasından tekrar kontrol edin");
}

async function loadHistory() {
  const box = $("#historyList");
  if (!box) return;
  try {
    const rows = await api("/scenarios");
    if (!rows.length) {
      box.innerHTML = `<p class="lede tight">Henüz kayıt yok.</p>`;
      return;
    }
    box.innerHTML = rows
      .slice(0, 12)
      .map((s) => {
        const title = escapeHtml(s.title || s.professional_script?.title || `Senaryo #${s.id}`);
        const meta = escapeHtml(
          `${(s.language || "tr").toUpperCase()} · ${s.duration_seconds || "—"}s · ${s.status || ""}`
        );
        return `<button type="button" class="history-item" data-id="${s.id}"><strong>${title}</strong><span>${meta}</span></button>`;
      })
      .join("");
    box.querySelectorAll(".history-item").forEach((btn) => {
      btn.addEventListener("click", async () => {
        setWorking(true, "Senaryo yükleniyor…");
        try {
          const scenario = await api(`/scenarios/${btn.dataset.id}`);
          renderScenario(scenario);
          const jobs = await api("/jobs");
          const related = (jobs || []).find((j) => j.scenario_id === scenario.id);
          if (related) renderJob(related);
        } catch (err) {
          setError($("#scenarioError"), err.message);
        } finally {
          setWorking(false);
        }
      });
    });
  } catch {
    box.innerHTML = `<p class="lede tight">Geçmiş yüklenemedi.</p>`;
  }
}

async function api(path, { method = "GET", body, auth = true } = {}) {
  const headers = { "Content-Type": "application/json" };
  if (auth && state.token) headers.Authorization = `Bearer ${state.token}`;
  const res = await fetch(`${API}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });
  let data = null;
  const text = await res.text();
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = { detail: text };
  }
  if (!res.ok) {
    const detail = data?.detail;
    const msg = typeof detail === "string" ? detail : JSON.stringify(detail || data);
    throw new Error(msg || `HTTP ${res.status}`);
  }
  return data;
}

function showAuth() {
  $("#authPanel").hidden = false;
  $("#studioPanel").hidden = true;
  $("#userBar").hidden = true;
}

function showStudio() {
  $("#authPanel").hidden = true;
  $("#studioPanel").hidden = false;
  $("#userBar").hidden = false;
}

async function refreshMe() {
  state.user = await api("/auth/me");
  const chip = $("#creditChip");
  if (state.user.unlimited_credits) {
    chip.textContent = "∞ kredi";
  } else {
    chip.textContent = `${state.user.credits} kredi`;
  }
  const adminLink = $("#adminLink");
  if (adminLink) {
    adminLink.hidden = !state.user.is_admin;
  }
  if (state.user.preferred_language) {
    const lang = $("#language");
    if ([...lang.options].some((o) => o.value === state.user.preferred_language)) {
      lang.value = state.user.preferred_language;
    }
  }
}

async function loadPricing() {
  try {
    const p = await api("/credits/pricing", { auth: false });
    state.pricing = p;
    state.scenarioCost = p.scenario;
    state.discussCost = p.discuss;
    state.refineCost = p.refine;
    state.copyUnlockCost = p.copy_unlock;
    const dur = Number($("#scenarioForm")?.duration_seconds?.value || 30);
    state.produceCost = Number(p.produce_by_duration?.[String(dur)] || p.produce_by_duration?.["30"] || 100);
    updateCostLabels();
  } catch {
    /* fiyat tablosu opsiyonel */
  }
}

function produceCostForDuration(seconds) {
  const key = String(seconds);
  const map = state.pricing?.produce_by_duration || {};
  if (map[key] != null) return map[key];
  // En yakın basamak
  const keys = Object.keys(map).map(Number).sort((a, b) => a - b);
  if (!keys.length) return state.produceCost;
  let best = keys[0];
  for (const k of keys) {
    if (seconds >= k) best = k;
  }
  return map[String(best)] || state.produceCost;
}

function updateCostLabels() {
  const convertBtn = $("#convertBtn");
  if (convertBtn && !convertBtn.disabled) {
    convertBtn.textContent = `AI1: Viral Senaryo Yaz (${state.scenarioCost} kredi)`;
  }
  const discussBtn = $("#discussBtn");
  if (discussBtn && !discussBtn.disabled) {
    discussBtn.textContent = `Gönder & uygula (${state.discussCost} kredi)`;
  }
  const produceBtn = $("#produceBtn");
  if (produceBtn && !produceBtn.disabled) {
    produceBtn.textContent = `AI2+AI3: Görsel Üret & Kurguya Ver (${state.produceCost} kredi)`;
  }
  const refineBtn = $("#refineBtn");
  if (refineBtn && !refineBtn.disabled) {
    refineBtn.textContent = `Revize et (${state.refineCost} kredi)`;
  }
  const unlockBtn = $("#unlockCopyBtn");
  if (unlockBtn && !unlockBtn.hidden && !state.copyUnlocked) {
    unlockBtn.textContent = `Kopyalamayı aç (${state.copyUnlockCost} kredi)`;
  }
}

async function boot() {
  if (!state.token) {
    showAuth();
    await loadPricing();
    return;
  }
  try {
    await refreshMe();
    showStudio();
    await loadPricing();
    await loadHistory();
  } catch {
    state.token = "";
    localStorage.removeItem(TOKEN_KEY);
    showAuth();
    await loadPricing();
  }
}

// Tabs
document.querySelectorAll(".tab").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    const tab = btn.dataset.tab;
    $("#loginForm").hidden = tab !== "login";
    $("#registerForm").hidden = tab !== "register";
    setError($("#authError"), "");
  });
});

$("#loginForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  setError($("#authError"), "");
  const fd = new FormData(e.target);
  try {
    const data = await api("/auth/login", {
      method: "POST",
      auth: false,
      body: { email: fd.get("email"), password: fd.get("password") },
    });
    state.token = data.access_token;
    localStorage.setItem(TOKEN_KEY, state.token);
    await refreshMe();
    showStudio();
    await loadHistory();
  } catch (err) {
    setError($("#authError"), err.message);
  }
});

$("#registerForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  setError($("#authError"), "");
  const fd = new FormData(e.target);
  try {
    const data = await api("/auth/register", {
      method: "POST",
      auth: false,
      body: {
        email: fd.get("email"),
        password: fd.get("password"),
        display_name: fd.get("display_name") || null,
        preferred_language: "tr",
      },
    });
    state.token = data.access_token;
    localStorage.setItem(TOKEN_KEY, state.token);
    await refreshMe();
    showStudio();
    await loadHistory();
  } catch (err) {
    setError($("#authError"), err.message);
  }
});

$("#logoutBtn").addEventListener("click", () => {
  state.token = "";
  state.user = null;
  localStorage.removeItem(TOKEN_KEY);
  showAuth();
});

// Settings
const dialog = $("#settingsDialog");
$("#settingsBtn").addEventListener("click", async () => {
  setError($("#settingsError"), "");
  try {
    const keys = await api("/api-keys");
    const box = $("#savedKeys");
    if (!keys.length) {
      box.textContent = "Kayıtlı anahtar yok.";
    } else {
      box.innerHTML = keys
        .map((k) => `<div>${k.provider}: <code>${k.key_hint}</code></div>`)
        .join("");
    }
  } catch (err) {
    setError($("#settingsError"), err.message);
  }
  dialog.showModal();
});

$("#closeSettingsBtn").addEventListener("click", () => dialog.close());

$("#settingsForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  setError($("#settingsError"), "");
  const fd = new FormData(e.target);
  const openrouter = String(fd.get("openrouter") || "").trim();
  const elevenlabs = String(fd.get("elevenlabs") || "").trim();
  try {
    if (openrouter) {
      await api("/api-keys", {
        method: "PUT",
        body: { provider: "openrouter", api_key: openrouter },
      });
    }
    if (elevenlabs) {
      await api("/api-keys", {
        method: "PUT",
        body: { provider: "elevenlabs", api_key: elevenlabs },
      });
    }
    e.target.reset();
    const keys = await api("/api-keys");
    $("#savedKeys").innerHTML = keys
      .map((k) => `<div>${k.provider}: <code>${k.key_hint}</code></div>`)
      .join("") || "Kayıtlı anahtar yok.";
  } catch (err) {
    setError($("#settingsError"), err.message);
  }
});

function renderScenario(scenario) {
  state.scenarioId = scenario.id;
  state.lastScenario = scenario;
  state.copyUnlocked = !!scenario.copy_unlocked || !!(state.user && state.user.unlimited_credits);
  state.copyUnlockCost = scenario.copy_unlock_cost || state.copyUnlockCost || 5;
  state.produceCost = scenario.produce_credit_cost || state.produceCost;
  state.discussCost = scenario.discuss_credit_cost || state.discussCost;

  const script = scenario.professional_script || {};
  $("#resultEmpty").hidden = true;
  $("#resultContent").hidden = false;
  $("#resultContent").classList.toggle("is-locked", !state.copyUnlocked);
  $("#resultTitle").textContent = script.title || scenario.title || "Senaryo";
  $("#resultHook").textContent = script.hook || "";
  $("#resultMeta").textContent = `${(scenario.language || "tr").toUpperCase()} · ${scenario.duration_seconds || "—"}s · ${scenario.style || "—"}`;
  $("#resultVoice").textContent = script.voiceover_full || "";
  $("#resultMusic").textContent = script.music_mood || "—";
  $("#resultCta").textContent = script.cta || "—";
  $("#resultId").textContent = scenario.id;
  setError($("#produceError"), "");
  setError($("#copyError"), "");

  const unlockBtn = $("#unlockCopyBtn");
  const copyBtn = $("#copyScenarioBtn");
  const hint = $("#copyHint");
  if (state.copyUnlocked) {
    unlockBtn.hidden = true;
    copyBtn.hidden = false;
    hint.hidden = true;
  } else {
    unlockBtn.hidden = false;
    unlockBtn.textContent = `Kopyalamayı aç (${state.copyUnlockCost} kredi)`;
    copyBtn.hidden = true;
    hint.hidden = false;
  }

  const badge = $("#resultBadge");
  if (script.mock) {
    badge.hidden = false;
  } else {
    badge.hidden = true;
  }

  const list = $("#resultScenes");
  list.innerHTML = "";
  (script.scenes || []).forEach((scene) => {
    const li = document.createElement("li");
    const role = scene.role ? ` · ${escapeHtml(String(scene.role).toUpperCase())}` : "";
    const cut = scene.cut ? ` · ${escapeHtml(scene.cut)}` : "";
    li.innerHTML = `
      <div class="scene-time">${escapeHtml(scene.timecode || "")}${role}${cut}</div>
      <p class="scene-visual">${escapeHtml(scene.visual || "")}</p>
      <p class="scene-narration">${escapeHtml(scene.narration || "")}</p>
      ${scene.on_screen_text ? `<p class="scene-visual">Ekran: ${escapeHtml(scene.on_screen_text)}</p>` : ""}
    `;
    list.appendChild(li);
  });

  renderDiscussion(scenario.discussion || []);
  updateCostLabels();
}

function renderDiscussion(messages) {
  const thread = $("#discussThread");
  if (!thread) return;
  if (!messages.length) {
    thread.innerHTML = `<div class="discuss-bubble director"><span class="discuss-role">Yönetmen</span>Senaryo hazır olunca burada konuşuruz.</div>`;
    return;
  }
  thread.innerHTML = messages
    .map((m) => {
      const role = m.role === "user" ? "user" : "director";
      const label = role === "user" ? "Sen" : "Yönetmen";
      return `<div class="discuss-bubble ${role}"><span class="discuss-role">${label}</span>${escapeHtml(m.content || "")}</div>`;
    })
    .join("");
  thread.scrollTop = thread.scrollHeight;
}

async function unlockAndCopyFlow() {
  setError($("#copyError"), "");
  if (!state.scenarioId) return;
  const btn = $("#unlockCopyBtn");
  btn.disabled = true;
  try {
    const scenario = await api(`/scenarios/${state.scenarioId}/unlock-copy`, { method: "POST" });
    renderScenario(scenario);
    await refreshMe();
  } catch (err) {
    setError($("#copyError"), err.message);
  } finally {
    btn.disabled = false;
  }
}

async function copyScenarioText() {
  setError($("#copyError"), "");
  if (!state.scenarioId) return;
  try {
    if (!state.copyUnlocked) {
      await unlockAndCopyFlow();
      if (!state.copyUnlocked) return;
    }
    const data = await api(`/scenarios/${state.scenarioId}/copy-text`);
    await navigator.clipboard.writeText(data.text || "");
    const btn = $("#copyScenarioBtn");
    const prev = btn.textContent;
    btn.textContent = "Kopyalandı ✓";
    setTimeout(() => {
      btn.textContent = prev;
    }, 1600);
  } catch (err) {
    setError($("#copyError"), err.message);
  }
}

function renderJob(job, { soft = false } = {}) {
  state.jobId = job.id;
  $("#playerSection").hidden = false;
  $("#jobMeta").textContent = `İş #${job.id} · rev ${job.revision} · ${job.status}`;
  $("#jobBadge").hidden = !job.is_mock;

  const video = $("#videoPlayer");
  const frame = $("#previewFrame");
  const audio = $("#audioPlayer");
  const dl = $("#downloadVideo");

  if (job.video_url && String(job.video_url).endsWith(".mp4")) {
    video.hidden = false;
    frame.hidden = true;
    video.src = mediaUrl(job.video_url);
    video.load();
    if (dl) {
      dl.hidden = false;
      dl.href = mediaUrl(job.video_url);
    }
  } else if (job.preview_url) {
    video.hidden = true;
    frame.hidden = false;
    frame.src = mediaUrl(job.preview_url);
    if (dl) dl.hidden = true;
  }

  if (job.audio_url) {
    audio.src = mediaUrl(job.audio_url);
  }

  const critiqueBox = $("#critiqueBox");
  if (critiqueBox) {
    const c = job.critique;
    if (c) {
      critiqueBox.hidden = false;
      const list = (arr) =>
        (arr || []).map((x) => `<li>${escapeHtml(x)}</li>`).join("") || "<li>—</li>";
      critiqueBox.innerHTML = `
        <h4>${escapeHtml(c.title || "Eleştiri Raporu")} · <strong>${escapeHtml(c.verdict || "")}</strong></h4>
        <div><strong>Güçlü</strong><ul>${list(c.strengths)}</ul></div>
        <div><strong>Risk</strong><ul>${list(c.risks)}</ul></div>
        <div><strong>Öneri</strong><ul>${list(c.suggestions)}</ul></div>
        <p>${escapeHtml(c.how_to_reply || "")}</p>
      `;
    } else {
      critiqueBox.hidden = true;
      critiqueBox.innerHTML = "";
    }
  }

  const thumbs = $("#sceneThumbs");
  if (thumbs) {
    const imgs = job.scene_images || [];
    thumbs.innerHTML = imgs
      .map(
        (s) =>
          `<img src="${escapeHtml(mediaUrl(s.url))}" alt="Sahne ${s.index}" title="Sahne ${s.index}" />`
      )
      .join("");
  }

  if (!soft && job.script_snapshot) {
    const base = state.lastScenario || {};
    renderScenario({
      id: job.scenario_id,
      language: base.language || "tr",
      duration_seconds: base.duration_seconds || 0,
      style: base.style || "—",
      title: job.script_snapshot.title,
      professional_script: job.script_snapshot,
      copy_unlocked: state.copyUnlocked || !!(state.user && state.user.unlimited_credits),
      copy_unlock_cost: state.copyUnlockCost,
      discussion: base.discussion || [],
      critique: base.critique || null,
    });
    $("#resultMeta").textContent = `Senaryo #${job.scenario_id} · rev ${job.revision}`;
  }

  const revBox = $("#revisionList");
  const revs = job.revisions || [];
  if (!revs.length) {
    revBox.innerHTML = `<div class="revision-item">Henüz geliştirme yok.</div>`;
  } else {
    revBox.innerHTML = revs
      .map((r) => {
        const fields = Array.isArray(r.changed_fields)
          ? r.changed_fields.join(", ")
          : r.changed_fields;
        return `<div class="revision-item"><strong>Rev ${r.revision}</strong> — ${escapeHtml(r.instruction)}<br/><span>${escapeHtml(fields || "")}</span></div>`;
      })
      .join("");
  }
}

function escapeHtml(str) {
  return String(str)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

$("#scenarioForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  setError($("#scenarioError"), "");
  const btn = $("#convertBtn");
  btn.disabled = true;
  btn.textContent = "Çevriliyor…";
  setWorking(true, "AI1 senaryo yazıyor…");
  const fd = new FormData(e.target);
  try {
    const scenario = await api("/scenarios/professionalize", {
      method: "POST",
      body: {
        language: fd.get("language"),
        title: fd.get("title") || null,
        duration_seconds: Number(fd.get("duration_seconds")),
        style: fd.get("style"),
        audience: fd.get("audience") || null,
        raw_input: fd.get("raw_input"),
      },
    });
    renderScenario(scenario);
    await refreshMe();
    await loadHistory();
  } catch (err) {
    setError($("#scenarioError"), err.message);
  } finally {
    btn.disabled = false;
    btn.textContent = `AI1: Viral Senaryo Yaz (${state.scenarioCost} kredi)`;
    setWorking(false);
  }
});

$("#unlockCopyBtn").addEventListener("click", () => {
  unlockAndCopyFlow();
});

$("#copyScenarioBtn").addEventListener("click", () => {
  copyScenarioText();
});

$("#discussBtn").addEventListener("click", async () => {
  setError($("#discussError"), "");
  if (!state.scenarioId) {
    setError($("#discussError"), "Önce senaryo üretin");
    return;
  }
  const message = ($("#discussInput").value || "").trim();
  if (message.length < 2) {
    setError($("#discussError"), "Kısa bir not yaz");
    return;
  }
  const btn = $("#discussBtn");
  btn.disabled = true;
  btn.textContent = "Uygulanıyor…";
  setWorking(true, "Yönetmen senaryoyu güncelliyor…");
  try {
    const scenario = await api(`/scenarios/${state.scenarioId}/discuss`, {
      method: "POST",
      body: { message },
    });
    $("#discussInput").value = "";
    renderScenario(scenario);
    await refreshMe();
  } catch (err) {
    setError($("#discussError"), err.message);
  } finally {
    btn.disabled = false;
    btn.textContent = `Gönder & uygula (${state.discussCost} kredi)`;
    setWorking(false);
  }
});

$("#produceBtn").addEventListener("click", async () => {
  setError($("#produceError"), "");
  if (!state.scenarioId) {
    setError($("#produceError"), "Önce senaryo üretin");
    return;
  }
  const btn = $("#produceBtn");
  btn.disabled = true;
  btn.textContent = "Kuyruğa alındı…";
  setWorking(true, "AI2+AI3 pipeline başlıyor…");
  try {
    const queued = await api("/jobs/produce", {
      method: "POST",
      body: { scenario_id: state.scenarioId },
    });
    renderJob(queued, { soft: true });
    $("#playerSection").scrollIntoView({ behavior: "smooth", block: "start" });
    const job = await pollJob(queued.id, { label: "AI2 görsel + AI3 kurgu" });
    renderJob(job);
    await refreshMe();
  } catch (err) {
    setError($("#produceError"), err.message);
  } finally {
    btn.disabled = false;
    btn.textContent = `AI2+AI3: Görsel Üret & Kurguya Ver (${state.produceCost} kredi)`;
    setWorking(false);
  }
});

$("#refineBtn").addEventListener("click", async () => {
  setError($("#refineError"), "");
  if (!state.jobId) {
    setError($("#refineError"), "Önce video üretin");
    return;
  }
  const instruction = ($("#refineInput").value || "").trim();
  if (instruction.length < 3) {
    setError($("#refineError"), "En az 3 karakter yazın");
    return;
  }
  const btn = $("#refineBtn");
  btn.disabled = true;
  btn.textContent = "Revize ediliyor…";
  setWorking(true, "Revizyon uygulanıyor…");
  try {
    const job = await api(`/jobs/${state.jobId}/refine`, {
      method: "POST",
      body: { instruction },
    });
    $("#refineInput").value = "";
    renderJob(job);
    await refreshMe();
  } catch (err) {
    setError($("#refineError"), err.message);
  } finally {
    btn.disabled = false;
    btn.textContent = `Revize et (${state.refineCost} kredi)`;
    setWorking(false);
  }
});

const durationInput = $("#scenarioForm")?.querySelector('[name="duration_seconds"]');
if (durationInput) {
  durationInput.addEventListener("change", () => {
    const dur = Number(durationInput.value || 30);
    state.produceCost = produceCostForDuration(dur);
    updateCostLabels();
  });
}

boot();
