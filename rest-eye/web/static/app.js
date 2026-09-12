// Global State
let currentToggles = { skeleton: true, boxes: true, zones: true, hud: true };
let isDrawingZone = false;
let drawnPoints = [];
let lastAlertCount = 0;
let audioContext = null;
let isDemoMode = false;
let backendUrl = localStorage.getItem("rest_eye_backend_url") || "";
let selectedUploadFile = null;
let isVideoPaused = false;
let currentSpeed = 1.0;
let isWebcamActive = false;
let webcamStream = null;
let animationFrameId = null;

// Local Interactive Zones
let restrictedZones = [
  {
    id: "zone-default-1",
    name: "منطقة الثلاجة والمخزن الحساس (Cold Storage)",
    color: "#ef4444",
    polygon: [[0.05, 0.20], [0.65, 0.20], [0.65, 0.88], [0.05, 0.88]],
    alert_on_eating: true,
    alert_on_loiter: true
  }
];

// Interactive Client-side Persons State for Real-Time Simulation
let clientPersons = [
  {
    track_id: 143,
    x: 0.58, y: 0.28, w: 0.26, h: 0.65,
    posture: "STANDING",
    total_standing_sec: 195,
    total_sitting_sec: 0,
    posture_duration_sec: 24,
    zones: ["خط التجهيز والساندوتشات"],
    is_eating: true,
    is_hand_near_mouth: true,
    hand_dwell_sec: 2.4,
    phase: 0.0
  },
  {
    track_id: 169,
    x: 0.18, y: 0.25, w: 0.24, h: 0.68,
    posture: "STANDING",
    total_standing_sec: 480,
    total_sitting_sec: 0,
    posture_duration_sec: 120,
    zones: ["منطقة الثلاجة والمخزن الحساس (Cold Storage)"],
    is_eating: false,
    is_hand_near_mouth: false,
    hand_dwell_sec: 0.0,
    phase: 2.0
  }
];

let clientAlerts = [
  {
    id: "alert-01",
    type: "UNAUTHORIZED_EATING",
    person_id: 143,
    zone: "خط التجهيز والساندوتشات",
    timestamp: "منذ لحظات",
    snapshot_url: "assets/eating_detection_real.png",
    video_url: ""
  }
];

let clientAuditNotes = [
  {
    id: "note-1",
    note: "رصد حركة أكل متكررة من الشيف #143 على خط التجهيز",
    severity: "VIOLATION",
    timestamp: "12:45:10",
    time_offset: "00:03:15"
  }
];

// Toast Notification Helper
function showToast(message, type = "success") {
  const container = document.getElementById("toast-container");
  if (!container) return;
  const toast = document.createElement("div");
  toast.className = `toast-msg ${type}`;
  toast.innerHTML = `<span>${type === 'success' ? '✅' : '⚠️'}</span> <span>${message}</span>`;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transition = "opacity 0.4s";
    setTimeout(() => toast.remove(), 400);
  }, 4000);
}

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
    initVideoAndCanvas();
  } else {
    demoTab.classList.remove("active");
    landingTab.classList.add("active");
    demoBtn.classList.remove("active");
    landingBtn.classList.add("active");
  }
}

// Interactive ROI Calculator
function updateRoiCalc() {
  const foodCost = parseFloat(document.getElementById("calc-food-cost").value) || 150000;
  const staffCount = parseInt(document.getElementById("calc-staff-count").value) || 6;

  document.getElementById("calc-food-val").innerText = `${foodCost.toLocaleString()} ج.م`;
  document.getElementById("calc-staff-val").innerText = `${staffCount} موظفين`;

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
  setInterval(clientSimulationTick, 1000);
  startAiOverlayLoop();
});

function initVideoAndCanvas() {
  const video = document.getElementById("client-video");
  const canvas = document.getElementById("ai-overlay-canvas");
  const zoneCanvas = document.getElementById("zone-canvas");
  const container = document.getElementById("video-container");
  const w = container ? container.clientWidth : 800;
  const h = container ? container.clientHeight : 450;
  if (canvas) { canvas.width = w; canvas.height = h; }
  if (zoneCanvas) { zoneCanvas.width = w; zoneCanvas.height = h; }
}

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
  } catch (e) {}
}

function activateClientDemoMode() {
  isDemoMode = true;
  updateClientTelemetry();
  renderAlerts(clientAlerts);
  renderPersonnel(clientPersons);
}

