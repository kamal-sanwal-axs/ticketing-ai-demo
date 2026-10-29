const STORAGE_TOKEN = "apex_ai_token";
const STORAGE_REGION = "apex_ai_region";
const STORAGE_PROFILE = "apex_ai_profile";
const STORAGE_SESSION_ID = "apex_ai_session_id";
const STORAGE_PENDING_CHAT = "apex_ai_pending_confirm";
const STORAGE_LAST_QUERY = "apex_ai_last_query";
const STORAGE_PENDING_RERUN = "apex_ai_pending_rerun";

const $ = (id) => document.getElementById(id);

function getToken() {
  return sessionStorage.getItem(STORAGE_TOKEN) || "";
}

function setSession(token, region, profile) {
  sessionStorage.setItem(STORAGE_TOKEN, token);
  sessionStorage.setItem(STORAGE_REGION, region);
  sessionStorage.setItem(STORAGE_PROFILE, JSON.stringify(profile));
}

function clearAuthSession() {
  sessionStorage.removeItem(STORAGE_TOKEN);
  sessionStorage.removeItem(STORAGE_REGION);
  sessionStorage.removeItem(STORAGE_PROFILE);
  sessionStorage.removeItem(STORAGE_SESSION_ID);
}

function clearSession() {
  clearAuthSession();
  sessionStorage.removeItem(STORAGE_PENDING_CHAT);
  sessionStorage.removeItem(STORAGE_LAST_QUERY);
  sessionStorage.removeItem(STORAGE_PENDING_RERUN);
}

function saveLastQuery(message, region) {
  if (!message?.trim()) return;
  sessionStorage.setItem(
    STORAGE_LAST_QUERY,
    JSON.stringify({ message: message.trim(), region: region || "US-West" }),
  );
}

function readPendingRerun() {
  try {
    return JSON.parse(sessionStorage.getItem(STORAGE_PENDING_RERUN) || "null");
  } catch {
    return null;
  }
}

function setPendingRerunFromLast(message, region) {
  const payload =
    message != null && String(message).trim()
      ? { message: String(message).trim(), region: region || "US-West" }
      : (() => {
          try {
            return JSON.parse(sessionStorage.getItem(STORAGE_LAST_QUERY) || "null");
          } catch {
            return null;
          }
        })();
  if (payload?.message) {
    sessionStorage.setItem(STORAGE_PENDING_RERUN, JSON.stringify(payload));
  }
}

function clearPendingRerun() {
  sessionStorage.removeItem(STORAGE_PENDING_RERUN);
}

function renderLoginRerunPrompt() {
  let box = document.getElementById("login-rerun-prompt");
  if (!box) {
    box = el("div", "login-rerun-prompt");
    box.id = "login-rerun-prompt";
    const errEl = $("login-error");
    if (errEl?.parentNode) {
      errEl.parentNode.insertBefore(box, errEl);
    }
  }
  const pending = readPendingRerun();
  if (!pending?.message) {
    box.hidden = true;
    box.innerHTML = "";
    return;
  }
  box.hidden = false;
  box.innerHTML = "";
  box.appendChild(el("p", "login-rerun-title", "Your last question"));
  box.appendChild(el("blockquote", "login-rerun-quote", pending.message));
  const label = el("label", "login-rerun-consent");
  const cb = document.createElement("input");
  cb.type = "checkbox";
  cb.id = "login-rerun-consent";
  cb.checked = true;
  label.appendChild(cb);
  label.appendChild(document.createTextNode(" Re-run this after I sign in"));
  box.appendChild(label);
}

function getOrCreateSessionId() {
  let id = sessionStorage.getItem(STORAGE_SESSION_ID);
  if (!id) {
    id = crypto.randomUUID();
    sessionStorage.setItem(STORAGE_SESSION_ID, id);
  }
  return id;
}

function startNewChat() {
  sessionStorage.setItem(STORAGE_SESSION_ID, crypto.randomUUID());
  sessionStorage.removeItem(STORAGE_PENDING_CHAT);
  const log = $("chat-log");
  if (log) log.innerHTML = "";
  updateConfirmStrip(null);
}

function ensureSessionIdFromServer(serverId) {
  if (serverId) sessionStorage.setItem(STORAGE_SESSION_ID, serverId);
}

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = text;
  return node;
}

function cellText(row, col) {
  const v = row[col.key];
  return String(v === undefined || v === null || v === "" ? "—" : v);
}

