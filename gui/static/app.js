const API = {
  models: "/api/models",
  projects: "/api/procedures",
  modelPreviews: "/api/model-previews",
};

const state = {
  models: [],
  projects: [],
  projectId: null,
  estimates: {},
  assets: [],
  runs: [],
  workspace: "image",
  selectedImageAssetId: null,
  imageModelPreviewById: {},
  videoModelPreviewById: {},
  activeViewerType: "image",
  activeViewerAssetId: null,
  pendingViewerType: null,
};

function el(id) {
  return document.getElementById(id);
}

function nowLabel() {
  return new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function log(message) {
  const node = el("activity-log");
  node.textContent += `[${nowLabel()}] ${message}\n`;
  node.scrollTop = node.scrollHeight;
}

async function request(url, options = {}) {
  const res = await fetch(url, options);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || JSON.stringify(body);
    } catch (_) {}
    throw new Error(detail);
  }
  return res.json();
}

function modelOptions(type) {
  return state.models.filter((m) => m.type === type);
}

function shortModelName(modelId) {
  if (modelId.length <= 26) return modelId;
  return `${modelId.slice(0, 23)}...`;
}

function modelPriceLabel(model) {
  const est = model.estimated_cost ?? model.default_estimated_cost;
  if (typeof est === "number" && Number.isFinite(est)) return `~$${est.toFixed(3)}`;
  return "~$--";
}

function populateModelSelect(selectId, fullNameId, type, previewById = {}) {
  const select = el(selectId);
  const current = select.value;
  select.innerHTML = "";
  modelOptions(type).forEach((m) => {
    const opt = document.createElement("option");
    opt.value = m.id;
    const merged = { ...m, estimated_cost: previewById[m.id] };
    const totalPrice = modelPriceLabel(merged);
    opt.textContent = `${shortModelName(m.id)} (${m.quality_stars || 2}★) - ${totalPrice}`;
    opt.title = `${m.id}\nEstimated total: ${totalPrice}`;
    select.appendChild(opt);
  });
  if (current && [...select.options].some((o) => o.value === current)) {
    select.value = current;
  }
  renderModelFullName(selectId, fullNameId);
}

function renderModelFullName(selectId, fullNameId) {
  const picked = el(selectId).value || "";
  if (!picked) {
    el(fullNameId).textContent = "";
    return;
  }
  const model = state.models.find((m) => m.id === picked);
  const previews = selectId === "step1-model" ? state.imageModelPreviewById : state.videoModelPreviewById;
  const price = model ? modelPriceLabel({ ...model, estimated_cost: previews[picked] }) : "~$--";
  el(fullNameId).textContent = `Full model: ${picked} | Estimated total: ${price}`;
}

function updatePromptCounter(textId, counterId) {
  const val = el(textId).value || "";
  el(counterId).textContent = `${val.length}/800`;
}

function setStepError(stepNum, msg) {
  const node = el(`step${stepNum}-error`);
  if (node) node.textContent = msg || "";
}

function clearErrors() {
  setStepError(1, "");
  setStepError(3, "");
}

function validateImageCreate() {
  const prompt = el("step1-prompt").value.trim();
  if (!prompt) return "Prompt is required.";
  const num = parseInt(el("step1-num-images").value || "0", 10);
  if (Number.isNaN(num) || num < 1 || num > 8) return "Num images must be between 1 and 8.";
  return "";
}

function validateVideoCreate() {
  const prompt = el("step3-prompt").value.trim();
  if (!prompt) return "Prompt is required.";
  const duration = parseInt(el("step3-duration").value || "0", 10);
  if (Number.isNaN(duration) || duration < 2 || duration > 20) return "Duration must be between 2 and 20 sec.";
  return "";
}

/** For live pricing only — prompt may be empty */
function validateImageEstimateParams() {
  const num = parseInt(el("step1-num-images").value || "0", 10);
  if (Number.isNaN(num) || num < 1 || num > 8) return "Num images must be between 1 and 8.";
  return "";
}

function validateVideoEstimateParams() {
  const duration = parseInt(el("step3-duration").value || "0", 10);
  if (Number.isNaN(duration) || duration < 2 || duration > 20) return "Duration must be between 2 and 20 sec.";
  return "";
}