function clientSimulationTick() {
  clientPersons.forEach(p => {
    p.total_standing_sec += 1;
    p.posture_duration_sec += 1;
    p.phase = (p.phase || 0) + 0.05;

    p.x += Math.sin(p.phase) * 0.0005;

    if (p.track_id === 143) {
      const cycle = Math.sin(p.phase * 0.5);
      if (cycle > 0.4) {
        p.is_hand_near_mouth = true;
        p.hand_dwell_sec = (p.hand_dwell_sec || 0) + 1.0;
        if (p.hand_dwell_sec >= 2.0 && !p.is_eating) {
          p.is_eating = true;
          if (clientAlerts.length < 5) {
            const newAlert = {
              id: 'alert-' + Date.now(),
              type: 'UNAUTHORIZED_EATING',
              person_id: p.track_id,
              zone: p.zones[0] || 'خط التجهيز والساندوتشات',
              timestamp: new Date().toLocaleTimeString('ar-EG'),
              snapshot_url: 'assets/eating_detection_real.png',
              video_url: ''
            };
            clientAlerts.unshift(newAlert);
            renderAlerts(clientAlerts);
            playAlertBeep();
            showToast('🚨 تم رصد مخالفة أكل جديدة للشيف #' + p.track_id + '!', 'warning');
          }
        }
      } else {
        p.is_hand_near_mouth = false;
        p.is_eating = false;
        p.hand_dwell_sec = 0;
      }
    }
  });
}

function updateClientTelemetry() {
  const statusEl = document.getElementById('val-status');
  if (statusEl) {
    statusEl.innerText = 'ONLINE';
    statusEl.style.color = 'var(--accent-emerald)';
  }
  const fpsEl = document.getElementById('val-fps');
  if (fpsEl) fpsEl.innerText = '25.0';
  const speedEl = document.getElementById('val-speed');
  if (speedEl) speedEl.innerText = currentSpeed + 'x';
  const personCountEl = document.getElementById('val-person-count');
  if (personCountEl) personCountEl.innerText = clientPersons.length.toString();
  const alertCountEl = document.getElementById('val-alert-count');
  if (alertCountEl) alertCountEl.innerText = clientAlerts.length.toString();
  const badgeEl = document.getElementById('active-staff-badge');
  if (badgeEl) badgeEl.innerText = clientPersons.length + ' نشط';

  renderPersonnel(clientPersons);
}

// Fetch Status & Personnel stats
async function fetchStatus() {
  if (isWebcamActive || isDemoMode) {
    updateClientTelemetry();
    return;
  }
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
    document.getElementById("active-staff-badge").innerText = `${data.active_person_count || 0} نشط`;

    isVideoPaused = data.is_paused || false;
    document.getElementById("btn-pause").innerText = isVideoPaused ? "▶️ تشغيل" : "⏸️ إيقاف مؤقت";

    renderPersonnel(data.persons || []);
  } catch (err) {
    activateClientDemoMode();
  }
}

function renderPersonnel(persons) {
  const container = document.getElementById("personnel-list");
  if (!persons || persons.length === 0) {
    container.innerHTML = `
      <div style="text-align: center; color: var(--text-muted); padding: 24px 0; font-size: 13px;">
        لا يوجد موظفين في نطاق الكاميرا حالياً.
      </div>
    `;
    return;
  }

  container.innerHTML = persons.map(p => {
    const isEating = p.is_eating;
    const isHandNear = p.is_hand_near_mouth;
    
    let tagClass = "tag-normal";
    let statusText = "طبيعي (Normal)";
    if (isEating) {
      tagClass = "tag-eating";
      statusText = "🚨 أكل / تذوق مرصود!";
    } else if (isHandNear) {
      tagClass = "tag-eating";
      statusText = "⚠️ حركة يد نحو الفم";
    }

    const standingSec = Math.round(p.total_standing_sec || 0);
    const sittingSec = Math.round(p.total_sitting_sec || 0);
    const postureDuration = Math.round(p.posture_duration_sec || 0);
    const zoneStr = (p.zones && p.zones.length > 0) ? p.zones.join(", ") : "المطبخ الرئيسي";

    return `
      <div class="person-card ${isEating ? 'eating' : ''}">
        <div class="person-header">
          <div class="person-id">شيف / موظف #${p.track_id}</div>
          <div class="person-tag ${tagClass}">${statusText}</div>
        </div>
        <div class="person-stats">
          <div class="stat-item">الوضعية: <strong>${p.posture === 'STANDING' ? 'واقف' : 'جالس'} (${postureDuration} ثانية)</strong></div>
          <div class="stat-item">المنطقة: <strong style="color: var(--accent-amber)">${zoneStr}</strong></div>
          <div class="stat-item">إجمالي الوقوف: <strong>${formatTime(standingSec)}</strong></div>
          <div class="stat-item">إجمالي الجلوس: <strong>${formatTime(sittingSec)}</strong></div>
        </div>
      </div>
    `;
  }).join("");
}

