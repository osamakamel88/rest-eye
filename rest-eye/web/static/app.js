// State variables
let currentToggles = { skeleton: true, boxes: true, zones: true, hud: true };
let isDrawingZone = false;
let drawnPoints = [];
let lastAlertCount = 0;
let audioContext = null;
let isDemoMode = false;
let backendUrl = "";
let selectedUploadFile = null;
let isVideoPaused = false;

// Tab Switcher
function switchMainTab(tab) {
  const landingTab = document.getElementById("landing-tab-content");
  const demoTab = document.getElementById("demo-tab-content");
  const landingBtn = document.getElementById("tab-landing-btn");
  const demoBtn = document.getElementById("tab-demo-btn");

  if (tab === "demo") {
    landingTab.classList.remove("active");
    demoTab.classList.add("active");
    landingBtn.classList.remove("active");
    demoBtn.classList.add("active");
    window.scrollTo({ top: 0, behavior: "smooth" });
  } else {
    demoTab.classList.remove("active");
    landingTab.classList.add("active");
    demoBtn.classList.remove("active");
    landingBtn.classList.add("active");
  }
}

// Interactive ROI Calculator for Egyptian Restaurants
function updateRoiCalc() {
  const foodCost = parseFloat(document.getElementById("calc-food-cost").value) || 150000;
  const staffCount = parseInt(document.getElementById("calc-staff-count").value) || 6;

  document.getElementById("calc-food-val").innerText = `${foodCost.toLocaleString()} ج.م`;
  document.getElementById("calc-staff-val").innerText = `${staffCount} موظفين`;

  // Savings estimate: 15% raw food shrinkage reduction + 3,000 EGP per staff idle time recovery
  const foodSavings = foodCost * 0.15;
  const productivitySavings = staffCount * 750;
  const totalMonthlySavings = Math.round(foodSavings + productivitySavings);
  const totalYearlySavings = totalMonthlySavings * 12;

  document.getElementById("calc-savings-monthly").innerText = `${totalMonthlySavings.toLocaleString()} ج.م`;
  document.getElementById("calc-savings-yearly").innerText = `${totalYearlySavings.toLocaleString()} ج.م`;
}

// Initialize
document.addEventListener("DOMContentLoaded", () => {
  setupCanvas();
  fetchStatus();
  fetchAlerts();
  fetchAuditNotes();
  setInterval(fetchStatus, 1000);
  setInterval(fetchAlerts, 2000);
});

// Sound alert synthesizer
function playAlertBeep() {
  try {
    if (!audioContext) {
      audioContext = new (window.AudioContext || window.webkitAudioContext)();
    }
    const osc = audioContext.createOscillator();
    const gain = audioContext.createGain();
    osc.type = "sine";
    osc.frequency.setValueAtTime(880, audioContext.currentTime);
    osc.frequency.exponentialRampToValueAtTime(440, audioContext.currentTime + 0.3);
    gain.gain.setValueAtTime(0.3, audioContext.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.3);
    osc.connect(gain);
    gain.connect(audioContext.destination);
    osc.start();
    osc.stop(audioContext.currentTime + 0.3);
  } catch (e) {
    console.log("Audio waiting for user gesture");
  }
}

// Fetch Status & Personnel stats
async function fetchStatus() {
  try {
    const res = await fetch(`${backendUrl}/api/status`);
    if (!res.ok) throw new Error("Backend offline");
    const data = await res.json();
    
    isDemoMode = false;
    document.getElementById("val-status").innerText = "ONLINE";
    document.getElementById("val-status").style.color = "var(--accent-emerald)";
    document.getElementById("val-fps").innerText = data.fps || "25.0";
    document.getElementById("val-speed").innerText = `${data.speed || 1.0}x`;
    document.getElementById("val-person-count").innerText = data.active_person_count || "0";
    document.getElementById("val-alert-count").innerText = data.total_alerts || "0";
    document.getElementById("val-source").innerText = data.source || "-";
    document.getElementById("active-staff-badge").innerText = `${data.active_person_count || 0} Active`;

    isVideoPaused = data.is_paused || false;
    document.getElementById("btn-pause").innerText = isVideoPaused ? "▶️ Resume" : "⏸️ Pause";

    renderPersonnel(data.persons || []);
  } catch (e) {
    if (!isDemoMode) {
      activateClientDemoMode();
    }
  }
}

