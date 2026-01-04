const metricSelect = document.getElementById("metric-select");
const metricTitle = document.getElementById("metric-title");
const metricDescription = document.getElementById("metric-description");
const metricBadge = document.querySelector(".metric-badge");
const regionBody = document.getElementById("region-table-body");
const rankingBody = document.getElementById("ranking-table-body");
const mapContainer = document.getElementById("map");

const state = {
  metrics: [],
  currentMetric: null,
};

function formatNumber(value) {
  if (value === undefined || value === null) {
    return "—";
  }
  return Number(value).toLocaleString("ja-JP");
}

async function fetchMetrics() {
  const response = await fetch("/api/metrics");
  if (!response.ok) {
    throw new Error("メトリクスを取得できませんでした。");
  }
  return response.json();
}

async function fetchData(metric) {
  const response = await fetch(`/api/data?metric=${metric}&limit=40`);
  if (!response.ok) {
    throw new Error("データ取得エラー");
  }
  return response.json();
}

async function fetchMapData(metric) {
  const response = await fetch(`/api/data/all?metric=${metric}`);
  if (!response.ok) {
    throw new Error("マップ用データの取得に失敗しました");
  }
  return response.json();
}

async function fetchRegions() {
  const response = await fetch("/api/regions");
  if (!response.ok) {
    throw new Error("地域データを取得できませんでした。");
  }
  return response.json();
}

function buildMetricOptions() {
  metricSelect.innerHTML = state.metrics
    .map(
      (metric) =>
        `<option value="${metric.name}">${metric.label}</option>`
    )
    .join("");
}

async function updateMetric(metric) {
  state.currentMetric = state.metrics.find((item) => item.name === metric);
  if (!state.currentMetric) {
    return;
  }
  metricTitle.textContent = state.currentMetric.label;
  metricDescription.textContent = state.currentMetric.description;
  if (metricBadge) {
    metricBadge.textContent = state.currentMetric.label;
  }
  const [rankingRecords, mapRecords] = await Promise.all([
    fetchData(state.currentMetric.name),
    fetchMapData(state.currentMetric.name),
  ]);
  renderChoropleth(mapRecords);
  renderRanking(rankingRecords);
}

function renderChoropleth(records) {
  const metricKey = state.currentMetric?.name;
  if (!metricKey) {
    return;
  }
  const filtered = records.filter(
    (row) => row.iso_alpha3 && row.values[metricKey] != null
  );
  if (!filtered.length) {
    mapContainer.innerHTML = "";
    return;
  }
  const values = filtered.map((row) => row.values[metricKey]);
  const zMin = Math.min(...values);
  const zMax = Math.max(...values);
  const data = {
    type: "choropleth",
    locationmode: "ISO-3",
    locations: filtered.map((row) => row.iso_alpha3),
    z: values,
    text: filtered.map(
      (row) => `${row.country}：${formatNumber(row.values[metricKey])}`
    ),
    colorscale: "Viridis",
    colorbar: {
      title: state.currentMetric?.label || "",
      titleside: "top",
      tickformat: ",.0f",
      ticks: "outside",
      lenmode: "fraction",
      len: 0.55,
    },
    zmin: zMin,
    zmax: zMax,
    marker: { line: { color: "#fff", width: 0.5 } },
    hoverinfo: "text",
  };
  const layout = {
    title: state.currentMetric?.label || "",
    geo: {
      showframe: false,
      showcoastlines: true,
      projection: {
        type: "natural earth",
        rotation: { lon: 180, lat: 0, roll: 0 },
      },
      center: { lon: 180, lat: 0 },
    },
    margin: { t: 30, l: 0, r: 0, b: 0 },
  };
  Plotly.react(mapContainer, [data], layout, { responsive: true });
}

function renderRanking(records) {
  const metricKey = state.currentMetric?.name;
  if (!metricKey) {
    return;
  }
  rankingBody.innerHTML = "";
  records.forEach((row) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${row.country}</td>
      <td>${row.region || "—"}</td>
      <td>${formatNumber(row.values[metricKey])}</td>
    `;
    rankingBody.appendChild(tr);
  });
}

function renderRegions(regions) {
  regionBody.innerHTML = "";
  regions.forEach((entry) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${entry.region}</td>
      <td>${formatNumber(entry.totals.total)}</td>
      <td>${formatNumber(entry.totals.long_term)}</td>
      <td>${formatNumber(entry.totals.permanent)}</td>
      <td>${formatNumber(entry.totals.adults)}</td>
    `;
    regionBody.appendChild(tr);
  });
}

async function init() {
  state.metrics = await fetchMetrics();
  buildMetricOptions();
  metricSelect.addEventListener("change", () => updateMetric(metricSelect.value));
  const regionData = await fetchRegions();
  renderRegions(regionData);
  await updateMetric(metricSelect.value || state.metrics[0]?.name);
}

document.addEventListener("DOMContentLoaded", init);
