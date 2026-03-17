const API = {
  models: "/api/models",
  estimate: "/api/estimate",
  run: "/api/run",
  outputs: "/api/outputs",
  workflows: "/api/workflows",
};

let state = {
  steps: [],
  models: [],
  costBreakdown: null,
  totalCost: 0,
  threshold: 5,
  confirmed: false,
  running: false,
  loadedProcedureName: null,
};

const VIDEO_MODEL_CAPS = {
  "fal-ai/kling-video/v3/pro/image-to-video": {
    durations: ["3", "4", "5", "6", "7", "8", "9", "10", "11", "12", "13", "14", "15"],
    defaultDuration: "5",
    aspectRatios: ["16:9", "9:16", "1:1"],
    defaultAspectRatio: "16:9",
    resolutions: null,
    defaultResolution: null,
    supportsAudio: true,
    defaultAudio: true,
  },
  "fal-ai/kling-video/v2.6/pro/image-to-video": {
    durations: ["5", "10"],
    defaultDuration: "5",
    aspectRatios: null,
    defaultAspectRatio: null,
    resolutions: null,
    defaultResolution: null,
    supportsAudio: true,
    defaultAudio: true,
  },
  "fal-ai/minimax-video/image-to-video": {
    durations: null,
    defaultDuration: null,
    aspectRatios: null,
    defaultAspectRatio: null,
    resolutions: null,
    defaultResolution: null,
    supportsAudio: false,
  },
  "fal-ai/wan/v2.2-a14b/text-to-video": {
    durations: ["4", "5", "6", "7", "8", "9", "10"],
    defaultDuration: "5",
    aspectRatios: ["16:9", "9:16", "1:1"],
    defaultAspectRatio: "16:9",
    resolutions: ["480p", "580p", "720p"],
    defaultResolution: "720p",
    supportsAudio: false,
  },
  "fal-ai/bytedance/seedance/v1/pro/text-to-video": {
    durations: ["2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12"],
    defaultDuration: "5",
    aspectRatios: ["21:9", "16:9", "4:3", "1:1", "3:4", "9:16"],
    defaultAspectRatio: "16:9",
    resolutions: ["480p", "720p", "1080p"],
    defaultResolution: "1080p",
    supportsAudio: false,
  },
  "fal-ai/bytedance/seedance/v1/pro/image-to-video": {
    durations: ["2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12"],
    defaultDuration: "5",
    aspectRatios: ["21:9", "16:9", "4:3", "1:1", "3:4", "9:16"],
    defaultAspectRatio: "16:9",
    resolutions: ["480p", "720p", "1080p"],
    defaultResolution: "1080p",
    supportsAudio: false,
  },
  "fal-ai/sora-2/image-to-video": {
    durations: ["4", "8", "12", "16", "20"],
    defaultDuration: "4",
    aspectRatios: ["9:16", "16:9"],
    defaultAspectRatio: "16:9",
    resolutions: ["720p"],
    defaultResolution: "720p",
    supportsAudio: false,
  },
  "fal-ai/sora-2/text-to-video": {
    durations: ["4", "8", "12", "16", "20"],
    defaultDuration: "4",
    aspectRatios: ["9:16", "16:9"],
    defaultAspectRatio: "16:9",
    resolutions: ["720p"],
    defaultResolution: "720p",
    supportsAudio: false,
  },
  "fal-ai/veo3.1/reference-to-video": {
    durations: ["4", "6", "8"],
    defaultDuration: "8",
    aspectRatios: ["16:9", "9:16"],
    defaultAspectRatio: "16:9",
    resolutions: ["720p", "1080p", "4k"],
    defaultResolution: "720p",
    supportsAudio: true,
    defaultAudio: true,
  },
  "fal-ai/veo3.1/image-to-video": {
    durations: ["4", "6", "8"],
    defaultDuration: "8",
    aspectRatios: ["16:9", "9:16"],
    defaultAspectRatio: "16:9",
    resolutions: ["720p", "1080p", "4k"],
    defaultResolution: "720p",
    supportsAudio: true,
    defaultAudio: true,
  },
  "fal-ai/veo3.1/fast/image-to-video": {
    durations: ["4", "6", "8"],
    defaultDuration: "8",
    aspectRatios: ["16:9", "9:16"],
    defaultAspectRatio: "16:9",
    resolutions: ["720p", "1080p", "4k"],
    defaultResolution: "720p",
    supportsAudio: true,
    defaultAudio: true,
  },
};