function imageCreatePayload() {
  return {
    model_id: el("step1-model").value,
    params: {
      prompt: el("step1-prompt").value.trim(),
      num_images: Math.max(1, parseInt(el("step1-num-images").value || "1", 10)),
      aspect_ratio: el("step1-aspect").value,
      resolution: el("step1-resolution").value,
    },
  };
}

function videoCreatePayload() {
  const source = el("step3-source-image").value;
  return {
    model_id: el("step3-model").value,
    params: {
      prompt: el("step3-prompt").value.trim(),
      source_asset_id: source ? parseInt(source, 10) : null,
      duration: parseInt(el("step3-duration").value || "5", 10),
      aspect_ratio: el("step3-aspect").value,
      resolution: el("step3-resolution").value,
    },
  };
}

function setWorkspace(workspace) {
  state.workspace = workspace;
  state.activeViewerType = workspace === "image" ? "image" : "video";
  el("image-workspace").classList.toggle("hidden", workspace !== "image");
  el("video-workspace").classList.toggle("hidden", workspace !== "video");
  el("open-image-workspace").classList.toggle("btn-workspace-active", workspace === "image");
  el("open-video-workspace").classList.toggle("btn-workspace-active", workspace === "video");
  ensureActiveViewerAsset();
  renderViewer();
}

function bindLightbox() {
  el("lightbox-close").onclick = () => hideLightbox();
  el("lightbox").onclick = (e) => {
    if (e.target.id === "lightbox") hideLightbox();
  };
}

function showLightbox(url, type) {
  const lb = el("lightbox");
  const img = el("lightbox-img");
  const video = el("lightbox-video");
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
  const lb = el("lightbox");
  const video = el("lightbox-video");
  lb.classList.add("hidden");
  video.pause();
  video.src = "";
}

async function loadModels() {
  const data = await request(API.models);
  state.models = data.models || [];
  await runParamRefresh();
}

async function requestModelPreviews(stepType, params) {
  const data = await request(API.modelPreviews, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ step_type: stepType, params }),
  });
  const map = {};
  (data.previews || []).forEach((p) => {
    map[p.id] = typeof p.estimated_cost === "number" ? p.estimated_cost : null;
  });
  return map;
}

async function refreshImageModelPreviews() {
  const params = imageCreatePayload().params;
  state.imageModelPreviewById = await requestModelPreviews("image", params);
  populateModelSelect("step1-model", "step1-model-full", "image", state.imageModelPreviewById);
}

async function refreshVideoModelPreviews() {
  const params = videoCreatePayload().params;
  delete params.source_asset_id;
  state.videoModelPreviewById = await requestModelPreviews("video", params);
  populateModelSelect("step3-model", "step3-model-full", "video", state.videoModelPreviewById);
}

let paramRefreshTimer = null;

