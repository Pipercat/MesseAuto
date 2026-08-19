const screens = {
  home: document.getElementById("home-screen"),
  pi: document.getElementById("pi-screen"),
  vehicle: document.getElementById("vehicle-screen"),
  tests: document.getElementById("tests-screen"),
};

const backButton = document.getElementById("back-button");
const systemMode = document.getElementById("system-mode");
const systemPill = document.querySelector(".system-pill");
const activeCount = document.getElementById("active-count");
const motorReadout = document.getElementById("motor-readout");
const voltageReadout = document.getElementById("voltage-readout");
const motorPercent = document.getElementById("motor-percent");
const motorVoltage = document.getElementById("motor-voltage");
const motorSlider = document.getElementById("motor-slider");
const testState = document.getElementById("test-state");
const testResult = document.getElementById("test-result");
const testLog = document.getElementById("test-log");
const chart = document.getElementById("live-chart");
const chartContext = chart.getContext("2d");
const piMode = document.getElementById("pi-mode");
const piGpioMode = document.getElementById("pi-gpio-mode");
const piRelayMode = document.getElementById("pi-relay-mode");
const piEspStatus = document.getElementById("pi-esp-status");
const piDbStatus = document.getElementById("pi-db-status");
const piActionStatus = document.getElementById("pi-action-status");

const state = {
  screen: "home",
  pins: [],
  outputs: {},
  effectiveOutputs: {},
  esp32Actor: null,
  databasePi: null,
  lastTestResult: null,
  settings: {},
  motor: 0,
  hardwareMode: "offline",
  testRunning: false,
  graphData: [],
  graphTimer: null,
  motorTimer: null,
};

const fallbackPins = [
  { id: "underbody", label: "Unterboden", gpio: 17, group: "lighting", kind: "digital" },
  { id: "lowBeam", label: "Abblendlicht", gpio: 27, group: "lighting", kind: "digital" },
  { id: "highBeam", label: "Fernlicht", gpio: 25, group: "lighting", kind: "digital" },
  { id: "indicatorLeft", label: "Links", gpio: 26, group: "indicators", kind: "digital" },
  { id: "indicatorRight", label: "Rechts", gpio: 5, group: "indicators", kind: "digital" },
  { id: "hazard", label: "Warnblinker", gpio: 6, group: "indicators", kind: "digital" },
  { id: "freeOne", label: "Frei 1", gpio: 16, group: "extensions", kind: "digital" },
  { id: "freeTwo", label: "Frei 2", gpio: 23, group: "extensions", kind: "digital" },
  { id: "fan", label: "Lüfter", gpio: 24, group: "extensions", kind: "digital" },
];

const shortLabels = {
  underbody: "Unterboden",
  lowBeam: "Abblendlicht",
  highBeam: "Fernlicht",
  indicatorLeft: "Links",
  indicatorRight: "Rechts",
  hazard: "Warnblinker",
  freeOne: "Frei 1",
  freeTwo: "Frei 2",
  fan: "Lüfter",
};