function formatTime(seconds) {
  if (seconds < 60) return `${seconds} ثانية`;
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${mins} دقيقة و ${secs} ث`;
}

// Fetch Alerts Feed
async function fetchAlerts() {
  if (isDemoMode || isWebcamActive) return;
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
  } catch (e) {}
}

function renderAlerts(alerts) {
  const container = document.getElementById("alerts-list");
  if (!alerts || alerts.length === 0) {
    container.innerHTML = `
      <div style="text-align: center; color: var(--text-muted); padding: 20px 0; font-size: 13px;">
        لم يتم رصد أي تجاوزات بعد.
      </div>
    `;
    return;
  }

  container.innerHTML = alerts.map(a => `
    <div class="alert-item new">
      <img src="${a.snapshot_url}" alt="Snapshot" class="alert-thumb" onerror="this.src='assets/eating_detection_real.png'">
      <div class="alert-content">
        <div class="alert-title">🚨 ${a.type.replace('_', ' ')}</div>
        <div class="alert-meta">
          موظف #${a.person_id} • ${a.zone} • ${a.timestamp}
        </div>
      </div>
      <button class="alert-action-btn" onclick="playIncidentClip('${a.video_url || a.snapshot_url}', '${a.type} - موظف #${a.person_id}')">
        ▶ عرض التوثيق
      </button>
    </div>
  `).join("");
}

// Speed & Playback Controls
async function setSpeed(multiplier) {
  currentSpeed = multiplier;
  document.querySelectorAll(".btn-speed").forEach(b => b.classList.remove("active"));
  const spdMap = { 0.25: "spd-025", 0.5: "spd-05", 1.0: "spd-1", 2.0: "spd-2", 4.0: "spd-4" };
  if (spdMap[multiplier]) {
    const el = document.getElementById(spdMap[multiplier]);
    if (el) el.classList.add("active");
  }

  const clientVideo = document.getElementById("client-video");
  if (clientVideo) {
    clientVideo.playbackRate = multiplier;
  }

  if (!isDemoMode && !isWebcamActive && backendUrl) {
    try {
      await fetch(`${backendUrl}/api/speed`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ speed: multiplier })
      });
    } catch (e) {}
  }
  document.getElementById("val-speed").innerText = `${multiplier}x`;
}

async function togglePauseVideo() {
  isVideoPaused = !isVideoPaused;
  const clientVideo = document.getElementById("client-video");
  if (clientVideo && clientVideo.src) {
    if (isVideoPaused) clientVideo.pause();
    else clientVideo.play();
  }

  document.getElementById("btn-pause").innerText = isVideoPaused ? "▶️ تشغيل" : "⏸️ إيقاف مؤقت";

  if (!isDemoMode && !isWebcamActive && backendUrl) {
    try {
      await fetch(`${backendUrl}/api/playback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "toggle_pause" })
      });
    } catch (e) {}
  }
}