async function refreshLiveEstimates() {
  const imgHint = el("step1-cost");
  const vidHint = el("step3-cost");
  const noProjectMsg = "Select a project to see the live estimate.";

  if (!state.projectId) {
    imgHint.textContent = noProjectMsg;
    vidHint.textContent = noProjectMsg;
    return;
  }

  const setImageEstimate = async () => {
    if (!el("step1-model").value) {
      imgHint.textContent = "Pick a model to see the estimate.";
      return;
    }
    const errImg = validateImageEstimateParams();
    if (errImg) {
      imgHint.textContent = "—";
      return;
    }
    try {
      const payload = imageCreatePayload();
      const data = await request(`${API.projects}/${state.projectId}/steps/generate_base_image/estimate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      state.estimates.generate_base_image = data.estimated_cost;
      imgHint.textContent = `$${data.estimated_cost.toFixed(4)}`;
    } catch (e) {
      imgHint.textContent = "Estimate unavailable";
      log(`Image estimate: ${e.message || String(e)}`);
    }
  };

  const setVideoEstimate = async () => {
    if (!el("step3-model").value) {
      vidHint.textContent = "Pick a model to see the estimate.";
      return;
    }
    const errVid = validateVideoEstimateParams();
    if (errVid) {
      vidHint.textContent = "—";
      return;
    }
    try {
      const payload = videoCreatePayload();
      const data = await request(`${API.projects}/${state.projectId}/steps/generate_video/estimate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      state.estimates.generate_video = data.estimated_cost;
      vidHint.textContent = `$${data.estimated_cost.toFixed(4)}`;
    } catch (e) {
      vidHint.textContent = "Estimate unavailable";
      log(`Video estimate: ${e.message || String(e)}`);
    }
  };

  await Promise.all([setImageEstimate(), setVideoEstimate()]);
}

async function runParamRefresh() {
  try {
    await refreshImageModelPreviews();
  } catch (e) {
    log(`Model previews (image): ${e.message || String(e)}`);
  }
  try {
    await refreshVideoModelPreviews();
  } catch (e) {
    log(`Model previews (video): ${e.message || String(e)}`);
  }
  try {
    await refreshLiveEstimates();
  } catch (e) {
    log(`Live estimates: ${e.message || String(e)}`);
  }
}

function scheduleParamRefresh() {
  if (paramRefreshTimer) clearTimeout(paramRefreshTimer);
  paramRefreshTimer = setTimeout(() => {
    paramRefreshTimer = null;
    runParamRefresh();
  }, 220);
}

/** Some browsers / styled selects are flaky on `change` alone; `input` catches more cases. */
function bindScheduleParamRefresh(node) {
  if (!node) return;
  const go = () => scheduleParamRefresh();
  node.addEventListener("change", go);
  node.addEventListener("input", go);
}

function closeProjectDropdown() {
  const dd = el("project-dropdown");
  const trig = el("project-picker-trigger");
  if (dd) dd.classList.add("hidden");
  if (trig) trig.setAttribute("aria-expanded", "false");
}

function toggleProjectDropdown() {
  const dd = el("project-dropdown");
  const trig = el("project-picker-trigger");
  if (!dd || !trig) return;
  dd.classList.toggle("hidden");
  const open = !dd.classList.contains("hidden");
  trig.setAttribute("aria-expanded", String(open));
}

function renderProjectPickerList() {
  const list = el("project-dropdown-list");
  if (!list) return;
  list.innerHTML = "";
  state.projects.forEach((p) => {
    const row = document.createElement("div");
    row.className = "project-dropdown-item";
    if (p.id === state.projectId) row.classList.add("project-dropdown-item-current");

    const pick = document.createElement("button");
    pick.type = "button";
    pick.className = "project-dropdown-name";
    pick.textContent = p.name;
    pick.onclick = (ev) => {
      ev.stopPropagation();
      closeProjectDropdown();
      safeAction(() => loadProject(p.id));
    };

    const del = document.createElement("button");
    del.type = "button";
    del.className = "project-delete-x";
    del.textContent = "×";
    del.setAttribute("aria-label", `Delete project ${p.name}`);
    del.onclick = (ev) => {
      ev.stopPropagation();
      safeAction(() => deleteProjectById(p.id, p.name));
    };

    row.appendChild(pick);
    row.appendChild(del);
    list.appendChild(row);
  });
}

async function refreshProjects() {
  const data = await request(API.projects);
  state.projects = data.procedures || data.projects || [];
  renderProjectPickerList();
}

async function createProject() {
  const name = prompt("Project name:");
  if (!name) return;
  const data = await request(API.projects, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  closeProjectDropdown();
  state.projectId = data.procedure.id;
  el("current-project").textContent = data.procedure.name;
  el("project-hint").textContent = "";
  await refreshProjects();
  await loadProject(data.procedure.id);
  log(`Created project "${data.procedure.name}"`);
}

async function renameProject() {
  if (!state.projectId) return;
  closeProjectDropdown();
  const current = state.projects.find((p) => p.id === state.projectId);
  const name = prompt("New project name:", current?.name || "");
  if (!name) return;
  const data = await request(`${API.projects}/${state.projectId}/rename`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  el("current-project").textContent = data.procedure.name;
  await refreshProjects();
  log(`Renamed project to "${data.procedure.name}"`);
}

async function deleteProjectById(id, name) {
  const label = (name || "").trim() || `project #${id}`;
  if (!confirm(`Delete project "${label}" and all its assets?`)) return;
  await request(`${API.projects}/${id}`, { method: "DELETE" });
  log(`Deleted project ${id}`);
  const wasCurrent = state.projectId === id;
  if (wasCurrent) {
    state.projectId = null;
    state.assets = [];
    state.runs = [];
    state.activeViewerAssetId = null;
    el("current-project").textContent = "No project selected";
    el("project-hint").textContent = "Create or load a project to unlock the pipeline.";
    renderViewer();
    renderRunHistory();
    await runParamRefresh();
  }
  closeProjectDropdown();
  await refreshProjects();
}

function confirmModal(message) {
  return new Promise((resolve) => {
    const modal = el("modal");
    el("modal-title").textContent = "Confirm estimated cost";
    el("modal-body").innerHTML = `<p>${message}</p>`;
    modal.classList.remove("hidden");
    el("modal-confirm").onclick = () => {
      modal.classList.add("hidden");
      resolve(true);
    };
    el("modal-cancel").onclick = () => {
      modal.classList.add("hidden");
      resolve(false);
    };
  });
}

async function estimateStep(stepKey, payload, targetHintId) {
  if (!state.projectId) throw new Error("Create or load a project first");
  const data = await request(`${API.projects}/${state.projectId}/steps/${stepKey}/estimate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  state.estimates[stepKey] = data.estimated_cost;
  el(targetHintId).textContent = `$${data.estimated_cost.toFixed(4)}`;
  return data.estimated_cost;
}

async function runStep(stepKey, payload, targetHintId) {
  const estimated = await estimateStep(stepKey, payload, targetHintId);
  const ok = await confirmModal(`Run for estimated API cost $${estimated.toFixed(4)}?`);
  if (!ok) return;
  const data = await request(`${API.projects}/${state.projectId}/steps/${stepKey}/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      model_id: payload.model_id,
      params: payload.params,
      confirmed: true,
      expected_cost: estimated,
    }),
  });
  el(targetHintId).textContent = `Confirmed: $${estimated.toFixed(4)}`;
  state.pendingViewerType = stepKey === "generate_base_image" ? "image" : "video";
  log(`Ran ${stepKey}: created ${(data.assets || []).length} asset(s).`);
  await loadProject(state.projectId);
}

