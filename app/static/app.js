const storageKeys = {
  viewMode: "ai-balance-monitor:view-mode",
  sortKey: "ai-balance-monitor:sort-key",
  sortDir: "ai-balance-monitor:sort-dir",
  customOrder: "ai-balance-monitor:custom-order",
};

function readCustomOrder() {
  try {
    const value = JSON.parse(localStorage.getItem(storageKeys.customOrder) || "[]");
    return Array.isArray(value) ? value.map(Number).filter(Number.isFinite) : [];
  } catch {
    return [];
  }
}

const state = {
  sites: [],
  editingSite: null,
  toastTimer: null,
  viewMode: ["list", "card", "compact-card"].includes(localStorage.getItem(storageKeys.viewMode))
    ? localStorage.getItem(storageKeys.viewMode)
    : "list",
  sortKey: localStorage.getItem(storageKeys.sortKey) || "custom",
  sortDir: localStorage.getItem(storageKeys.sortDir) || "asc",
  customOrder: readCustomOrder(),
};

const $ = (selector) => document.querySelector(selector);

function bindLiquidGlass() {
  const surfaces = document.querySelectorAll(".overview-panel, .monitor-panel, .metric, .site-card, .table-wrap, dialog");
  surfaces.forEach((surface) => {
    if (surface.dataset.glassBound) return;
    surface.dataset.glassBound = "true";
    surface.addEventListener("pointermove", (event) => {
      const rect = surface.getBoundingClientRect();
      surface.style.setProperty("--pointer-x", `${event.clientX - rect.left}px`);
      surface.style.setProperty("--pointer-y", `${event.clientY - rect.top}px`);
    });
  });
}

function api(path, options = {}) {
  return fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  }).then(async (response) => {
    if (response.ok) return response.status === 204 ? null : response.json();
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `请求失败 (${response.status})`);
  });
}

function toast(message, isError = false) {
  const element = $("#toast");
  clearTimeout(state.toastTimer);
  element.textContent = message;
  element.className = `toast show${isError ? " error" : ""}`;
  state.toastTimer = setTimeout(() => { element.className = "toast"; }, 3500);
}

function formatBalance(value, currency) {
  if (value === null || value === undefined) return "-";
  return `${Number(value).toLocaleString(undefined, { maximumFractionDigits: 4 })} ${currency}`;
}

function formatDate(value) {
  return value ? new Date(`${value}Z`).toLocaleString() : "从未";
}

function statusBadge(site) {
  if (!site.enabled) return '<span class="badge off">已停用</span>';
  if (site.last_status === "error") return '<span class="badge error">检查失败</span>';
  if (site.low_balance_threshold > 0 && site.last_balance !== null && site.last_balance <= site.low_balance_threshold) {
    return '<span class="badge warn">低余额</span>';
  }
  if (site.last_status === "ok") return '<span class="badge ok">正常</span>';
  return '<span class="badge">等待检查</span>';
}

function siteTone(site) {
  if (!site.enabled) return "off";
  if (site.last_status === "error") return "error";
  if (site.low_balance_threshold > 0 && site.last_balance !== null && site.last_balance <= site.low_balance_threshold) return "warn";
  if (site.last_status === "ok") return "ok";
  return "pending";
}

function siteStatusRank(site) {
  if (!site.enabled) return 4;
  if (site.last_status === "error") return 0;
  if (site.low_balance_threshold > 0 && site.last_balance !== null && site.last_balance <= site.low_balance_threshold) return 1;
  if (site.last_status === "ok") return 2;
  return 3;
}

function normalizeOrder() {
  const knownIds = new Set(state.sites.map((site) => site.id));
  state.customOrder = state.customOrder.filter((id) => knownIds.has(id));
  for (const site of state.sites) {
    if (!state.customOrder.includes(site.id)) state.customOrder.push(site.id);
  }
  localStorage.setItem(storageKeys.customOrder, JSON.stringify(state.customOrder));
}