function el(id) {
  return document.getElementById(id);
}

async function fetchModels() {
  const res = await fetch(API.models);
  const data = await res.json();
  state.models = data.models || [];
  return state.models;
}

function buildWorkflow() {
  return { steps: state.steps.map(s => ({ ...s })) };
}

function renderSteps() {
  const container = el("steps");
  if (state.steps.length === 0) {
    container.innerHTML = '<p class="hint">No steps. Click "Add step" to start.</p>';
    return;
  }
  container.innerHTML = state.steps.map((s, i) => `
    <div class="step-card" data-index="${i}">
      <div class="step-info">
        <span class="step-name">${i + 1}. ${s.name}</span>
        <span class="step-meta">${s.type} → ${s.output_key}</span>
      </div>
      <div class="step-actions">
        <button class="edit-step btn" data-index="${i}" title="Edit">Edit</button>
        <button class="remove-step" data-index="${i}" title="Remove">×</button>
      </div>
    </div>
  `).join("");
  container.querySelectorAll(".remove-step").forEach(btn => {
    btn.onclick = () => removeStep(parseInt(btn.dataset.index));
  });
  container.querySelectorAll(".edit-step").forEach(btn => {
    btn.onclick = () => showEditStepModal(parseInt(btn.dataset.index));
  });
}

function addStep(step) {
  state.steps.push(step);
  state.costBreakdown = null;
  state.confirmed = false;
  renderSteps();
  updateRunButton();
}

function removeStep(index) {
  state.steps.splice(index, 1);
  state.costBreakdown = null;
  state.confirmed = false;
  renderSteps();
  updateRunButton();
}

function bindOutputClicks() {
  el("outputs-gallery")?.querySelectorAll(".output-thumb").forEach((el) => {
    el.onclick = () => showLightbox(el.dataset.url, el.dataset.type);
  });
}

function showLightbox(url, type) {
  const lb = document.getElementById("lightbox");
  const img = document.getElementById("lightbox-img");
  const video = document.getElementById("lightbox-video");
  img.classList.add("hidden");
  video.classList.add("hidden");
  if (type === "video") {
    video.src = url;
    video.classList.remove("hidden");
  } else {
    img.src = url;
    img.classList.remove("hidden");
  }
  lb.classList.remove("hidden");
}

function hideLightbox() {
  document.getElementById("lightbox").classList.add("hidden");
  const video = document.getElementById("lightbox-video");
  video.pause();
  video.src = "";
}

function updateRunButton() {
  const btn = el("run-btn");
  btn.disabled = state.steps.length === 0 || state.running;
  el("run-hint").textContent = state.costBreakdown
    ? "Click Run to confirm and execute."
    : "Estimate cost first, then run.";
}

function updateSaveButton() {
  const btn = el("save-btn");
  btn.textContent = state.loadedProcedureName ? "Save" : "Save new procedure";
}

function updateCurrentProcedureLabel() {
  const el = document.getElementById("current-procedure");
  if (el) el.textContent = state.loadedProcedureName || "New procedure";
}

async function refreshWorkflows() {
  try {
    const res = await fetch(API.workflows);
    const data = await res.json();
    const workflows = data.workflows || [];
    const menu = el("load-menu");
    menu.innerHTML = "";
    const newBtn = document.createElement("button");
    newBtn.textContent = "New procedure";
    newBtn.className = "load-item load-new";
    newBtn.onclick = () => {
      newProcedure();
      menu.classList.add("hidden");
    };
    menu.appendChild(newBtn);
    if (workflows.length === 0) {
      const empty = document.createElement("div");
      empty.className = "load-empty";
      empty.textContent = "No saved procedures";
      menu.appendChild(empty);
    } else {
      workflows.forEach((w) => {
        const row = document.createElement("div");
        row.className = "load-item-row";
        const loadBtn = document.createElement("button");
        loadBtn.textContent = w;
        loadBtn.className = "load-item";
        loadBtn.onclick = () => {
          loadWorkflow(w);
          menu.classList.add("hidden");
        };
        const renameBtn = document.createElement("button");
        renameBtn.textContent = "✎";
        renameBtn.className = "load-rename";
        renameBtn.title = "Rename procedure";
        renameBtn.onclick = (e) => {
          e.stopPropagation();
          renameWorkflow(w);
        };
        const delBtn = document.createElement("button");
        delBtn.textContent = "×";
        delBtn.className = "load-delete";
        delBtn.title = "Delete procedure";
        delBtn.onclick = (e) => {
          e.stopPropagation();
          if (confirm(`Delete procedure "${w}"?`)) deleteWorkflow(w);
        };
        row.appendChild(loadBtn);
        row.appendChild(renameBtn);
        row.appendChild(delBtn);
        menu.appendChild(row);
      });
    }
  } catch (e) {
    console.error("Failed to load procedures:", e);
  }
}