function visibleAssetsByType(type) {
  return state.assets.filter((a) => a.kind === type && !a.archived);
}

function ensureActiveViewerAsset() {
  const assets = visibleAssetsByType(state.activeViewerType);
  if (assets.length === 0) {
    state.activeViewerAssetId = null;
    return;
  }
  const exists = assets.some((a) => a.id === state.activeViewerAssetId);
  if (!exists) {
    state.activeViewerAssetId = assets[0].id;
  }
}

function renderViewer() {
  const select = el("viewer-asset-select");
  const empty = el("viewer-empty");
  const img = el("viewer-image");
  const video = el("viewer-video");
  const meta = el("viewer-meta");
  const useSourceBtn = el("viewer-use-source-btn");

  const assets = visibleAssetsByType(state.activeViewerType);
  select.innerHTML = "";
  assets.forEach((a) => {
    const opt = document.createElement("option");
    opt.value = String(a.id);
    opt.textContent = `#${a.id} ${a.source}`;
    select.appendChild(opt);
  });

  if (!assets.length || state.activeViewerAssetId === null) {
    empty.classList.remove("hidden");
    img.classList.add("hidden");
    video.classList.add("hidden");
    meta.textContent = "No media available for this type.";
    useSourceBtn.classList.add("hidden");
    el("viewer-edit-btn").disabled = true;
    el("viewer-archive-btn").disabled = true;
    el("viewer-delete-btn").disabled = true;
    return;
  }

  select.value = String(state.activeViewerAssetId);
  const asset = assets.find((a) => a.id === state.activeViewerAssetId);
  if (!asset) return;

  empty.classList.add("hidden");
  img.classList.add("hidden");
  video.classList.add("hidden");
  if (asset.kind === "image") {
    img.src = asset.url;
    img.classList.remove("hidden");
  } else {
    video.src = asset.url;
    video.classList.remove("hidden");
  }
  meta.textContent = `Asset #${asset.id} - ${asset.source}`;
  useSourceBtn.classList.toggle("hidden", asset.kind !== "image");
  el("viewer-edit-btn").disabled = false;
  el("viewer-archive-btn").disabled = false;
  el("viewer-delete-btn").disabled = false;
}

function populateVideoSource(images) {
  const select = el("step3-source-image");
  const current = state.selectedImageAssetId ? String(state.selectedImageAssetId) : select.value;
  select.innerHTML = `<option value="">None (text-to-video)</option>`;
  images.forEach((img) => {
    const opt = document.createElement("option");
    opt.value = String(img.id);
    opt.textContent = `#${img.id} ${img.source}`;
    select.appendChild(opt);
  });
  if (current && [...select.options].some((o) => o.value === current)) {
    select.value = current;
  }
}