function appendColorCell(td, hexValue) {
  const text = String(hexValue === undefined || hexValue === null || hexValue === "" ? "—" : hexValue);
  const wrap = el("span", "color-cell");
  if (text !== "—" && /^#?[0-9a-f]{3,8}$/i.test(text.trim())) {
    const swatch = el("span", "color-swatch");
    const color = text.startsWith("#") ? text : `#${text}`;
    swatch.style.backgroundColor = color;
    swatch.title = color;
    wrap.appendChild(swatch);
  }
  wrap.appendChild(document.createTextNode(text));
  td.appendChild(wrap);
}

function mountInteractiveTable(parent, { columns, rows, totalCount, tableClass = "data-table" }) {
  const allRows = Array.isArray(rows) ? rows : [];
  const total = totalCount ?? allRows.length;

  const toolbar = el("div", "table-toolbar");
  const globalSearch = el("input", "table-search-global");
  globalSearch.type = "search";
  globalSearch.placeholder = "Search all columns…";
  globalSearch.setAttribute("aria-label", "Search all columns");
  toolbar.appendChild(globalSearch);

  const countEl = el("span", "table-row-count muted", "");
  toolbar.appendChild(countEl);
  parent.appendChild(toolbar);

  const wrap = el("div", "table-wrap table-wrap-scroll");
  const table = el("table", tableClass);
  table.setAttribute("role", "table");

  const thead = el("thead");
  const headerRow = el("tr");
  columns.forEach((col) => {
    const th = el("th", null, col.label);
    th.setAttribute("data-col", col.key);
    headerRow.appendChild(th);
  });
  thead.appendChild(headerRow);

  const filterRow = el("tr", "table-filter-row");
  const columnInputs = [];
  columns.forEach((col) => {
    const th = el("th");
    const input = el("input", "table-col-filter");
    input.type = "search";
    input.placeholder = `Filter ${col.label}`;
    input.setAttribute("aria-label", `Filter ${col.label}`);
    input.dataset.colKey = col.key;
    columnInputs.push(input);
    th.appendChild(input);
    filterRow.appendChild(th);
  });
  thead.appendChild(filterRow);
  table.appendChild(thead);

  const tbody = el("tbody");
  allRows.forEach((row) => {
    const tr = el("tr");
    columns.forEach((col) => {
      const td = el("td");
      if (col.cellType === "color" || col.key === "color") {
        appendColorCell(td, row[col.key]);
      } else {
        td.textContent = cellText(row, col);
      }
      td.setAttribute("data-col", col.key);
      if (col.key === "id" || col.key.endsWith("Id")) td.classList.add("cell-mono");
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });
  table.appendChild(tbody);
  wrap.appendChild(table);
  parent.appendChild(wrap);

  function rowMatches(tr) {
    const globalQ = globalSearch.value.trim().toLowerCase();
    if (globalQ) {
      const hay = Array.from(tr.querySelectorAll("td"))
        .map((td) => td.textContent.toLowerCase())
        .join(" ");
      if (!hay.includes(globalQ)) return false;
    }
    for (const input of columnInputs) {
      const q = input.value.trim().toLowerCase();
      if (!q) continue;
      const key = input.dataset.colKey;
      const td = tr.querySelector(`td[data-col="${key}"]`);
      const text = (td?.textContent || "").toLowerCase();
      if (!text.includes(q)) return false;
    }
    return true;
  }

  function applyFilters() {
    let visible = 0;
    tbody.querySelectorAll("tr").forEach((tr) => {
      const show = rowMatches(tr);
      tr.hidden = !show;
      if (show) visible += 1;
    });
    countEl.textContent = `Showing ${visible} of ${total} row(s)`;
  }

  globalSearch.addEventListener("input", applyFilters);
  columnInputs.forEach((input) => input.addEventListener("input", applyFilters));
  applyFilters();
}

function renderDisplay(display) {
  const root = el("div", "display");

  const head = el("div", "display-head");
  if (display.badge) head.appendChild(el("span", "badge", display.badge));
  if (display.title) head.appendChild(el("h3", "display-title", display.title));
  if (display.subtitle) head.appendChild(el("p", "display-subtitle muted", display.subtitle));
  root.appendChild(head);

  if (display.level === "error") root.classList.add("display-error");
  if (display.level === "warning") root.classList.add("display-warning");

  const showTable =
    (display.type === "table" || display.type === "dashboard") &&
    display.rows &&
    display.columns?.length;
  if (showTable) {
    mountInteractiveTable(root, {
      columns: display.columns,
      rows: display.rows,
      totalCount: display.count ?? display.rows.length,
    });
  }

  if (display.charts?.length) {
    display.charts.forEach((chart) => {
      const wrap = el("div", "chart-block");
      if (chart.title) wrap.appendChild(el("h4", "display-section-title", chart.title));
      const max = Math.max(...(chart.values || [1]), 1);
      (chart.labels || []).forEach((label, idx) => {
        const row = el("div", "chart-bar-row");
        row.appendChild(el("span", "chart-label", label));
        const track = el("div", "chart-bar-track");
        const bar = el("div", "chart-bar-fill");
        const val = chart.values[idx] ?? 0;
        bar.style.width = `${Math.round((val / max) * 100)}%`;
        track.appendChild(bar);
        row.appendChild(track);
        row.appendChild(el("span", "chart-value", String(val)));
        wrap.appendChild(row);
      });
      root.appendChild(wrap);
    });
  }

  if (display.sections?.length) {
    display.sections.forEach((section) => {
      const block = el("section", "display-section");
      if (section.title) block.appendChild(el("h4", "display-section-title", section.title));
      if (section.paragraphs) {
        section.paragraphs.forEach((p) => {
          if (p) block.appendChild(el("p", "display-p", p));
        });
      }
      if (section.fields?.length) {
        const dl = el("dl", "field-list field-list-compact");
        section.fields.forEach((f) => {
          dl.appendChild(el("dt", null, f.label));
          dl.appendChild(el("dd", null, String(f.value ?? "—")));
        });
        block.appendChild(dl);
      }
      if (section.table?.columns?.length && section.table.rows) {
        mountInteractiveTable(block, {
          columns: section.table.columns,
          rows: section.table.rows,
          totalCount: section.table.rows.length,
          tableClass: "data-table data-table-compact",
        });
      }
      if (section.items?.length) {
        const ul = el("ul", "display-list");
        section.items.forEach((item) => ul.appendChild(el("li", null, item)));
        block.appendChild(ul);
      }
      if (section.links?.length) {
        const ul = el("ul", "display-links");
        section.links.forEach((link) => {
          const li = el("li");
          const a = el("a", "display-link");
          a.href = link.href;
          a.target = "_blank";
          a.rel = "noopener noreferrer";
          a.textContent = link.label;
          li.appendChild(a);
          if (link.note) {
            li.appendChild(el("span", "display-link-note muted", ` — ${link.note}`));
          }
          ul.appendChild(li);
        });
        block.appendChild(ul);
      }
      root.appendChild(block);
    });
  }

  if (display.fields?.length) {
    const dl = el("dl", "field-list");
    display.fields.forEach((f) => {
      dl.appendChild(el("dt", null, f.label));
      dl.appendChild(el("dd", null, String(f.value ?? "—")));
    });
    root.appendChild(dl);
  }

  if (display.paragraphs) {
    display.paragraphs.forEach((p) => {
      if (p) root.appendChild(el("p", "display-p", p));
    });
  }

  if (display.items?.length) {
    if (display.itemsTitle) root.appendChild(el("h4", "display-items-title", display.itemsTitle));
    const ul = el("ul", "display-list");
    display.items.forEach((item) => ul.appendChild(el("li", null, item)));
    root.appendChild(ul);
  }

  if (display.footnote) root.appendChild(el("p", "display-footnote muted", display.footnote));

  if (display.type === "sandbox" && display.sandbox_html) {
    const frame = el("iframe", "sandbox-iframe");
    frame.title = display.title || "Sandbox output";
    frame.setAttribute("sandbox", "allow-scripts");
    frame.srcdoc = display.sandbox_html;
    root.appendChild(frame);
  }

  if (display.citations?.length) {
    const block = el("div", "display-citations");
    block.appendChild(el("h4", "display-section-title", "Sources"));
    const ul = el("ul", "display-citations-list");
    display.citations.forEach((cite) => {
      const li = el("li", "display-citation-item");
      if (cite.href) {
        const a = el("a", null, cite.label || cite.href);
        a.href = cite.href;
        a.target = "_blank";
        a.rel = "noopener noreferrer";
        li.appendChild(a);
      } else {
        li.appendChild(document.createTextNode(cite.label || "—"));
      }
      if (cite.status) {
        li.appendChild(el("span", "muted", ` · ${cite.status}`));
      }
      ul.appendChild(li);
    });
    block.appendChild(ul);
    root.appendChild(block);
  }

  return root;
}

function mountConfirmBar(parent, mutationToken) {
  if (!mutationToken || !parent) return;
  const bar = el("div", "confirm-bar");
  const hint = el(
    "p",
    "confirm-hint muted",
    "Review the preview, then confirm to send this update/delete to apex-dev.",
  );
  bar.appendChild(hint);
  const btn = el("button", "btn-confirm-mutation", "Confirm update/delete");
  btn.type = "button";
  btn.dataset.mutationToken = mutationToken;
  bar.appendChild(btn);
  parent.appendChild(bar);
}

function ensureConfirmStrip() {
  let strip = document.getElementById("confirm-strip");
  if (strip) return strip;
  strip = el("div", "confirm-strip");
  strip.id = "confirm-strip";
  strip.hidden = true;
  const panel = document.querySelector(".chat-panel");
  const form = $("chat-form");
  if (panel && form) {
    panel.insertBefore(strip, form);
  }
  return strip;
}

function updateConfirmStrip(pending) {
  const strip = ensureConfirmStrip();
  strip.innerHTML = "";
  if (!pending?.mutation_token) {
    strip.hidden = true;
    return;
  }
  strip.hidden = false;
  strip.appendChild(
    el("p", "confirm-strip-title", "Pending change — review the message above, then confirm."),
  );
  mountConfirmBar(strip, pending.mutation_token);
}

async function loadRegions(selectEl) {
  const res = await fetch("/api/regions");
  const regions = await res.json();
  selectEl.innerHTML = regions
    .map((r) => `<option value="${r.id}">${r.label}</option>`)
    .join("");
}

function showLogin() {
  $("screen-login").hidden = false;
  $("screen-main").hidden = true;
  document.body.classList.remove("layout-chat");
}

function decodeJwtPayload(token) {
  try {
    const segment = token.split(".")[1];
    if (!segment) return null;
    const padded = segment.replace(/-/g, "+").replace(/_/g, "/");
    const json = atob(padded.padEnd(padded.length + ((4 - (padded.length % 4)) % 4), "="));
    return JSON.parse(json);
  } catch {
    return null;
  }
}

function isTokenExpired(token, skewSeconds = 30) {
  const payload = decodeJwtPayload(token);
  if (!payload?.exp) return false;
  return Date.now() / 1000 >= payload.exp - skewSeconds;
}

function redirectToLogin(message, options = {}) {
  const { rerunMessage, rerunRegion, clearChat = false } = options;
  setPendingRerunFromLast(rerunMessage, rerunRegion);
  clearAuthSession();
  if (clearChat) {
    $("chat-log").innerHTML = "";
    sessionStorage.removeItem(STORAGE_PENDING_CHAT);
    clearPendingRerun();
    sessionStorage.removeItem(STORAGE_LAST_QUERY);
  }
  $("token").value = "";
  showLogin();
  const errEl = $("login-error");
  errEl.textContent =
    message || "Your session expired. Sign in again with a fresh token from apex-dev.";
  errEl.hidden = false;
  renderLoginRerunPrompt();
}

function authErrorMessage(res, errBody) {
  const detail = errBody?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((d) => d.msg || JSON.stringify(d)).join("; ");
  return errBody?.message || res.statusText || "Unauthorized";
}

function renderStackDetails(stack, region) {
  const last = stack.last_llm_context;
  const rows = [
    ["Chat model", stack.chat_model || stack.chat_model_label || "—"],
    ["Embed", `${stack.embed_backend || "—"} · ${stack.embed_model || "—"}`],
    ["Rerank", stack.rerank_model || "—"],
    [
      "Context budget",
      `synthesis ${stack.context_budget_tokens?.toLocaleString() || "—"} tok · routing ${stack.context_routing_budget_tokens?.toLocaleString() || "—"} tok`,
    ],
  ];
  if (last) {
    const usedPct =
      last.percent_used ??
      (last.percent_left != null ? 100 - last.percent_left : null);
    rows.push([
      "Last LLM call",
      `~${last.estimated_tokens?.toLocaleString()} / ${last.budget_tokens?.toLocaleString()} tok (${usedPct != null ? `${usedPct}% used` : "—"}${last.routing ? ", routing" : ", synthesis"}${last.prompt_trimmed ? ", trimmed" : ""})`,
    ]);
  }
  rows.push([
    "Indexed sources",
    `${stack.tool_count || 0} tools · ${stack.kb_chunks || 0} KB · ${stack.openapi_sources || 0} OpenAPI${stack.kg_enabled ? " · Neo4j KG" : ""} · ${stack.vector_store || "—"}`,
  ]);
  rows.push(["Environment", `${stack.environment || "—"}${region ? ` · region ${region}` : ""}`]);
  const dl = el("dl");
  for (const [dt, dd] of rows) {
    const block = el("div");
    block.appendChild(el("dt", "", dt));
    block.appendChild(el("dd", "", dd));
    dl.appendChild(block);
  }
  return dl;
}

function applyStackStatus(stack, region) {
  if (!stack) return;
  const last = stack.last_llm_context;
  const ctxUsed =
    stack.context_percent_used ??
    last?.percent_used ??
    (last?.percent_left != null ? 100 - last.percent_left : null);
  const summary = stack.bar_label || [
    stack.chat_model_label || "LLM",
    ctxUsed != null ? `${ctxUsed}% ctx used` : "ctx —",
    `${stack.sources_count || 0} sources`,
    region || stack.environment || "",
  ].join(" · ");
  $("stack-context-summary").textContent = summary;
  const details = $("stack-context-details");
  details.innerHTML = "";
  details.appendChild(renderStackDetails(stack, region));
}

async function refreshStackBar(region) {
  const r = region || sessionStorage.getItem(STORAGE_REGION) || "US-West";
  try {
    const res = await fetch(`/api/ui/stack?region=${encodeURIComponent(r)}`);
    if (!res.ok) return;
    const stack = await res.json();
    applyStackStatus(stack, r);
  } catch {
    $("stack-context-summary").textContent = "Stack status unavailable";
  }
}

function showMain(profile, region) {
  $("screen-login").hidden = true;
  $("screen-main").hidden = false;
  document.body.classList.add("layout-chat");
  $("welcome-title").textContent = `Welcome, ${profile.name}`;
  $("welcome-sub").textContent = `Signed in to ${profile.tenant || "apex-dev"}.`;
  $("profile-email").textContent = profile.email || profile.userId || "";
  $("profile-region").textContent = `Region: ${region}`;
  $("region-main").value = region;
  refreshStackBar(region);
}

function appendUserMessage(text) {
  const div = el("div", "msg user");
  div.appendChild(el("span", "msg-label", "You"));
  div.appendChild(el("p", "msg-body", text));
  $("chat-log").appendChild(div);
  $("chat-log").scrollTop = $("chat-log").scrollHeight;
}

function showThinkingLoader() {
  hideThinkingLoader();
  const div = el("div", "msg bot thinking");
  div.id = "thinking-loader";
  div.setAttribute("aria-busy", "true");
  div.setAttribute("aria-live", "polite");
  div.appendChild(el("span", "msg-label", "Assistant"));
  const body = el("div", "thinking-body");
  body.appendChild(el("span", "thinking-text", "Working"));
  const dots = el("span", "thinking-dots", "…");
  dots.setAttribute("aria-hidden", "true");
  body.appendChild(dots);
  const sub = el(
    "p",
    "thinking-sub muted",
    "Routing, retrieving context, and calling APEX APIs — this can take a few seconds.",
  );
  div.appendChild(body);
  div.appendChild(sub);
  $("chat-log").appendChild(div);
  $("chat-log").scrollTop = $("chat-log").scrollHeight;
  const sendBtn = $("btn-send");
  if (sendBtn) sendBtn.disabled = true;
}

function hideThinkingLoader() {
  const node = document.getElementById("thinking-loader");
  if (node) node.remove();
  const sendBtn = $("btn-send");
  if (sendBtn) sendBtn.disabled = false;
}

function updateThinkingLabel(text) {
  const sub = document.querySelector("#thinking-loader .thinking-sub");
  if (sub) sub.textContent = text;
}

async function consumeChatSse(response) {
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let result = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() || "";
    for (const block of parts) {
      const lines = block.split("\n");
      let event = "message";
      let data = "";
      for (const line of lines) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        if (line.startsWith("data:")) data += line.slice(5).trim();
      }
      if (!data) continue;
      try {
        const parsed = JSON.parse(data);
        if (event === "status" && parsed.label) {
          updateThinkingLabel(parsed.label);
        } else if (event === "result") {
          result = parsed;
        } else if (event === "error") {
          throw new Error(parsed.message || "Stream error");
        }
      } catch (e) {
        if (event === "error") throw e;
      }
    }
  }
  return result;
}