function newProcedure() {
  state.steps = [];
  state.loadedProcedureName = null;
  state.costBreakdown = null;
  state.confirmed = false;
  renderSteps();
  updateRunButton();
  updateSaveButton();
  updateCurrentProcedureLabel();
  showCost("");
}

async function renameWorkflow(name) {
  const newName = prompt("New name for procedure:", name);
  if (!newName || newName.trim() === name) return;
  try {
    const res = await fetch(`${API.workflows}/${encodeURIComponent(name)}/rename`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ new_name: newName.trim() }),
    });
    if (!res.ok) {
      const err = await res.json();
      alert("Rename failed: " + (err.detail || res.statusText));
      return;
    }
    const data = await res.json();
    if (state.loadedProcedureName === name) {
      state.loadedProcedureName = data.renamed_to;
      updateSaveButton();
      updateCurrentProcedureLabel();
    }
    refreshWorkflows();
  } catch (e) {
    alert("Rename failed: " + e.message);
  }
}

async function deleteWorkflow(name) {
  try {
    const res = await fetch(`${API.workflows}/${encodeURIComponent(name)}`, { method: "DELETE" });
    if (!res.ok) {
      const err = await res.json();
      alert("Delete failed: " + (err.detail || res.statusText));
      return;
    }
    if (state.loadedProcedureName === name) {
      state.loadedProcedureName = null;
      state.steps = [];
      renderSteps();
      updateRunButton();
      updateSaveButton();
      updateCurrentProcedureLabel();
    }
    refreshWorkflows();
  } catch (e) {
    alert("Delete failed: " + e.message);
  }
}

async function toggleLoadMenu() {
  const menu = el("load-menu");
  if (menu.classList.contains("hidden")) {
    await refreshWorkflows();
    menu.classList.remove("hidden");
    const close = (e) => {
      if (!el("load-btn").contains(e.target) && !menu.contains(e.target)) {
        menu.classList.add("hidden");
        document.removeEventListener("click", close);
      }
    };
    setTimeout(() => document.addEventListener("click", close), 0);
  } else {
    menu.classList.add("hidden");
  }
}

async function saveWorkflow() {
  if (state.steps.length === 0) {
    showCost("Add at least one step before saving.");
    return;
  }
  if (state.loadedProcedureName) {
    try {
      const res = await fetch(`${API.workflows}/save`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: state.loadedProcedureName,
          workflow: buildWorkflow(),
          overwrite: true,
        }),
      });
      if (!res.ok) {
        const err = await res.json();
        alert("Save failed: " + (err.detail || res.statusText));
        return;
      }
      el("run-hint").textContent = `Saved ${state.loadedProcedureName}`;
      refreshWorkflows();
    } catch (e) {
      alert("Save failed: " + e.message);
    }
    return;
  }
  const modal = el("save-modal");
  el("save-modal-title").textContent = "Save new procedure";
  el("save-name").value = state.steps[0] ? (state.steps[0].name || "procedure").replace(/\s+/g, "_").toLowerCase() : "procedure";
  modal.classList.remove("hidden");

  el("save-ok").onclick = async () => {
    const name = el("save-name").value.trim() || "procedure";
    try {
      const res = await fetch(`${API.workflows}/save`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, workflow: buildWorkflow(), overwrite: false }),
      });
      if (!res.ok) {
        const err = await res.json();
        alert("Save failed: " + (err.detail || res.statusText));
        return;
      }
      const data = await res.json();
      modal.classList.add("hidden");
      state.loadedProcedureName = data.saved_as;
      updateSaveButton();
      updateCurrentProcedureLabel();
      el("run-hint").textContent = `Saved as ${data.saved_as}`;
      refreshWorkflows();
    } catch (e) {
      alert("Save failed: " + e.message);
    }
  };
  el("save-cancel").onclick = () => modal.classList.add("hidden");
}