function currentViewerAsset() {
  if (!state.activeViewerAssetId) return null;
  return state.assets.find((a) => a.id === state.activeViewerAssetId) || null;
}

async function editImageAsset(asset) {
  const action = prompt(
    "Edit image action:\n1 = AI modify (new variant)\n2 = Flip\n3 = Zoom\n4 = Filter (vivid)\n5 = Revert",
    "1",
  );
  if (!action) return;
  if (action === "1") {
    const promptText = prompt("Describe the image modification:");
    if (!promptText) return;
    const imageModels = modelOptions("image");
    const defaultModel = imageModels[0]?.id || "";
    const modelId = prompt("Model ID for AI modify:", defaultModel);
    if (!modelId) return;
    const estimate = await request(`${API.projects}/${state.projectId}/steps/modify_images/estimate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        model_id: modelId,
        params: { prompt: promptText, image_url: "placeholder" },
      }),
    });
    const ok = await confirmModal(`Run AI image modify for $${estimate.estimated_cost.toFixed(4)}?`);
    if (!ok) return;
    await request(`/api/assets/${asset.id}/image-ai-edit`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        model_id: modelId,
        prompt: promptText,
        params: {},
        confirmed: true,
        expected_cost: estimate.estimated_cost,
      }),
    });
    state.pendingViewerType = "image";
    log(`AI modified image #${asset.id}.`);
  } else {
    const opMap = {
      "2": { operation: "flip_horizontal", params: {} },
      "3": { operation: "zoom", params: { zoom_factor: 1.1 } },
      "4": { operation: "filter", params: { filter: "vivid" } },
      "5": { operation: "revert", params: {} },
    };
    const payload = opMap[action];
    if (!payload) return;
    await request(`/api/assets/${asset.id}/image-transform`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    log(`Applied image edit on #${asset.id}.`);
  }
  await loadProject(state.projectId);
}

async function editVideoAsset(asset) {
  const action = prompt("Edit video action:\n1 = Cut\n2 = Add shake (2%-4%)", "1");
  if (!action) return;
  if (action === "1") {
    const startSec = parseFloat(prompt("Cut start (sec):", "0") || "0");
    const endSec = parseFloat(prompt("Cut end (sec):", "3") || "3");
    if (Number.isNaN(startSec) || Number.isNaN(endSec) || endSec <= startSec) {
      throw new Error("Cut end must be greater than cut start.");
    }
    await request(`/api/assets/${asset.id}/video-cut`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ start_sec: startSec, end_sec: endSec }),
    });
    log(`Cut video #${asset.id}.`);
  } else if (action === "2") {
    const intensity = parseFloat(prompt("Shake intensity (0.02 - 0.04):", "0.03") || "0.03");
    if (Number.isNaN(intensity) || intensity < 0.02 || intensity > 0.04) {
      throw new Error("Shake intensity must be between 0.02 and 0.04.");
    }
    await request(`/api/assets/${asset.id}/video-shake`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ intensity, first_seconds: 1.0 }),
    });
    log(`Added shake to video #${asset.id}.`);
  }
  state.pendingViewerType = "video";
  await loadProject(state.projectId);
}

function renderRunHistory() {
  const box = el("run-history");
  if (!state.projectId) {
    box.innerHTML = `<div class="helper-text">No project selected.</div>`;
    return;
  }
  if (!state.runs.length) {
    box.innerHTML = `<div class="helper-text">No runs yet.</div>`;
    return;
  }
  box.innerHTML = state.runs.slice(0, 12).map((run) => {
    const date = run.created_at ? new Date(run.created_at).toLocaleString() : "-";
    return `<div class="run-entry"><strong>${run.step_key}</strong> - ${run.status} - $${Number(run.estimated_cost || 0).toFixed(4)} - ${date}</div>`;
  }).join("");
}

function applyStepConfig(configs, stepKey, modelEl, mapper) {
  const cfg = (configs || []).find((c) => c.step_key === stepKey);
  if (!cfg) return;
  if (cfg.model_id && [...modelEl.options].some((o) => o.value === cfg.model_id)) {
    modelEl.value = cfg.model_id;
  }
  mapper(cfg.params || {});
}