function appendBotMessage(data) {
  const div = el("div", "msg bot");
  div.appendChild(el("span", "msg-label", "Assistant"));
  if (data.semantic_routing?.label) {
    const sem = el("div", "msg-meta semantic-routing");
    sem.appendChild(el("span", "intent-pill muted", data.semantic_routing.label));
    div.appendChild(sem);
  }
  if (data.intent) {
    const meta = el("div", "msg-meta");
    meta.appendChild(el("span", "intent-pill", data.intent.replace(/_/g, " ")));
    div.appendChild(meta);
  }
  const mutationToken =
    data.mutation_token ||
    data.display?.pending_confirmation?.mutation_token ||
    null;
  if (data.error) {
    div.classList.add("msg-error");
  }
  if (data.display) {
    div.appendChild(renderDisplay(data.display));
    if (data.requires_confirmation && mutationToken) {
      mountConfirmBar(div, mutationToken);
    }
    if (
      data.answer &&
      (data.display.type === "table" ||
        (data.error && data.display.level !== "error") ||
        (data.display.level === "error" && data.display.type !== "article"))
    ) {
      div.appendChild(el("p", "msg-summary muted", data.answer));
    }
  } else {
    div.appendChild(el("p", "msg-body", data.answer || "No response."));
  }
  $("chat-log").appendChild(div);
  $("chat-log").scrollTop = $("chat-log").scrollHeight;

  if (data.requires_confirmation && mutationToken) {
    let pendingMessage = null;
    try {
      pendingMessage = JSON.parse(sessionStorage.getItem(STORAGE_PENDING_CHAT) || "null");
    } catch {
      pendingMessage = null;
    }
    updateConfirmStrip({
      mutation_token: mutationToken,
      message: pendingMessage?.message,
    });
  } else if (!data.requires_confirmation) {
    updateConfirmStrip(null);
  }
}