function compareValue(left, right) {
  if (typeof left === "number" && typeof right === "number") return left - right;
  return String(left ?? "").localeCompare(String(right ?? ""), "zh-CN", { numeric: true, sensitivity: "base" });
}

function getSortValue(site) {
  if (state.sortKey === "name") return site.name;
  if (state.sortKey === "type") return site.site_type;
  if (state.sortKey === "balance") return site.last_balance ?? Number.NEGATIVE_INFINITY;
  if (state.sortKey === "status") return siteStatusRank(site);
  if (state.sortKey === "checked") return site.last_checked_at ? Date.parse(`${site.last_checked_at}Z`) : 0;
  if (state.sortKey === "created") return site.created_at ? Date.parse(`${site.created_at}Z`) : 0;
  return state.customOrder.indexOf(site.id);
}

function sortedSites() {
  normalizeOrder();
  return [...state.sites].sort((a, b) => {
    const result = compareValue(getSortValue(a), getSortValue(b));
    if (state.sortKey === "custom") return result;
    if (result !== 0) return state.sortDir === "desc" ? -result : result;
    return compareValue(a.name, b.name);
  });
}

function actionButtons(site) {
  const reorderButtons = state.sortKey === "custom" ? `
    <button class="icon-button" title="上移" aria-label="上移" data-action="move-up" data-id="${site.id}">&#8593;</button>
    <button class="icon-button" title="下移" aria-label="下移" data-action="move-down" data-id="${site.id}">&#8595;</button>` : "";
  return `
    <div class="row-actions">
      ${reorderButtons}
      <button class="icon-button" title="打开中转站" aria-label="打开中转站" data-action="open" data-id="${site.id}">&#8599;</button>
      <button class="icon-button" title="立即检查" aria-label="立即检查" data-action="check" data-id="${site.id}">&#8635;</button>
      <button class="icon-button" title="检查记录" aria-label="检查记录" data-action="logs" data-id="${site.id}">&#8801;</button>
      <button class="icon-button" title="编辑站点" aria-label="编辑站点" data-action="edit" data-id="${site.id}">&#9998;</button>
      <button class="icon-button danger-button" title="删除站点" aria-label="删除站点" data-action="delete" data-id="${site.id}">&#215;</button>
    </div>`;
}

function renderCards(sites) {
  const compact = state.viewMode === "compact-card";
  $("#siteCards").classList.toggle("compact", compact);
  $("#siteCards").innerHTML = sites.map((site) => compact ? `
    <article class="site-card compact tone-${siteTone(site)}">
      <div class="site-card-header">
        <div>
          <div class="site-name">${escapeHtml(site.name)}</div>
          <div class="balance">${formatBalance(site.last_balance, site.currency)}</div>
        </div>
        ${statusBadge(site)}
      </div>
      ${site.last_error ? `<div class="card-error" title="${escapeHtml(site.last_error)}">${escapeHtml(site.last_error)}</div>` : ""}
      ${actionButtons(site)}
    </article>` : `
    <article class="site-card tone-${siteTone(site)}">
      <div class="site-card-header">
        <div>
          <div class="site-name">${escapeHtml(site.name)}</div>
          <div class="site-url" title="${escapeHtml(site.base_url)}">${escapeHtml(site.base_url)}</div>
        </div>
        ${statusBadge(site)}
      </div>
      <div class="card-balance-row">
        <div>
          <span>当前余额</span>
          <strong>${formatBalance(site.last_balance, site.currency)}</strong>
        </div>
        <span class="type-chip">${site.site_type === "newapi" ? "NewAPI" : "Sub2API"}</span>
      </div>
      <div class="card-meta">
        <div><span>最后检查</span><strong>${formatDate(site.last_checked_at)}</strong></div>
        <div><span>周期</span><strong>${site.check_interval_seconds || 300}s</strong></div>
      </div>
      ${site.last_error ? `<div class="card-error" title="${escapeHtml(site.last_error)}">${escapeHtml(site.last_error)}</div>` : ""}
      ${actionButtons(site)}
    </article>`).join("");
}

