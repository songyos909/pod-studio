// ---------- helpers ----------
const $ = (id) => document.getElementById(id);
const esc = (s) => (s || "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

async function api(path, method = "GET", body) {
  const opt = { method, headers: { "Content-Type": "application/json" } };
  if (body) opt.body = JSON.stringify(body);
  const r = await fetch(path, opt);
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.error || `HTTP ${r.status}`);
  return data;
}

// ---------- tabs ----------
document.querySelectorAll(".tab").forEach((t) => {
  t.onclick = () => {
    document.querySelectorAll(".tab").forEach((x) => x.classList.remove("active"));
    document.querySelectorAll(".panel").forEach((x) => x.classList.remove("active"));
    t.classList.add("active");
    $(t.dataset.tab).classList.add("active");
    if (t.dataset.tab === "prompts") loadPrompts();
    if (t.dataset.tab === "gallery") loadGallery();
    if (t.dataset.tab === "generate") loadGenerateOptions();
    if (t.dataset.tab === "bundle") loadBundle();
    if (t.dataset.tab === "ebooks") loadEbooks();
    if (t.dataset.tab === "store") loadStore();
    if (t.dataset.tab === "settings") loadSettings();
  };
});

// ---------- status ----------
async function refreshStatus() {
  try {
    const s = await api("/api/status");
    setDot("st-comfy", s.comfyui);
    setDot("st-claude", s.anthropic);
  } catch (e) { /* ignore */ }
}
function setDot(id, ok) {
  const el = $(id);
  el.classList.toggle("on", ok);
  el.classList.toggle("off", !ok);
}

// ---------- AI Studio ----------
const AI_OPTIONS = {
  "opt-style": ["minimalist", "kawaii / cute", "retro / vintage", "watercolor", "flat vector",
    "bold line art", "anime", "realistic", "hand-drawn doodle", "pop art", "cottagecore", "cyberpunk"],
  "opt-camera": ["front view", "flat lay (top-down)", "close-up", "isometric", "full scene",
    "centered / isolated", "portrait crop", "wide landscape"],
  "opt-palette": ["pastel", "vibrant / bold", "monochrome", "earthy / muted", "neon",
    "black & white", "warm tones", "cool tones"],
  "opt-audience": ["kids", "teens", "adults", "gift / occasion", "holiday / seasonal",
    "pet lovers", "home decor", "office / stationery"],
};
function populateAiOptions() {
  for (const [id, vals] of Object.entries(AI_OPTIONS)) {
    const sel = $(id);
    if (!sel || sel.options.length) continue;
    sel.innerHTML = `<option value="">— ไม่ระบุ —</option>` +
      vals.map((v) => `<option value="${esc(v)}">${esc(v)}</option>`).join("");
  }
}
function collectAiOptions() {
  return {
    style: $("opt-style").value,
    camera: $("opt-camera").value,
    palette: $("opt-palette").value,
    audience: $("opt-audience").value,
    extra: $("opt-extra").value.trim(),
  };
}

let lastDesigns = [];
$("btn-brainstorm").onclick = async () => {
  const brief = $("brief").value.trim();
  if (!brief) { alert("กรุณาใส่ไอเดีย/ธีม"); return; }
  const btn = $("btn-brainstorm");
  btn.disabled = true;
  $("studio-status").textContent = "⏳ ทีม AI กำลังทำงาน (อาจใช้เวลาสักครู่)...";
  $("designs").innerHTML = "";
  $("art-direction").textContent = "";
  $("studio-actions").style.display = "none";
  try {
    const data = await api("/api/brainstorm", "POST", { brief, count: parseInt($("count").value) || 6, options: collectAiOptions() });
    lastDesigns = data.designs || [];
    $("art-direction").textContent = data.art_direction ? "🎯 ทิศทาง: " + data.art_direction : "";
    $("designs").innerHTML = lastDesigns.map((d, i) => cardHtml(d, i)).join("");
    $("studio-status").textContent = `✅ ได้ ${lastDesigns.length} ดีไซน์ — เลือกที่ชอบแล้วเพิ่มเข้า prompts`;
    $("studio-actions").style.display = lastDesigns.length ? "block" : "none";
    document.querySelectorAll(".card .pick input").forEach((cb) => {
      cb.onchange = () => cb.closest(".card").classList.toggle("sel", cb.checked);
    });
  } catch (e) {
    $("studio-status").textContent = "❌ " + e.message;
  } finally {
    btn.disabled = false;
  }
};

function cardHtml(d, i) {
  const tags = (d.tags || "").split(",").filter(Boolean).map((t) => `<span class="tag">${esc(t.trim())}</span>`).join("");
  return `<div class="card">
    <label class="pick"><input type="checkbox" data-i="${i}" checked /> เลือก</label>
    <h4>${esc(d.title)}</h4>
    <div class="idea">${esc(d.idea || "")}</div>
    <div class="pr">${esc(d.prompt)}</div>
    <div class="tags">${tags}</div>
  </div>`;
}

