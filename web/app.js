// Plain JS, no framework. User and model text is inserted with textContent, never innerHTML.
const $ = (id) => document.getElementById(id);
const body = document.body;
const recBtn = $("rec"), statusEl = $("status"), resultEl = $("result");
const transcriptEl = $("transcript"), answerEl = $("answer"), actionsEl = $("actions");
const errorEl = $("error"), waveEl = $("wave"), timerEl = $("timer"), toastEl = $("toast");

let recorder = null, chunks = [], pendingId = null;
let audioCtx = null, rafId = 0, timerId = 0;

const IDLE_STATUS = "Tap the orb and speak";
const kindLabel = { udhaar: "Udhaar · credit given", payment: "Payment received" };
const rs = (n) => "Rs " + Number(n).toLocaleString("en-PK");
const hasUrdu = (s) => /[؀-ۿ]/.test(s);
const CHECK_SVG = '<svg viewBox="0 0 24 24"><path d="M20 6 9 17l-5-5"/></svg>';

function setMode(mode) { // "" | "recording" | "busy"
  body.classList.toggle("recording", mode === "recording");
  body.classList.toggle("busy", mode === "busy");
  recBtn.disabled = mode === "busy";
  recBtn.setAttribute("aria-label", mode === "recording" ? "Stop" : "Record");
}

function setStatus(msg) { statusEl.textContent = msg; }

function el(tag, cls, text) {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text !== undefined) node.textContent = text;
  return node;
}

// Urdu-script text gets the Nastaliq font and RTL direction.
function nameEl(tag, cls, name) {
  const node = el(tag, cls, name);
  if (hasUrdu(name)) { node.lang = "ur"; node.dir = "rtl"; }
  return node;
}

function toast(msg) {
  toastEl.textContent = msg;
  toastEl.hidden = false;
  clearTimeout(toast.t);
  toast.t = setTimeout(() => { toastEl.hidden = true; }, 2600);
}

// ---------- friendly errors ----------

function describeError(status, message) {
  const m = (message || "").toLowerCase();
  if (m.includes("could not understand"))
    return ["Couldn't understand that", "Say the customer's name, the amount, and whether it's udhaar or a payment."];
  if (m.includes("ollama"))
    return ["AI model is offline", "Start Ollama with `ollama serve`, then try again."];
  if (m.includes("ffmpeg") || m.includes("decode") || status === 400)
    return ["Couldn't read the recording", "Check your microphone and record again."];
  if (m.includes("empty transcript") || m.includes("transcript is empty"))
    return ["Didn't hear anything", "Hold the device closer and speak a little louder."];
  if (m.includes("microphone"))
    return ["Microphone blocked", "Allow microphone access in your browser's address bar, then try again."];
  if (m.includes("failed to fetch") || m.includes("networkerror"))
    return ["Can't reach Voice Khata", "Make sure the server is running (`make run`)."];
  if (status === 404)
    return ["That entry expired", "Nothing was saved. Please record it again."];
  if (status === 413)
    return ["Recording too long", "Keep it to one short sentence."];
  return ["Something went wrong", "Please try again."];
}

function showError(status, detail) {
  const message = typeof detail === "object" && detail ? detail.message : String(detail || "");
  const heard = typeof detail === "object" && detail ? detail.transcript : "";
  const [title, hint] = describeError(status, message);
  $("err-title").textContent = title;
  $("err-hint").textContent = hint;
  $("err-tech").textContent = (status ? `HTTP ${status} · ` : "") + message;
  $("err-details").open = false;
  $("err-heard").hidden = !heard;
  if (heard) {
    const t = $("err-transcript");
    t.textContent = heard;
    t.lang = hasUrdu(heard) ? "ur" : "";
  }
  resultEl.hidden = true;
  errorEl.hidden = false;
  setStatus(IDLE_STATUS);
}

function clearPanels() { errorEl.hidden = true; resultEl.hidden = true; }

// ---------- customers ----------

async function loadCustomers() {
  try {
    const rows = await (await fetch("/api/customers")).json();
    const ul = $("customers");
    ul.replaceChildren();
    $("cust-count").textContent = rows.length ? `${rows.length} total` : "";
    if (!rows.length) ul.append(el("li", "empty", "No customers yet. Record your first entry."));
    for (const r of rows) {
      const li = el("li");
      const avatar = nameEl("span", "avatar", [...r.name.trim()][0] || "?");
      const bal = el("span", "cust-bal");
      if (r.balance > 0) { bal.classList.add("owes"); bal.append(rs(r.balance), el("small", "", "owes you")); }
      else if (r.balance < 0) { bal.classList.add("credit"); bal.append(rs(-r.balance), el("small", "", "you owe")); }
      else { bal.classList.add("settled"); bal.append(rs(0), el("small", "", "settled")); }
      li.append(avatar, nameEl("span", "cust-name", r.name), bal);
      ul.append(li);
    }
  } catch { /* the list is informational only */ }
}

// ---------- recording visuals ----------

