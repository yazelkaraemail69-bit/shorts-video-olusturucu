const API = "/api";
const TOKEN_KEY = "vam_token";

const $ = (sel, root = document) => root.querySelector(sel);

const state = {
  token: localStorage.getItem(TOKEN_KEY) || "",
  user: null,
  scenarioId: null,
  jobId: null,
  copyUnlocked: false,
  copyUnlockCost: 1,
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

async function boot() {
  if (!state.token) {
    showAuth();
    return;
  }
  try {
    await refreshMe();
    showStudio();
  } catch {
    state.token = "";
    localStorage.removeItem(TOKEN_KEY);
    showAuth();
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
  state.copyUnlockCost = scenario.copy_unlock_cost || 1;

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

function renderJob(job) {
  state.jobId = job.id;
  $("#playerSection").hidden = false;
  $("#jobMeta").textContent = `İş #${job.id} · rev ${job.revision} · ${job.status}`;
  $("#jobBadge").hidden = !job.is_mock;

  const video = $("#videoPlayer");
  const frame = $("#previewFrame");
  const audio = $("#audioPlayer");
  const dl = $("#downloadVideo");
  const bust = Date.now();

  if (job.video_url && String(job.video_url).endsWith(".mp4")) {
    video.hidden = false;
    frame.hidden = true;
    video.src = `${job.video_url}?t=${bust}`;
    video.load();
    if (dl) {
      dl.hidden = false;
      dl.href = job.video_url;
    }
  } else if (job.preview_url) {
    video.hidden = true;
    frame.hidden = false;
    frame.src = `${job.preview_url}?t=${bust}`;
    if (dl) dl.hidden = true;
  }

  if (job.audio_url) {
    audio.src = `${job.audio_url}?t=${bust}`;
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
          `<img src="${escapeHtml(s.url)}?t=${bust}" alt="Sahne ${s.index}" title="Sahne ${s.index}" />`
      )
      .join("");
  }

  // Senaryo panelini güncel snapshot ile yenile
  if (job.script_snapshot) {
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
  } catch (err) {
    setError($("#scenarioError"), err.message);
  } finally {
    btn.disabled = false;
    btn.textContent = "AI1: Viral Senaryo Yaz";
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
    btn.textContent = "Gönder & uygula";
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
    btn.textContent = "AI2+AI3 çalışıyor…";
  try {
    const job = await api("/jobs/produce", {
      method: "POST",
      body: { scenario_id: state.scenarioId },
    });
    renderJob(job);
    await refreshMe();
    $("#playerSection").scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (err) {
    setError($("#produceError"), err.message);
  } finally {
    btn.disabled = false;
    btn.textContent = "AI2+AI3: Görsel Üret & Kurguya Ver";
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
    btn.textContent = "Revize et";
  }
});

boot();