$("btn-add-selected").onclick = async () => {
  const picked = [...document.querySelectorAll(".card .pick input:checked")].map((cb) => lastDesigns[+cb.dataset.i]);
  if (!picked.length) { alert("ยังไม่ได้เลือกดีไซน์"); return; }
  const rows = picked.map((d) => ({ title: d.title, prompt: d.prompt, negative: d.negative, seed: "", tags: d.tags }));
  const res = await api("/api/prompts", "POST", { rows });
  $("studio-status").textContent = `➕ เพิ่ม ${res.added} ดีไซน์เข้า prompts.csv แล้ว (รวม ${res.total})`;
};

// ---------- Prompts ----------
async function loadPrompts() {
  const data = await api("/api/prompts");
  const rows = data.prompts || [];
  if (!rows.length) { $("prompts-list").innerHTML = '<p class="empty">ยังไม่มี prompt</p>'; return; }
  $("prompts-list").innerHTML = `<table><tr><th>title</th><th>prompt</th><th>tags</th><th></th></tr>` +
    rows.map((r) => `<tr><td>${esc(r.title)}</td><td>${esc(r.prompt)}</td><td>${esc(r.tags)}</td>
      <td class="del"><button data-t="${esc(r.title)}">ลบ</button></td></tr>`).join("") + `</table>`;
  document.querySelectorAll("#prompts-list .del button").forEach((b) => {
    b.onclick = async () => { await api("/api/prompts/delete", "POST", { title: b.dataset.t }); loadPrompts(); };
  });
}
$("btn-add-prompt").onclick = async () => {
  const row = { title: $("p-title").value, prompt: $("p-prompt").value, negative: $("p-negative").value, seed: "", tags: $("p-tags").value };
  if (!row.prompt.trim()) { alert("ต้องมี prompt"); return; }
  await api("/api/prompts", "POST", { rows: [row] });
  ["p-title", "p-prompt", "p-negative", "p-tags"].forEach((id) => ($(id).value = ""));
  loadPrompts();
};

// ---------- jobs (generate / upload) ----------
async function pollJob(jobId, logEl, btn) {
  const poll = async () => {
    const job = await api(`/api/jobs/${jobId}`);
    logEl.textContent = job.log.join("\n");
    logEl.scrollTop = logEl.scrollHeight;
    if (job.status === "running") { setTimeout(poll, 1200); }
    else { if (btn) btn.disabled = false; if (job.status === "done") loadGallery(); }
  };
  poll();
}

const numOrNull = (id) => { const v = $(id).value.trim(); return v === "" ? null : Number(v); };
const strOrNull = (id) => { const v = $(id).value.trim(); return v === "" ? null : v; };

$("btn-generate").onclick = async () => {
  const bg = $("g-bg").value;
  const body = {
    limit: parseInt($("g-limit").value) || null,
    force: $("g-force").checked,
    remove_bg: bg === "on" ? true : bg === "off" ? false : null,
    coloring: $("g-coloring").checked,
    workflow: strOrNull("g-workflow"),
    checkpoint: strOrNull("g-ckpt"),
    width: numOrNull("g-width"), height: numOrNull("g-height"),
    steps: numOrNull("g-steps"), cfg: numOrNull("g-cfg"),
    sampler: strOrNull("g-sampler"), scheduler: strOrNull("g-scheduler"),
    seed: numOrNull("g-seed"), batch: numOrNull("g-batch"),
  };
  $("btn-generate").disabled = true;
  $("gen-log").textContent = "⏳ เริ่มงาน...";
  const { job_id } = await api("/api/generate", "POST", body);
  pollJob(job_id, $("gen-log"), $("btn-generate"));
};

// โหลดตัวเลือกการเจน (โมเดล/sampler จาก ComfyUI + chip preset + placeholder จาก config)
let genOptsLoaded = false;
let genMeta = {};
let genWorkflows = [];
async function loadGenerateOptions(force) {
  if (genOptsLoaded && !force) return;
  // workflow dropdown
  try {
    const w = await api("/api/workflows");
    genWorkflows = w.workflows || [];
    $("g-workflow").innerHTML = genWorkflows.map((x) =>
      `<option value="${esc(x.name)}">${esc(x.label)}</option>`).join("");
    $("g-workflow").value = w.active || (genWorkflows[0] && genWorkflows[0].name);
    $("g-workflow").onchange = applyWorkflowChoice;
  } catch (e) { /* ignore */ }
  // chip preset (ใช้ชุดเดียวกับ Settings)
  if (!$("g-gen-presets").children.length) {
    $("g-gen-presets").innerHTML = GEN_PRESETS.map((p, i) =>
      `<button type="button" class="chip" data-gi="${i}">${p.label}<small>${p.sub}</small></button>`).join("");
    document.querySelectorAll('#g-gen-presets .chip').forEach((c) => {
      c.onclick = () => {
        const p = GEN_PRESETS[+c.dataset.gi];
        $("g-width").value = p.w; $("g-height").value = p.h;
        document.querySelectorAll('#g-gen-presets .chip').forEach((x) => x.classList.remove("active"));
        c.classList.add("active");
      };
    });
  }
  // placeholder จาก config + เติม dropdown
  try {
    const c = await fetch("/api/config").then((r) => r.json());
    const g = c.generation || {};
    $("g-width").placeholder = g.width ?? "config";
    $("g-height").placeholder = g.height ?? "config";
    $("g-steps").placeholder = g.steps ?? "config";
    $("g-cfg").placeholder = g.cfg ?? "config";
    $("g-seed").placeholder = g.seed ?? "config";
    $("g-batch").placeholder = g.batch_size ?? "config";
    window._cfgGen = g;
  } catch (e) { /* ignore */ }
  await loadGenerateMeta();
  genOptsLoaded = true;
}
async function loadGenerateMeta() {
  genMeta = { checkpoints: [], samplers: [], schedulers: [], unets: [], clips: [], vaes: [] };
  try { genMeta = await api("/api/comfy-meta"); } catch (e) { /* offline */ }
  const g = window._cfgGen || {};
  fillOptSelect("g-sampler", genMeta.samplers, g.sampler_name, "— ใช้ค่า config —");
  fillOptSelect("g-scheduler", genMeta.schedulers, g.scheduler, "— ใช้ค่า config —");
  applyWorkflowChoice();
}