const testPlans = {
  lights: {
    label: "Lichttest",
    steps: [
      ["Unterbodenbeleuchtung einschalten", () => setOutput("underbody", true)],
      ["Abblendlicht einschalten", () => setOutput("lowBeam", true)],
      ["Fernlicht einschalten", () => setOutput("highBeam", true)],
      ["GPIO-Zustand prüfen", waitStep],
      ["Alle Lichter ausschalten", () => setMany(["underbody", "lowBeam", "highBeam"], false)],
    ],
  },
  indicators: {
    label: "Blinkertest",
    steps: [
      ["Blinker links blinken", () => pulseOutput("indicatorLeft", 3)],
      ["Blinker rechts blinken", () => pulseOutput("indicatorRight", 3)],
      ["Warnblinkanlage aktivieren", () => setOutput("hazard", true)],
      ["Blinkausgang prüfen", waitStep],
      ["Blinker ausschalten", () => setMany(["indicatorLeft", "indicatorRight", "hazard"], false)],
    ],
  },
  motor: {
    label: "Motortest",
    steps: [
      ["Motor-PWM auf 100 %", () => setMotor(100)],
      ["PWM-Signal halten", waitStep],
      ["Motor-PWM auf 50 %", () => setMotor(50)],
      ["PWM-Signal halten", waitStep],
      ["Motor-PWM auf 0 %", () => setMotor(0)],
    ],
  },
  fan: {
    label: "Lüftertest",
    steps: [
      ["Lüfter einschalten", () => setOutput("fan", true)],
      ["GPIO-Zustand prüfen", waitStep],
      ["Lüfter ausschalten", () => setOutput("fan", false)],
    ],
  },
  full: {
    label: "Gesamttest",
    steps: [
      ["Licht einschalten", () => setMany(["underbody", "lowBeam", "highBeam"], true)],
      ["Motor-PWM auf 100 %", () => setMotor(100)],
      ["Motor-PWM auf 50 %", () => setMotor(50)],
      ["Motor-PWM auf 0 %", () => setMotor(0)],
      ["Licht ausschalten", () => setMany(["underbody", "lowBeam", "highBeam"], false)],
      ["Blinker prüfen", () => pulseMany(["indicatorLeft", "indicatorRight"], 2)],
      ["Lüfter prüfen", () => pulseOutput("fan", 1)],
      ["System zurücksetzen", resetHardware],
    ],
  },
};

async function apiRequest(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok || payload.ok === false) {
    throw new Error(payload.error || `API-Fehler ${response.status}`);
  }
  return payload;
}

async function loadInitialState() {
  try {
    const payload = await apiRequest("/api/state");
    applyBackendState(payload.state);
    updateSystemMode(payload.state);
    renderControls();
  } catch (error) {
    state.pins = fallbackPins;
    state.outputs = Object.fromEntries(fallbackPins.map((pin) => [pin.id, false]));
    state.hardwareMode = "offline";
    updateSystemMode(null, error);
    renderControls();
  }
  drawGraph();
  routeTo(requestedInitialScreen());
  window.setInterval(refreshRuntimeState, 1000);
  window.setInterval(refreshAdminOverview, 5000);
}

function requestedInitialScreen() {
  const params = new URLSearchParams(window.location.search);
  const requested = params.get("screen") || params.get("route") || "home";
  return Object.prototype.hasOwnProperty.call(screens, requested) ? requested : "home";
}

async function refreshRuntimeState() {
  try {
    const payload = await apiRequest("/api/state");
    applyBackendState(payload.state);
    updateSystemMode(payload.state);
  } catch (error) {
    updateSystemMode(null, error);
  }
}

function applyBackendState(backendState) {
  state.pins = backendState.pins || fallbackPins;
  state.outputs = backendState.outputs || state.outputs;
  state.effectiveOutputs = backendState.effectiveOutputs || state.outputs;
  state.esp32Actor = backendState.esp32Actor || null;
  state.databasePi = backendState.databasePi || null;
  state.lastTestResult = backendState.lastTestResult || null;
  state.settings = backendState.settings || {};
  state.motor = backendState.motor?.percent ?? 0;
  state.hardwareMode = backendState.mode || "unknown";
  motorSlider.value = String(state.motor);
  updateVehicleUi();
  updatePiScreen();
}

function updateSystemMode(backendState, error = null) {
  systemPill.classList.remove("is-gpio", "is-simulation", "is-offline");

  if (error) {
    systemPill.classList.add("is-offline");
    systemMode.textContent = "Offline";
    return;
  }

  if (backendState?.isRealHardware) {
    systemPill.classList.add("is-gpio");
    systemMode.textContent = "GPIO aktiv";
  } else {
    systemPill.classList.add("is-simulation");
    systemMode.textContent = "Simulation";
  }
}

function routeTo(screenName) {
  state.screen = screenName;
  Object.entries(screens).forEach(([name, screen]) => {
    screen.classList.toggle("is-active", name === screenName);
  });
  backButton.hidden = screenName === "home";
  window.scrollTo({ top: 0, behavior: "auto" });

  if (screenName === "tests") {
    drawGraph();
  }

  if (screenName === "pi") {
    updatePiScreen();
    refreshAdminOverview();
  }
}