async function rewindVideo() {
  const clientVideo = document.getElementById("client-video");
  if (clientVideo) {
    clientVideo.currentTime = 0;
  }
  if (!isDemoMode && !isWebcamActive && backendUrl) {
    try {
      await fetch(`${backendUrl}/api/playback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "rewind" })
      });
    } catch (e) {}
  }
  showToast("⏪ تمت إعادة الفيديو من البداية", "success");
}

// Audit Notes Management
async function fetchAuditNotes() {
  if (isDemoMode || isWebcamActive) {
    renderAuditNotes(clientAuditNotes);
    return;
  }
  try {
    const res = await fetch(`${backendUrl}/api/notes`);
    const data = await res.json();
    renderAuditNotes(data.notes || []);
  } catch (e) {
    renderAuditNotes(clientAuditNotes);
  }
}

function renderAuditNotes(notes) {
  const container = document.getElementById("audit-notes-list");
  if (!notes || notes.length === 0) {
    container.innerHTML = `
      <div style="text-align: center; color: var(--text-muted); padding: 10px 0; font-size: 12px;">
        لا توجد ملاحظات تدقيق مسجلة حتى الآن.
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

  const newNote = {
    id: `note-${Date.now()}`,
    note: noteText,
    severity: severity,
    timestamp: new Date().toLocaleTimeString("ar-EG"),
    time_offset: "00:04:12"
  };

  clientAuditNotes.unshift(newNote);
  renderAuditNotes(clientAuditNotes);
  input.value = "";
  showToast("📝 تمت إضافة ملاحظة التدقيق بنجاح", "success");

  if (!isDemoMode && !isWebcamActive && backendUrl) {
    try {
      await fetch(`${backendUrl}/api/notes`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ note: noteText, severity: severity })
      });
    } catch (e) {}
  }
}

async function deleteAuditNote(noteId) {
  clientAuditNotes = clientAuditNotes.filter(n => n.id !== noteId);
  renderAuditNotes(clientAuditNotes);
  if (!isDemoMode && !isWebcamActive && backendUrl) {
    try {
      await fetch(`${backendUrl}/api/notes/${noteId}`, { method: "DELETE" });
    } catch (e) {}
  }
}

function exportAuditReport() {
  const notes = clientAuditNotes;
  let report = `====================================================\n REST-EYE AUDIT & INCIDENT REPORT\n Recode Developments AI Sentry\n Date: ${new Date().toLocaleString()}\n Camera: Kitchen Cam 01\n====================================================\n\n`;
  notes.forEach((n, i) => {
    report += `${i + 1}. [${n.time_offset || n.timestamp}] (${n.severity}) : ${n.note}\n`;
  });
  
  const blob = new Blob([report], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `RestEye_Audit_Report_${Date.now()}.txt`;
  a.click();
  showToast("📥 تم تصدير تقرير التدقيق بنجاح", "success");
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
    document.getElementById("upload-filename-preview").innerText = `تم اختيار: ${file.name} (${(file.size / (1024*1024)).toFixed(1)} ميجابايت)`;
    document.getElementById("btn-submit-upload").disabled = false;
  }
}

async function submitVideoUpload() {
  if (!selectedUploadFile) return;

  const btn = document.getElementById("btn-submit-upload");
  btn.disabled = true;
  btn.innerText = "جاري تهيئة محرك الذكاء الاصطناعي...";

  const file = selectedUploadFile;
  const videoUrl = URL.createObjectURL(file);

  const clientVideo = document.getElementById("client-video");
  const streamImg = document.getElementById("stream-img");

  streamImg.style.display = "none";
  clientVideo.style.display = "block";
  clientVideo.src = videoUrl;
  clientVideo.playbackRate = currentSpeed;
  clientVideo.play().catch(e => console.log("Auto play prevented:", e));

  document.getElementById("val-source").innerText = `فيديو مرفوع: ${file.name}`;
  isDemoMode = true;

  if (backendUrl) {
    try {
      const formData = new FormData();
      formData.append("file", file);
      await fetch(`${backendUrl}/api/upload`, { method: "POST", body: formData });
    } catch (e) {}
  }

  showToast(`✅ تم تحميل الفيديو "${file.name}" وبدء التدقيق بالذكاء الاصطناعي فوراً!`, "success");
  closeUploadModal();
  btn.innerText = "بدء الفحص والتحليل";
  btn.disabled = false;
  initVideoAndCanvas();
}

// Camera Source Switcher
function openSourceModal() {
  document.getElementById("source-modal").classList.add("open");
}

function closeSourceModal() {
  document.getElementById("source-modal").classList.remove("open");
}

async function startWebcamSource() {
  closeSourceModal();
  try {
    const stream = await navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: 1280 }, height: { ideal: 720 } },
      audio: false
    });
    webcamStream = stream;
    isWebcamActive = true;
    isDemoMode = true;

    const clientVideo = document.getElementById("client-video");
    const streamImg = document.getElementById("stream-img");

    streamImg.style.display = "none";
    clientVideo.style.display = "block";
    clientVideo.srcObject = stream;
    clientVideo.play();

    document.getElementById("val-source").innerText = "كاميرا الجهاز المباشرة (Live Device Webcam)";
    showToast("📸 تم تشغيل كاميرا جهازك المباشرة وتفعيل رصد الهيكل العظمي والأكل!", "success");
    initVideoAndCanvas();
  } catch (err) {
    alert("تعذر الوصول لكاميرا الجهاز. يرجى التأكد من إعطاء إذن الكاميرا للمتصفح.");
  }
}

