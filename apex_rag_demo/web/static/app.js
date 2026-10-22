const STORAGE_TOKEN = "apex_ai_token";
const STORAGE_REGION = "apex_ai_region";
const STORAGE_PROFILE = "apex_ai_profile";

const $ = (id) => document.getElementById(id);

function getToken() {
  return sessionStorage.getItem(STORAGE_TOKEN) || "";
}

function setSession(token, region, profile) {
  sessionStorage.setItem(STORAGE_TOKEN, token);
  sessionStorage.setItem(STORAGE_REGION, region);
  sessionStorage.setItem(STORAGE_PROFILE, JSON.stringify(profile));
}

function clearSession() {
  sessionStorage.removeItem(STORAGE_TOKEN);
  sessionStorage.removeItem(STORAGE_REGION);
  sessionStorage.removeItem(STORAGE_PROFILE);
}

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = text;
  return node;
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

  if (display.type === "table" && display.rows && display.columns?.length) {
    root.appendChild(
      el("p", "display-meta muted", `${display.count ?? display.rows.length} row(s)`),
    );
    const wrap = el("div", "table-wrap");
    const table = el("table", "data-table");
    const thead = el("thead");
    const headerRow = el("tr");
    display.columns.forEach((col) => headerRow.appendChild(el("th", null, col.label)));
    thead.appendChild(headerRow);
    table.appendChild(thead);
    const tbody = el("tbody");
    display.rows.forEach((row) => {
      const tr = el("tr");
      display.columns.forEach((col) => {
        tr.appendChild(el("td", null, String(row[col.key] ?? "—")));
      });
      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    wrap.appendChild(table);
    root.appendChild(wrap);
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
      if (section.table?.columns?.length && section.table.rows) {
        const wrap = el("div", "table-wrap");
        const table = el("table", "data-table data-table-compact");
        const thead = el("thead");
        const headerRow = el("tr");
        section.table.columns.forEach((col) =>
          headerRow.appendChild(el("th", null, col.label)),
        );
        thead.appendChild(headerRow);
        table.appendChild(thead);
        const tbody = el("tbody");
        section.table.rows.forEach((row) => {
          const tr = el("tr");
          section.table.columns.forEach((col) => {
            tr.appendChild(el("td", null, String(row[col.key] ?? "—")));
          });
          tbody.appendChild(tr);
        });
        table.appendChild(tbody);
        wrap.appendChild(table);
        block.appendChild(wrap);
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

  return root;
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

function showMain(profile, region) {
  $("screen-login").hidden = true;
  $("screen-main").hidden = false;
  document.body.classList.add("layout-chat");
  $("welcome-title").textContent = `Welcome, ${profile.name}`;
  $("welcome-sub").textContent = `Signed in to ${profile.tenant || "apex-dev"}.`;
  $("profile-email").textContent = profile.email || profile.userId || "";
  $("profile-region").textContent = `Region: ${region}`;
  $("region-main").value = region;
}

function appendUserMessage(text) {
  const div = el("div", "msg user");
  div.appendChild(el("span", "msg-label", "You"));
  div.appendChild(el("p", "msg-body", text));
  $("chat-log").appendChild(div);
  $("chat-log").scrollTop = $("chat-log").scrollHeight;
}

function appendBotMessage(data) {
  const div = el("div", "msg bot");
  div.appendChild(el("span", "msg-label", "Assistant"));
  if (data.display) {
    div.appendChild(renderDisplay(data.display));
    if (data.answer && data.display.type === "table") {
      div.appendChild(el("p", "msg-summary muted", data.answer));
    }
  } else {
    div.appendChild(el("p", "msg-body", data.answer || "No response."));
  }
  $("chat-log").appendChild(div);
  $("chat-log").scrollTop = $("chat-log").scrollHeight;
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
  } catch (e) {
    $("login-error").textContent = String(e);
    $("login-error").hidden = false;
  } finally {
    $("btn-login").disabled = false;
  }
}

async function sendChat(message) {
  const token = getToken();
  const region = sessionStorage.getItem(STORAGE_REGION) || "US-West";
  const execute_writes = $("execute-writes").checked;

  appendUserMessage(message);

  const res = await fetch("/api/chat", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ message, region, execute_writes }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
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

  const data = await res.json();
  appendBotMessage(data);
}

function initFromSession() {
  const token = getToken();
  if (!token) return;
  const region = sessionStorage.getItem(STORAGE_REGION) || "US-West";
  let profile = {};
  try {
    profile = JSON.parse(sessionStorage.getItem(STORAGE_PROFILE) || "{}");
  } catch {
    profile = { name: "APEX User" };
  }
  showMain(profile, region);
}

document.addEventListener("DOMContentLoaded", async () => {
  await loadRegions($("region"));
  await loadRegions($("region-main"));

  $("btn-login").addEventListener("click", login);
  $("btn-logout").addEventListener("click", () => {
    clearSession();
    $("token").value = "";
    $("chat-log").innerHTML = "";
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
  });

  $("chat-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const input = $("chat-input");
    const text = input.value.trim();
    if (!text) return;
    input.value = "";
    sendChat(text);
  });

  initFromSession();
  if (!getToken()) showLogin();
});