const READINESS_CLASS = { BEREIT: "is-ready", EINGESCHRÄNKT: "is-limited", "NICHT BEREIT": "is-not-ready" };
const DEVICE_LABELS = { pi1: "Pi 1", pi2: "Pi 2", esp32_actor: "ESP Actor", esp32_sensor_aux: "ESP Sensor/Aux" };

function formatUptime(seconds) {
  if (!Number.isFinite(seconds)) {
    return "--";
  }
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return `${h}h ${m}m`;
}

function formatBytes(bytes) {
  if (!Number.isFinite(bytes)) {
    return "--";
  }
  return `${(bytes / (1024 * 1024)).toFixed(0)} MB`;
}

function renderMetrics(containerId, metrics) {
  const container = document.getElementById(containerId);
  if (!container || !metrics) {
    return;
  }
  container.innerHTML = `
    <div><span>CPU</span><strong>${metrics.cpu.percent.toFixed(0)}%</strong></div>
    <div><span>Temp</span><strong>${metrics.cpu.temperature_c !== null ? metrics.cpu.temperature_c.toFixed(1) + "°C" : "--"}</strong></div>
    <div><span>RAM</span><strong>${metrics.memory.percent.toFixed(0)}%</strong></div>
    <div><span>Disk</span><strong>${metrics.disk.percent.toFixed(0)}%</strong></div>
    <div><span>Swap</span><strong>${metrics.swap.percent.toFixed(0)}%</strong></div>
    ${metrics.sqlite_db_bytes !== undefined ? `<div><span>SQLite</span><strong>${formatBytes(metrics.sqlite_db_bytes)}</strong></div>` : ""}
  `;
}

async function refreshAdminOverview() {
  if (state.screen !== "pi") {
    return;
  }
  try {
    const devicesPayload = await apiRequest("/api/admin/devices");
    const readinessEl = document.getElementById("admin-readiness");
    if (readinessEl) {
      readinessEl.textContent = devicesPayload.readiness;
      readinessEl.className = `admin-readiness ${READINESS_CLASS[devicesPayload.readiness] || ""}`;
    }
    const cardsContainer = document.getElementById("admin-device-cards");
    if (cardsContainer) {
      cardsContainer.innerHTML = Object.entries(devicesPayload.devices)
        .map(([key, info]) => {
          const online = info.status === "online" || info.status === "connected";
          return `
            <div class="admin-device-card ${online ? "is-online" : "is-offline"}">
              <span class="admin-device-name">${DEVICE_LABELS[key] || key}</span>
              <span class="admin-device-status">${online ? "ONLINE" : "OFFLINE"}</span>
            </div>
          `;
        })
        .join("");
    }
  } catch (error) {
    // naechster Poll versucht es erneut
  }

  try {
    const metricsPayload = await apiRequest("/api/admin/metrics");
    renderMetrics("admin-pi1-metrics", metricsPayload.metrics);
    const uptimeEl = document.getElementById("admin-pi1-uptime");
    if (uptimeEl) {
      uptimeEl.textContent = `Uptime ${formatUptime(metricsPayload.metrics.uptime_s)}`;
    }
  } catch (error) {
    // Pi1-Metriken lokal, sollten immer erreichbar sein
  }

  try {
    const pi2Response = await fetch("http://10.42.0.12:9000/api/admin/metrics");
    const pi2Payload = await pi2Response.json();
    if (pi2Payload.ok) {
      renderMetrics("admin-pi2-metrics", pi2Payload.metrics);
      const uptimeEl = document.getElementById("admin-pi2-uptime");
      if (uptimeEl) {
        uptimeEl.textContent = `Uptime ${formatUptime(pi2Payload.metrics.uptime_s)}`;
      }
    }
  } catch (error) {
    const uptimeEl = document.getElementById("admin-pi2-uptime");
    if (uptimeEl) {
      uptimeEl.textContent = "nicht erreichbar";
    }
  }

  try {
    const servicesPayload = await apiRequest("/api/admin/services");
    const container = document.getElementById("admin-services");
    if (container) {
      container.innerHTML = Object.entries(servicesPayload.services)
        .map(([unit, status]) => {
          const canRestart = servicesPayload.restartable.includes(unit);
          return `
            <div class="admin-service-row">
              <span>${unit} — ${status}</span>
              ${canRestart ? `<button class="pi-action-button" type="button" data-admin-restart="${unit}">Neu starten</button>` : ""}
            </div>
          `;
        })
        .join("");
    }
  } catch (error) {
    // naechster Poll versucht es erneut
  }
}