function renderSites() {
  const rows = $("#siteRows");
  const sites = sortedSites();
  rows.innerHTML = sites.map((site) => `
    <tr class="tone-${siteTone(site)}">
      <td>
        <div class="site-name">${escapeHtml(site.name)}</div>
        <div class="site-url">${escapeHtml(site.base_url)}</div>
      </td>
      <td>${site.site_type === "newapi" ? "NewAPI" : "Sub2API"}</td>
      <td>
        <div class="balance">${formatBalance(site.last_balance, site.currency)}</div>
      </td>
      <td>${statusBadge(site)}${site.last_error ? `<div class="site-url" title="${escapeHtml(site.last_error)}">${escapeHtml(site.last_error)}</div>` : ""}</td>
      <td>${formatDate(site.last_checked_at)}</td>
      <td>
        ${actionButtons(site)}
      </td>
    </tr>`).join("");
  renderCards(sites);
  bindLiquidGlass();
  $("#emptyState").hidden = state.sites.length !== 0;
  $("#siteTableWrap").hidden = state.sites.length === 0 || state.viewMode !== "list";
  $("#siteCards").hidden = state.sites.length === 0 || !["card", "compact-card"].includes(state.viewMode);
  $("#listModeButton").classList.toggle("active", state.viewMode === "list");
  $("#cardModeButton").classList.toggle("active", state.viewMode === "card");
  $("#compactCardModeButton").classList.toggle("active", state.viewMode === "compact-card");
  $("#sortKey").value = state.sortKey;
  $("#sortDirectionButton").textContent = state.sortDir === "asc" ? "↓" : "↑";
  $("#sortDirectionButton").title = state.sortDir === "asc" ? "当前升序，点击切换为降序" : "当前降序，点击切换为升序";
  $("#lastRefresh").textContent = `刷新于 ${new Date().toLocaleTimeString()}`;
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
  }[char]));
}

async function refresh() {
  try {
    const [summary, sites] = await Promise.all([api("/api/summary"), api("/api/sites")]);
    state.sites = sites;
    $("#totalSites").textContent = summary.total_sites;
    $("#enabledSites").textContent = summary.enabled_sites;
    $("#healthySites").textContent = summary.healthy_sites;
    $("#alertingSites").textContent = summary.alerting_sites;
    $("#errorSites").textContent = summary.error_sites;
    renderSites();
  } catch (error) {
    toast(error.message, true);
  }
}

function defaultForType(type) {
  if (type === "newapi") {
    return { endpoint: "/api/user/self", header: "Authorization", prefix: "Bearer", divisor: "500000" };
  }
  return { endpoint: "/v1/usage", header: "Authorization", prefix: "Bearer", divisor: "1" };
}

function openSiteDialog(site = null) {
  state.editingSite = site;
  const isEdit = Boolean(site);
  $("#siteDialogTitle").textContent = isEdit ? "编辑站点" : "添加站点";
  $("#siteId").value = site?.id || "";
  $("#name").value = site?.name || "";
  $("#siteType").value = site?.site_type || "newapi";
  $("#baseUrl").value = site?.base_url || "";
  $("#apiToken").value = "";
  $("#apiToken").placeholder = isEdit ? "留空可保留现有令牌" : "Bearer Token 或 API Key";
  $("#apiToken").required = !isEdit;
  $("#authMode").value = site?.auth_mode || "bearer";
  $("#authHeaderName").value = site?.auth_header_name || "";
  $("#authPrefix").value = site?.auth_prefix || "";
  $("#extraHeaders").value = site?.extra_headers || "";
  $("#endpointPath").value = site?.endpoint_path || defaultForType($("#siteType").value).endpoint;
  $("#balancePath").value = site?.balance_path || "";
  $("#quotaDivisor").value = site?.quota_divisor || defaultForType($("#siteType").value).divisor;
  $("#currency").value = site?.currency || "USD";
  $("#threshold").value = site?.low_balance_threshold ?? 0;
  $("#checkInterval").value = site?.check_interval_seconds || "";
  $("#enabled").checked = site?.enabled ?? true;
  $("#siteDialog").showModal();
}