// Standalone Demo Mode for Vercel Client Demos
function activateClientDemoMode() {
  isDemoMode = true;
  document.getElementById("val-status").innerText = "CLIENT DEMO";
  document.getElementById("val-status").style.color = "var(--accent-sky)";
  document.getElementById("val-fps").innerText = "24.0";
  document.getElementById("val-source").innerText = "Kitchen Camera #01 (Live AI Simulation)";
  
  const img = document.getElementById("stream-img");
  if (!img.complete || img.naturalWidth === 0) {
    img.src = "https://images.unsplash.com/photo-1556910103-1c02745aae4d?w=1280&q=80";
  }

  const mockPersons = [
    {
      track_id: 143,
      posture: "STANDING",
      posture_duration_sec: 24,
      total_standing_sec: 195,
      total_sitting_sec: 0,
      zones: ["Kitchen Prep Counter"],
      is_eating: true,
      is_hand_near_mouth: true
    },
    {
      track_id: 169,
      posture: "STANDING",
      posture_duration_sec: 120,
      total_standing_sec: 480,
      total_sitting_sec: 0,
      zones: ["Restricted Inventory"],
      is_eating: false,
      is_hand_near_mouth: false
    }
  ];

  document.getElementById("val-person-count").innerText = "2";
  document.getElementById("val-alert-count").innerText = "1";
  document.getElementById("active-staff-badge").innerText = "2 Active";
  renderPersonnel(mockPersons);

  const mockAlerts = [
    {
      id: "demo-01",
      type: "UNAUTHORIZED_EATING",
      person_id: 143,
      zone: "Kitchen / Storage Area",
      timestamp: "Just now",
      snapshot_url: "https://images.unsplash.com/photo-1556910103-1c02745aae4d?w=400&q=80",
      video_url: "#"
    }
  ];
  renderAlerts(mockAlerts);
}

function renderPersonnel(persons) {
  const container = document.getElementById("personnel-list");
  if (!persons || persons.length === 0) {
    container.innerHTML = `
      <div style="text-align: center; color: var(--text-muted); padding: 24px 0; font-size: 13px;">
        No personnel currently in camera view.
      </div>
    `;
    return;
  }

  container.innerHTML = persons.map(p => {
    const isEating = p.is_eating;
    const isHandNear = p.is_hand_near_mouth;
    
    let tagClass = "tag-normal";
    let statusText = "Normal";
    if (isEating) {
      tagClass = "tag-eating";
      statusText = "EATING DETECTED!";
    } else if (isHandNear) {
      tagClass = "tag-eating";
      statusText = "EATING / DRINKING";
    }

    const standingSec = Math.round(p.total_standing_sec || 0);
    const sittingSec = Math.round(p.total_sitting_sec || 0);
    const postureDuration = Math.round(p.posture_duration_sec || 0);
    const zoneStr = (p.zones && p.zones.length > 0) ? p.zones.join(", ") : "Main Area";

    return `
      <div class="person-card ${isEating ? 'eating' : ''}">
        <div class="person-header">
          <div class="person-id">Staff Person #${p.track_id}</div>
          <div class="person-tag ${tagClass}">${statusText}</div>
        </div>
        <div class="person-stats">
          <div class="stat-item">Posture: <strong>${p.posture} (${postureDuration}s)</strong></div>
          <div class="stat-item">Zone: <strong style="color: var(--accent-amber)">${zoneStr}</strong></div>
          <div class="stat-item">Total Standing: <strong>${formatTime(standingSec)}</strong></div>
          <div class="stat-item">Total Sitting: <strong>${formatTime(sittingSec)}</strong></div>
        </div>
      </div>
    `;
  }).join("");
}

