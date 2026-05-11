// SubSync Studio — frontend logic
const $ = (sel) => document.querySelector(sel);
const state = {
  files: { video: null, sub: null, ref: null },
  session: null,
  outputFile: null,
  previewVtt: null,
  cues: [],
};

// ---------------------------------------------------------------------------
// Drag & drop
// ---------------------------------------------------------------------------
function bindDrop(zoneId, inputId, nameId, key) {
  const zone = $("#" + zoneId);
  const input = $("#" + inputId);
  const name = $("#" + nameId);

  const setFile = (file) => {
    state.files[key] = file;
    name.textContent = file ? file.name : "لم يُختر ملف";
    if (key === "video" && file) {
      const url = URL.createObjectURL(file);
      const player = $("#player");
      player.src = url;
      $("#preview-card").classList.remove("hidden");
    }
  };

  zone.addEventListener("click", () => input.click());
  input.addEventListener("change", (e) => setFile(e.target.files[0] || null));

  ["dragover", "dragenter"].forEach((ev) =>
    zone.addEventListener(ev, (e) => {
      e.preventDefault();
      zone.classList.add("dragover");
    })
  );
  ["dragleave", "drop"].forEach((ev) =>
    zone.addEventListener(ev, (e) => {
      e.preventDefault();
      zone.classList.remove("dragover");
    })
  );
  zone.addEventListener("drop", (e) => {
    const f = e.dataTransfer.files[0];
    if (f) setFile(f);
  });
}

bindDrop("drop-video", "file-video", "name-video", "video");
bindDrop("drop-sub", "file-sub", "name-sub", "sub");
bindDrop("drop-ref", "file-ref", "name-ref", "ref");

// ---------------------------------------------------------------------------
// Health badge
// ---------------------------------------------------------------------------
async function refreshHealth() {
  try {
    const r = await fetch("/api/health");
    const h = await r.json();
    const badge = (label, ok) =>
      `<span class="${ok ? "ok" : "bad"}">${ok ? "●" : "○"} ${label}</span>`;
    $("#health").innerHTML =
      badge("ffsubsync", h.ffsubsync) +
      badge("ffmpeg", h.ffmpeg) +
      badge("OpenSubtitles", h.opensubtitles);
  } catch {
    $("#health").innerHTML = '<span class="bad">الخادم غير متصل</span>';
  }
}
refreshHealth();

// ---------------------------------------------------------------------------
// Sync flow
// ---------------------------------------------------------------------------
function msToTime(ms) {
  const h = Math.floor(ms / 3600000);
  const m = Math.floor((ms % 3600000) / 60000);
  const s = Math.floor((ms % 60000) / 1000);
  const cs = ms % 1000;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}.${String(cs).padStart(3, "0")}`;
}
function timeToMs(str) {
  const m = str.trim().match(/^(\d{1,2}):(\d{2}):(\d{2})[.,](\d{1,3})$/);
  if (!m) return null;
  return (+m[1]) * 3600000 + (+m[2]) * 60000 + (+m[3]) * 1000 + (+m[4]);
}

function setStatus(text, cls = "") {
  const el = $("#status");
  el.textContent = text;
  el.className = "status " + cls;
}

$("#btn-sync").addEventListener("click", async () => {
  if (!state.files.sub) {
    setStatus("ارفع ملف الترجمة أولاً.", "error");
    return;
  }
  if (!state.files.video && !state.files.ref) {
    setStatus("ارفع فيديو أو ترجمة مرجعية.", "error");
    return;
  }

  const fd = new FormData();
  fd.append("subtitle", state.files.sub);
  if (state.files.video) fd.append("video", state.files.video);
  if (state.files.ref) fd.append("reference", state.files.ref);

  $("#btn-sync").disabled = true;
  setStatus("جاري التحليل والمزامنة... قد يستغرق دقيقة على الفيديوهات الطويلة.", "working");

  try {
    const r = await fetch("/api/sync", { method: "POST", body: fd });
    if (!r.ok) {
      const err = await r.json().catch(() => ({ detail: "خطأ غير معروف" }));
      throw new Error(err.detail || "فشلت المزامنة");
    }
    const data = await r.json();
    state.session = data.session_id;
    state.outputFile = data.output_file;
    state.previewVtt = data.preview_vtt;
    state.cues = data.cues;

    setStatus(`✓ تمت المزامنة بنجاح (${data.method}).`, "success");
    $("#method-info").classList.remove("hidden");
    $("#method-info").textContent =
      data.method === "audio-vad"
        ? "تمت المزامنة عبر تحليل الصوت — تطابق دقيق على طول الفيديو حتى لو اختلفت النسخ."
        : "تمت المزامنة عبر ترجمة مرجعية متزامنة مسبقاً.";

    attachPreviewTrack();
    renderEditor();
    refreshDownloadLink();
    $("#editor-card").classList.remove("hidden");
  } catch (e) {
    setStatus("✗ " + e.message, "error");
  } finally {
    $("#btn-sync").disabled = false;
  }
});

// ---------------------------------------------------------------------------
// Video preview with subtitles
// ---------------------------------------------------------------------------
function attachPreviewTrack() {
  const player = $("#player");
  // remove old tracks
  Array.from(player.querySelectorAll("track")).forEach((t) => t.remove());
  if (!state.session || !state.previewVtt) return;

  const track = document.createElement("track");
  track.kind = "subtitles";
  track.label = "Synced";
  track.srclang = "ar";
  track.default = true;
  track.src = `/api/download/${state.session}/${state.previewVtt}`;
  player.appendChild(track);

  $("#preview-card").classList.remove("hidden");
}

// ---------------------------------------------------------------------------
// Editor
// ---------------------------------------------------------------------------
function renderEditor() {
  const tbody = $("#cues-table tbody");
  tbody.innerHTML = "";
  state.cues.forEach((cue, i) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td class="idx">${i + 1}</td>
      <td class="time"><input data-i="${i}" data-k="start" value="${msToTime(cue.start_ms)}" /></td>
      <td class="time"><input data-i="${i}" data-k="end"   value="${msToTime(cue.end_ms)}" /></td>
      <td><textarea rows="2" data-i="${i}" data-k="text">${cue.text}</textarea></td>
    `;
    tbody.appendChild(tr);
  });

  tbody.addEventListener("input", (ev) => {
    const el = ev.target;
    const i = +el.dataset.i;
    const k = el.dataset.k;
    if (!state.cues[i]) return;
    if (k === "text") {
      state.cues[i].text = el.value;
    } else {
      const ms = timeToMs(el.value);
      if (ms != null) state.cues[i][k === "start" ? "start_ms" : "end_ms"] = ms;
    }
  });
}