function applyViewerAutoSelection() {
  if (state.pendingViewerType) {
    const t = state.pendingViewerType;
    state.pendingViewerType = null;
    if (t === "image") {
      setWorkspace("image");
    } else if (t === "video") {
      setWorkspace("video");
    }
    const newest = visibleAssetsByType(state.activeViewerType)[0];
    state.activeViewerAssetId = newest ? newest.id : null;
  } else {
    state.activeViewerType = state.workspace === "video" ? "video" : "image";
    ensureActiveViewerAsset();
  }
}

async function loadProject(id) {
  if (!id) return;
  state.projectId = parseInt(id, 10);
  const data = await request(`${API.projects}/${state.projectId}`);
  const runs = await request(`${API.projects}/${state.projectId}/runs`);
  state.assets = data.assets || [];
  state.runs = runs.runs || [];
  el("current-project").textContent = data.procedure.name;
  el("project-hint").textContent = "";
  renderRunHistory();

  const images = visibleAssetsByType("image");
  populateVideoSource(images);

  applyStepConfig(data.step_configs, "generate_base_image", el("step1-model"), (p) => {
    if (p.prompt) el("step1-prompt").value = p.prompt;
    if (p.num_images) el("step1-num-images").value = String(p.num_images);
    if (p.aspect_ratio) el("step1-aspect").value = p.aspect_ratio;
    if (p.resolution) el("step1-resolution").value = p.resolution;
  });
  applyStepConfig(data.step_configs, "generate_video", el("step3-model"), (p) => {
    if (p.prompt) el("step3-prompt").value = p.prompt;
    if (p.duration) el("step3-duration").value = String(p.duration).replace("s", "");
    if (p.aspect_ratio) el("step3-aspect").value = p.aspect_ratio;
    if (p.resolution) el("step3-resolution").value = p.resolution;
    if (p.source_asset_id) {
      state.selectedImageAssetId = parseInt(String(p.source_asset_id), 10);
      el("step3-source-image").value = String(p.source_asset_id);
    }
  });

  applyViewerAutoSelection();
  renderViewer();

  renderModelFullName("step1-model", "step1-model-full");
  renderModelFullName("step3-model", "step3-model-full");
  updatePromptCounter("step1-prompt", "step1-prompt-count");
  updatePromptCounter("step3-prompt", "step3-prompt-count");
  await runParamRefresh();
}

async function saveStepConfig(stepKey, payload) {
  await request(`${API.projects}/${state.projectId}/steps/${stepKey}/config`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

async function importImage(file) {
  const name = String(file?.name || "").toLowerCase();
  const allowedExt = [".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff"];
  const hasAllowedExt = allowedExt.some((ext) => name.endsWith(ext));
  const mime = String(file?.type || "").toLowerCase();
  const looksLikeImage = hasAllowedExt || mime.startsWith("image/");
  if (!looksLikeImage) {
    throw new Error("Please select a valid image file (.png, .jpg, .jpeg, .webp, .gif, .bmp, .tif, .tiff).");
  }
  const fd = new FormData();
  fd.append("file", file);
  await request(`${API.projects}/${state.projectId}/assets/import-image`, {
    method: "POST",
    body: fd,
  });
  state.pendingViewerType = "image";
  log(`Imported image "${file.name}"`);
  await loadProject(state.projectId);
}

async function importVideo(file) {
  const name = String(file?.name || "").toLowerCase();
  const allowedExt = [".mp4", ".mov", ".webm", ".m4v", ".avi", ".mkv"];
  const hasAllowedExt = allowedExt.some((ext) => name.endsWith(ext));
  const mime = String(file?.type || "").toLowerCase();
  const looksLikeVideo = hasAllowedExt || mime.startsWith("video/");
  if (!looksLikeVideo) {
    throw new Error("Please select a valid video file (.mp4, .mov, .webm, .m4v, .avi, .mkv).");
  }
  const fd = new FormData();
  fd.append("file", file);
  await request(`${API.projects}/${state.projectId}/assets/import-video`, {
    method: "POST",
    body: fd,
  });
  state.pendingViewerType = "video";
  log(`Imported video "${file.name}"`);
  await loadProject(state.projectId);
}

async function viewerArchiveToggle() {
  const asset = currentViewerAsset();
  if (!asset) return;
  await request(`/api/assets/${asset.id}/archive`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ archived: !asset.archived }),
  });
  state.pendingViewerType = asset.kind;
  await loadProject(state.projectId);
}