function formatTime(seconds) {
  if (seconds < 60) return `${seconds}s`;
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${mins}m ${secs}s`;
}

// Fetch Alerts Feed
async function fetchAlerts() {
  if (isDemoMode) return;
  try {
    const res = await fetch(`${backendUrl}/api/alerts`);
    if (!res.ok) return;
    const data = await res.json();
    const alerts = data.alerts || [];

    if (alerts.length > lastAlertCount && lastAlertCount !== 0) {
      playAlertBeep();
    }
    lastAlertCount = alerts.length;

    renderAlerts(alerts);
  } catch (e) {
    // handled
  }
}

function renderAlerts(alerts) {
  const container = document.getElementById("alerts-list");
  if (!alerts || alerts.length === 0) {
    container.innerHTML = `
      <div style="text-align: center; color: var(--text-muted); padding: 20px 0; font-size: 13px;">
        No violations recorded yet.
      </div>
    `;
    return;
  }

  container.innerHTML = alerts.map(a => `
    <div class="alert-item new">
      <img src="${a.snapshot_url}" alt="Snapshot" class="alert-thumb" onerror="this.src='https://images.unsplash.com/photo-1556910103-1c02745aae4d?w=200&q=80'">
      <div class="alert-content">
        <div class="alert-title">🚨 ${a.type.replace('_', ' ')}</div>
        <div class="alert-meta">
          Person #${a.person_id} • ${a.zone} • ${a.timestamp}
        </div>
      </div>
      <button class="alert-action-btn" onclick="playIncidentClip('${a.video_url}', '${a.type} - Person #${a.person_id}')">
        ▶ Watch Clip
      </button>
    </div>
  `).join("");
}

// Speed & Playback Controls
async function setSpeed(multiplier) {
  document.querySelectorAll(".btn-speed").forEach(b => b.classList.remove("active"));
  const spdMap = { 0.25: "spd-025", 0.5: "spd-05", 1.0: "spd-1", 2.0: "spd-2", 4.0: "spd-4" };
  if (spdMap[multiplier]) {
    const el = document.getElementById(spdMap[multiplier]);
    if (el) el.classList.add("active");
  }

  if (!isDemoMode) {
    await fetch(`${backendUrl}/api/speed`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ speed: multiplier })
    });
  }
  document.getElementById("val-speed").innerText = `${multiplier}x`;
}

async function togglePauseVideo() {
  if (!isDemoMode) {
    const res = await fetch(`${backendUrl}/api/playback`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "toggle_pause" })
    });
    const data = await res.json();
    isVideoPaused = data.is_paused;
    document.getElementById("btn-pause").innerText = isVideoPaused ? "▶️ Resume" : "⏸️ Pause";
  }
}

async function rewindVideo() {
  if (!isDemoMode) {
    await fetch(`${backendUrl}/api/playback`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "rewind" })
    });
  }
}

// Audit Notes Management
async function fetchAuditNotes() {
  if (isDemoMode) return;
  try {
    const res = await fetch(`${backendUrl}/api/notes`);
    const data = await res.json();
    renderAuditNotes(data.notes || []);
  } catch (e) {}
}

function renderAuditNotes(notes) {
  const container = document.getElementById("audit-notes-list");
  if (!notes || notes.length === 0) {
    container.innerHTML = `
      <div style="text-align: center; color: var(--text-muted); padding: 10px 0; font-size: 12px;">
        No audit notes recorded yet.
      </div>
    `;
    return;
  }

  container.innerHTML = notes.map(n => `
    <div class="audit-note-item ${n.severity ? n.severity.toLowerCase() : 'normal'}">
      <div>
        <strong style="color: #93c5fd; margin-right: 6px;">[${n.time_offset || n.timestamp}]</strong>
        <span>${n.note}</span>
      </div>
      <button onclick="deleteAuditNote('${n.id}')" style="background: none; border: none; color: #ef4444; cursor: pointer; font-size: 12px;">✕</button>
    </div>
  `).join("");
}

async function submitAuditNote() {
  const input = document.getElementById("audit-note-input");
  const severity = document.getElementById("audit-severity").value;
  const noteText = input.value.trim();
  if (!noteText) return;

  if (isDemoMode) {
    const mockNotes = [
      { id: "note-1", note: noteText, timestamp: new Date().toLocaleTimeString(), time_offset: "00:01:24", severity: severity }
    ];
    renderAuditNotes(mockNotes);
    input.value = "";
    return;
  }

  await fetch(`${backendUrl}/api/notes`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ note: noteText, severity: severity })
  });

  input.value = "";
  fetchAuditNotes();
}

async function deleteAuditNote(noteId) {
  if (!isDemoMode) {
    await fetch(`${backendUrl}/api/notes/${noteId}`, { method: "DELETE" });
    fetchAuditNotes();
  }
}

function exportAuditReport() {
  fetch(`${backendUrl}/api/notes`).then(res => res.json()).then(data => {
    const notes = data.notes || [];
    let report = `REST-EYE AUDIT & INCIDENT REPORT\nGenerated: ${new Date().toLocaleString()}\nCamera: Kitchen Cam 01\n\n`;
    notes.forEach((n, i) => {
      report += `${i + 1}. [${n.timestamp}] (${n.severity}) : ${n.note}\n`;
    });
    
    const blob = new Blob([report], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `RestEye_Audit_Report_${Date.now()}.txt`;
    a.click();
  });
}

// Upload Modal & Logic
function openUploadModal() {
  document.getElementById("upload-modal").classList.add("open");
}

function closeUploadModal() {
  document.getElementById("upload-modal").classList.remove("open");
  selectedUploadFile = null;
  document.getElementById("upload-filename-preview").innerText = "";
  document.getElementById("btn-submit-upload").disabled = true;
}

function handleFileSelected(event) {
  const file = event.target.files[0];
  if (file) {
    selectedUploadFile = file;
    document.getElementById("upload-filename-preview").innerText = `Selected: ${file.name} (${(file.size / (1024*1024)).toFixed(1)} MB)`;
    document.getElementById("btn-submit-upload").disabled = false;
  }
}

async function submitVideoUpload() {
  if (!selectedUploadFile) return;

  const btn = document.getElementById("btn-submit-upload");
  btn.disabled = true;
  btn.innerText = "Uploading & Initializing AI...";

  const formData = new FormData();
  formData.append("file", selectedUploadFile);

  try {
    const res = await fetch(`${backendUrl}/api/upload`, {
      method: "POST",
      body: formData
    });
    const data = await res.json();
    alert(`Video "${selectedUploadFile.name}" uploaded successfully! Starting real-time AI audit.`);
    closeUploadModal();
    setTimeout(() => {
      const img = document.getElementById("stream-img");
      img.src = `${backendUrl}/api/stream?t=` + Date.now();
    }, 800);
  } catch (e) {
    alert("Upload failed. Please check network connection.");
  } finally {
    btn.innerText = "Upload & Analyze";
  }
}

// Video Modal Controls
function playIncidentClip(videoUrl, title) {
  if (isDemoMode || !videoUrl || videoUrl === "#") {
    alert(`Incident Review: ${title}\n[In live deployment, the 8-second MP4 clip recorded by the AI Sentry plays here].`);
    return;
  }
  const modal = document.getElementById("video-modal");
  const player = document.getElementById("incident-player");
  const modalTitle = document.getElementById("modal-video-title");
  
  modalTitle.innerText = title;
  player.src = videoUrl;
  modal.classList.add("open");
  player.play().catch(e => console.log("Autoplay blocked:", e));
}

function closeVideoModal() {
  const modal = document.getElementById("video-modal");
  const player = document.getElementById("incident-player");
  player.pause();
  player.src = "";
  modal.classList.remove("open");
}

// Toggle overlays
async function toggleOverlay(type) {
  currentToggles[type] = !currentToggles[type];
  
  const btnMap = {
    skeleton: "tog-skel",
    boxes: "tog-box",
    zones: "tog-zones",
    hud: "tog-hud"
  };
  const btn = document.getElementById(btnMap[type]);
  if (btn) {
    btn.classList.toggle("active", currentToggles[type]);
  }

  if (!isDemoMode) {
    await fetch(`${backendUrl}/api/toggles`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(currentToggles)
    });
  }
}

// Interactive Zone Drawing Canvas
function setupCanvas() {
  const canvas = document.getElementById("zone-canvas");
  const img = document.getElementById("stream-img");

  function resizeCanvas() {
    canvas.width = img.clientWidth || 800;
    canvas.height = img.clientHeight || 450;
    drawCanvasPoints();
  }

  window.addEventListener("resize", resizeCanvas);
  img.addEventListener("load", resizeCanvas);

  canvas.addEventListener("click", (e) => {
    if (!isDrawingZone) return;
    const rect = canvas.getBoundingClientRect();
    const normX = (e.clientX - rect.left) / rect.width;
    const normY = (e.clientY - rect.top) / rect.height;
    
    drawnPoints.push([Math.round(normX * 1000) / 1000, Math.round(normY * 1000) / 1000]);
    drawCanvasPoints();
  });
}

function startDrawingZone() {
  isDrawingZone = true;
  drawnPoints = [];
  const canvas = document.getElementById("zone-canvas");
  canvas.classList.add("active");
  document.getElementById("btn-draw-zone").style.display = "none";
  document.getElementById("btn-cancel-draw").style.display = "inline-block";
  document.getElementById("btn-save-draw").style.display = "inline-block";
}

function cancelDrawingZone() {
  isDrawingZone = false;
  drawnPoints = [];
  const canvas = document.getElementById("zone-canvas");
  canvas.classList.remove("active");
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  
  document.getElementById("btn-draw-zone").style.display = "inline-block";
  document.getElementById("btn-cancel-draw").style.display = "none";
  document.getElementById("btn-save-draw").style.display = "none";
}

function drawCanvasPoints() {
  const canvas = document.getElementById("zone-canvas");
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  if (drawnPoints.length === 0) return;

  ctx.strokeStyle = "#ef4444";
  ctx.fillStyle = "rgba(239, 68, 68, 0.35)";
  ctx.lineWidth = 2;
  ctx.setLineDash([6, 6]);

  ctx.beginPath();
  drawnPoints.forEach((p, i) => {
    const px = p[0] * canvas.width;
    const py = p[1] * canvas.height;
    if (i === 0) ctx.moveTo(px, py);
    else ctx.lineTo(px, py);
  });

  if (drawnPoints.length >= 3) {
    ctx.closePath();
    ctx.fill();
  }
  ctx.stroke();

  ctx.setLineDash([]);
  drawnPoints.forEach((p, i) => {
    const px = p[0] * canvas.width;
    const py = p[1] * canvas.height;
    ctx.fillStyle = "#ffffff";
    ctx.beginPath();
    ctx.arc(px, py, 5, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
  });
}

async function saveDrawnZone() {
  if (drawnPoints.length < 3) {
    alert("Please click at least 3 points on the camera view to form a polygon zone.");
    return;
  }

  const zoneName = prompt("Enter a name for this Restricted Zone:", "Inventory Storage Shelf");
  if (!zoneName) return;

  if (isDemoMode) {
    alert(`Restricted Zone "${zoneName}" created successfully! The AI Sentry is now monitoring this boundary.`);
    cancelDrawingZone();
    return;
  }

  try {
    const currentZonesRes = await fetch(`${backendUrl}/api/zones`);
    const currentZonesData = await currentZonesRes.json();
    const existing = currentZonesData.zones || [];

    const newZone = {
      name: zoneName,
      type: "restricted_eating",
      color: "#ef4444",
      polygon: drawnPoints,
      alert_on_eating: true,
      alert_on_loiter: true,
      loiter_threshold_sec: 90.0
    };

    existing.push(newZone);

    await fetch(`${backendUrl}/api/zones`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(existing)
    });

    alert("Restricted zone saved successfully!");
  } catch (e) {
    console.error("Error saving zone:", e);
  } finally {
    cancelDrawingZone();
  }
}

// Connect Modal Controls
function openConnectModal() {
  document.getElementById("connect-modal").classList.add("open");
  document.getElementById("backend-url-input").value = backendUrl || "";
}

function closeConnectModal() {
  document.getElementById("connect-modal").classList.remove("open");
}

function setBackendPreset(val) {
  document.getElementById("backend-url-input").value = val;
}

function submitBackendConnect() {
  const url = document.getElementById("backend-url-input").value.trim().replace(/\/$/, "");
  backendUrl = url;
  localStorage.setItem("rest_eye_backend_url", backendUrl);
  closeConnectModal();
  isDemoMode = false;
  
  const img = document.getElementById("stream-img");
  img.src = `${backendUrl}/api/stream?t=` + Date.now();
  
  fetchStatus();
  fetchAlerts();
}

// Source Modal Controls
function openSourceModal() {
  document.getElementById("source-modal").classList.add("open");
}

function closeSourceModal() {
  document.getElementById("source-modal").classList.remove("open");
}

function setSourcePreset(val) {
  document.getElementById("source-input").value = val;
}

async function submitSourceChange() {
  const val = document.getElementById("source-input").value.trim();
  if (!val) return;

  if (!isDemoMode) {
    await fetch(`${backendUrl}/api/source`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source: val })
    });
  }

  closeSourceModal();
  setTimeout(() => {
    const img = document.getElementById("stream-img");
    img.src = `${backendUrl}/api/stream?t=` + Date.now();
  }, 500);
}

function handleStreamError() {
  if (!isDemoMode) {
    setTimeout(() => {
      const img = document.getElementById("stream-img");
      img.src = `${backendUrl}/api/stream?t=` + Date.now();
    }, 2000);
  }
}