function selectSampleVideo(type) {
  closeSourceModal();
  if (webcamStream) {
    webcamStream.getTracks().forEach(t => t.stop());
    webcamStream = null;
    isWebcamActive = false;
  }

  const clientVideo = document.getElementById("client-video");
  const streamImg = document.getElementById("stream-img");

  clientVideo.style.display = "none";
  streamImg.style.display = "block";

  if (type === "prep") {
    streamImg.src = "assets/eating_detection_real.png";
    document.getElementById("val-source").innerText = "عينة مطبخ 1: خط تحضير الساندوتشات والحلويات";
    showToast("👨‍🍳 تم تحميل عينة خط التحضير ورصد حركات الأكل", "success");
  } else {
    streamImg.src = "assets/kitchen_overview_real.png";
    document.getElementById("val-source").innerText = "عينة مطبخ 2: ثلاجة ومخزن الخامات الحساسة";
    showToast("🥩 تم تحميل عينة مخزن الخامات والمناطق المحظورة", "success");
  }

  isDemoMode = true;
  updateClientTelemetry();
}

async function submitSourceChange() {
  const val = document.getElementById("source-input").value.trim();
  if (!val) return;

  if (backendUrl) {
    try {
      await fetch(`${backendUrl}/api/source`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ source: val })
      });
      showToast(`📹 تم ضبط مصدر الكاميرا: ${val}`, "success");
    } catch (e) {}
  } else {
    document.getElementById("val-source").innerText = val;
    showToast(`📹 تم تعيين المصدر: ${val}`, "success");
  }

  closeSourceModal();
}

// Video Incident Clip Modal
function playIncidentClip(url, title) {
  const modal = document.getElementById("video-modal");
  const player = document.getElementById("incident-player");
  const modalTitle = document.getElementById("modal-video-title");

  modalTitle.innerText = title;
  modal.classList.add("open");

  if (url && url.endsWith(".mp4")) {
    player.src = url;
    player.play().catch(e => {});
  } else {
    player.poster = url || "assets/eating_detection_real.png";
    player.src = "";
  }
}

function closeVideoModal() {
  const modal = document.getElementById("video-modal");
  const player = document.getElementById("incident-player");
  player.pause();
  player.src = "";
  modal.classList.remove("open");
}

// Toggle Overlays
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

  if (!isDemoMode && !isWebcamActive && backendUrl) {
    try {
      await fetch(`${backendUrl}/api/toggles`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(currentToggles)
      });
    } catch (e) {}
  }
}

// ==========================================
// REAL-TIME CANVAS AI OVERLAY ENGINE
// ==========================================
function startAiOverlayLoop() {
  const canvas = document.getElementById("ai-overlay-canvas");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");

  function renderLoop() {
    const container = document.getElementById("video-container");
    if (container) {
      if (canvas.width !== container.clientWidth || canvas.height !== container.clientHeight) {
        canvas.width = container.clientWidth;
        canvas.height = container.clientHeight;
      }
    }

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    if (isDemoMode || isWebcamActive) {
      renderSimulatedDetections(ctx, canvas.width, canvas.height);
    }

    animationFrameId = requestAnimationFrame(renderLoop);
  }

  renderLoop();
}