// เปลี่ยนรายการ checkpoint ตามชนิด workflow (sdxl=checkpoints, flux=unets, gguf=unets_gguf)
function applyWorkflowChoice() {
  const name = $("g-workflow").value;
  const wf = genWorkflows.find((x) => x.name === name) || {};
  let list;
  if (wf.gguf) list = genMeta.unets_gguf && genMeta.unets_gguf.length ? genMeta.unets_gguf : [];
  else if (name === "sdxl") list = genMeta.checkpoints;
  else list = genMeta.unets && genMeta.unets.length ? genMeta.unets : genMeta.checkpoints;
  fillOptSelect("g-ckpt", list, "", "— ใช้ค่า config —");
  if (wf.gguf)
    $("g-wf-hint").textContent = "GGUF: โมเดลเล็ก/เร็ว — ต้องโหลดไฟล์ .gguf วางใน ComfyUI/models/unet ก่อน (ดู README)";
  else if (wf.negative === false)
    $("g-wf-hint").textContent = "Flux: ไม่ใช้ negative prompt • CFG = guidance (~4) • โมเดลตั้งใน config แล้ว เว้น checkpoint ว่างได้";
  else
    $("g-wf-hint").textContent = "SDXL: ใช้ negative prompt ได้ • CFG แนะนำ ~7";
}
function fillOptSelect(id, values, currentLabel, blank) {
  const sel = $(id);
  const hint = currentLabel ? `${blank} (${currentLabel})` : blank;
  let html = `<option value="">${esc(hint)}</option>`;
  (values || []).forEach((v) => { html += `<option value="${esc(v)}">${esc(v)}</option>`; });
  sel.innerHTML = html;
}
$("g-refresh-meta").onclick = () => loadGenerateMeta();

// ---------- Modal (shared) ----------
function openModal(html) {
  $("modal-body").innerHTML = html;
  $("modal").style.display = "flex";
  if (window.lucide) lucide.createIcons();
}
function closeModal() {
  $("modal").style.display = "none";
  $("modal-body").innerHTML = "";
}
$("modal-close").onclick = closeModal;
$("modal").onclick = (e) => { if (e.target.id === "modal") closeModal(); };
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeModal(); });

// ---------- Gallery ----------
let galleryItems = [];
async function loadGallery() {
  const data = await api("/api/catalog");
  galleryItems = data.items || [];
  if (!galleryItems.length) { $("gallery-grid").innerHTML = '<p class="empty">ยังไม่มีดีไซน์ — ไปแท็บ "สร้างภาพ"</p>'; return; }
  $("gallery-grid").innerHTML = galleryItems.map((it, i) => `<div class="item">
    <button class="del-btn" data-slug="${esc(it.slug)}" title="ลบ (ย้ายถังขยะ)"><i data-lucide="trash-2"></i></button>
    <img src="${esc(it.preview_url)}" loading="lazy" alt="${esc(it.title)}" data-i="${i}" />
    <div class="cap"><b>${esc(it.title)}</b>${esc(it.tags || "")}</div>
  </div>`).join("");
  if (window.lucide) lucide.createIcons();
  document.querySelectorAll("#gallery-grid img").forEach((img) => {
    img.onclick = () => showDesign(galleryItems[+img.dataset.i]);
  });
  document.querySelectorAll("#gallery-grid .del-btn").forEach((b) => {
    b.onclick = async (e) => {
      e.stopPropagation();
      if (!confirm("ลบดีไซน์นี้? (ย้ายไปถังขยะ output/_trash/ กู้คืนได้)")) return;
      await api("/api/catalog/delete", "POST", { slug: b.dataset.slug });
      loadGallery();
    };
  });
}
function showDesign(it) {
  if (!it) return;
  const tags = (it.tags || "").split(",").filter(Boolean).map((t) => `<span class="tag">${esc(t.trim())}</span>`).join("");
  openModal(`
    <img class="modal-img" src="${esc(it.image_url || it.preview_url)}" alt="${esc(it.title)}" />
    <h3 style="margin:14px 0 4px;color:#fff;">${esc(it.title)}</h3>
    <div class="tags" style="margin-bottom:10px;">${tags}</div>
    <div class="hint" style="margin:0;">seed: ${esc(it.seed || "-")} • ${esc(it.print_width || "")}×${esc(it.print_height || "")}px • ${esc(it.dpi || "")} DPI</div>
    <div style="margin-top:14px;"><a class="modal-link" href="${esc(it.image_url || it.preview_url)}" target="_blank">เปิดไฟล์เต็ม <i data-lucide="external-link"></i></a></div>
  `);
}
$("btn-refresh-gallery").onclick = loadGallery;