$("#btn-shift-back").addEventListener("click", () => shiftAll(-500));
$("#btn-shift-fwd").addEventListener("click", () => shiftAll(500));
function shiftAll(deltaMs) {
  state.cues.forEach((c) => {
    c.start_ms = Math.max(0, c.start_ms + deltaMs);
    c.end_ms = Math.max(0, c.end_ms + deltaMs);
  });
  renderEditor();
}

$("#btn-save").addEventListener("click", async () => {
  if (!state.session) return;
  setStatus("جاري حفظ التعديلات...", "working");
  try {
    const r = await fetch("/api/save", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: state.session,
        file_name: state.outputFile,
        cues: state.cues,
        output_format: $("#output-format").value,
      }),
    });
    if (!r.ok) throw new Error((await r.json()).detail);
    const data = await r.json();
    state.outputFile = data.file_name;
    state.previewVtt = data.preview_vtt;
    attachPreviewTrack();
    refreshDownloadLink();
    setStatus("✓ تم الحفظ.", "success");
  } catch (e) {
    setStatus("✗ " + e.message, "error");
  }
});

function refreshDownloadLink() {
  const fmt = $("#output-format").value;
  const link = $("#btn-download");
  if (!state.session || !state.outputFile) {
    link.removeAttribute("href");
    return;
  }
  link.href = `/api/download/${state.session}/${state.outputFile}?fmt=${fmt}`;
  link.textContent = `⬇️ تحميل (.${fmt})`;
}
$("#output-format").addEventListener("change", refreshDownloadLink);

// ---------------------------------------------------------------------------
// OpenSubtitles search
// ---------------------------------------------------------------------------
$("#btn-search").addEventListener("click", async () => {
  const q = $("#search-q").value.trim();
  const langs = $("#search-langs").value.trim() || "en,ar";
  const box = $("#search-results");
  if (!q) {
    box.innerHTML = '<div class="search-hit">أدخل اسم الفيلم/المسلسل أولاً.</div>';
    return;
  }
  box.innerHTML = '<div class="search-hit">جاري البحث...</div>';
  try {
    const r = await fetch(`/api/search?q=${encodeURIComponent(q)}&languages=${encodeURIComponent(langs)}`);
    if (!r.ok) throw new Error((await r.json()).detail);
    const data = await r.json();
    if (!data.hits.length) {
      box.innerHTML = '<div class="search-hit">لا نتائج.</div>';
      return;
    }
    box.innerHTML = "";
    data.hits.forEach((hit) => {
      const div = document.createElement("div");
      div.className = "search-hit";
      div.innerHTML = `
        <div>
          <strong>${hit.movie_name || "—"}</strong>
          <div class="meta">${hit.language} • ${hit.release || ""} • تحميلات: ${hit.download_count}</div>
        </div>
        <button data-fid="${hit.file_id}">استخدم كترجمة</button>
      `;
      box.appendChild(div);
    });
    box.addEventListener("click", onSearchPick, { once: true });
  } catch (e) {
    box.innerHTML = `<div class="search-hit">خطأ: ${e.message}</div>`;
  }
});

async function onSearchPick(ev) {
  const btn = ev.target.closest("button[data-fid]");
  if (!btn) return;
  const fid = btn.dataset.fid;
  setStatus("جاري تحميل الترجمة من OpenSubtitles...", "working");
  try {
    const fd = new FormData();
    fd.append("file_id", fid);
    const r = await fetch("/api/fetch", { method: "POST", body: fd });
    if (!r.ok) throw new Error((await r.json()).detail);
    const data = await r.json();
    const f = await fetch(`/api/fetched/${data.session_id}/${data.file_name}`);
    const blob = await f.blob();
    const file = new File([blob], data.file_name);
    state.files.sub = file;
    $("#name-sub").textContent = file.name;
    setStatus("✓ تم تحميل الترجمة. اضغط 'مزامنة الآن'.", "success");
  } catch (e) {
    setStatus("✗ " + e.message, "error");
  }
}