async function loadWorkflow(name) {
  if (!name) return;
  try {
    const res = await fetch(`${API.workflows}/${encodeURIComponent(name)}`);
    if (!res.ok) {
      const err = await res.json();
      alert("Load failed: " + (err.detail || res.statusText));
      return;
    }
    const data = await res.json();
    state.steps = data.steps || [];
    state.loadedProcedureName = name;
    state.costBreakdown = null;
    state.confirmed = false;
    renderSteps();
    updateRunButton();
    updateSaveButton();
    updateCurrentProcedureLabel();
    showCost("");
  } catch (e) {
    alert("Load failed: " + e.message);
  }
}

async function estimateCost() {
  if (state.steps.length === 0) {
    showCost("Add at least one step.");
    return;
  }
  try {
    const res = await fetch(API.estimate, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ workflow: buildWorkflow(), confirmed: false }),
    });
    if (!res.ok) {
      const err = await res.json();
      showCost("Error: " + (err.detail || res.statusText));
      return;
    }
    const data = await res.json();
    state.costBreakdown = data.breakdown;
    state.totalCost = data.total;
    state.threshold = data.threshold || 5;
    renderCost(data);
  } catch (e) {
    showCost("Failed to estimate: " + e.message);
  }
}

function showCost(msg) {
  el("cost-display").innerHTML = `<span class="total">${msg}</span>`;
}

function renderCost(data) {
  const lines = (data.breakdown || []).map(b => `${b.name}: $${b.cost.toFixed(4)}`);
  lines.push("─".repeat(40));
  lines.push(`Total: $${data.total.toFixed(4)}`);
  el("cost-display").innerHTML = lines.map(l => `<div>${l}</div>`).join("") +
    `<div class="total">Estimate ready. Click "Run procedure" to confirm.</div>`;
}

function showConfirmModal() {
  const total = state.totalCost;
  const aboveThreshold = total > state.threshold;
  const modal = el("modal");
  const body = el("modal-body");
  el("modal-title").textContent = "Confirm cost";
  body.innerHTML = `
    <p>Estimated cost: <strong>$${total.toFixed(2)}</strong></p>
    ${aboveThreshold ? `<p>Above $${state.threshold} limit. Type the amount to confirm:</p>
      <input type="text" id="confirm-input" placeholder="$${total.toFixed(2)}" style="width:100%;padding:0.5rem;margin-top:0.5rem;">` : ""}
  `;
  modal.classList.remove("hidden");

  const doConfirm = () => {
    if (aboveThreshold) {
      const input = el("confirm-input");
      const expected = `$${total.toFixed(2)}`;
      if (input.value.trim() !== expected) {
        return;
      }
    }
    state.confirmed = true;
    modal.classList.add("hidden");
    updateRunButton();
    runWorkflow();
  };

  el("modal-confirm").onclick = doConfirm;
  el("modal-cancel").onclick = () => modal.classList.add("hidden");
}