async function login() {
  const token = $("token").value.trim().replace(/^Bearer\s+/i, "");
  const region = $("region").value;
  $("login-error").hidden = true;

  if (!token) {
    $("login-error").textContent = "Token is required.";
    $("login-error").hidden = false;
    return;
  }

  $("btn-login").disabled = true;
  try {
    const res = await fetch("/api/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token, region }),
    });
    const data = await res.json();
    if (!data.ok) {
      $("login-error").textContent = data.message || "Login failed.";
      $("login-error").hidden = false;
      return;
    }
    setSession(token, region, data.profile);
    showMain(data.profile, region);
    const consent = document.getElementById("login-rerun-consent");
    const pending = readPendingRerun();
    if (consent?.checked && pending?.message) {
      clearPendingRerun();
      const rerunRegion = pending.region || region;
      if (rerunRegion !== region) {
        sessionStorage.setItem(STORAGE_REGION, rerunRegion);
        $("profile-region").textContent = `Region: ${rerunRegion}`;
        $("region-main").value = rerunRegion;
      }
      await sendChat(pending.message, { skipUserEcho: true });
    } else {
      clearPendingRerun();
    }
  } catch (e) {
    $("login-error").textContent = String(e);
    $("login-error").hidden = false;
  } finally {
    $("btn-login").disabled = false;
  }
}

