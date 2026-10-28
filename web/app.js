// Plain JS, no framework. All text is inserted with textContent (never innerHTML).
const $ = (id) => document.getElementById(id);
const recBtn = $("rec"), statusEl = $("status"), resultEl = $("result");
const transcriptEl = $("transcript"), answerEl = $("answer"), actionsEl = $("actions");

let recorder = null, chunks = [], pendingId = null;

function setStatus(msg, isError = false) {
  statusEl.textContent = msg;
  statusEl.className = isError ? "error" : "";
}

function line(text, cls) {
  const p = document.createElement("p");
  p.textContent = text;
  if (cls) p.className = cls;
  return p;
}

const kindLabel = { udhaar: "Udhaar (credit given)", payment: "Payment received" };

async function loadCustomers() {
  try {
    const rows = await (await fetch("/api/customers")).json();
    const ul = $("customers");
    ul.replaceChildren();
    if (!rows.length) { const li = document.createElement("li"); li.textContent = "No customers yet."; ul.append(li); }
    for (const r of rows) {
      const li = document.createElement("li");
      const n = document.createElement("span"), b = document.createElement("span");
      n.textContent = r.name; n.dir = "auto";
      b.textContent = r.balance;
      li.append(n, b);
      ul.append(li);
    }
  } catch { /* the list is informational only */ }
}

async function toggleRecording() {
  if (recorder) { recorder.stop(); return; }
  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  } catch {
    setStatus("Microphone access was denied or is unavailable.", true);
    return;
  }
  chunks = [];
  recorder = new MediaRecorder(stream); // webm/opus in Chrome and Firefox
  recorder.ondataavailable = (e) => chunks.push(e.data);
  recorder.onstop = () => {
    stream.getTracks().forEach((t) => t.stop());
    const blob = new Blob(chunks, { type: recorder.mimeType });
    recorder = null;
    recBtn.textContent = "🎙 Record";
    recBtn.classList.remove("recording");
    send(blob);
  };
  recorder.start();
  recBtn.textContent = "⏹ Stop";
  recBtn.classList.add("recording");
  setStatus("Recording…");
}

async function send(blob) {
  recBtn.disabled = true;
  resultEl.hidden = true;
  setStatus("Transcribing and understanding… (the first request can be slow while the model loads)");
  try {
    const form = new FormData();
    form.append("file", blob, "recording.webm");
    const res = await fetch("/api/process", { method: "POST", body: form });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || res.statusText);
    show(data);
    setStatus("");
  } catch (e) {
    setStatus(e.message, true);
  } finally {
    recBtn.disabled = false;
  }
}

function show(data) {
  transcriptEl.textContent = data.transcript;
  answerEl.replaceChildren();
  actionsEl.hidden = true;
  pendingId = null;

  if (data.action === "get_balance") {
    const b = data.balance;
    if (!b.found) {
      answerEl.append(line(`No customer named “${b.customer_name}”.`, "warn"));
      if (b.similar_names.length) answerEl.append(line("Similar: " + b.similar_names.join(", ")));
    } else if (b.balance >= 0) {
      answerEl.append(line(`${b.customer_name} owes you Rs ${b.balance}.`));
    } else {
      answerEl.append(line(`You owe ${b.customer_name} Rs ${-b.balance}.`));
    }
  } else {
    const p = data.proposal;
    pendingId = p.id;
    answerEl.append(line(`${kindLabel[p.kind]}: Rs ${p.amount}`));
    answerEl.append(line(`Customer: ${p.customer_name}${p.is_new_customer ? " (NEW customer)" : ""}`));
    if (p.is_new_customer && p.similar_names.length) {
      answerEl.append(line("Similar existing: " + p.similar_names.join(", ") + ". Discard if this is one of them.", "warn"));
    }
    if (p.note) answerEl.append(line(`Note: ${p.note}`));
    answerEl.append(line("Nothing is saved until you confirm.", "hint"));
    actionsEl.hidden = false;
  }
  resultEl.hidden = false;
}

$("confirm").addEventListener("click", async () => {
  if (!pendingId) return;
  try {
    const res = await fetch("/api/confirm", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ proposal_id: pendingId }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || res.statusText);
    answerEl.replaceChildren(line(`Saved. ${data.customer_name} now owes Rs ${data.balance}.`));
    actionsEl.hidden = true; pendingId = null;
    loadCustomers();
  } catch (e) { setStatus(e.message, true); }
});

$("discard").addEventListener("click", () => {
  pendingId = null; resultEl.hidden = true; setStatus("Discarded. Nothing was saved.");
});

recBtn.addEventListener("click", toggleRecording);
loadCustomers();
