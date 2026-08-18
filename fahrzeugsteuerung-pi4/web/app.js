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
const piPulseDuration = document.getElementById("pi-pulse-duration");
const piMotorPin = document.getElementById("pi-motor-pin");
const piEspStatus = document.getElementById("pi-esp-status");
const piEspPort = document.getElementById("pi-esp-port");
const piEspMessages = document.getElementById("pi-esp-messages");
const piEspLastSeen = document.getElementById("pi-esp-last-seen");
const piEspUnknown = document.getElementById("pi-esp-unknown");
const piEspRaw = document.getElementById("pi-esp-raw");
const piDbStatus = document.getElementById("pi-db-status");
const piDbUrl = document.getElementById("pi-db-url");
const piOutputMap = document.getElementById("pi-output-map");
const piOutputSummary = document.getElementById("pi-output-summary");
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
  }
}

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
  if (!piMode || !piOutputMap) {
    return;
  }

  const digitalPins = (state.pins.length ? state.pins : fallbackPins).filter((pin) => pin.kind === "digital");
  const effectiveOutputs = state.effectiveOutputs || state.outputs || {};
  const activeCount = Object.values(effectiveOutputs).filter(Boolean).length;
  const relayMode = state.settings.digitalGpioMode === "pulse_only" ? "Impulsbetrieb" : "Dauerpegel";
  const pulseSeconds = Number(state.settings.pulseDuration);
  const motorPin = (state.pins || []).find((pin) => pin.id === "motor");
  const esp = state.esp32Actor || {};
  const databasePi = state.databasePi || {};
  const displayedAge = esp.lastSeenAgeSeconds ?? esp.lastRawAgeSeconds;
  const hasAge = displayedAge !== null && displayedAge !== undefined;
  const age = hasAge ? Number(displayedAge) : NaN;
  const candidatePort = Array.isArray(esp.candidatePorts) ? esp.candidatePorts[0] : "";

  piMode.textContent = state.hardwareMode === "gpio" ? "GPIO aktiv" : state.hardwareMode;
  piGpioMode.textContent = state.hardwareMode === "gpio" ? "echte Hardware" : "Simulation";
  piRelayMode.textContent = relayMode;
  piPulseDuration.textContent = Number.isFinite(pulseSeconds) ? `${Math.round(pulseSeconds * 1000)} ms` : "--";
  piMotorPin.textContent = motorPin ? `GPIO ${motorPin.gpio}` : "GPIO 22";

  if (esp.enabled === false || esp.runtimeMode === "standalone_pc_flash") {
    piEspStatus.textContent = "Standalone";
    piEspPort.textContent = "PC-Flash";
    piEspMessages.textContent = "aus";
    piEspLastSeen.textContent = "nicht am Pi";
    piEspUnknown.textContent = "0";
    piEspRaw.textContent = "Pi-GPIO";
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
    piEspPort.textContent = shortPortName(esp.port || candidatePort || "--");
    piEspMessages.textContent = String(esp.messageCount || 0);
    piEspLastSeen.textContent = Number.isFinite(age) ? `${age.toFixed(1).replace(".", ",")} s` : "--";
    piEspUnknown.textContent = String((esp.unknownMessageCount || 0) + (esp.decodeErrorCount || 0));
    piEspRaw.textContent = esp.lastRawLine ? "Status empfangen" : "--";
  }
  piDbStatus.textContent = databasePi.enabled ? databaseStatusLabel(databasePi) : "nicht eingerichtet";
  piDbUrl.textContent = databasePi.url ? databasePi.url.replace("http://", "") : "--";
  piOutputSummary.textContent = `${activeCount} aktiv`;

  piOutputMap.innerHTML = "";
  digitalPins.forEach((pin) => {
    const item = document.createElement("div");
    item.className = "pi-output-item";
    item.classList.toggle("is-active", Boolean(effectiveOutputs[pin.id]));
    item.innerHTML = `
      <span>${shortLabels[pin.id] || pin.label}</span>
      <strong>GPIO ${pin.gpio}</strong>
    `;
    piOutputMap.appendChild(item);
  });
}

function showPiActionStatus(message, type = "") {
  if (!piActionStatus) {
    return;
  }
  piActionStatus.className = `pi-action-status${type ? ` is-${type}` : ""}`;
  piActionStatus.textContent = message;
}

function shortPortName(port) {
  if (!port || port === "--") {
    return "--";
  }
  if (String(port).includes("CP2102") || String(port).includes("Silicon_Labs")) {
    return "CP2102 USB";
  }
  const parts = String(port).split("/");
  return parts[parts.length - 1] || String(port);
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