function collectSiteForm() {
  const optionalNumber = (selector) => {
    const value = $(selector).value.trim();
    return value ? Number(value) : null;
  };
  const authPrefix = $("#authPrefix").value.trim();
  return {
    name: $("#name").value.trim(),
    site_type: $("#siteType").value,
    base_url: $("#baseUrl").value.trim(),
    api_token: $("#apiToken").value,
    endpoint_path: $("#endpointPath").value.trim() || null,
    auth_mode: $("#authMode").value,
    auth_header_name: $("#authHeaderName").value.trim() || null,
    auth_prefix: authPrefix || null,
    extra_headers: $("#extraHeaders").value.trim(),
    balance_path: $("#balancePath").value.trim(),
    quota_divisor: optionalNumber("#quotaDivisor"),
    currency: $("#currency").value.trim() || "USD",
    low_balance_threshold: Number($("#threshold").value || 0),
    check_interval_seconds: optionalNumber("#checkInterval"),
    enabled: $("#enabled").checked,
  };
}

async function saveSite(event) {
  event.preventDefault();
  const payload = collectSiteForm();
  const id = $("#siteId").value;
  if (id && !confirm(`确定保存“${payload.name || "该站点"}”的修改吗？`)) return;
  try {
    await api(id ? `/api/sites/${id}` : "/api/sites", {
      method: id ? "PUT" : "POST",
      body: JSON.stringify(payload),
    });
    $("#siteDialog").close();
    toast("站点已保存");
    await refresh();
  } catch (error) {
    toast(error.message, true);
  }
}

async function showLogs(site) {
  try {
    const logs = await api(`/api/sites/${site.id}/logs`);
    $("#logsTitle").textContent = `${site.name} 的检查记录`;
    $("#logsContent").innerHTML = logs.length ? logs.map((log) => `
      <article class="log-entry">
        <div class="log-meta"><span>${formatDate(log.checked_at)}</span><span>${log.status === "ok" ? "成功" : "失败"}</span></div>
        <div class="log-message">${log.status === "ok" ? `余额：${formatBalance(log.balance, site.currency)}` : escapeHtml(log.message || "未知错误")}</div>
      </article>`).join("") : '<div class="log-entry">暂无检查记录。</div>';
    $("#logsDialog").showModal();
  } catch (error) {
    toast(error.message, true);
  }
}

function moveSite(siteId, direction) {
  if (state.sortKey !== "custom") {
    state.sortKey = "custom";
    state.customOrder = sortedSites().map((site) => site.id);
  }
  normalizeOrder();
  const index = state.customOrder.indexOf(siteId);
  const target = index + direction;
  if (index < 0 || target < 0 || target >= state.customOrder.length) return;
  [state.customOrder[index], state.customOrder[target]] = [state.customOrder[target], state.customOrder[index]];
  localStorage.setItem(storageKeys.customOrder, JSON.stringify(state.customOrder));
  localStorage.setItem(storageKeys.sortKey, state.sortKey);
  renderSites();
}

async function handleSiteAction(event) {
  const button = event.target.closest("button[data-action]");
  if (!button) return;
  const site = state.sites.find((item) => item.id === Number(button.dataset.id));
  if (!site) return;
  try {
    if (button.dataset.action === "open") {
      window.open(site.base_url, "_blank", "noopener,noreferrer");
      return;
    }
    if (button.dataset.action === "move-up") return moveSite(site.id, -1);
    if (button.dataset.action === "move-down") return moveSite(site.id, 1);
    if (button.dataset.action === "edit") return openSiteDialog(site);
    if (button.dataset.action === "logs") return showLogs(site);
    if (button.dataset.action === "delete") {
      if (!confirm(`确定删除“${site.name}”吗？其检查记录也会一并删除。`)) return;
      await api(`/api/sites/${site.id}`, { method: "DELETE" });
      toast("站点已删除");
      return refresh();
    }
    if (button.dataset.action === "check") {
      button.disabled = true;
      const result = await api(`/api/sites/${site.id}/check`, { method: "POST" });
      toast(result.status === "ok" ? `检查成功：${formatBalance(result.balance, result.currency)}` : `检查失败：${result.error}`, result.status !== "ok");
      return refresh();
    }
  } catch (error) {
    toast(error.message, true);
  } finally {
    button.disabled = false;
  }
}

