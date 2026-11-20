"use strict";
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const state = { lang: "en", tab: "paste", demo: null, health: null, c: null, dtab: "grievance", poll: null };

async function api(path, opts = {}) {
  const r = await fetch(path, opts);
  let data = null;
  try { data = await r.json(); } catch (e) { /* not json */ }
  if (!r.ok) throw new Error((data && (data.detail || data.message)) || `Request failed (${r.status})`);
  return data;
}
const post = (path, body) => api(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) });
const fmtDate = (iso) => { if (!iso) return ""; const d = new Date(iso + "T00:00:00"); return d.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" }); };

/* ---------------- input card ---------------- */
function setTab(t) {
  state.tab = t;
  $$(".tab").forEach((b) => b.classList.toggle("on", b.dataset.tab === t));
  ["paste", "file", "demo"].forEach((k) => ($("#pane-" + k).hidden = k !== t));
}
$$(".tab").forEach((b) => b.addEventListener("click", () => setTab(b.dataset.tab)));
$$(".lang .chip").forEach((b) => b.addEventListener("click", () => {
  state.lang = b.dataset.lang;
  $$(".lang .chip").forEach((x) => x.classList.toggle("on", x === b));
}));
const fileIn = $("#file");
fileIn.addEventListener("change", () => { $("#file-name").textContent = fileIn.files[0] ? fileIn.files[0].name : "PNG, JPG, WEBP or PDF, up to 8 MB"; });
const drop = $("#drop");
["dragover", "dragenter"].forEach((e) => drop.addEventListener(e, (ev) => { ev.preventDefault(); drop.classList.add("over"); }));
["dragleave", "drop"].forEach((e) => drop.addEventListener(e, (ev) => { ev.preventDefault(); drop.classList.remove("over"); }));
drop.addEventListener("drop", (ev) => { if (ev.dataTransfer.files[0]) { fileIn.files = ev.dataTransfer.files; fileIn.dispatchEvent(new Event("change")); } });

async function init() {
  try {
    state.health = await api("/api/health");
    const b = $("#engine");
    if (state.health.mode === "ai") { b.textContent = "AI on: " + (state.health.model || "Gemini"); b.classList.add("ai"); }
    else { b.textContent = "Basic mode (no AI key)"; }
    if (!state.health.files) {
      const w = $("#file-warn"); w.hidden = false;
      w.textContent = "Photo and PDF reading needs the AI model, which is not set up on this server. Paste the text instead.";
    }
  } catch (e) { $("#engine").textContent = "offline"; }
  try {
    const demos = await api("/api/demo");
    $("#demo-list").innerHTML = demos.map((d) => `<button class="demo" data-id="${esc(d.id)}"><span>${esc(d.title)}</span><small>Select</small></button>`).join("");
    $$(".demo").forEach((b) => b.addEventListener("click", () => {
      state.demo = b.dataset.id;
      $$(".demo").forEach((x) => x.classList.toggle("on", x === b));
      $$(".demo small").forEach((x) => (x.textContent = "Select"));
      $("small", b).textContent = "Selected";
    }));
  } catch (e) { /* ignore */ }
  const m = location.hash.match(/case=([a-f0-9]+)/);
  if (m) { try { show(await api("/api/case/" + m[1])); } catch (e) { location.hash = ""; } }
}

let stepTimer = null;
function startSteps() {
  const ol = $("#steps"); ol.hidden = false;
  const items = $$("li", ol); let i = 0;
  items.forEach((li) => (li.className = ""));
  items[0].className = "active";
  stepTimer = setInterval(() => {
    if (i < items.length - 1) { items[i].className = "done"; i++; items[i].className = "active"; }
  }, 1100);
}
function stopSteps(ok) {
  clearInterval(stepTimer);
  const ol = $("#steps");
  if (ok) $$("li", ol).forEach((li) => (li.className = "done"));
  setTimeout(() => (ol.hidden = true), ok ? 500 : 0);
}

$("#go").addEventListener("click", async () => {
  const err = $("#err"); err.textContent = ""; err.className = "hint";
  const fd = new FormData(); fd.append("lang", state.lang);
  if (state.tab === "paste") {
    const t = $("#letter").value.trim();
    if (t.length < 30) { err.textContent = "Please paste the letter text first."; err.className = "hint warn"; return; }
    fd.append("text", t);
  } else if (state.tab === "file") {
    if (!fileIn.files[0]) { err.textContent = "Please choose a photo or PDF."; err.className = "hint warn"; return; }
    fd.append("file", fileIn.files[0]);
  } else {
    if (!state.demo) { err.textContent = "Please select a demo case."; err.className = "hint warn"; return; }
    fd.append("demo_id", state.demo);
  }
  const btn = $("#go"); btn.disabled = true; startSteps();
  try {
    const c = await api("/api/analyze", { method: "POST", body: fd });
    stopSteps(true); show(c);
  } catch (e) { stopSteps(false); err.textContent = e.message; err.className = "hint warn"; }
  btn.disabled = false;
});

/* ---------------- result ---------------- */
function show(c) {
  state.c = c; location.hash = "case=" + c.id;
  const a = c.analysis;
  const pct = Math.round(a.confidence * 100);
  const mode = c.engine === "ai" ? `Read by AI${c.model ? " (" + esc(c.model) + ")" : ""}` : "Basic mode: keyword rules, no AI";
  const redTxt = Object.keys(c.redactions || {}).length ? `Hidden before analysis: ${Object.entries(c.redactions).map(([k, v]) => v + " " + k.replace(/_/g, " ")).join(", ")}.` : "";
  const rules = c.rules.map((r) => {
    const badge = r.type === "tip" ? `<span class="v tip">Practical tip</span>` : r.verified ? `<span class="v ok">Verified ${esc(fmtDate(r.checked))}</span>` : `<span class="v chk">Check before relying</span>`;
    const link = r.source_url ? `<a href="${esc(r.source_url)}" target="_blank" rel="noopener">${esc(r.source_name)}</a>` : `<span class="hint">${esc(r.source_name)}</span>`;
    return `<div class="rule"><h4>${esc(r.title)} ${badge}</h4><p>${esc(r.text)}</p>${link}</div>`;
  }).join("");
  $("#result").hidden = false;
  $("#result").innerHTML = `
  <section class="card" id="s1">
    <div class="sec-head"><span class="num" style="background:#4285F4">1</span><h2>Why it was rejected</h2></div>
    <span class="pill blue">${esc(c.category_label)}</span>
    <p class="big">${esc(a.plain_explanation)}</p>
    ${a.clause_cited ? `<div class="quote"><small class="hint">Clause the insurer relies on</small><br>${esc(a.clause_cited)}</div>` : ""}
    <div class="meta">
      ${a.insurer ? `<span>Insurer: <b>${esc(a.insurer)}</b></span>` : ""}
      ${a.claim_amount_inr ? `<span>Claim: <b>Rs. ${Number(a.claim_amount_inr).toLocaleString("en-IN")}</b></span>` : ""}
      <span>Confidence <span class="meter"><i style="width:${pct}%;background:${pct < 60 ? "#EA4335" : "#34A853"}"></i></span>${pct}%</span>
    </div>
    ${a.policy_cancelled_by_insurer ? `<div class="flag"><b>The insurer cancelled your policy.</b> Ask for the written notice and the basis for cancelling. See the rules below.</div>` : ""}
    ${a.needs_human_review ? `<div class="flag">This result is uncertain, so a human reviewer will look at it closely.</div>` : ""}
    ${a.missing_info && a.missing_info.length ? `<h3>The letter does not say</h3><ul class="clean">${a.missing_info.map((m) => `<li>${esc(m)}</li>`).join("")}</ul>` : ""}
    ${(c.notes || []).map((n) => `<div class="note">${esc(n)}</div>`).join("")}
    <p class="hint">${mode}. ${esc(redTxt)}</p>
  </section>

  <section class="card" id="s2">
    <div class="sec-head"><span class="num" style="background:#EA4335">2</span><h2>Your rights and the rules that apply</h2></div>
    ${rules}
  </section>

  <section class="card" id="s3">
    <div class="sec-head"><span class="num" style="background:#FBBC04;color:#1F1F1F">3</span><h2>Your deadlines</h2></div>
    <p class="hint" style="margin-top:0">Enter your dates to get a timeline based on the Insurance Ombudsman rules (1-month wait for the insurer, then 1 year to file).</p>
    <div class="grid2">
      <label>Date of the rejection letter<input type="date" id="d-rej" value="${esc(c.details.rejection_date || "")}"></label>
      <label>Date you sent your grievance to the insurer<input type="date" id="d-gri" value="${esc(c.details.grievance_date || "")}"></label>
    </div>
    <div class="row"><button class="btn sm" id="d-go">Show my timeline</button></div>
    <ul class="timeline" id="timeline"></ul>
  </section>

  <section class="card" id="s4">
    <div class="sec-head"><span class="num" style="background:#34A853">4</span><h2>Your appeal drafts</h2></div>
    <p class="hint" style="margin-top:0">Fill what you know. Anything missing becomes a [PLACEHOLDER] in the draft. Every draft goes to a human reviewer before you can copy or download it.</p>
    <div class="grid2">
      <label>Your name<input type="text" id="f-name" value="${esc(c.details.name || "")}"></label>
      <label>Patient name (if different)<input type="text" id="f-patient" value="${esc(c.details.patient || "")}"></label>
      <label>Policy number<input type="text" id="f-policy" value="${esc(c.details.policy_no || "")}"></label>
      <label>Claim number<input type="text" id="f-claim" value="${esc(c.details.claim_no || "")}"></label>
      <label>Hospital<input type="text" id="f-hosp" value="${esc(c.details.hospital || "")}"></label>
      <label>Your phone / email<input type="text" id="f-contact" value="${esc(c.details.contact || "")}"></label>
    </div>
    <label class="field" style="margin-top:10px">Anything else the draft should mention
      <input type="text" id="f-notes" value="${esc(c.details.notes || "")}" placeholder="e.g. documents were sent on 5 April by email"></label>
    <p class="hint">If AI is on, these details are sent to the AI model only to write your draft. Leave a field blank to get a [PLACEHOLDER] instead. You can delete everything with "Delete my data" below.</p>
    <div class="row"><button class="btn primary sm" id="draft-go">${c.draft ? "Regenerate drafts" : "Create my drafts"}</button><span class="hint" id="draft-err"></span></div>
    <div id="draft-out"></div>
  </section>

  <section class="card" id="s5">
    <div class="sec-head"><span class="num" style="background:#4285F4">5</span><h2>Check against official sources</h2></div>
    <p class="hint" style="margin-top:0">Searches the web for IRDAI rules and Insurance Ombudsman or court decisions on a similar situation. Sources from government sites are marked in green; other sites are shown too, so check them yourself.</p>
    <div class="row"><button class="btn sm" id="v-go">Verify this with official sources</button></div>
    <div id="v-out"></div>
  </section>

  <section class="card" id="s6">
    <div class="sec-head"><span class="num" style="background:#EA4335">6</span><h2>Ask about your case</h2></div>
    <div class="chat" id="chat"></div>
    <div class="chat-in"><input type="text" id="q" placeholder="e.g. Can I still appeal? What if they do not reply?"><button class="btn primary sm" id="q-go">Ask</button></div>
    <div class="sugg">
      <button class="chip" data-q="What should I do first?">What should I do first?</button>
      <button class="chip" data-q="Is there a time limit to appeal?">Is there a time limit?</button>
      <button class="chip" data-q="Does it cost anything to go to the Ombudsman?">Does the Ombudsman cost money?</button>
    </div>
  </section>

  <div class="row" style="margin-bottom:30px">
    <button class="btn sm" onclick="window.print()">Print this page</button>
    <button class="btn sm" id="again">Analyse another letter</button>
    <button class="btn sm danger" id="del">Delete my data</button>
  </div>`;

  renderTimeline(c.deadlines); renderDraft(); renderVerify(c.verify); renderChat();
  $("#d-go").onclick = onDeadlines; $("#draft-go").onclick = onDraft; $("#v-go").onclick = onVerify;
  $("#q-go").onclick = () => ask($("#q").value);
  $("#q").addEventListener("keydown", (e) => { if (e.key === "Enter") ask($("#q").value); });
  $$(".sugg .chip").forEach((b) => (b.onclick = () => ask(b.dataset.q)));
  $("#again").onclick = () => { $("#result").hidden = true; location.hash = ""; window.scrollTo({ top: 0, behavior: "smooth" }); };
  $("#del").onclick = async () => {
    if (!confirm("Delete this case and everything saved with it?")) return;
    await api("/api/case/" + state.c.id, { method: "DELETE" }); $("#again").click(); state.c = null;
  };
  startPoll();
  if (!state._scrolled) { $("#result").scrollIntoView({ behavior: "smooth", block: "start" }); }
}

function renderTimeline(items) {
  const ul = $("#timeline"); if (!ul) return;
  ul.innerHTML = (items || []).map((d) => `<li class="${esc(d.status)}"><b>${esc(d.label)}${d.date ? ": " + esc(fmtDate(d.date)) : ""}</b><small>${esc(d.note)}</small></li>`).join("");
}
async function onDeadlines() {
  const r = await post(`/api/case/${state.c.id}/deadlines`, { rejection_date: $("#d-rej").value, grievance_date: $("#d-gri").value });
  state.c.deadlines = r.deadlines; renderTimeline(r.deadlines);
}

function details() {
  return { name: $("#f-name").value.trim(), patient: $("#f-patient").value.trim(), policy_no: $("#f-policy").value.trim(), claim_no: $("#f-claim").value.trim(),
    hospital: $("#f-hosp").value.trim(), contact: $("#f-contact").value.trim(), notes: $("#f-notes").value.trim(),
    rejection_date: $("#d-rej").value, grievance_date: $("#d-gri").value };
}
async function onDraft() {
  const b = $("#draft-go"); b.disabled = true; $("#draft-err").innerHTML = `<span class="spin"></span>Writing your drafts...`;
  try {
    const c = await post(`/api/case/${state.c.id}/draft`, details());
    state.c = c; renderDraft(); renderTimeline(c.deadlines); startPoll();
    $("#draft-err").textContent = ""; b.textContent = "Regenerate drafts";
  } catch (e) { $("#draft-err").textContent = e.message; $("#draft-err").className = "hint warn"; }
  b.disabled = false;
}
function renderDraft() {
  const out = $("#draft-out"); if (!out) return;
  const c = state.c; if (!c.draft) { out.innerHTML = ""; return; }
  const d = c.draft, st = c.status, ok = st === "approved";
  const pill = ok ? `<span class="pill green">Approved by human reviewer</span>` : st === "changes_requested" ? `<span class="pill red">Reviewer asked for changes</span>` : `<span class="pill yellow">Awaiting human review</span>`;
  const note = c.review && c.review.note ? `<div class="note"><b>Reviewer note:</b> ${esc(c.review.note)}</div>` : "";
  const text = state.dtab === "ombudsman" ? d.ombudsman_complaint : state.dtab === "checklist" ? null : d.grievance_body;
  const body = text === null
    ? `<div>${d.checklist.map((x, i) => `<label class="check"><input type="checkbox" id="ck${i}"><span>${esc(x)}</span></label>`).join("")}</div>`
    : `<pre class="doc" id="doc-text">${esc(text)}</pre>`;
  const hist = (c.review.history || []).map((h) => `<li>${esc(h.event)}</li>`).join("");
  out.innerHTML = `
    <div class="status">${pill}<span class="hint">${d.engine === "ai" ? "Drafted by AI from the verified rule library" : "Drafted from a template (basic mode)"}</span></div>
    ${note}
    <div class="dtabs">
      ${[["grievance", "Email to insurer"], ["ombudsman", "Ombudsman complaint"], ["checklist", "Document checklist"]].map(([k, l]) => `<button class="chip ${state.dtab === k ? "on" : ""}" data-dt="${k}">${l}</button>`).join("")}
    </div>
    <div class="wm ${ok ? "" : "locked"}">${body}</div>
    <div class="row">
      <button class="btn sm" id="copy" ${ok ? "" : "disabled"}>Copy</button>
      <a class="btn sm" id="dl" ${ok ? `href="/api/case/${c.id}/download?kind=${state.dtab}"` : `aria-disabled="true" style="opacity:.5;pointer-events:none"`} download>Download .txt</a>
      ${ok ? "" : `<a class="btn sm" href="/reviewer#${c.id}" target="_blank" rel="noopener">Open reviewer console (demo)</a>`}
    </div>
    ${ok ? "" : `<p class="hint">Copy and download unlock when the reviewer approves. ${st === "pending_review" ? "This page updates by itself." : "Change the details above and regenerate."}</p>`}
    ${hist ? `<ul class="clean hint">${hist}</ul>` : ""}`;
  $$("[data-dt]", out).forEach((b) => (b.onclick = () => { state.dtab = b.dataset.dt; renderDraft(); }));
  const cp = $("#copy"); if (cp) cp.onclick = async () => { const t = $("#doc-text"); if (t) { await navigator.clipboard.writeText(t.textContent); cp.textContent = "Copied"; setTimeout(() => (cp.textContent = "Copy"), 1500); } };
}
function startPoll() {
  clearInterval(state.poll);
  if (!state.c || state.c.status !== "pending_review") return;
  state.poll = setInterval(async () => {
    try {
      const c = await api("/api/case/" + state.c.id);
      if (c.status !== state.c.status) { state.c = c; renderDraft(); clearInterval(state.poll); }
    } catch (e) { clearInterval(state.poll); }
  }, 4000);
}

async function onVerify() {
  const b = $("#v-go"); b.disabled = true; $("#v-out").innerHTML = `<p class="hint"><span class="spin"></span>Searching official sources...</p>`;
  try { const r = await post(`/api/case/${state.c.id}/verify`); state.c.verify = r; renderVerify(r); }
  catch (e) { $("#v-out").innerHTML = `<p class="hint warn">${esc(e.message)}</p>`; }
  b.disabled = false;
}
function renderVerify(v) {
  const out = $("#v-out"); if (!out || !v) return;
  const label = v.mode === "web" ? "Live web check" : v.mode === "ai-no-search" ? "AI check without live search" : "Official sources behind the rules";
  out.innerHTML = `<p class="hint"><b>${label}</b></p>${v.text ? `<div class="answer">${esc(v.text)}</div>` : ""}
    <div class="srcs">${(v.sources || []).map((s) => `<a class="src ${s.official ? "off" : ""}" href="${esc(s.url)}" target="_blank" rel="noopener">${s.official ? "Official: " : ""}${esc(s.title)}</a>`).join("")}</div>`;
}

function renderChat() {
  const el = $("#chat"); if (!el) return;
  el.innerHTML = (state.c.chat || []).map((m) => `<div class="msg q">${esc(m.q)}</div><div class="msg a">${esc(m.a)}</div>`).join("");
}
async function ask(q) {
  q = (q || "").trim(); if (q.length < 3) return;
  $("#q").value = "";
  const el = $("#chat"); el.insertAdjacentHTML("beforeend", `<div class="msg q">${esc(q)}</div><div class="msg a" id="pending"><span class="spin"></span>Thinking...</div>`);
  try {
    const r = await post(`/api/case/${state.c.id}/chat`, { question: q, lang: state.lang });
    state.c.chat.push({ q, a: r.answer, engine: r.engine }); renderChat();
  } catch (e) { $("#pending").textContent = e.message; }
}

init();