function showConfirmDialog(text) {
  return new Promise((resolve) => {
    const overlay = document.getElementById("admin-confirm-overlay");
    const textEl = document.getElementById("admin-confirm-text");
    const okBtn = document.getElementById("admin-confirm-ok");
    const cancelBtn = document.getElementById("admin-confirm-cancel");
    textEl.textContent = text;
    overlay.hidden = false;

    const cleanup = (result) => {
      overlay.hidden = true;
      okBtn.removeEventListener("click", onOk);
      cancelBtn.removeEventListener("click", onCancel);
      resolve(result);
    };
    const onOk = () => cleanup(true);
    const onCancel = () => cleanup(false);
    okBtn.addEventListener("click", onOk);
    cancelBtn.addEventListener("click", onCancel);
  });
}

document.addEventListener("click", async (event) => {
  const restartButton = event.target.closest("[data-admin-restart]");
  if (restartButton) {
    const unit = restartButton.dataset.adminRestart;
    const confirmed = await showConfirmDialog(`Dienst "${unit}" auf diesem Pi neu starten?`);
    if (!confirmed) {
      return;
    }
    await fetch("/api/admin/service/restart", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ service: unit }),
    }).catch(() => {});
    refreshAdminOverview();
  }

  const powerButton = event.target.closest("[data-admin-power]");
  if (powerButton) {
    const action = powerButton.dataset.adminPower;
    const labels = {
      "pi1-reboot": ["Pi 1", "/api/admin/reboot", "neu starten"],
      "pi1-shutdown": ["Pi 1", "/api/admin/shutdown", "herunterfahren"],
      "pi2-reboot": ["Pi 2", "http://10.42.0.12:9000/api/admin/reboot", "neu starten"],
      "pi2-shutdown": ["Pi 2", "http://10.42.0.12:9000/api/admin/shutdown", "herunterfahren"],
    };
    const [target, path, verb] = labels[action];
    const confirmed = await showConfirmDialog(`${target} wirklich ${verb}? Das Fahrzeug wird vorher sicher ausgeschaltet.`);
    if (!confirmed) {
      return;
    }
    await fetch(path, { method: "POST" }).catch(() => {});
  }
});

function renderControls() {
  const containers = {
    lighting: document.getElementById("lighting-controls"),
    indicators: document.getElementById("indicator-controls"),
    extensions: document.getElementById("extension-controls"),
  };

  Object.values(containers).forEach((container) => {
    container.innerHTML = "";
  });

  state.pins
    .filter((pin) => pin.kind === "digital" && containers[pin.group])
    .forEach((pin) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "control-button";
      button.dataset.output = pin.id;
      button.innerHTML = `
        <span class="control-label">${shortLabels[pin.id] || pin.label}</span>
        <span class="control-gpio">GPIO ${pin.gpio}</span>
      `;
      button.addEventListener("click", () => setOutput(pin.id, !state.outputs[pin.id]));
      containers[pin.group].appendChild(button);
    });

  updateVehicleUi();
  updatePiScreen();
}

async function setOutput(outputId, value) {
  setLocalOutput(outputId, value);
  try {
    const payload = await apiRequest(`/api/output/${outputId}`, {
      method: "POST",
      body: JSON.stringify({ active: Boolean(value) }),
    });
    applyBackendState(payload.state);
    return payload.state;
  } catch (error) {
    await refreshStateAfterError(error);
    throw error;
  }
}

async function setMany(outputIds, value) {
  outputIds.forEach((outputId) => setLocalOutput(outputId, value));
  try {
    const payload = await apiRequest("/api/outputs", {
      method: "POST",
      body: JSON.stringify({ ids: outputIds, active: Boolean(value) }),
    });
    applyBackendState(payload.state);
    return payload.state;
  } catch (error) {
    await refreshStateAfterError(error);
    throw error;
  }
}

