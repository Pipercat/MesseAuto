(function () {
  "use strict";

  const dataNode = document.getElementById("dashboard-data");
  let dashboard = {};

  try {
    dashboard = JSON.parse(dataNode ? dataNode.textContent : "{}") || {};
  } catch (error) {
    dashboard = {};
  }

  const palette = {
    text: "#071421",
    muted: "#5a677a",
    grid: "rgba(7,20,33,0.14)",
    yellow: "#ffd44a",
    green: "#57e389",
    cyan: "#62d6ff",
    red: "#ff6b6b",
    blue: "#7aa7ff",
  };

  const chartFont = '24px "Segoe UI", system-ui, sans-serif';
  const labelFont = '22px "Segoe UI", system-ui, sans-serif';

  function canvasContext(id) {
    const canvas = document.getElementById(id);
    if (!canvas) {
      return null;
    }

    const rect = canvas.getBoundingClientRect();
    const ratio = window.devicePixelRatio || 1;
    canvas.width = Math.max(1, Math.floor(rect.width * ratio));
    canvas.height = Math.max(1, Math.floor(rect.height * ratio));

    const ctx = canvas.getContext("2d");
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    ctx.clearRect(0, 0, rect.width, rect.height);
    ctx.font = chartFont;
    ctx.lineJoin = "round";
    ctx.lineCap = "round";

    return { canvas, ctx, width: rect.width, height: rect.height };
  }

  function emptyState(surface, text) {
    const { ctx, width, height } = surface;
    ctx.fillStyle = palette.muted;
    ctx.font = chartFont;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(text, width / 2, height / 2);
  }

  function drawGrid(surface, left, top, right, bottom) {
    const { ctx, width, height } = surface;
    ctx.strokeStyle = palette.grid;
    ctx.lineWidth = 1;
    ctx.beginPath();
    for (let index = 0; index <= 3; index += 1) {
      const y = top + ((height - top - bottom) / 3) * index;
      ctx.moveTo(left, y);
      ctx.lineTo(width - right, y);
    }
    ctx.stroke();
  }

  function drawBars(id, rows) {
    const surface = canvasContext(id);
    if (!surface) {
      return;
    }

    const values = Array.isArray(rows) ? rows.slice(0, 6) : [];
    if (!values.length) {
      emptyState(surface, "Noch keine Nutzung");
      return;
    }

    const { ctx, width, height } = surface;
    const left = 154;
    const right = 34;
    const top = 12;
    const gap = 14;
    const rowHeight = Math.max(30, (height - top - gap * (values.length - 1)) / values.length);
    const max = Math.max(...values.map((row) => rowValue(row)), 1);

    values.forEach((row, index) => {
      const y = top + index * (rowHeight + gap);
      const value = rowValue(row);
      const barWidth = ((width - left - right) * value) / max;

      ctx.fillStyle = "rgba(255,255,255,0.09)";
      roundRect(ctx, left, y, width - left - right, rowHeight, 8);
      ctx.fill();

      ctx.fillStyle = palette.yellow;
      roundRect(ctx, left, y, Math.max(8, barWidth), rowHeight, 8);
      ctx.fill();

      ctx.fillStyle = palette.text;
      ctx.font = labelFont;
      ctx.textAlign = "right";
      ctx.textBaseline = "middle";
      ctx.fillText(shortLabel(row.label || row.type || "event"), left - 14, y + rowHeight / 2);

      ctx.textAlign = "left";
      ctx.fillText(String(value), left + Math.max(12, barWidth) + 12, y + rowHeight / 2);
    });
  }

  function drawLine(id, points, options) {
    const surface = canvasContext(id);
    if (!surface) {
      return;
    }

    const series = normalizeSeries(points);
    if (series.length < 2) {
      emptyState(surface, options.empty);
      return;
    }

    lineChart(surface, [
      {
        points: series,
        color: options.color,
        fill: options.fill,
        label: options.label,
      },
    ], options);
  }

  function drawDualSensor(id, rows) {
    const surface = canvasContext(id);
    if (!surface) {
      return;
    }

    const source = Array.isArray(rows) ? rows : [];
    const temperature = source
      .filter((row) => Number.isFinite(Number(row.temperature)))
      .map((row, index) => ({ x: index, y: Number(row.temperature), label: row.time || row.label || "" }));
    const distance = source
      .filter((row) => Number.isFinite(Number(row.distance)))
      .map((row, index) => ({ x: index, y: Number(row.distance), label: row.time || row.label || "" }));

    if (temperature.length < 2 && distance.length < 2) {
      emptyState(surface, "Kein Sensor-USB erkannt");
      return;
    }

    lineChart(surface, [
      { points: temperature, color: palette.green, label: "Temp" },
      { points: distance, color: palette.cyan, label: "Distanz" },
    ], {
      empty: "Kein Sensor-USB erkannt",
      ySuffix: "",
      minPadding: 4,
    });
  }

  function drawVehicle(id, motorRows, outputRows) {
    const surface = canvasContext(id);
    if (!surface) {
      return;
    }

    const motors = normalizeSeries(motorRows).map((row) => ({
      x: row.x,
      y: Math.max(0, Math.min(100, row.y)),
      label: row.label,
    }));

    const outputs = normalizeSeries(outputRows).map((row) => ({
      x: row.x,
      y: Math.max(0, Math.min(100, row.y * 12.5)),
      label: row.label,
    }));

    if (motors.length < 2 && outputs.length < 2) {
      emptyState(surface, "Noch kein Fahrzeugverlauf");
      return;
    }

    lineChart(surface, [
      { points: motors, color: palette.red, label: "Motor %" },
      { points: outputs, color: palette.blue, label: "Aktive Ausgänge" },
    ], {
      empty: "Noch kein Fahrzeugverlauf",
      ySuffix: "%",
      fixedMin: 0,
      fixedMax: 100,
    });
  }

  function normalizeSeries(rows) {
    if (!Array.isArray(rows)) {
      return [];
    }
    return rows
      .map((row, index) => ({
        x: index,
        y: Number(row.count ?? row.value ?? row.y),
        label: row.time || row.label || "",
      }))
      .filter((row) => Number.isFinite(row.y));
  }

  function rowValue(row) {
    const value = Number(row.value ?? row.count ?? row.y ?? 0);
    return Number.isFinite(value) ? value : 0;
  }

  function lineChart(surface, seriesList, options) {
    const { ctx, width, height } = surface;
    const series = seriesList.filter((item) => item.points.length >= 2);
    if (!series.length) {
      emptyState(surface, options.empty || "Noch keine Daten");
      return;
    }

    const left = 82;
    const right = 28;
    const top = 54;
    const bottom = 46;
    const allValues = series.flatMap((item) => item.points.map((point) => point.y));
    let min = Number.isFinite(options.fixedMin) ? options.fixedMin : Math.min(...allValues);
    let max = Number.isFinite(options.fixedMax) ? options.fixedMax : Math.max(...allValues);

    if (min === max) {
      min -= options.minPadding || 1;
      max += options.minPadding || 1;
    }

    const plotWidth = width - left - right;
    const plotHeight = height - top - bottom;
    const maxLength = Math.max(...series.map((item) => item.points.length));

    drawGrid(surface, left, top, right, bottom);

    ctx.fillStyle = palette.muted;
    ctx.font = labelFont;
    ctx.textAlign = "right";
    ctx.textBaseline = "middle";
    ctx.fillText(formatValue(max, options.ySuffix), left - 12, top + 4);
    ctx.fillText(formatValue(min, options.ySuffix), left - 12, top + plotHeight);

    series.forEach((item) => {
      ctx.strokeStyle = item.color;
      ctx.lineWidth = 4;
      ctx.beginPath();

      item.points.forEach((point, index) => {
        const x = left + (plotWidth * index) / Math.max(1, item.points.length - 1);
        const y = top + plotHeight - ((point.y - min) / (max - min)) * plotHeight;
        if (index === 0) {
          ctx.moveTo(x, y);
        } else {
          ctx.lineTo(x, y);
        }
      });
      ctx.stroke();

      if (item.fill) {
        const lastIndex = item.points.length - 1;
        const lastX = left + plotWidth;
        const firstX = left;
        ctx.lineTo(lastX, top + plotHeight);
        ctx.lineTo(firstX, top + plotHeight);
        ctx.closePath();
        ctx.fillStyle = item.fill;
        ctx.fill();
      }
    });

    drawLegend(ctx, series, width, height);

    const firstLabel = series[0].points[0] ? series[0].points[0].label : "";
    const lastSeries = series[0].points;
    const lastLabel = lastSeries[lastSeries.length - 1] ? lastSeries[lastSeries.length - 1].label : "";

    ctx.fillStyle = palette.muted;
    ctx.font = labelFont;
    ctx.textAlign = "left";
    ctx.textBaseline = "bottom";
    ctx.fillText(firstLabel || "Start", left, height - 4);
    ctx.textAlign = "right";
    ctx.fillText(lastLabel || `${maxLength} Punkte`, width - right, height - 4);
  }

  function drawLegend(ctx, series, width) {
    let x = width - 26;
    const y = 22;
    ctx.font = labelFont;
    ctx.textBaseline = "middle";

    [...series].reverse().forEach((item) => {
      const labelWidth = ctx.measureText(item.label).width;
      x -= labelWidth + 44;
      ctx.fillStyle = item.color;
      ctx.fillRect(x, y - 8, 24, 16);
      ctx.fillStyle = palette.text;
      ctx.textAlign = "left";
      ctx.fillText(item.label, x + 34, y);
      x -= 20;
    });
  }

  function formatValue(value, suffix) {
    const rounded = Math.round(value * 10) / 10;
    return `${rounded}${suffix || ""}`;
  }

  function shortLabel(value) {
    const labels = {
      sensor_measurement: "Sensor",
      vehicle_heartbeat: "Heartbeat",
      test_result: "Tests",
      actor_status: "ESP",
      vehicle_output: "Ausgang",
      vehicle_outputs: "Ausgänge",
      vehicle_motor: "Motor",
    };
    const key = String(value);
    return labels[key] || key.replace(/_/g, " ").slice(0, 12);
  }

  function roundRect(ctx, x, y, width, height, radius) {
    const r = Math.min(radius, width / 2, height / 2);
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.arcTo(x + width, y, x + width, y + height, r);
    ctx.arcTo(x + width, y + height, x, y + height, r);
    ctx.arcTo(x, y + height, x, y, r);
    ctx.arcTo(x, y, x + width, y, r);
    ctx.closePath();
  }

  function renderCharts() {
    drawBars("function-usage-chart", dashboard.functionUsage);
    drawLine("vehicle-timeline-chart", dashboard.vehicleTimeline, {
      color: palette.yellow,
      fill: "rgba(255, 212, 74, 0.16)",
      label: "Befehle",
      empty: "Noch kein Befehlsverlauf",
    });
    drawLine("motor-chart", dashboard.motorHistory, {
      color: palette.red,
      fill: "rgba(255, 107, 107, 0.12)",
      label: "Motor %",
      empty: "Noch kein Motorverlauf",
      fixedMin: 0,
      fixedMax: 100,
      ySuffix: "%",
    });
    drawVehicle("vehicle-chart", dashboard.motorHistory, dashboard.outputHistory);
  }

  window.addEventListener("resize", renderCharts);
  renderCharts();
})();