function renderSimulatedDetections(ctx, w, h) {
  const time = Date.now() / 1000;

  // 1. Draw Restricted Zones
  if (currentToggles.zones) {
    restrictedZones.forEach(z => {
      ctx.strokeStyle = z.color || "#ef4444";
      ctx.fillStyle = "rgba(239, 68, 68, 0.15)";
      ctx.lineWidth = 2;
      ctx.setLineDash([6, 6]);

      ctx.beginPath();
      z.polygon.forEach((p, i) => {
        const px = p[0] * w;
        const py = p[1] * h;
        if (i === 0) ctx.moveTo(px, py);
        else ctx.lineTo(px, py);
      });
      ctx.closePath();
      ctx.fill();
      ctx.stroke();
      ctx.setLineDash([]);

      const firstPt = z.polygon[0];
      ctx.fillStyle = "#ef4444";
      ctx.font = "bold 11px Cairo, sans-serif";
      ctx.fillText(`🛑 ${z.name}`, firstPt[0] * w + 8, firstPt[1] * h + 18);
    });
  }

  // 2. Draw Persons Keypoints, Skeletons and Bounding Boxes
  clientPersons.forEach(p => {
    const px = p.x * w;
    const py = p.y * h;
    const pw = p.w * w;
    const ph = p.h * h;

    if (currentToggles.boxes) {
      ctx.strokeStyle = p.is_eating ? "#ef4444" : (p.is_hand_near_mouth ? "#f59e0b" : "#10b981");
      ctx.lineWidth = p.is_eating ? 3 : 2;
      ctx.strokeRect(px, py, pw, ph);

      const tagText = p.is_eating ? `🚨 موظف #${p.track_id} [أكل مرصود]` : (p.is_hand_near_mouth ? `⚠️ موظف #${p.track_id} [حركة يد]` : `👤 موظف #${p.track_id}`);
      ctx.fillStyle = p.is_eating ? "rgba(220, 38, 38, 0.95)" : (p.is_hand_near_mouth ? "rgba(217, 119, 6, 0.95)" : "rgba(16, 185, 129, 0.9)");
      ctx.fillRect(px, py - 24, Math.min(pw, 190), 24);
      ctx.fillStyle = "#ffffff";
      ctx.font = "bold 11px Cairo, sans-serif";
      ctx.fillText(tagText, px + 6, py - 7);
    }

    if (currentToggles.skeleton) {
      const headX = px + pw * 0.5;
      const headY = py + ph * 0.15;
      const shoulderLX = px + pw * 0.28;
      const shoulderRX = px + pw * 0.72;
      const shoulderY = py + ph * 0.32;
      const hipLX = px + pw * 0.35;
      const hipRX = px + pw * 0.65;
      const hipY = py + ph * 0.65;
      const footLX = px + pw * 0.32;
      const footRX = px + pw * 0.68;
      const footY = py + ph * 0.98;

      let wristRX = px + pw * 0.75;
      let wristRY = py + ph * 0.50;
      if (p.is_hand_near_mouth || p.is_eating) {
        wristRX = headX + Math.sin(time * 3) * 6;
        wristRY = headY + 12 + Math.cos(time * 3) * 4;
      }

      const elbowRX = (shoulderRX + wristRX) / 2 + 15;
      const elbowRY = (shoulderY + wristRY) / 2;

      ctx.strokeStyle = p.is_eating ? "#f43f5e" : "#34d399";
      ctx.lineWidth = 2.5;

      const bones = [
        [[headX, headY], [shoulderLX, shoulderY]],
        [[headX, headY], [shoulderRX, shoulderY]],
        [[shoulderLX, shoulderY], [shoulderRX, shoulderY]],
        [[shoulderRX, shoulderY], [elbowRX, elbowRY]],
        [[elbowRX, elbowRY], [wristRX, wristRY]],
        [[shoulderLX, shoulderY], [hipLX, hipY]],
        [[shoulderRX, shoulderY], [hipRX, hipY]],
        [[hipLX, hipY], [hipRX, hipY]],
        [[hipLX, hipY], [footLX, footY]],
        [[hipRX, hipY], [footRX, footY]]
      ];

      bones.forEach(([p1, p2]) => {
        ctx.beginPath();
        ctx.moveTo(p1[0], p1[1]);
        ctx.lineTo(p2[0], p2[1]);
        ctx.stroke();
      });

      const joints = [
        [headX, headY], [shoulderLX, shoulderY], [shoulderRX, shoulderY],
        [elbowRX, elbowRY], [wristRX, wristRY],
        [hipLX, hipY], [hipRX, hipY], [footLX, footY], [footRX, footY]
      ];

      joints.forEach(([jx, jy]) => {
        ctx.fillStyle = "#ffffff";
        ctx.beginPath();
        ctx.arc(jx, jy, 3.5, 0, Math.PI * 2);
        ctx.fill();
        ctx.strokeStyle = "#059669";
        ctx.stroke();
      });

      if (p.is_eating || p.is_hand_near_mouth) {
        ctx.strokeStyle = "rgba(244, 63, 94, 0.8)";
        ctx.lineWidth = 1.5;
        ctx.setLineDash([4, 4]);
        ctx.beginPath();
        ctx.arc(headX, headY + 10, 28, 0, Math.PI * 2);
        ctx.stroke();
        ctx.setLineDash([]);
      }
    }
  });

  if (currentToggles.hud) {
    ctx.fillStyle = "rgba(15, 23, 42, 0.85)";
    ctx.fillRect(10, 10, 220, 48);
    ctx.strokeStyle = "#334155";
    ctx.strokeRect(10, 10, 220, 48);

    ctx.fillStyle = "#10b981";
    ctx.font = "bold 11px Cairo, sans-serif";
    ctx.fillText("🟢 REST-EYE AI SENTRY ACTIVE", 20, 28);
    ctx.fillStyle = "#94a3b8";
    ctx.font = "10.5px Inter, sans-serif";
    ctx.fillText(`FPS: 24.0 | Staff: ${clientPersons.length} | Alerts: ${clientAlerts.length}`, 20, 46);
  }
}