// ---------- Upload ----------
function uploadBody(validateOnly) {
  return {
    platform: $("u-platform").value,
    limit: parseInt($("u-limit").value) || null,
    use_preview: $("u-preview").checked,
    validate_only: validateOnly,
  };
}
$("btn-validate").onclick = async () => {
  $("upload-log").textContent = "⏳ ทดสอบการเชื่อมต่อ...";
  const { job_id } = await api("/api/upload", "POST", uploadBody(true));
  pollJob(job_id, $("upload-log"), null);
};
$("btn-upload").onclick = async () => {
  if (!confirm("อัปโหลดขึ้นร้านค้าจริง? (เริ่มเป็น draft ตาม config)")) return;
  $("btn-upload").disabled = true;
  $("upload-log").textContent = "⏳ กำลังอัปโหลด...";
  const { job_id } = await api("/api/upload", "POST", uploadBody(false));
  pollJob(job_id, $("upload-log"), $("btn-upload"));
};

// ---------- Shop (เว็บร้าน) ----------
$("btn-build-site").onclick = async () => {
  $("site-msg").textContent = "⏳ กำลังสร้างหน้าร้าน...";
  $("btn-build-site").disabled = true;
  try {
    const r = await api("/api/build-site", "POST", {});
    $("site-msg").textContent = `✅ สร้างแล้ว ${r.products} สินค้า` +
      (r.gas_configured ? " (เชื่อม Google Apps Script แล้ว)" : " — ยังไม่ตั้ง gas_url จะใช้อีเมลรับออเดอร์แทน");
  } catch (e) {
    $("site-msg").textContent = "❌ " + e.message;
  } finally {
    $("btn-build-site").disabled = false;
  }
};

// ---------- Bundle (รวมเป็น PDF) ----------
let bundlePool = [];   // คลังรูป (catalog + อัปโหลด): {key, type, value, title, url}
let bundleSeq = [];    // ลำดับหน้าในเล่ม (เก็บ key)

async function loadBundle() {
  const data = await api("/api/catalog");
  const seen = new Set();
  const designs = (data.items || []).filter((it) => {
    const s = it.slug || it.title;
    if (seen.has(s)) return false; seen.add(s); return true;
  }).map((it) => ({ key: "slug:" + it.slug, type: "slug", value: it.slug, title: it.title, url: it.preview_url }));
  // คงรูปที่อัปโหลดไว้ในรอบนี้ (type=file) ไว้ในคลัง
  const uploaded = bundlePool.filter((p) => p.type === "file");
  bundlePool = [...designs, ...uploaded];
  renderPool();
  renderSeq();
}

function renderPool() {
  if (!bundlePool.length) { $("bundle-grid").innerHTML = '<p class="empty">ยังไม่มีรูป — สร้างภาพ หรือกดเพิ่มรูปจากเครื่อง</p>'; return; }
  $("bundle-grid").innerHTML = bundlePool.map((p) => `
    <div class="item ${bundleSeq.includes(p.key) ? "in-seq" : ""}" data-key="${esc(p.key)}">
      <img src="${esc(p.url)}" loading="lazy" alt="${esc(p.title)}" />
      <div class="cap"><b>${esc(p.title)}</b></div>
    </div>`).join("");
  document.querySelectorAll("#bundle-grid .item").forEach((el) => {
    el.onclick = () => { toggleSeq(el.dataset.key); };
  });
}

function toggleSeq(key) {
  const i = bundleSeq.indexOf(key);
  if (i >= 0) bundleSeq.splice(i, 1); else bundleSeq.push(key);
  renderPool(); renderSeq();
}