function startVisuals(stream) {
  const started = Date.now();
  timerEl.textContent = "00:00";
  timerId = setInterval(() => {
    const s = Math.floor((Date.now() - started) / 1000);
    timerEl.textContent = `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
  }, 250);

  try {
    audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    const analyser = audioCtx.createAnalyser();
    analyser.fftSize = 128;
    audioCtx.createMediaStreamSource(stream).connect(analyser);
    const data = new Uint8Array(analyser.frequencyBinCount);
    const ctx = waveEl.getContext("2d");
    const W = waveEl.width, H = waveEl.height, bars = 40, gap = 6, bw = (W - gap * (bars - 1)) / bars;
    const grad = ctx.createLinearGradient(0, 0, W, 0);
    grad.addColorStop(0, "#fb7185"); grad.addColorStop(.5, "#fb923c"); grad.addColorStop(1, "#fb7185");
    const draw = () => {
      analyser.getByteFrequencyData(data);
      ctx.clearRect(0, 0, W, H);
      ctx.fillStyle = grad;
      for (let i = 0; i < bars; i++) {
        // mirror around the centre so the wave looks symmetric
        const idx = Math.abs(i - bars / 2) | 0;
        const v = data[idx + 2] / 255;
        const h = Math.max(6, v * H);
        const x = i * (bw + gap);
        ctx.beginPath();
        ctx.roundRect(x, (H - h) / 2, bw, h, bw / 2);
        ctx.fill();
      }
      rafId = requestAnimationFrame(draw);
    };
    draw();
  } catch { /* visualiser is decoration only */ }
}

function stopVisuals() {
  clearInterval(timerId);
  cancelAnimationFrame(rafId);
  if (audioCtx) { audioCtx.close(); audioCtx = null; }
}

// ---------- record → process ----------

async function toggleRecording() {
  if (recorder) { recorder.stop(); return; }
  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  } catch {
    showError(0, "Microphone access was denied or is unavailable.");
    return;
  }
  clearPanels();
  chunks = [];
  recorder = new MediaRecorder(stream); // webm/opus in Chrome and Firefox
  recorder.ondataavailable = (e) => chunks.push(e.data);
  recorder.onstop = () => {
    stopVisuals();
    stream.getTracks().forEach((t) => t.stop());
    const blob = new Blob(chunks, { type: recorder.mimeType });
    recorder = null;
    send(blob);
  };
  recorder.start();
  setMode("recording");
  startVisuals(stream);
  setStatus("Listening… tap again to stop");
}

async function send(blob) {
  setMode("busy");
  setStatus("Gemma is listening and thinking…");
  try {
    const form = new FormData();
    form.append("file", blob, "recording.webm");
    const res = await fetch("/api/process", { method: "POST", body: form });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) { showError(res.status, data.detail || res.statusText); return; }
    show(data);
    setStatus(IDLE_STATUS);
  } catch (e) {
    showError(0, e.message);
  } finally {
    setMode("");
  }
}

function show(data) {
  errorEl.hidden = true;
  transcriptEl.textContent = data.transcript;
  transcriptEl.lang = hasUrdu(data.transcript) ? "ur" : "";
  answerEl.replaceChildren();
  actionsEl.hidden = true;
  pendingId = null;
  const box = el("div", "summary");

  if (data.action === "get_balance") {
    const b = data.balance;
    box.append(el("span", "kind balance", "Balance check"));
    if (!b.found) {
      const who = el("p", "who", "No customer named ");
      who.append(nameEl("span", "name", b.customer_name));
      who.style.marginTop = "12px";
      box.append(who);
      if (b.similar_names.length) box.append(el("p", "warn", "Did you mean: " + b.similar_names.join(", ") + "?"));
    } else {
      const owes = b.balance >= 0;
      box.append(el("p", "amount " + (owes ? "udhaar" : "payment"), rs(Math.abs(b.balance))));
      const who = el("p", "who");
      if (owes) who.append(nameEl("span", "name", b.customer_name), " owes you");
      else who.append("You owe ", nameEl("span", "name", b.customer_name));
      box.append(who);
    }
  } else {
    const p = data.proposal;
    pendingId = p.id;
    box.append(el("span", "kind " + p.kind, kindLabel[p.kind]));
    box.append(el("p", "amount " + p.kind, rs(p.amount)));
    const who = el("p", "who");
    who.append(nameEl("span", "name", p.customer_name));
    if (p.is_new_customer) who.append(el("span", "new-badge", "NEW"));
    box.append(who);
    if (p.note) box.append(el("p", "note", p.note));
    if (p.is_new_customer && p.similar_names.length) {
      box.append(el("p", "warn", "Similar existing customer: " + p.similar_names.join(", ") +
        ". Discard and re-record if it's the same person."));
    }
    box.append(el("p", "hint", "Nothing is saved until you confirm."));
    actionsEl.hidden = false;
  }
  answerEl.append(box);
  resultEl.hidden = false;
}

$("confirm").addEventListener("click", async () => {
  if (!pendingId) return;
  try {
    const res = await fetch("/api/confirm", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ proposal_id: pendingId }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) { showError(res.status, data.detail || res.statusText); return; }
    const box = el("div", "summary");
    const saved = el("p", "saved");
    saved.innerHTML = CHECK_SVG; // static markup, no user data
    saved.append("Saved to khata");
    const who = el("p", "who");
    who.append(nameEl("span", "name", data.customer_name),
      data.balance >= 0 ? ` now owes ${rs(data.balance)}` : ` is owed ${rs(-data.balance)}`);
    box.append(saved, who);
    answerEl.replaceChildren(box);
    actionsEl.hidden = true; pendingId = null;
    toast("✓ Entry saved");
    loadCustomers();
  } catch (e) { showError(0, e.message); }
});

$("discard").addEventListener("click", () => {
  pendingId = null; resultEl.hidden = true; toast("Discarded. Nothing was saved.");
});

$("err-close").addEventListener("click", () => { errorEl.hidden = true; });
$("err-retry").addEventListener("click", () => { errorEl.hidden = true; toggleRecording(); });

recBtn.addEventListener("click", toggleRecording);
loadCustomers();