async function runWorkflow() {
  if (!state.confirmed || state.running) return;
  state.running = true;
  let runCompleted = false;
  let runErrored = false;
  el("run-btn").disabled = true;
  el("progress-panel").classList.remove("hidden");
  el("outputs-panel").classList.add("hidden");
  const progressSteps = el("progress-steps");
  const progressLog = el("progress-log");
  progressSteps.innerHTML = state.steps.map((s, i) =>
    `<div class="progress-step" id="ps-${i}">${i + 1}. ${s.name} — waiting</div>`
  ).join("");
  progressLog.innerHTML = "";
  state.outputMedia = [];

  const log = (msg) => {
    progressLog.innerHTML += msg + "\n";
    progressLog.scrollTop = progressLog.scrollHeight;
  };

  try {
    const res = await fetch(API.run, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        workflow: buildWorkflow(),
        confirmed: true,
        procedure_name: state.steps[0]?.name?.replace(/\s+/g, "_").toLowerCase() || "output",
      }),
    });
    if (!res.ok) {
      log("Error: " + res.statusText);
      state.running = false;
      updateRunButton();
      return;
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      const lines = buf.split("\n\n");
      buf = lines.pop() || "";
      for (const line of lines) {
        if (line.startsWith("event:")) {
          const eventMatch = line.match(/event:\s*(\S+)/);
          const dataMatch = line.match(/data:\s*(.+)/);
          const eventType = eventMatch ? eventMatch[1] : "message";
          const data = dataMatch ? JSON.parse(dataMatch[1]) : {};
          if (eventType === "step_start") {
            const el = document.getElementById(`ps-${data.step - 1}`);
            if (el) {
              el.textContent = `${data.step}. ${data.name} — running...`;
              el.classList.add("running");
            }
            log(`[${data.step}/${data.total}] ${data.name} started`);
          } else if (eventType === "step_end") {
            const el = document.getElementById(`ps-${data.step - 1}`);
            if (el) {
              el.textContent = `${data.step}. ${data.name} — done (${data.elapsed}s)`;
              el.classList.remove("running");
              el.classList.add("done");
            }
            log(`[${data.step}] ${data.name} completed in ${data.elapsed}s`);
            if (data.output) {
              if (data.output.images) {
                data.output.images.forEach(img => {
                  if (img && img.url) state.outputMedia.push({ type: "image", url: img.url });
                });
              }
              if (data.output.video) {
                const videoUrl = typeof data.output.video === "string"
                  ? data.output.video
                  : data.output.video.url;
                if (videoUrl) {
                  state.outputMedia.push({ type: "video", url: videoUrl });
                }
              }
            }
          } else if (eventType === "complete") {
            log("Procedure complete.");
            runCompleted = true;
          } else if (eventType === "error") {
            log("Error: " + (data.message || "Unknown"));
            runErrored = true;
          }
        }
      }
    }

    if (state.outputMedia && state.outputMedia.length > 0) {
      el("outputs-panel").classList.remove("hidden");
      const gallery = el("outputs-gallery");
      gallery.innerHTML = state.outputMedia.map((m, i) => {
        if (m.type === "video") {
          return `<video src="${m.url}" controls class="output-thumb" data-url="${m.url}" data-type="video"></video>`;
        }
        return `<img src="${m.url}" alt="output" class="output-thumb" data-url="${m.url}" data-type="image">`;
      }).join("");
      bindOutputClicks();
    } else if (runCompleted && !runErrored) {
      const outRes = await fetch(API.outputs);
      const outData = await outRes.json();
      if (outData.files && outData.files.length > 0) {
        el("outputs-panel").classList.remove("hidden");
        const gallery = el("outputs-gallery");
        gallery.innerHTML = outData.files.map(f => {
          const ext = (f.name || "").toLowerCase();
          if (ext.match(/\.(mp4|webm|mov)$/)) {
            return `<video src="${f.url}" controls class="output-thumb" data-url="${f.url}" data-type="video"></video>`;
          }
          return `<img src="${f.url}" alt="${f.name}" class="output-thumb" data-url="${f.url}" data-type="image">`;
        }).join("");
        bindOutputClicks();
      }
    } else {
      // Prevent displaying stale outputs from previous runs on failed executions.
      el("outputs-panel").classList.add("hidden");
    }
  } catch (e) {
    runErrored = true;
    log("Error: " + e.message);
    el("outputs-panel").classList.add("hidden");
  }
  state.running = false;
  updateRunButton();
}

function resetStepModalFields() {
  el("new-step-name").value = "";
  el("new-step-output-key").value = "";
  el("new-step-prompt").value = "";
  el("new-step-from-key").value = "";
  el("new-step-llm-model").value = "";
  el("new-step-num-images").value = "1";
  el("new-step-seed").value = "";
  el("new-step-aspect-ratio").value = "auto";
  el("new-step-resolution").value = "1K";
  el("new-step-output-format").value = "png";
  el("new-step-safety-tolerance").value = "4";
  el("new-step-video-aspect-ratio").value = "16:9";
  el("new-step-video-resolution").value = "720p";
  el("new-step-video-duration").value = "5";
  el("new-step-video-generate-audio").checked = true;
  el("new-step-video-image-source").value = "";
  el("new-step-video-image-url").value = "";
}