function renderSeq() {
  $("b-count").textContent = bundleSeq.length ? bundleSeq.length + " หน้า" : "";
  if (!bundleSeq.length) { $("bundle-seq").innerHTML = '<p class="empty" style="padding:20px 0;">ยังไม่ได้เลือก — กดรูปทางซ้ายเพื่อเพิ่ม</p>'; return; }
  $("bundle-seq").innerHTML = bundleSeq.map((key, i) => {
    const p = bundlePool.find((x) => x.key === key) || { title: "(หาย)", url: "" };
    return `<div class="seq-item">
      <span class="seq-no">${i + 1}</span>
      <img src="${esc(p.url)}" alt="" />
      <span class="seq-title">${esc(p.title)}</span>
      <span class="seq-btns">
        <button data-act="up" data-i="${i}" ${i === 0 ? "disabled" : ""}><i data-lucide="chevron-up"></i></button>
        <button data-act="down" data-i="${i}" ${i === bundleSeq.length - 1 ? "disabled" : ""}><i data-lucide="chevron-down"></i></button>
        <button data-act="rm" data-i="${i}"><i data-lucide="x"></i></button>
      </span>
    </div>`;
  }).join("");
  if (window.lucide) lucide.createIcons();
  document.querySelectorAll("#bundle-seq .seq-btns button").forEach((b) => {
    b.onclick = () => {
      const i = +b.dataset.i, act = b.dataset.act;
      if (act === "rm") bundleSeq.splice(i, 1);
      else if (act === "up" && i > 0) [bundleSeq[i - 1], bundleSeq[i]] = [bundleSeq[i], bundleSeq[i - 1]];
      else if (act === "down" && i < bundleSeq.length - 1) [bundleSeq[i + 1], bundleSeq[i]] = [bundleSeq[i], bundleSeq[i + 1]];
      renderPool(); renderSeq();
    };
  });
}

$("b-clear").onclick = () => { bundleSeq = []; renderPool(); renderSeq(); };

$("b-upload").onchange = async (e) => {
  const files = [...e.target.files];
  for (const file of files) {
    const fd = new FormData();
    fd.append("file", file);
    try {
      const r = await fetch("/api/bundle/upload", { method: "POST", body: fd });
      const d = await r.json();
      if (d.path) {
        const key = "file:" + d.path;
        bundlePool.push({ key, type: "file", value: d.path, title: d.name, url: d.url });
        bundleSeq.push(key);  // อัปโหลดแล้วเพิ่มเข้าเล่มเลย
      }
    } catch (err) { alert("อัปโหลดไม่สำเร็จ: " + err.message); }
  }
  e.target.value = "";
  renderPool(); renderSeq();
};

$("btn-bundle").onclick = async () => {
  if (!bundleSeq.length) { alert("เลือกอย่างน้อย 1 รูป"); return; }
  const items = bundleSeq.map((key) => {
    const p = bundlePool.find((x) => x.key === key);
    return { type: p.type, value: p.value };
  });
  $("bundle-msg").textContent = "⏳ กำลังสร้าง PDF...";
  $("btn-bundle").disabled = true;
  try {
    const r = await api("/api/bundle", "POST", {
      title: $("b-title").value || "My Collection",
      page_size: $("b-size").value, items,
      page_numbers: $("b-pagenum").checked, cover: $("b-cover").checked,
    });
    $("bundle-msg").innerHTML = `✅ ${r.pages} หน้า — ` +
      `<a href="${r.pdf_url}" target="_blank" download>⬇️ ดาวน์โหลด PDF</a>`;
  } catch (e) {
    $("bundle-msg").textContent = "❌ " + e.message;
  } finally {
    $("btn-bundle").disabled = false;
  }
};

// ---------- E-book library ----------
async function loadEbooks() {
  const data = await api("/api/bundles");
  const items = data.items || [];
  if (!items.length) { $("ebooks-grid").innerHTML = '<p class="empty">ยังไม่มี E-book — ไปแท็บ "PDF/หนังสือ"</p>'; return; }
  $("ebooks-grid").innerHTML = items.map((b) => `
    <div class="item ebook-card">
      <button class="del-btn" data-name="${esc(b.name)}" title="ลบ (ย้ายถังขยะ)"><i data-lucide="trash-2"></i></button>
      <div class="ebook-thumb" data-url="${esc(b.url)}" data-name="${esc(b.name)}">${b.preview ? `<img src="${esc(b.preview)}" loading="lazy" alt="" />` : '<i data-lucide="file-text"></i>'}</div>
      <div class="cap">
        <b>${esc(b.name)}</b>
        ${b.pages ? b.pages + " หน้า • " : ""}${esc(String(b.size_mb))} MB<br>${esc(b.mtime)}
        <div style="margin-top:8px; display:flex; gap:6px;">
          <a class="modal-link" href="${esc(b.url)}" target="_blank" style="font-size:12px;">เปิด <i data-lucide="external-link"></i></a>
          <a class="modal-link" href="${esc(b.url)}" download style="font-size:12px;">ดาวน์โหลด <i data-lucide="download"></i></a>
        </div>
      </div>
    </div>`).join("");
  if (window.lucide) lucide.createIcons();
  document.querySelectorAll(".ebook-thumb").forEach((el) => {
    el.onclick = () => openModal(`<h3 style="margin:0 0 12px;color:#fff;">${esc(el.dataset.name)}</h3>
      <iframe class="modal-iframe" src="${esc(el.dataset.url)}"></iframe>`);
  });
  document.querySelectorAll("#ebooks-grid .del-btn").forEach((b) => {
    b.onclick = async (e) => {
      e.stopPropagation();
      if (!confirm("ลบ E-book นี้? (ย้ายไปถังขยะ กู้คืนได้)")) return;
      await api("/api/bundles/delete", "POST", { name: b.dataset.name });
      loadEbooks();
    };
  });
}
$("btn-refresh-ebooks").onclick = loadEbooks;

