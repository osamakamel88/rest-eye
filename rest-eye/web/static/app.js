// State variables
let currentToggles = { skeleton: true, boxes: true, zones: true, hud: true };
let isDrawingZone = false;
let drawnPoints = []; // [{x, y}] normalized 0.0-1.0
let lastAlertCount = 0;
let audioContext = null;
let isDemoMode = false;
let backendUrl = "";

// Initialize
document.addEventListener("DOMContentLoaded", () => {
  setupCanvas();
  fetchStatus();
  fetchAlerts();
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
    document.getElementById("val-person-count").innerText = data.active_person_count || "0";
    document.getElementById("val-alert-count").innerText = data.total_alerts || "0";
    document.getElementById("val-source").innerText = data.source || "-";
    document.getElementById("active-staff-badge").innerText = `${data.active_person_count || 0} Active`;

    renderPersonnel(data.persons || []);
  } catch (e) {
    // If backend is not reached (e.g. running on Vercel as a standalone client demo), activate interactive demo mode
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
  
  // Replace missing MJPEG stream with interactive demo display if image fails
  const img = document.getElementById("stream-img");
  if (!img.complete || img.naturalWidth === 0) {
    img.src = "https://images.unsplash.com/photo-1556910103-1c02745aae4d?w=1280&q=80";
  }

  // Simulated live personnel
  const mockPersons = [
    {
      track_id: 209,
      posture: "STANDING",
      posture_duration_sec: 14,
      total_standing_sec: 185,
      total_sitting_sec: 0,
      zones: ["Restricted Inventory"],
      is_eating: true,
      is_hand_near_mouth: true
    },
    {
      track_id: 231,
      posture: "STANDING",
      posture_duration_sec: 240,
      total_standing_sec: 720,
      total_sitting_sec: 0,
      zones: ["Prep Counter"],
      is_eating: false,
      is_hand_near_mouth: false
    },
    {
      track_id: 186,
      posture: "STANDING",
      posture_duration_sec: 45,
      total_standing_sec: 320,
      total_sitting_sec: 0,
      zones: ["Main Kitchen"],
      is_eating: false,
      is_hand_near_mouth: false
    }
  ];

  document.getElementById("val-person-count").innerText = "3";
  document.getElementById("val-alert-count").innerText = "1";
  document.getElementById("active-staff-badge").innerText = "3 Active";
  renderPersonnel(mockPersons);

  const mockAlerts = [
    {
      id: "demo-01",
      type: "UNAUTHORIZED_EATING",
      person_id: 209,
      zone: "Restricted Inventory / Storage",
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
      tagClass = "tag-loiter";
      statusText = "Hand Near Mouth";
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
    // handled by fetchStatus demo mode
  }
}

function renderAlerts(alerts) {
  const container = document.getElementById("alerts-list");
  if (!alerts || alerts.length === 0) {
    container.innerHTML = `
      <div style="text-align: center; color: var(--text-muted); padding: 24px 0; font-size: 13px;">
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
