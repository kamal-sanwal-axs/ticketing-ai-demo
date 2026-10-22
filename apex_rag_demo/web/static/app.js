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
}

function showMain(profile, region) {
  $("screen-login").hidden = true;
  $("screen-main").hidden = false;
  $("welcome-title").textContent = `Welcome, ${profile.name}`;
  $("welcome-sub").textContent = `You are signed in to ${profile.tenant || "apex-dev"}.`;
  $("profile-email").textContent = profile.email || profile.userId || "";
  $("profile-region").textContent = `Region: ${region}`;
  $("region-main").value = region;
}

function appendMessage(role, text) {
  const div = document.createElement("div");
  div.className = `msg ${role}`;
  div.textContent = role === "user" ? `You: ${text}` : text;
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

  appendMessage("user", message);

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
    appendMessage("bot", `Error: ${err.detail || res.statusText}`);
    return;
  }

  const data = await res.json();
  appendMessage("bot", data.answer);
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