async function pulseOutput(outputId, times = 2) {
  for (let index = 0; index < times; index += 1) {
    await setOutput(outputId, true);
    await wait(320);
    await setOutput(outputId, false);
    await wait(260);
  }
}

async function pulseMany(outputIds, times = 2) {
  for (let index = 0; index < times; index += 1) {
    await setMany(outputIds, true);
    await wait(320);
    await setMany(outputIds, false);
    await wait(260);
  }
}

async function setMotor(value) {
  const percent = clampPercent(value);
  setLocalMotor(percent);
  try {
    const payload = await apiRequest("/api/motor", {
      method: "POST",
      body: JSON.stringify({ percent }),
    });
    applyBackendState(payload.state);
    return payload.state;
  } catch (error) {
    await refreshStateAfterError(error);
    throw error;
  }
}

function scheduleMotorUpdate(value) {
  const percent = clampPercent(value);
  setLocalMotor(percent);
  window.clearTimeout(state.motorTimer);
  state.motorTimer = window.setTimeout(() => {
    setMotor(percent).catch(showError);
  }, 90);
}

async function resetHardware() {
  const payload = await apiRequest("/api/reset", { method: "POST" });
  applyBackendState(payload.state);
  return payload.state;
}

async function probeEspActor() {
  const payload = await apiRequest("/api/esp32/actor/probe", { method: "POST" });
  applyBackendState(payload.state);
  showPiActionStatus(
    payload.probe?.sent ? "ESP-Impulsdiagnose gesendet" : "Kein serieller ESP-Port offen",
    payload.probe?.sent ? "ok" : "error",
  );
  return payload;
}

async function refreshPiStatus() {
  const payload = await apiRequest("/api/state");
  applyBackendState(payload.state);
  showPiActionStatus("Status aktualisiert", "ok");
}

async function refreshStateAfterError(error) {
  showError(error);
  try {
    const payload = await apiRequest("/api/state");
    applyBackendState(payload.state);
  } catch {
    updateSystemMode(null, error);
  }
}

function setLocalOutput(outputId, value) {
  state.outputs[outputId] = Boolean(value);
  emitControlChange({ type: "gpio", id: outputId, value: state.outputs[outputId] });
  updateVehicleUi();
}

function setLocalMotor(percent) {
  state.motor = clampPercent(percent);
  motorSlider.value = String(state.motor);
  emitControlChange({ type: "pwm", id: "motor", gpio: 22, value: state.motor });
  updateVehicleUi();
}

function updateVehicleUi() {
  const activeOutputs = Object.values(state.outputs).filter(Boolean).length;
  const voltage = (state.motor / 100) * 5;
  activeCount.textContent = String(activeOutputs);
  motorReadout.textContent = `${state.motor} %`;
  voltageReadout.textContent = formatVoltage(voltage);
  motorPercent.textContent = `${state.motor} %`;
  motorVoltage.textContent = formatVoltage(voltage);

  document.querySelectorAll(".control-button").forEach((button) => {
    const outputId = button.dataset.output;
    button.classList.toggle("is-active", Boolean(state.outputs[outputId]));
    button.setAttribute("aria-pressed", String(Boolean(state.outputs[outputId])));
  });
}

function updatePiScreen() {
  if (!piMode) {
    return;
  }

  const relayMode = state.settings.digitalGpioMode === "pulse_only" ? "Impulsbetrieb" : "Dauerpegel";
  const esp = state.esp32Actor || {};
  const databasePi = state.databasePi || {};
  const candidatePort = Array.isArray(esp.candidatePorts) ? esp.candidatePorts[0] : "";

  piMode.textContent = state.hardwareMode === "gpio" ? "GPIO aktiv" : state.hardwareMode;
  piGpioMode.textContent = state.hardwareMode === "gpio" ? "echte Hardware" : "Simulation";
  piRelayMode.textContent = relayMode;

  if (esp.enabled === false || esp.runtimeMode === "standalone_pc_flash") {
    piEspStatus.textContent = "Standalone";
  } else {
    piEspStatus.textContent = esp.connected
    ? esp.relayMode === "pulse_only" || esp.protocol === "relay_pulse_serial"
      ? "Impuls-Relais aktiv"
      : esp.protocol === "legacy"
      ? "Legacy aktiv"
      : "Serial-Status aktiv"
    : esp.serialActive
      ? "Serial-Diagnose aktiv"
      : candidatePort
          ? "USB erkannt"
          : "nicht verbunden";
  }
  piDbStatus.textContent = databasePi.enabled ? databaseStatusLabel(databasePi) : "nicht eingerichtet";
}

