/**
 * Dev Workflow Runner 클라이언트.
 *
 * Transcript는 localStorage에 저장되어 production과 분리된다.
 * 서버에는 workflow 실행 결과와 상태 JSON만 요청한다.
 */

const STORAGE_KEY_PREFIX = "dev_runner_transcript";
const STATE_STORAGE_KEY = "dev_runner_user_id";

const $select = document.getElementById("workflow-select");
const $userIdInput = document.getElementById("user-id-input");
const $form = document.getElementById("message-form");
const $input = document.getElementById("message-input");
const $transcript = document.getElementById("transcript");
const $stateView = document.getElementById("state-view");
const $traceView = document.getElementById("trace-view");
const $btnReset = document.getElementById("btn-reset");
const $btnReload = document.getElementById("btn-reload");
const $btnExportJson = document.getElementById("btn-export-json");
const $btnExportTxt = document.getElementById("btn-export-txt");

/* ── Transcript (localStorage) ── */

function normalizeUserId(value) {
  return (value || "").trim();
}

function getActiveUserId() {
  return normalizeUserId($userIdInput.value);
}

function getTranscriptStorageKey() {
  const workflowId = $select.value || "_default";
  const userId = getActiveUserId() || "dev_local";
  return `${STORAGE_KEY_PREFIX}:${userId}:${workflowId}`;
}

function loadTranscript() {
  try {
    return JSON.parse(localStorage.getItem(getTranscriptStorageKey())) || [];
  } catch {
    return [];
  }
}

function saveTranscript(entries) {
  localStorage.setItem(getTranscriptStorageKey(), JSON.stringify(entries));
}

function appendTranscript(role, text) {
  const entries = loadTranscript();
  entries.push({ role, text, ts: new Date().toISOString() });
  saveTranscript(entries);
  renderTranscript();
}

function clearTranscript() {
  localStorage.removeItem(getTranscriptStorageKey());
  renderTranscript();
}

function renderTranscript() {
  const entries = loadTranscript();
  if (entries.length === 0) {
    $transcript.innerHTML = '<p class="empty">대화를 시작하세요.</p>';
    return;
  }
  $transcript.innerHTML = entries
    .map(
      (e) =>
        `<div class="msg msg-${e.role}"><span class="role">${e.role === "user" ? "나" : "Bot"}</span><span class="text">${escapeHtml(e.text)}</span></div>`
    )
    .join("");
  $transcript.scrollTop = $transcript.scrollHeight;
}

/* ── State / Trace rendering ── */

function renderState(state) {
  if (!state) {
    $stateView.textContent = "상태 없음";
    return;
  }
  $stateView.textContent = JSON.stringify(state, null, 2);
}

function renderTrace(trace) {
  if (!trace || trace.length === 0) {
    $traceView.innerHTML = "<p>trace 없음</p>";
    return;
  }
  $traceView.innerHTML = trace
    .map(
      (t) =>
        `<div class="trace-step">` +
        `<span class="step-num">#${t.step}</span> ` +
        `<span class="node-id">${escapeHtml(t.node_id)}</span> ` +
        `<span class="action">${escapeHtml(t.action || t.error || "")}</span> ` +
        `<span class="elapsed">${t.elapsed_ms != null ? t.elapsed_ms + "ms" : ""}</span>` +
        (t.reply_preview
          ? `<div class="reply-preview">${escapeHtml(t.reply_preview)}</div>`
          : "") +
        `</div>`
    )
    .join("");
}

/* ── API calls ── */

async function fetchWorkflows() {
  const res = await fetch("/api/workflows");
  const data = await res.json();
  $select.innerHTML = '<option value="">워크플로 선택...</option>';
  (data.workflows || []).forEach((id) => {
    const opt = document.createElement("option");
    opt.value = id;
    opt.textContent = id === "start_chat" ? "start_chat (전체 진입)" : id;
    $select.appendChild(opt);
  });
}

async function sendMessage(workflowId, message) {
  const userId = getActiveUserId();
  const res = await fetch("/api/send", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ workflow_id: workflowId, message, user_id: userId }),
  });
  return res.json();
}

async function fetchState() {
  const userId = getActiveUserId();
  const workflowId = $select.value;
  if (!workflowId) {
    renderState(null);
    return;
  }

  const res = await fetch(
    `/api/state?user_id=${encodeURIComponent(userId)}&workflow_id=${encodeURIComponent(workflowId)}`
  );
  const data = await res.json();
  renderState(data.state);
}

async function resetState() {
  const userId = getActiveUserId();
  const workflowId = $select.value;
  if (!workflowId) {
    renderState(null);
    return;
  }

  await fetch(
    `/api/state?user_id=${encodeURIComponent(userId)}&workflow_id=${encodeURIComponent(workflowId)}`,
    { method: "DELETE" }
  );
  clearTranscript();
  renderState(null);
  $traceView.innerHTML = "<p>trace 없음</p>";
}

async function reloadWorkflows() {
  await fetch("/api/reload", { method: "POST" });
  await fetchWorkflows();
}

/* ── Export ── */

function exportJson() {
  const entries = loadTranscript();
  downloadFile(
    JSON.stringify(entries, null, 2),
    "transcript.json",
    "application/json"
  );
}

function exportTxt() {
  const entries = loadTranscript();
  const text = entries
    .map((e) => `[${e.ts}] ${e.role}: ${e.text}`)
    .join("\n");
  downloadFile(text, "transcript.txt", "text/plain");
}

function downloadFile(content, filename, mimeType) {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

/* ── Helpers ── */

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

function syncUserIdFromStorage() {
  const storedUserId = normalizeUserId(localStorage.getItem(STATE_STORAGE_KEY));
  if (storedUserId) {
    $userIdInput.value = storedUserId;
  }
}

function persistUserId() {
  const userId = getActiveUserId();
  if (!userId) {
    localStorage.removeItem(STATE_STORAGE_KEY);
    return;
  }
  localStorage.setItem(STATE_STORAGE_KEY, userId);
}

/* ── Event handlers ── */

$form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const workflowId = $select.value;
  if (!workflowId) {
    alert("워크플로를 먼저 선택하세요.");
    return;
  }
  const message = $input.value.trim();
  if (!message) return;

  $input.value = "";
  $input.disabled = true;

  appendTranscript("user", message);

  try {
    const result = await sendMessage(workflowId, message);

    if (result.error) {
      appendTranscript("system", `오류: ${result.error}`);
    } else {
      appendTranscript("bot", result.reply);
      renderState(result.state);
      renderTrace(result.trace);
    }
  } catch (err) {
    appendTranscript("system", `네트워크 오류: ${err.message}`);
  } finally {
    $input.disabled = false;
    $input.focus();
  }
});

$select.addEventListener("change", () => {
  renderTranscript();
  fetchState();
});

$userIdInput.addEventListener("change", () => {
  $userIdInput.value = getActiveUserId();
  persistUserId();
  renderTranscript();
  fetchState();
});

$btnReset.addEventListener("click", () => {
  if (confirm("State와 대화 기록을 모두 초기화할까요?")) {
    resetState();
  }
});

$btnReload.addEventListener("click", reloadWorkflows);
$btnExportJson.addEventListener("click", exportJson);
$btnExportTxt.addEventListener("click", exportTxt);

/* ── Init ── */

syncUserIdFromStorage();
persistUserId();
renderTranscript();
fetchWorkflows();
fetchState();