function populateStepModalFromStep(step) {
  el("new-step-name").value = step.name || "";
  el("new-step-output-key").value = step.output_key || "";
  const params = step.params || {};
  el("new-step-prompt").value = params.prompt || "";
  el("new-step-from-key").value = params.from_key || "";
  el("new-step-llm-model").value = params.model || "";
  el("new-step-num-images").value = String(params.num_images ?? 1);
  el("new-step-seed").value = params.seed !== undefined && params.seed !== null ? String(params.seed) : "";
  el("new-step-aspect-ratio").value = params.aspect_ratio || "auto";
  el("new-step-resolution").value = params.resolution || "1K";
  el("new-step-output-format").value = params.output_format || "png";
  el("new-step-safety-tolerance").value = String(params.safety_tolerance ?? 4);
  el("new-step-video-aspect-ratio").value = String(params.aspect_ratio || "16:9");
  el("new-step-video-resolution").value = String(params.resolution || "720p");
  const durationVal = params.duration !== undefined ? String(params.duration).replace("s", "") : "5";
  el("new-step-video-duration").value = durationVal;
  el("new-step-video-generate-audio").checked = params.generate_audio !== false;
  const imgSource = el("new-step-video-image-source");
  const urlInput = el("new-step-video-image-url");
  if (params.output_image) {
    imgSource.value = params.output_image;
    urlInput.value = "";
    urlInput.classList.add("hidden");
  } else if (params.image_url) {
    imgSource.value = "url";
    urlInput.value = params.image_url;
    urlInput.classList.remove("hidden");
  } else {
    imgSource.value = "";
    urlInput.value = "";
    urlInput.classList.add("hidden");
  }
}

function getParamsFromStepModal(type) {
  const params = {};
  if (type === "custom") {
    params.from_key = el("new-step-from-key").value.trim() || "generated_image";
    return params;
  }
  params.prompt = el("new-step-prompt").value.trim() || (type === "ai_image" ? "A beautiful image" : "");
  if (type === "ai_text") {
    const m = el("new-step-llm-model").value.trim();
    if (m) params.model = m;
  }
  if (type === "ai_image") {
    const n = parseInt(el("new-step-num-images").value, 10);
    params.num_images = isNaN(n) || n < 1 ? 1 : n;
    const seedVal = el("new-step-seed").value.trim();
    if (seedVal) {
      const s = parseInt(seedVal, 10);
      if (!isNaN(s)) params.seed = s;
    }
    params.aspect_ratio = el("new-step-aspect-ratio").value || "auto";
    params.resolution = el("new-step-resolution").value || "1K";
    params.output_format = el("new-step-output-format").value || "png";
    params.safety_tolerance = String(el("new-step-safety-tolerance").value || "4");
  }
  if (type === "ai_video") {
    const modelId = el("new-step-model").value;
    const caps = getVideoModelCaps(modelId);
    const ar = el("new-step-video-aspect-ratio").value;
    const res = el("new-step-video-resolution").value;
    const duration = el("new-step-video-duration").value;
    if (caps.aspectRatios && ar) params.aspect_ratio = ar;
    if (caps.resolutions && res) params.resolution = res;
    const normalizedDuration = normalizeVideoDurationForModel(modelId, duration);
    if (caps.durations && normalizedDuration !== null) {
      if (modelId === "fal-ai/wan/v2.2-a14b/text-to-video") {
        const sec = parseInt(String(normalizedDuration), 10);
        if (!isNaN(sec)) {
          params.frames_per_second = 16;
          params.num_frames = sec * 16 + 1;
        }
      } else {
        params.duration = normalizedDuration;
      }
    }
    if (caps.supportsAudio) {
      params.generate_audio = el("new-step-video-generate-audio").checked;
    }
    const source = el("new-step-video-image-source").value;
    if (source === "url") {
      const url = el("new-step-video-image-url").value.trim();
      if (url) params.image_url = url;
    } else if (source) {
      params.output_image = source;
    }
  }
  return params;
}

function getModelsForStepType(type) {
  if (type === "ai_image") return state.models.filter(m => m.type === "image");
  if (type === "ai_text") return state.models.filter(m => m.type === "text");
  if (type === "ai_video") return state.models.filter(m => m.type === "video");
  return [];
}