function showPiActionStatus(message, type = "") {
  if (!piActionStatus) {
    return;
  }
  piActionStatus.className = `pi-action-status${type ? ` is-${type}` : ""}`;
  piActionStatus.textContent = message;
}

function databaseStatusLabel(databasePi) {
  if (databasePi.lastOk === true) {
    return "verbunden";
  }
  if (databasePi.lastOk === false) {
    return "Fehler";
  }
  return "bereit";
}

function emitControlChange(detail) {
  window.dispatchEvent(new CustomEvent("vehicle-control", { detail }));
}

function clampPercent(value) {
  return Math.max(0, Math.min(100, Math.round(Number(value) || 0)));
}

function formatVoltage(value) {
  return `${value.toFixed(1).replace(".", ",")} V`;
}

function wait(ms) {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}

async function waitStep() {
  await wait(700);
}

function appendLog(text) {
  const item = document.createElement("li");
  item.textContent = text;
  testLog.appendChild(item);
  testLog.scrollTop = testLog.scrollHeight;
}

function showError(error) {
  testResult.className = "result-banner is-error";
  testResult.textContent = error?.message || "Fehler bei der Hardware-Ansteuerung";
}

async function runTest(testId) {
  if (state.testRunning) {
    return;
  }

  const plan = testPlans[testId];
  const completedSteps = [];
  state.testRunning = true;
  testLog.innerHTML = "";
  testResult.className = "result-banner";
  testResult.textContent = "Test läuft";
  testState.textContent = plan.label;
  document.querySelectorAll(".test-button").forEach((button) => {
    button.disabled = true;
  });
  startGraph();

  try {
    for (const [label, action] of plan.steps) {
      appendLog(label);
      await action();
      completedSteps.push(label);
      await updateGraphPoint();
      await wait(420);
    }

    stopGraph();
    testResult.textContent = `${plan.label}: abgeschlossen`;
    testResult.classList.add("is-ok");
    await reportTestResult(testId, true, `${plan.label}: abgeschlossen`, completedSteps).catch(() => {
      appendLog("Datenbankmeldung konnte nicht gespeichert werden");
    });
  } catch (error) {
    stopGraph();
    showError(error);
    await reportTestResult(testId, false, error?.message || `${plan.label}: fehlgeschlagen`, completedSteps).catch(() => {});
  } finally {
    state.testRunning = false;
    testState.textContent = "Bereit";
    document.querySelectorAll(".test-button").forEach((button) => {
      button.disabled = false;
    });
  }
}

async function reportTestResult(testId, passed, message, steps) {
  const plan = testPlans[testId] || { label: testId };
  const metrics = await readMetrics();
  return apiRequest("/api/test-result", {
    method: "POST",
    body: JSON.stringify({
      test: plan.label,
      test_id: testId,
      passed,
      message,
      steps,
      metrics,
    }),
  });
}

async function readMetrics() {
  try {
    const payload = await apiRequest("/api/metrics");
    return payload.metrics;
  } catch {
    return calculatedMetrics();
  }
}

function calculatedMetrics() {
  const active = state.outputs;
  const lightLoad = ["underbody", "lowBeam", "highBeam"].filter((id) => active[id]).length * 0.28;
  const indicatorLoad = ["indicatorLeft", "indicatorRight", "hazard"].filter((id) => active[id]).length * 0.16;
  const fanLoad = active.fan ? 0.38 : 0;
  const extensionLoad = (active.freeOne ? 0.1 : 0) + (active.freeTwo ? 0.1 : 0);
  const motorLoad = state.motor * 0.021;
  const noise = (Math.random() - 0.5) * 0.08;

  return {
    current: Math.max(0, 0.12 + lightLoad + indicatorLoad + fanLoad + extensionLoad + motorLoad + noise),
    voltage: Math.max(0, 5 - state.motor * 0.004 - Math.max(0, noise) * 0.2),
    pwm: state.motor,
  };
}