async function sendChat(message, options = {}) {
  const token = getToken();
  if (!token || isTokenExpired(token)) {
    redirectToLogin("Your access token expired. Paste a new JWT from apex-dev.", {
      rerunMessage: message,
    });
    return;
  }
  const region = sessionStorage.getItem(STORAGE_REGION) || "US-West";
  const confirm_mutation = Boolean(options.confirm_mutation);
  const mutation_token = options.mutation_token || null;
  const session_id = getOrCreateSessionId();

  if (!options.skipUserEcho) {
    appendUserMessage(confirm_mutation ? `Confirm: ${message}` : message);
  }

  if (!confirm_mutation) {
    saveLastQuery(message, region);
    sessionStorage.setItem(
      STORAGE_PENDING_CHAT,
      JSON.stringify({ message, region, mutation_token: null }),
    );
  }

  showThinkingLoader();
  let data;
  try {
    const res = await fetch("/api/chat/stream", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        message,
        region,
        confirm_mutation,
        mutation_token,
        session_id,
      }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      if (res.status === 401) {
        redirectToLogin(authErrorMessage(res, err), { rerunMessage: message, rerunRegion: region });
        return;
      }
      appendBotMessage({
        answer: String(err.detail || res.statusText),
        display: {
          type: "article",
          title: "Error",
          level: "error",
          paragraphs: [String(err.detail || res.statusText)],
        },
      });
      return;
    }
    data = await consumeChatSse(res);
    if (!data) {
      appendBotMessage({
        answer: "No response from server.",
        display: {
          type: "article",
          title: "Error",
          level: "error",
          paragraphs: ["Empty stream response."],
        },
      });
      return;
    }
  } finally {
    hideThinkingLoader();
  }
  ensureSessionIdFromServer(data.session_id);
  if (data.requires_confirmation && data.mutation_token) {
    sessionStorage.setItem(
      STORAGE_PENDING_CHAT,
      JSON.stringify({ message, region, mutation_token: data.mutation_token }),
    );
  } else if (confirm_mutation) {
    sessionStorage.removeItem(STORAGE_PENDING_CHAT);
  }
  appendBotMessage(data);
  if (data.stack_status) applyStackStatus(data.stack_status, region);
}