function getVideoModelCaps(modelId) {
  return VIDEO_MODEL_CAPS[modelId] || {
    durations: ["4", "5", "6", "8", "10"],
    defaultDuration: "5",
    aspectRatios: ["21:9", "16:9", "4:3", "1:1", "3:4", "9:16"],
    defaultAspectRatio: "16:9",
    resolutions: ["480p", "720p", "1080p"],
    defaultResolution: "720p",
    supportsAudio: false,
    defaultAudio: false,
  };
}

function normalizeVideoDurationForModel(modelId, duration) {
  if (!duration) return null;
  const seconds = parseInt(duration, 10);
  if (isNaN(seconds)) return null;
  if (modelId && modelId.startsWith("fal-ai/veo3.1/")) return `${seconds}s`;
  if (modelId && modelId.startsWith("fal-ai/sora-2/")) return seconds;
  return String(seconds);
}

function repopulateSelect(selectEl, values, preferredValue) {
  if (!values || values.length === 0) return;
  const prev = preferredValue || selectEl.value;
  selectEl.innerHTML = "";
  values.forEach((v) => {
    const opt = document.createElement("option");
    opt.value = v;
    opt.textContent = v;
    selectEl.appendChild(opt);
  });
  if (values.includes(prev)) {
    selectEl.value = prev;
  } else if (values.length > 0) {
    selectEl.value = values[0];
  }
}

function populateVideoControls() {
  const modelId = el("new-step-model").value;
  const caps = getVideoModelCaps(modelId);
  const aspectGroup = el("video-aspect-ratio-group");
  const resolutionGroup = el("video-resolution-group");
  const durationGroup = el("video-duration-group");
  const audioGroup = el("video-audio-group");
  aspectGroup.classList.toggle("hidden", !caps.aspectRatios);
  resolutionGroup.classList.toggle("hidden", !caps.resolutions);
  durationGroup.classList.toggle("hidden", !caps.durations);
  audioGroup.classList.toggle("hidden", !caps.supportsAudio);
  repopulateSelect(el("new-step-video-aspect-ratio"), caps.aspectRatios, caps.defaultAspectRatio);
  repopulateSelect(el("new-step-video-resolution"), caps.resolutions, caps.defaultResolution);
  repopulateSelect(el("new-step-video-duration"), caps.durations, caps.defaultDuration);
  el("new-step-video-generate-audio").checked = !!caps.defaultAudio;
}

async function populateVideoImageSelect() {
  const select = el("new-step-video-image-source");
  const currentVal = select.value;
  select.innerHTML = '<option value="">None (text-to-video)</option>';
  try {
    const res = await fetch(API.outputs);
    const data = await res.json();
    const imageExt = /\.(png|jpe?g|webp|gif)$/i;
    const images = (data.files || []).filter(f => imageExt.test(f.name || ""));
    images.forEach(f => {
      const opt = document.createElement("option");
      opt.value = f.name;
      opt.textContent = f.name;
      select.appendChild(opt);
    });
    select.appendChild(new Option("Custom URL...", "url"));
    if (currentVal && [...select.options].some(o => o.value === currentVal)) {
      select.value = currentVal;
    }
  } catch (_) {}
}

function populateModelSelect(type, currentModelId) {
  const modelSelect = el("new-step-model");
  const models = getModelsForStepType(type);
  modelSelect.innerHTML = "";
  models.forEach(m => {
    const opt = document.createElement("option");
    opt.value = m.id;
    opt.textContent = m.id;
    modelSelect.appendChild(opt);
  });
  const hasCurrent = models.some(m => m.id === currentModelId);
  modelSelect.value = hasCurrent ? currentModelId : (models[0]?.id || "");
}