// ---------- Settings ----------
const GEN_PRESETS = [
  { label: "จัตุรัส", sub: "1024×1024", w: 1024, h: 1024 },
  { label: "แนวตั้ง", sub: "832×1216", w: 832, h: 1216 },
  { label: "แนวนอน", sub: "1216×832", w: 1216, h: 832 },
  { label: "ตั้ง 3:4", sub: "896×1152", w: 896, h: 1152 },
  { label: "นอน 4:3", sub: "1152×896", w: 1152, h: 896 },
];
const PRINT_PRESETS = [
  { label: "เสื้อยืด 15×18\"", sub: "4500×5400 @300", w: 4500, h: 5400, dpi: 300 },
  { label: "โปสเตอร์ 18×24\"", sub: "5400×7200 @300", w: 5400, h: 7200, dpi: 300 },
  { label: "โปสเตอร์ 24×36\"", sub: "7200×10800 @300", w: 7200, h: 10800, dpi: 300 },
  { label: "สติกเกอร์ 4×4\"", sub: "1200×1200 @300", w: 1200, h: 1200, dpi: 300 },
  { label: "A4 พิมพ์", sub: "2480×3508 @300", w: 2480, h: 3508, dpi: 300 },
  { label: "โปสการ์ด 4×6\"", sub: "1200×1800 @300", w: 1200, h: 1800, dpi: 300 },
];

let cfgCache = {};

function getCfg(path) {
  return path.split(".").reduce((o, k) => (o == null ? undefined : o[k]), cfgCache);
}

function fillFields() {
  document.querySelectorAll("[data-cfg]").forEach((el) => {
    const v = getCfg(el.dataset.cfg);
    if (v === undefined || v === null) return;
    if (el.type === "checkbox") el.checked = !!v;
    else el.value = v;
  });
  markActivePresets();
  updateDimReadout();
  updateProviderHint();
}

function setSelectOptions(sel, values, current) {
  if (!values || !values.length) {
    // ComfyUI offline — เก็บค่าปัจจุบันไว้เป็นตัวเลือกเดียว
    if (current) sel.innerHTML = `<option value="${esc(current)}">${esc(current)}</option>`;
    return;
  }
  if (current && !values.includes(current)) values = [current, ...values];
  sel.innerHTML = values.map((v) => `<option value="${esc(v)}">${esc(v)}</option>`).join("");
  if (current) sel.value = current;
}

async function loadSettings() {
  cfgCache = await api("/api/config");
  renderPresets();
  fillFields();
  loadComfyMeta();
}

async function loadComfyMeta() {
  let meta = { checkpoints: [], samplers: [], schedulers: [], online: false };
  try { meta = await api("/api/comfy-meta"); } catch (e) { /* offline */ }
  setSelectOptions($("cfg-generation.checkpoint"), meta.checkpoints, getCfg("generation.checkpoint"));
  setSelectOptions($("cfg-generation.sampler_name"), meta.samplers, getCfg("generation.sampler_name"));
  setSelectOptions($("cfg-generation.scheduler"), meta.schedulers, getCfg("generation.scheduler"));
}

function renderPresets() {
  $("gen-presets").innerHTML = GEN_PRESETS.map((p, i) =>
    `<button type="button" class="chip" data-kind="gen" data-i="${i}">${p.label}<small>${p.sub}</small></button>`).join("");
  $("print-presets").innerHTML = PRINT_PRESETS.map((p, i) =>
    `<button type="button" class="chip" data-kind="print" data-i="${i}">${esc(p.label)}<small>${p.sub}</small></button>`).join("");
  document.querySelectorAll(".chip[data-kind]").forEach((c) => {
    c.onclick = () => {
      if (c.dataset.kind === "gen") {
        const p = GEN_PRESETS[+c.dataset.i];
        $("cfg-generation.width").value = p.w;
        $("cfg-generation.height").value = p.h;
      } else {
        const p = PRINT_PRESETS[+c.dataset.i];
        $("cfg-postprocess.target_width").value = p.w;
        $("cfg-postprocess.target_height").value = p.h;
        $("cfg-postprocess.dpi").value = p.dpi;
      }
      markActivePresets();
      updateDimReadout();
    };
  });
}

function markActivePresets() {
  const gw = +$("cfg-generation.width").value, gh = +$("cfg-generation.height").value;
  document.querySelectorAll('.chip[data-kind="gen"]').forEach((c) => {
    const p = GEN_PRESETS[+c.dataset.i];
    c.classList.toggle("active", p.w === gw && p.h === gh);
  });
  const pw = +$("cfg-postprocess.target_width").value, ph = +$("cfg-postprocess.target_height").value;
  document.querySelectorAll('.chip[data-kind="print"]').forEach((c) => {
    const p = PRINT_PRESETS[+c.dataset.i];
    c.classList.toggle("active", p.w === pw && p.h === ph);
  });
}

