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

function updateRunButton() {
  const btn = el("run-btn");
  btn.disabled = state.steps.length === 0 || state.running;
  el("run-hint").textContent = state.costBreakdown
    ? "Click Run to confirm and execute."
    : "Estimate cost first, then run.";
}

async function refreshWorkflows() {
  try {
    const res = await fetch(API.workflows);
    const data = await res.json();
    const workflows = data.workflows || [];
    const menu = el("load-menu");
    menu.innerHTML = "";
    if (workflows.length === 0) {
      menu.innerHTML = '<div class="load-empty">No saved procedures</div>';
    } else {
      workflows.forEach((w) => {
        const btn = document.createElement("button");
        btn.textContent = w;
        btn.onclick = () => {
          loadWorkflow(w);
          menu.classList.add("hidden");
        };
        menu.appendChild(btn);
      });
    }
  } catch (e) {
    console.error("Failed to load procedures:", e);
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
  const modal = el("save-modal");
  el("save-name").value = state.steps[0] ? (state.steps[0].name || "procedure").replace(/\s+/g, "_").toLowerCase() : "procedure";
  modal.classList.remove("hidden");

  el("save-ok").onclick = async () => {
    const name = el("save-name").value.trim() || "procedure";
    try {
      const res = await fetch(`${API.workflows}/save`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, workflow: buildWorkflow() }),
      });
      if (!res.ok) {
        const err = await res.json();
        alert("Save failed: " + (err.detail || res.statusText));
        return;
      }
      const data = await res.json();
      modal.classList.add("hidden");
      const hint = el("run-hint");
      hint.textContent = `Saved as ${data.saved_as}`;
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
    state.costBreakdown = null;
    state.confirmed = false;
    renderSteps();
    updateRunButton();
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
      body: JSON.stringify({ workflow: buildWorkflow(), confirmed: true }),
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
                state.outputMedia.push({ type: "video", url: data.output.video });
              }
            }
          } else if (eventType === "complete") {
            log("Procedure complete.");
          } else if (eventType === "error") {
            log("Error: " + (data.message || "Unknown"));
          }
        }
      }
    }

    if (state.outputMedia && state.outputMedia.length > 0) {
      el("outputs-panel").classList.remove("hidden");
      const gallery = el("outputs-gallery");
      gallery.innerHTML = state.outputMedia.map(m => {
        if (m.type === "video") {
          return `<video src="${m.url}" controls></video>`;
        }
        return `<img src="${m.url}" alt="output">`;
      }).join("");
    } else {
      const outRes = await fetch(API.outputs);
      const outData = await outRes.json();
      if (outData.files && outData.files.length > 0) {
        el("outputs-panel").classList.remove("hidden");
        const gallery = el("outputs-gallery");
        gallery.innerHTML = outData.files.map(f => {
          const ext = (f.name || "").toLowerCase();
          if (ext.match(/\.(mp4|webm|mov)$/)) {
            return `<video src="${f.url}" controls></video>`;
          }
          return `<img src="${f.url}" alt="${f.name}">`;
        }).join("");
      }
    }
  } catch (e) {
    log("Error: " + e.message);
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
  el("new-step-video-image-url").value = params.image_url || "";
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
    if (seedVal) params.seed = parseInt(seedVal, 10);
    params.aspect_ratio = el("new-step-aspect-ratio").value || "auto";
    params.resolution = el("new-step-resolution").value || "1K";
    params.output_format = el("new-step-output-format").value || "png";
    params.safety_tolerance = parseInt(el("new-step-safety-tolerance").value, 10) || 4;
  }
  if (type === "ai_video") {
    const url = el("new-step-video-image-url").value.trim();
    if (url) params.image_url = url;
  }
  return params;
}

function toggleStepModalVisibility(type, isEdit) {
  const typeSelect = el("new-step-type");
  typeSelect.disabled = !!isEdit;
  const t = type || typeSelect.value;
  el("new-step-model-group").classList.toggle("hidden", t === "custom");
  el("new-step-from-key-group").classList.toggle("hidden", t !== "custom");
  el("new-step-prompt-group").classList.toggle("hidden", t === "custom");
  el("new-step-llm-model-group").classList.toggle("hidden", t !== "ai_text");
  el("new-step-image-params-group").classList.toggle("hidden", t !== "ai_image");
  el("new-step-video-image-url-group").classList.toggle("hidden", t !== "ai_video");
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
  const modelSelect = el("new-step-model");
  modelSelect.innerHTML = "";
  [...state.models.filter(m => m.type === "image"), ...state.models.filter(m => m.type === "text"), ...state.models.filter(m => m.type === "video")].forEach(m => {
    const opt = document.createElement("option");
    opt.value = m.id;
    opt.textContent = m.id;
    modelSelect.appendChild(opt);
  });
  modelSelect.value = state.models[0]?.id || "";
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
      step.model_id = modelSelect.value || state.models[0]?.id;
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
  const modelSelect = el("new-step-model");
  modelSelect.innerHTML = "";
  [...state.models.filter(m => m.type === "image"), ...state.models.filter(m => m.type === "text"), ...state.models.filter(m => m.type === "video")].forEach(m => {
    const opt = document.createElement("option");
    opt.value = m.id;
    opt.textContent = m.id;
    modelSelect.appendChild(opt);
  });
  modelSelect.value = step.model_id || state.models[0]?.id || "";
  toggleStepModalVisibility(step.type, true);
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
      updated.model_id = modelSelect.value || state.models[0]?.id;
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