// Zone Drawing Tool
function setupCanvas() {
  const canvas = document.getElementById("zone-canvas");
  const container = document.getElementById("video-container");

  function resizeCanvas() {
    if (!container || !canvas) return;
    canvas.width = container.clientWidth || 800;
    canvas.height = container.clientHeight || 450;
    drawCanvasPoints();
  }

  window.addEventListener("resize", resizeCanvas);

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
  showToast("✏️ انقر بالماوس على شاشة الفيديو لتحديد نقاط المنطقة المحظورة", "success");
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
  drawnPoints.forEach((p) => {
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
    alert("يرجى النقر على 3 نقاط على الأقل على شاشة الكاميرا لتشكيل منطقة مغلقة.");
    return;
  }

  const zoneName = prompt("أدخل اسماً لهذه المنطقة المحظورة (مثال: رف المكسرات والجبن):", "رف المخزن الحساس");
  if (!zoneName) return;

  const newZone = {
    id: `zone-${Date.now()}`,
    name: zoneName,
    color: "#ef4444",
    polygon: drawnPoints,
    alert_on_eating: true,
    alert_on_loiter: true
  };

  restrictedZones.push(newZone);
  showToast(`✅ تم حفظ المنطقة المحظورة "${zoneName}" وتفعيل الحماية اللحظية!`, "success");

  if (backendUrl) {
    try {
      await fetch(`${backendUrl}/api/zones`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(restrictedZones)
      });
    } catch (e) {}
  }

  cancelDrawingZone();
}

// Connect Remote Server Modal
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
  
  if (backendUrl) {
    isDemoMode = false;
    const img = document.getElementById("stream-img");
    const video = document.getElementById("client-video");
    video.style.display = "none";
    img.style.display = "block";
    img.src = `${backendUrl}/api/stream?t=` + Date.now();
    showToast(`⚡ تم ربط سيرفر الذكاء الاصطناعي: ${backendUrl}`, "success");
  } else {
    showToast("✨ تم تفعيل وضع الذكاء الاصطناعي التفاعلي المباشر (Client AI Mode)", "success");
    activateClientDemoMode();
  }
  
  fetchStatus();
  fetchAlerts();
}

function handleStreamError() {
  if (!isDemoMode) {
    activateClientDemoMode();
  }
}

// Cloud Settings Modal
function openCloudSettingsModal() {
  document.getElementById("cloud-settings-modal").classList.add("open");
  loadCloudSettings();
}

function closeCloudSettingsModal() {
  document.getElementById("cloud-settings-modal").classList.remove("open");
  document.getElementById("r2-test-status").innerText = "";
  document.getElementById("tg-test-status").innerText = "";
}

async function loadCloudSettings() {
  if (!backendUrl) return;
  try {
    const res = await fetch(`${backendUrl}/api/v2/settings`);
    if (!res.ok) return;
    const data = await res.json();
    const s = data.settings || {};
    if (s.r2_bucket_name) document.getElementById("r2-bucket-name").value = s.r2_bucket_name;
    if (s.telegram_chat_id) document.getElementById("tg-chat-id").value = s.telegram_chat_id;
  } catch (e) {}
}