function updateDimReadout() {
  const w = +$("cfg-postprocess.target_width").value, h = +$("cfg-postprocess.target_height").value;
  const dpi = +$("cfg-postprocess.dpi").value || 300;
  if (!w || !h) { $("dim-readout").textContent = ""; return; }
  const inW = (w / dpi).toFixed(1), inH = (h / dpi).toFixed(1);
  const cmW = (w / dpi * 2.54).toFixed(1), cmH = (h / dpi * 2.54).toFixed(1);
  const mp = (w * h / 1e6).toFixed(1);
  $("dim-readout").innerHTML = `📐 ไฟล์ <b>${w}×${h}px</b> ที่ ${dpi} DPI ≈ <b>${inW}×${inH} นิ้ว</b> (${cmW}×${cmH} ซม.) • ${mp} ล้านพิกเซล`;
}

const PROVIDER_HINTS = {
  gemini: "ฟรี: ขอคีย์ที่ aistudio.google.com/apikey แล้วตั้ง env GEMINI_API_KEY หรือใส่ credentials.yaml",
  ollama: "ฟรี 100% ในเครื่อง: ลง Ollama แล้ว `ollama pull llama3.1` — ไม่ต้องมีคีย์",
  groq: "ฟรี: ขอคีย์ที่ console.groq.com/keys แล้วตั้ง env GROQ_API_KEY",
  anthropic: "เสียเงิน: ตั้ง env ANTHROPIC_API_KEY (คุณภาพสูงสุด)",
  openai: "เสียเงิน: ตั้ง env OPENAI_API_KEY",
};
function updateProviderHint() {
  const p = $("cfg-agents.provider").value;
  $("provider-hint").textContent = PROVIDER_HINTS[p] || "";
}

async function saveConfig(btn) {
  const updates = {};
  document.querySelectorAll("[data-cfg]").forEach((el) => {
    updates[el.dataset.cfg] = el.type === "checkbox" ? el.checked : el.value;
  });
  btn.disabled = true;
  $("cfg-msg").textContent = "⏳ กำลังบันทึก...";
  try {
    const r = await api("/api/config", "POST", { updates });
    $("cfg-msg").textContent = `✅ บันทึกแล้ว (${r.updated.length} ค่า)` +
      (r.skipped.length ? ` — ข้าม ${r.skipped.length}` : "");
    refreshStatus();
  } catch (e) {
    $("cfg-msg").textContent = "❌ " + e.message;
  } finally {
    btn.disabled = false;
  }
}

$("btn-save-config").onclick = (e) => saveConfig(e.currentTarget);
$("btn-save-config2").onclick = (e) => saveConfig(e.currentTarget);
$("btn-refresh-meta").onclick = loadComfyMeta;
$("cfg-agents.provider").onchange = updateProviderHint;
["cfg-postprocess.target_width", "cfg-postprocess.target_height", "cfg-postprocess.dpi",
 "cfg-generation.width", "cfg-generation.height"].forEach((id) => {
  $(id).addEventListener("input", () => { markActivePresets(); updateDimReadout(); });
});

// ---------- Store (admin) ----------
let storeSources = [];
const MODE_LABEL = { mock: "โหมดทดสอบ (ไม่มีคีย์ Stripe)", test: "Stripe TEST", live: "Stripe LIVE (เก็บเงินจริง)" };

async function loadStore() {
  // status
  try {
    const s = await api("/api/store/status");
    $("store-mode").textContent = MODE_LABEL[s.mode] || s.mode;
    $("store-mode").className = "badge" + (s.mode === "live" ? "" : " alt");
    $("store-status").innerHTML = `โหมด: <b>${MODE_LABEL[s.mode] || s.mode}</b> • ` +
      `สินค้า ${s.products} (เปิดขาย ${s.active}) • คำสั่งซื้อ ${s.orders} (จ่ายแล้ว ${s.paid})` +
      (s.mode === "mock" ? `<br><span style="color:#fca5a5;">ยังไม่ได้ตั้งคีย์ Stripe — ใส่ใน credentials.yaml (stripe.secret_key) เพื่อรับเงินจริง</span>` : "");
  } catch (e) { $("store-status").textContent = "❌ " + e.message; }
  // sources dropdown
  try {
    const d = await api("/api/store/sources");
    storeSources = d.sources || [];
    $("sp-source").innerHTML = `<option value="">— เลือกไฟล์ —</option>` +
      storeSources.map((s, i) => `<option value="${i}">[${s.kind === "pdf" ? "PDF" : "ดีไซน์"}] ${esc(s.title)}</option>`).join("");
  } catch (e) { /* ignore */ }
  loadStoreProducts();
  loadStoreOrders();
}

$("sp-source").onchange = () => {
  const i = $("sp-source").value;
  if (i === "") return;
  const s = storeSources[+i];
  $("sp-file").value = s.file;
  $("sp-preview").value = s.preview || "";
  if (!$("sp-title").value) $("sp-title").value = s.title.replace(/\.pdf$/i, "");
  $("sp-filehint").textContent = "ไฟล์ที่ลูกค้าจะได้: " + s.file + (s.pages ? ` (${s.pages} หน้า)` : "");
};