async function viewerDelete() {
  const asset = currentViewerAsset();
  if (!asset) return;
  if (!confirm("Delete this asset?")) return;
  await request(`/api/assets/${asset.id}`, { method: "DELETE" });
  state.pendingViewerType = asset.kind;
  await loadProject(state.projectId);
}

function wireEvents() {
  el("open-image-workspace").onclick = () => setWorkspace("image");
  el("open-video-workspace").onclick = () => setWorkspace("video");

  el("viewer-asset-select").onchange = (e) => {
    const value = parseInt(e.target.value || "0", 10);
    state.activeViewerAssetId = value || null;
    renderViewer();
  };

  el("viewer-use-source-btn").onclick = () => safeAction(async () => {
    const asset = currentViewerAsset();
    if (!asset || asset.kind !== "image") return;
    state.selectedImageAssetId = asset.id;
    el("step3-source-image").value = String(asset.id);
    log(`Selected image #${asset.id} as video source.`);
    setWorkspace("video");
  });

  el("viewer-edit-btn").onclick = () => safeAction(async () => {
    const asset = currentViewerAsset();
    if (!asset) return;
    if (asset.kind === "image") {
      await editImageAsset(asset);
    } else {
      await editVideoAsset(asset);
    }
  });

  el("viewer-archive-btn").onclick = () => safeAction(viewerArchiveToggle);
  el("viewer-delete-btn").onclick = () => safeAction(viewerDelete);

  el("project-picker-trigger").onclick = (e) => {
    e.stopPropagation();
    toggleProjectDropdown();
  };

  el("project-create-option").onclick = (e) => {
    e.stopPropagation();
    closeProjectDropdown();
    safeAction(createProject);
  };

  el("rename-project-btn").onclick = () => safeAction(renameProject);

  document.addEventListener("click", (e) => {
    const picker = el("project-picker");
    if (picker && !picker.contains(e.target)) closeProjectDropdown();
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeProjectDropdown();
  });

  [["step1-model", "step1-model-full"], ["step3-model", "step3-model-full"]].forEach(([sid, fid]) =>
    el(sid).addEventListener("change", () => {
      renderModelFullName(sid, fid);
      scheduleParamRefresh();
    }),
  );
  [["step1-prompt", "step1-prompt-count"], ["step3-prompt", "step3-prompt-count"]].forEach(([tid, cid]) =>
    el(tid).addEventListener("input", () => {
      updatePromptCounter(tid, cid);
      scheduleParamRefresh();
    }),
  );

  [
    "step1-num-images",
    "step1-resolution",
    "step1-aspect",
    "step3-duration",
    "step3-resolution",
    "step3-aspect",
  ].forEach((id) => bindScheduleParamRefresh(el(id)));

  bindScheduleParamRefresh(el("step3-source-image"));

  document.querySelectorAll(".step-run-btn").forEach((btn) => {
    btn.onclick = () => safeAction(async () => {
      clearErrors();
      const step = btn.dataset.step;
      const payload = step === "generate_base_image" ? imageCreatePayload() : videoCreatePayload();
      const hint = step === "generate_base_image" ? "step1-cost" : "step3-cost";
      const err = step === "generate_base_image" ? validateImageCreate() : validateVideoCreate();
      if (err) {
        setStepError(step === "generate_base_image" ? 1 : 3, err);
        throw new Error(err);
      }
      await saveStepConfig(step, payload);
      await runStep(step, payload, hint);
    });
  });

  el("import-image-btn").onclick = () => el("import-image-input").click();
  el("import-image-input").onchange = (e) => safeAction(async () => {
    const file = e.target.files?.[0];
    if (!file) return;
    await importImage(file);
    e.target.value = "";
  });

  el("import-video-btn").onclick = () => el("import-video-input").click();
  el("import-video-input").onchange = (e) => safeAction(async () => {
    const file = e.target.files?.[0];
    if (!file) return;
    await importVideo(file);
    e.target.value = "";
  });
}

async function safeAction(fn) {
  try {
    await fn();
  } catch (err) {
    alert(err.message || String(err));
    log(`Error: ${err.message || String(err)}`);
  }
}

async function init() {
  bindLightbox();
  wireEvents();
  setWorkspace("image");
  await loadModels();
  await refreshProjects();
  renderRunHistory();
  updatePromptCounter("step1-prompt", "step1-prompt-count");
  updatePromptCounter("step3-prompt", "step3-prompt-count");
  log("Ready. Choose or create a project from the header menu.");
}

init();