function toggleStepModalVisibility(type, isEdit, preserveModelId) {
  const typeSelect = el("new-step-type");
  typeSelect.disabled = !!isEdit;
  const t = type || typeSelect.value;
  el("new-step-model-group").classList.toggle("hidden", t === "custom");
  el("new-step-from-key-group").classList.toggle("hidden", t !== "custom");
  el("new-step-prompt-group").classList.toggle("hidden", t === "custom");
  el("new-step-llm-model-group").classList.toggle("hidden", t !== "ai_text");
  el("new-step-image-params-group").classList.toggle("hidden", t !== "ai_image");
  el("new-step-video-params-group").classList.toggle("hidden", t !== "ai_video");
  el("new-step-video-image-group").classList.toggle("hidden", t !== "ai_video");
  if (t !== "custom") {
    populateModelSelect(t, preserveModelId ?? el("new-step-model").value);
  }
  const promptInput = el("new-step-prompt");
  promptInput.placeholder = t === "ai_video" ? "Describe the video..." : t === "ai_image" ? "Describe the image..." : "Enter prompt...";
  if (t === "ai_video") {
    populateVideoControls();
    populateVideoImageSelect();
    el("new-step-model").onchange = () => {
      populateVideoControls();
    };
    const imgSource = el("new-step-video-image-source");
    const urlInput = el("new-step-video-image-url");
    const syncUrlVisibility = () => {
      urlInput.classList.toggle("hidden", imgSource.value !== "url");
    };
    imgSource.onchange = syncUrlVisibility;
    syncUrlVisibility();
  } else {
    el("new-step-model").onchange = null;
    el("new-step-video-image-url").classList.add("hidden");
  }
  if (t === "custom" && state.steps.length > 0 && !isEdit) {
    const last = state.steps[state.steps.length - 1];
    el("new-step-from-key").value = last.output_key || "generated_image";
  }
}

function showAddStepModal() {
  const modal = el("step-modal");
  el("step-modal-title").textContent = "Add step";
  el("step-modal-ok").textContent = "Add";
  resetStepModalFields();
  const typeSelect = el("new-step-type");
  toggleStepModalVisibility(null, false);
  typeSelect.onchange = () => toggleStepModalVisibility(null, false);
  modal.classList.remove("hidden");

  el("step-modal-ok").onclick = () => {
    const type = typeSelect.value;
    const name = el("new-step-name").value.trim() || "Step";
    const outputKey = el("new-step-output-key").value.trim() || "output";
    const step = {
      type,
      name,
      output_key: outputKey,
      params: getParamsFromStepModal(type),
    };
    if (type !== "custom") {
      const models = getModelsForStepType(type);
      step.model_id = el("new-step-model").value || models[0]?.id;
    } else {
      step.fn = "save_outputs";
    }
    addStep(step);
    modal.classList.add("hidden");
  };
  el("step-modal-cancel").onclick = () => modal.classList.add("hidden");
}

function showEditStepModal(index) {
  const step = state.steps[index];
  if (!step) return;
  const modal = el("step-modal");
  el("step-modal-title").textContent = "Edit step";
  el("step-modal-ok").textContent = "Save";
  resetStepModalFields();
  populateStepModalFromStep(step);
  const typeSelect = el("new-step-type");
  typeSelect.value = step.type || "ai_image";
  toggleStepModalVisibility(step.type, true, step.model_id);
  modal.classList.remove("hidden");

  el("step-modal-ok").onclick = () => {
    const type = step.type;
    const name = el("new-step-name").value.trim() || "Step";
    const outputKey = el("new-step-output-key").value.trim() || "output";
    const updated = {
      type,
      name,
      output_key: outputKey,
      params: getParamsFromStepModal(type),
    };
    if (type !== "custom") {
      const models = getModelsForStepType(type);
      updated.model_id = el("new-step-model").value || models[0]?.id;
    } else {
      updated.fn = "save_outputs";
    }
    state.steps[index] = updated;
    state.costBreakdown = null;
    state.confirmed = false;
    renderSteps();
    updateRunButton();
    modal.classList.add("hidden");
  };
  el("step-modal-cancel").onclick = () => modal.classList.add("hidden");
}

function init() {
  fetchModels();
  refreshWorkflows();
  renderSteps();
  updateSaveButton();
  updateCurrentProcedureLabel();
  document.getElementById("lightbox-close").onclick = hideLightbox;
  document.getElementById("lightbox").onclick = (e) => {
    if (e.target.id === "lightbox" || e.target.classList.contains("lightbox-content")) hideLightbox();
  };
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") hideLightbox();
  });
  el("add-step").onclick = () => showAddStepModal();
  el("save-btn").onclick = saveWorkflow;
  el("load-btn").onclick = toggleLoadMenu;
  el("estimate-btn").onclick = estimateCost;
  el("run-btn").onclick = () => {
    if (state.costBreakdown === null) {
      estimateCost().then(() => {
        if (state.costBreakdown) showConfirmModal();
      });
    } else {
      showConfirmModal();
    }
  };
}

init();