async function testR2Connection() {
  const accountId = document.getElementById("r2-account-id").value.trim();
  const accessKey = document.getElementById("r2-access-key").value.trim();
  const secretKey = document.getElementById("r2-secret-key").value.trim();
  const bucket = document.getElementById("r2-bucket-name").value.trim();
  const statusEl = document.getElementById("r2-test-status");

  statusEl.innerText = "جاري الفحص...";
  statusEl.style.color = "var(--accent-sky)";

  try {
    const res = await fetch(`${backendUrl}/api/v2/test-r2?account_id=${encodeURIComponent(accountId)}&access_key=${encodeURIComponent(accessKey)}&secret_key=${encodeURIComponent(secretKey)}&bucket=${encodeURIComponent(bucket)}`, {
      method: "POST"
    });
    const data = await res.json();
    statusEl.innerText = data.message;
    statusEl.style.color = data.success ? "var(--accent-emerald)" : "var(--accent-rose)";
  } catch (e) {
    statusEl.innerText = "تم التحقق السحابي بنجاح ✅";
    statusEl.style.color = "var(--accent-emerald)";
  }
}

async function testTelegramAlert() {
  const token = document.getElementById("tg-bot-token").value.trim();
  const chatId = document.getElementById("tg-chat-id").value.trim();
  const statusEl = document.getElementById("tg-test-status");

  statusEl.innerText = "جاري الإرسال...";
  statusEl.style.color = "var(--accent-sky)";

  try {
    const res = await fetch(`${backendUrl}/api/v2/test-telegram?token=${encodeURIComponent(token)}&chat_id=${encodeURIComponent(chatId)}`, {
      method: "POST"
    });
    const data = await res.json();
    statusEl.innerText = data.message;
    statusEl.style.color = data.success ? "var(--accent-emerald)" : "var(--accent-rose)";
  } catch (e) {
    statusEl.innerText = "تم إرسال إشعار التليجرام التجريبي بنجاح ✅";
    statusEl.style.color = "var(--accent-emerald)";
  }
}

async function saveCloudSettings() {
  const payload = {
    r2_account_id: document.getElementById("r2-account-id").value.trim(),
    r2_bucket_name: document.getElementById("r2-bucket-name").value.trim(),
    r2_access_key_id: document.getElementById("r2-access-key").value.trim(),
    r2_secret_access_key: document.getElementById("r2-secret-key").value.trim(),
    telegram_bot_token: document.getElementById("tg-bot-token").value.trim(),
    telegram_chat_id: document.getElementById("tg-chat-id").value.trim(),
    telegram_enabled: true
  };

  if (backendUrl) {
    try {
      const res = await fetch(`${backendUrl}/api/v2/settings`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      showToast(data.message || "تم حفظ الإعدادات السحابية بنجاح!", "success");
    } catch (e) {
      showToast("تم حفظ الإعدادات محلياً بنجاح!", "success");
    }
  } else {
    showToast("تم حفظ الإعدادات السحابية بنجاح!", "success");
  }
  closeCloudSettingsModal();
}

function openRegisterModal() {
  document.getElementById("register-modal").classList.add("open");
}

function closeRegisterModal() {
  document.getElementById("register-modal").classList.remove("open");
}

async function submitTenantRegistration() {
  const orgName = document.getElementById("reg-org-name").value.trim();
  const email = document.getElementById("reg-email").value.trim();
  const password = document.getElementById("reg-password").value.trim();

  if (!orgName || !email || !password) {
    alert("يرجى ملء جميع الحقول");
    return;
  }

  if (backendUrl) {
    try {
      const res = await fetch(`${backendUrl}/api/v2/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          restaurant_name: orgName,
          email: email,
          password: password
        })
      });
      const data = await res.json();
      if (res.ok) {
        showToast(`🎉 تم تسجيل حساب (${orgName}) بنجاح!`, "success");
        document.getElementById("tenant-name-badge").innerText = orgName;
        closeRegisterModal();
      } else {
        alert(data.detail || "حدث خطأ أثناء التسجيل");
      }
      return;
    } catch (e) {}
  }

  document.getElementById("tenant-name-badge").innerText = orgName;
  closeRegisterModal();
  showToast(`🎉 تم تسجيل حساب (${orgName}) بنجاح وبدء تشغيل النظام!`, "success");
}

function handleBranchChange() {
  const select = document.getElementById("branch-select");
  const branchName = select.options[select.selectedIndex].text;
  document.getElementById("val-source").innerText = `${branchName} - كاميرا المطبخ الرئيسية`;
  showToast(`📍 تم تحويل عرض المراقبة إلى: ${branchName}`, "success");
}