async function openTelegramDialog() {
  try {
    const config = await api("/api/telegram");
    $("#telegramEnabled").checked = config.enabled;
    $("#telegramBotToken").value = "";
    $("#telegramBotToken").placeholder = config.bot_token_masked || "输入 Bot Token";
    $("#telegramChatId").value = config.chat_id || "";
    $("#telegramDialog").showModal();
  } catch (error) {
    toast(error.message, true);
  }
}

async function saveTelegram(event) {
  event.preventDefault();
  try {
    await api("/api/telegram", {
      method: "PUT",
      body: JSON.stringify({
        enabled: $("#telegramEnabled").checked,
        bot_token: $("#telegramBotToken").value.trim(),
        chat_id: $("#telegramChatId").value.trim(),
      }),
    });
    $("#telegramDialog").close();
    toast("Telegram 设置已保存");
  } catch (error) {
    toast(error.message, true);
  }
}

async function testTelegram() {
  try {
    await api("/api/telegram/test", { method: "POST" });
    toast("测试消息已发送");
  } catch (error) {
    toast(error.message, true);
  }
}

$("#addSiteButton").addEventListener("click", () => openSiteDialog());
$("#emptyAddButton").addEventListener("click", () => openSiteDialog());
$("#checkAllButton").addEventListener("click", async () => {
  try {
    $("#checkAllButton").disabled = true;
    const result = await api("/api/check-all", { method: "POST" });
    toast(`已检查 ${result.checked} 个到期站点`);
    await refresh();
  } catch (error) {
    toast(error.message, true);
  } finally {
    $("#checkAllButton").disabled = false;
  }
});
$("#telegramButton").addEventListener("click", openTelegramDialog);
$("#siteForm").addEventListener("submit", saveSite);
$("#telegramForm").addEventListener("submit", saveTelegram);
$("#telegramTestButton").addEventListener("click", testTelegram);
$("#siteRows").addEventListener("click", handleSiteAction);
$("#siteCards").addEventListener("click", handleSiteAction);
document.querySelectorAll("[data-view-mode]").forEach((button) => {
  button.addEventListener("click", () => {
    state.viewMode = button.dataset.viewMode;
    localStorage.setItem(storageKeys.viewMode, state.viewMode);
    renderSites();
  });
});
$("#sortKey").addEventListener("change", () => {
  state.sortKey = $("#sortKey").value;
  localStorage.setItem(storageKeys.sortKey, state.sortKey);
  renderSites();
});
$("#sortDirectionButton").addEventListener("click", () => {
  state.sortDir = state.sortDir === "asc" ? "desc" : "asc";
  localStorage.setItem(storageKeys.sortDir, state.sortDir);
  renderSites();
});
document.querySelectorAll("[data-close]").forEach((button) => {
  button.addEventListener("click", () => $(`#${button.dataset.close}`).close());
});
$("#siteType").addEventListener("change", () => {
  if (!state.editingSite) {
    const defaults = defaultForType($("#siteType").value);
    $("#endpointPath").value = defaults.endpoint;
    $("#authHeaderName").value = defaults.header;
    $("#authPrefix").value = defaults.prefix;
    $("#quotaDivisor").value = defaults.divisor;
  }
});
$("#authMode").addEventListener("change", () => {
  if (state.editingSite) return;
  const isApiKey = $("#authMode").value === "api_key";
  $("#authHeaderName").value = isApiKey ? "x-api-key" : "Authorization";
  $("#authPrefix").value = isApiKey ? "" : "Bearer";
});

refresh();
bindLiquidGlass();
setInterval(refresh, 30000);
