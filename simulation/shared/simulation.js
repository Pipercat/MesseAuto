(() => {
  const KEY = 'messeauto-simulation-v2';
  const EVENT = 'messeauto-simulation-update';

  const defaults = {
    outputs: {
      underbody: false,
      lowBeam: false,
      highBeam: false,
      leftIndicator: false,
      rightIndicator: false,
      hazard: false,
      fan: false
    },
    sensors: {
      temperature: 23.4,
      seatDistance: 42,
      sensorError: false
    },
    connections: {
      pi1: true,
      pi2: true,
      espActor: true,
      espSensor: true
    },
    telemetry: {
      records: 0,
      lastUpdate: null
    },
    pulses: {},
    logs: []
  };

  const clone = value => JSON.parse(JSON.stringify(value));

  function merge(base, next) {
    const result = clone(base);
    Object.keys(next || {}).forEach(key => {
      if (next[key] && typeof next[key] === 'object' && !Array.isArray(next[key])) {
        result[key] = merge(result[key] || {}, next[key]);
      } else {
        result[key] = next[key];
      }
    });
    return result;
  }

  function load() {
    try {
      return merge(defaults, JSON.parse(localStorage.getItem(KEY) || '{}'));
    } catch (_) {
      return clone(defaults);
    }
  }

  function save(state) {
    localStorage.setItem(KEY, JSON.stringify(state));
    window.dispatchEvent(new CustomEvent(EVENT, { detail: clone(state) }));
  }

  function addLog(state, source, text) {
    state.logs.unshift({ time: new Date().toLocaleTimeString('de-DE'), source, text });
    state.logs = state.logs.slice(0, 60);
  }

  function seatPosition(distance) {
    if (distance < 32) return 'VORNE';
    if (distance > 65) return 'HINTEN';
    return 'MITTE';
  }

  function gpioFor(id) {
    return {
      underbody: 17,
      lowBeam: 27,
      highBeam: 25,
      leftIndicator: 6,
      rightIndicator: 5,
      fan: 22
    }[id] ?? null;
  }

  function setOutput(id, enabled, source = 'SIM') {
    const state = load();
    if (!(id in state.outputs)) return;
    const changed = state.outputs[id] !== enabled;
    state.outputs[id] = enabled;

    if (id === 'hazard') {
      state.outputs.leftIndicator = enabled;
      state.outputs.rightIndicator = enabled;
    }

    if (changed) {
      const gpio = gpioFor(id);
      if (gpio !== null) {
        state.pulses[id] = Date.now() + 420;
        addLog(state, 'PI1 GPIO', `BCM ${gpio}: 200-ms-Impuls für ${id}`);
      }
      addLog(state, source, `${id} = ${enabled ? 'AN' : 'AUS'}`);
    }
    save(state);
  }

  function toggleOutput(id, source = 'SIM') {
    const state = load();
    setOutput(id, !state.outputs[id], source);
  }

  function setSensor(name, value, source = 'ESP SENSOR') {
    const state = load();
    state.sensors[name] = value;
    addLog(state, source, `${name} = ${value}`);
    save(state);
  }

  function setConnection(name, value) {
    const state = load();
    state.connections[name] = !!value;
    addLog(state, 'SYSTEM', `${name} ${value ? 'verbunden' : 'getrennt'}`);
    save(state);
  }

  function reset() {
    const state = clone(defaults);
    addLog(state, 'SYSTEM', 'Simulation zurückgesetzt');
    save(state);
  }

  function tickTelemetry() {
    const state = load();
    if (state.connections.pi1 && state.connections.pi2) {
      state.telemetry.records += 1;
      state.telemetry.lastUpdate = new Date().toISOString();
      save(state);
    }
  }

  let lastBlink = false;
  function blinkPhase() {
    return Math.floor(Date.now() / 500) % 2 === 0;
  }

  function subscribe(callback) {
    const emit = () => callback(load(), blinkPhase());
    window.addEventListener('storage', emit);
    window.addEventListener(EVENT, emit);
    setInterval(() => {
      const phase = blinkPhase();
      if (phase !== lastBlink) {
        lastBlink = phase;
        emit();
      }
    }, 120);
    emit();
    return emit;
  }

  window.MesseAutoSim = {
    load,
    save,
    subscribe,
    setOutput,
    toggleOutput,
    setSensor,
    setConnection,
    seatPosition,
    reset,
    tickTelemetry,
    addLog
  };
})();