async function loadStoreProducts() {
  const d = await api("/api/store/products");
  const items = d.products || [];
  if (!items.length) { $("store-products").innerHTML = '<p class="empty">ยังไม่มีสินค้า — เพิ่มด้านบน</p>'; return; }
  $("store-products").innerHTML = items.map((p) => `
    <div class="item">
      <button class="del-btn" data-id="${esc(p.id)}" title="ลบ"><i data-lucide="trash-2"></i></button>
      <div class="ebook-thumb" style="aspect-ratio:1;">${p.preview ? `<img src="/${esc(p.preview)}" style="width:100%;height:100%;object-fit:cover;" />` : '<i data-lucide="file-text"></i>'}</div>
      <div class="cap">
        <b>${esc(p.title)}</b>
        ${p.price} ${esc((p.currency||"thb").toUpperCase())} • ${p.active ? "🟢 เปิดขาย" : "⚪ ปิด"}
        <div style="margin-top:8px;"><button class="sp-edit" data-id="${esc(p.id)}" style="padding:6px 12px;font-size:12px;">แก้ไข</button></div>
      </div>
    </div>`).join("");
  if (window.lucide) lucide.createIcons();
  document.querySelectorAll("#store-products .sp-edit").forEach((b) => {
    b.onclick = () => { const p = items.find((x) => x.id === b.dataset.id); editProduct(p); };
  });
  document.querySelectorAll("#store-products .del-btn").forEach((b) => {
    b.onclick = async () => {
      if (!confirm("ลบสินค้านี้?")) return;
      await api("/api/store/products/delete", "POST", { id: b.dataset.id });
      loadStore();
    };
  });
}

function editProduct(p) {
  if (!p) return;
  $("sp-id").value = p.id; $("sp-title").value = p.title; $("sp-desc").value = p.description || "";
  $("sp-price").value = p.price; $("sp-currency").value = p.currency || "thb";
  $("sp-file").value = p.file; $("sp-preview").value = p.preview || "";
  $("sp-active").checked = !!p.active;
  $("sp-filehint").textContent = "ไฟล์: " + p.file;
  $("sp-msg").textContent = "กำลังแก้ไข: " + p.title;
  $("store").scrollIntoView({ behavior: "smooth" });
}
function resetProductForm() {
  ["sp-id", "sp-title", "sp-desc", "sp-price", "sp-file", "sp-preview"].forEach((id) => ($(id).value = ""));
  $("sp-currency").value = "thb"; $("sp-active").checked = true; $("sp-source").value = "";
  $("sp-filehint").textContent = ""; $("sp-msg").textContent = "";
}
$("sp-reset").onclick = resetProductForm;

$("sp-save").onclick = async () => {
  const product = {
    id: $("sp-id").value || undefined,
    title: $("sp-title").value.trim(),
    description: $("sp-desc").value.trim(),
    price: $("sp-price").value,
    currency: $("sp-currency").value.trim() || "thb",
    file: $("sp-file").value.trim(),
    preview: $("sp-preview").value.trim(),
    active: $("sp-active").checked,
  };
  if (!product.title || !product.file) { $("sp-msg").textContent = "❌ ต้องมีชื่อสินค้าและเลือกไฟล์ต้นทาง"; return; }
  if (!product.price || +product.price <= 0) { $("sp-msg").textContent = "❌ ใส่ราคาให้ถูกต้อง"; return; }
  $("sp-save").disabled = true;
  try {
    await api("/api/store/products", "POST", { product });
    $("sp-msg").textContent = "✅ บันทึกแล้ว";
    resetProductForm();
    loadStore();
  } catch (e) { $("sp-msg").textContent = "❌ " + e.message; }
  finally { $("sp-save").disabled = false; }
};

async function loadStoreOrders() {
  const d = await api("/api/store/orders");
  const items = d.items || [];
  if (!items.length) { $("store-orders").innerHTML = '<p class="empty">ยังไม่มีคำสั่งซื้อ</p>'; return; }
  $("store-orders").innerHTML = `<table><tr><th>เวลา</th><th>สถานะ</th><th>ยอด</th><th>อีเมล</th><th>สินค้า</th></tr>` +
    items.map((o) => `<tr>
      <td>${esc((o.created_at || "").replace("T", " ").slice(0, 16))}</td>
      <td>${o.status === "paid" ? '<span style="color:var(--ok)">จ่ายแล้ว</span>' : '<span style="color:var(--muted)">รอจ่าย</span>'}</td>
      <td>${o.amount_total} ${esc((o.currency || "thb").toUpperCase())}</td>
      <td>${esc(o.email || "-")}</td>
      <td>${esc((o.items || []).map((i) => i.title).join(", "))}</td>
    </tr>`).join("") + `</table>`;
}

// ---------- init ----------
populateAiOptions();
refreshStatus();
setInterval(refreshStatus, 15000);