async function initFromSession() {
  const token = getToken();
  if (!token) return;
  if (isTokenExpired(token)) {
    redirectToLogin("Your access token expired. Paste a new JWT from apex-dev.");
    return;
  }
  const region = sessionStorage.getItem(STORAGE_REGION) || "US-West";
  let profile = {};
  try {
    profile = JSON.parse(sessionStorage.getItem(STORAGE_PROFILE) || "{}");
  } catch {
    profile = { name: "APEX User" };
  }
  try {
    const res = await fetch(`/api/profile?region=${encodeURIComponent(region)}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (res.status === 401) {
      const err = await res.json().catch(() => ({}));
      redirectToLogin(authErrorMessage(res, err));
      return;
    }
    if (res.ok) {
      profile = await res.json();
      sessionStorage.setItem(STORAGE_PROFILE, JSON.stringify(profile));
    }
  } catch {
    // Offline or server down — keep cached profile until a chat call fails.
  }
  showMain(profile, region);
}

document.addEventListener("DOMContentLoaded", async () => {
  await loadRegions($("region"));
  await loadRegions($("region-main"));

  $("btn-login").addEventListener("click", login);
  $("btn-new-chat").addEventListener("click", () => {
    startNewChat();
  });

  $("btn-logout").addEventListener("click", () => {
    clearSession();
    $("token").value = "";
    $("chat-log").innerHTML = "";
    updateConfirmStrip(null);
    renderLoginRerunPrompt();
    showLogin();
  });

  $("btn-change-region").addEventListener("click", () => {
    $("region-picker").hidden = false;
  });

  $("btn-save-region").addEventListener("click", () => {
    const region = $("region-main").value;
    sessionStorage.setItem(STORAGE_REGION, region);
    $("profile-region").textContent = `Region: ${region}`;
    $("region-picker").hidden = true;
    refreshStackBar(region);
  });

  $("stack-context-toggle").addEventListener("click", () => {
    const details = $("stack-context-details");
    const open = details.hidden;
    details.hidden = !open;
    $("stack-context-toggle").setAttribute("aria-expanded", open ? "true" : "false");
    $("stack-context-chevron").textContent = open ? "▾" : "▸";
  });

  document.addEventListener("click", (e) => {
    const btn = e.target.closest(".btn-confirm-mutation");
    if (!btn) return;
    let pending = null;
    try {
      pending = JSON.parse(sessionStorage.getItem(STORAGE_PENDING_CHAT) || "null");
    } catch {
      pending = null;
    }
    const token = btn.dataset.mutationToken || pending?.mutation_token;
    const message = pending?.message;
    if (!message || !token) return;
    sendChat(message, { confirm_mutation: true, mutation_token: token, skipUserEcho: false });
  });

  $("chat-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const input = $("chat-input");
    const text = input.value.trim();
    if (!text) return;
    input.value = "";
    sendChat(text);
  });

  await initFromSession();
  if (!getToken()) {
    showLogin();
    renderLoginRerunPrompt();
  }
});