async function updateGraphPoint() {
  state.graphData.push(await readMetrics());
  if (state.graphData.length > 64) {
    state.graphData.shift();
  }
  drawGraph();
}

function startGraph() {
  window.clearInterval(state.graphTimer);
  state.graphData = [];
  updateGraphPoint();
  state.graphTimer = window.setInterval(() => {
    updateGraphPoint();
  }, 320);
}

function stopGraph() {
  window.clearInterval(state.graphTimer);
  state.graphTimer = null;
  updateGraphPoint();
}

function drawGraph() {
  const width = chart.width;
  const height = chart.height;
  const padding = 34;
  const plotWidth = width - padding * 2;
  const plotHeight = height - padding * 2;
  const data = state.graphData.length ? state.graphData : [{ current: 0, voltage: 5, pwm: 0 }];

  chartContext.clearRect(0, 0, width, height);
  chartContext.fillStyle = "#070b10";
  chartContext.fillRect(0, 0, width, height);

  chartContext.strokeStyle = "rgba(255,255,255,0.08)";
  chartContext.lineWidth = 1;
  for (let index = 0; index <= 5; index += 1) {
    const y = padding + (plotHeight / 5) * index;
    chartContext.beginPath();
    chartContext.moveTo(padding, y);
    chartContext.lineTo(width - padding, y);
    chartContext.stroke();
  }

  drawLine(data, "current", 3.2, "#ffd400", padding, plotWidth, plotHeight);
  drawLine(data, "voltage", 5, "#4ab8ff", padding, plotWidth, plotHeight);
  drawLine(data, "pwm", 100, "#4bd69d", padding, plotWidth, plotHeight);

  chartContext.fillStyle = "rgba(244,247,251,0.72)";
  chartContext.font = "14px Segoe UI, Arial";
  chartContext.fillText("0", 10, height - padding + 5);
  chartContext.fillText("max", 10, padding + 5);
}

function drawLine(data, key, maxValue, color, padding, plotWidth, plotHeight) {
  chartContext.beginPath();
  data.forEach((point, index) => {
    const x = padding + (plotWidth / Math.max(data.length - 1, 1)) * index;
    const y = padding + plotHeight - (Math.min(point[key] || 0, maxValue) / maxValue) * plotHeight;
    if (index === 0) {
      chartContext.moveTo(x, y);
    } else {
      chartContext.lineTo(x, y);
    }
  });
  chartContext.strokeStyle = color;
  chartContext.lineWidth = 3;
  chartContext.lineJoin = "round";
  chartContext.lineCap = "round";
  chartContext.stroke();
}

document.querySelectorAll("[data-route]").forEach((button) => {
  button.addEventListener("click", () => routeTo(button.dataset.route));
});

document.querySelectorAll("[data-test]").forEach((button) => {
  button.addEventListener("click", () => runTest(button.dataset.test));
});

document.querySelectorAll("[data-pi-action]").forEach((button) => {
  button.addEventListener("click", async () => {
    button.disabled = true;
    showPiActionStatus("Arbeite ...");
    try {
      if (button.dataset.piAction === "reset") {
        await resetHardware();
        showPiActionStatus("Alle Ausgänge zurückgesetzt", "ok");
      } else if (button.dataset.piAction === "probe") {
        await probeEspActor();
      } else {
        await refreshPiStatus();
      }
    } catch (error) {
      showPiActionStatus(error?.message || "Aktion fehlgeschlagen", "error");
    } finally {
      button.disabled = false;
    }
  });
});

backButton.addEventListener("click", () => routeTo("home"));
motorSlider.addEventListener("input", () => scheduleMotorUpdate(motorSlider.value));
motorSlider.addEventListener("change", () => setMotor(motorSlider.value).catch(showError));

loadInitialState().then(() => {
  const requestedScreen = new URLSearchParams(window.location.search).get("screen");
  if (requestedScreen && screens[requestedScreen]) {
    routeTo(requestedScreen);
  }
});
