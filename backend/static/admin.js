const API = "/api";
const TOKEN_KEY = "vam_token";

const $ = (sel) => document.querySelector(sel);
const token = localStorage.getItem(TOKEN_KEY) || "";

async function api(path, { method = "GET", body } = {}) {
  const headers = { "Content-Type": "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(`${API}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });
  const text = await res.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = { detail: text };
  }
  if (!res.ok) {
    const detail = data?.detail;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail || data));
  }
  return data;
}

function setError(msg) {
  const el = $("#adminError");
  if (!msg) {
    el.hidden = true;
    el.textContent = "";
    return;
  }
  el.hidden = false;
  el.textContent = msg;
}

function creditLabel(u) {
  return u.unlimited_credits ? "∞" : String(u.credits);
}

function renderUsers(users) {
  const tbody = $("#userRows");
  tbody.innerHTML = users
    .map((u) => {
      const status = u.is_active
        ? `<span class="pill pill-on">aktif</span>`
        : `<span class="pill pill-off">pasif</span>`;
      const adminTag = u.is_admin ? `<span class="pill pill-admin">admin</span>` : "";
      const toggleLabel = u.is_active ? "Pasifleştir" : "Aktifleştir";
      return `<tr>
        <td>${u.id}</td>
        <td>${escapeHtml(u.email)}${adminTag}<br/><span style="color:var(--muted);font-size:.8rem">${escapeHtml(u.display_name || "")}</span></td>
        <td><strong>${creditLabel(u)}</strong></td>
        <td>${status}</td>
        <td>
          <div class="admin-actions">
            <input type="number" id="amt-${u.id}" placeholder="+/-" />
            <button type="button" class="ghost-btn" data-grant="${u.id}">Kredi</button>
            <button type="button" class="ghost-btn" data-toggle="${u.id}" data-active="${u.is_active}">${toggleLabel}</button>
          </div>
        </td>
      </tr>`;
    })
    .join("");

  tbody.querySelectorAll("[data-grant]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const id = btn.getAttribute("data-grant");
      const input = $(`#amt-${id}`);
      const amount = Number(input.value);
      if (!amount) {
        setError("Kredi miktarı girin");
        return;
      }
      setError("");
      try {
        await api(`/admin/users/${id}/credits`, {
          method: "POST",
          body: { amount, reason: "Admin panelinden ayar" },
        });
        input.value = "";
        await load();
      } catch (err) {
        setError(err.message);
      }
    });
  });

  tbody.querySelectorAll("[data-toggle]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const id = btn.getAttribute("data-toggle");
      const active = btn.getAttribute("data-active") === "true";
      setError("");
      try {
        await api(`/admin/users/${id}`, {
          method: "PATCH",
          body: { is_active: !active },
        });
        await load();
      } catch (err) {
        setError(err.message);
      }
    });
  });
}

function escapeHtml(str) {
  return String(str)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

async function load() {
  const stats = await api("/admin/stats");
  $("#statUsers").textContent = stats.users;
  $("#statActive").textContent = stats.active_users;
  $("#statScenarios").textContent = stats.scenarios;
  $("#statJobs").textContent = stats.jobs;
  const users = await api("/admin/users");
  renderUsers(users);
}

$("#logoutBtn").addEventListener("click", () => {
  localStorage.removeItem(TOKEN_KEY);
  location.href = "/";
});

$("#refreshBtn").addEventListener("click", () => {
  load().catch((err) => setError(err.message));
});

async function boot() {
  if (!token) {
    $("#gate").hidden = false;
    $("#gateMsg").textContent = "Önce stüdyodan admin hesabıyla giriş yapın.";
    return;
  }
  try {
    const me = await api("/auth/me");
    if (!me.is_admin) {
      $("#gate").hidden = false;
      $("#gateMsg").textContent = "Bu panel yalnızca admin hesabına açık.";
      return;
    }
    $("#adminApp").hidden = false;
    await load();
  } catch (err) {
    $("#gate").hidden = false;
    $("#gateMsg").textContent = err.message || "Oturum geçersiz.";
  }
}

boot();
