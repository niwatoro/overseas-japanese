const metricSelect = document.getElementById("metric-select");
const rankingBody = document.getElementById("ranking-table-body");
const mapContainer = document.getElementById("map");
const regionChartContainer = document.getElementById("region-chart");
const FLAG_CDN_BASE = "https://flagcdn.com";

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

function buildFlagMarkup(isoAlpha2) {
  if (!isoAlpha2 || typeof isoAlpha2 !== "string") {
    return "—";
  }
  const normalized = isoAlpha2.trim().toLowerCase();
  if (normalized.length !== 2) {
    return "—";
  }
  const src = `${FLAG_CDN_BASE}/w40/${normalized}.png`;
  return `<img src="${src}" alt="国旗" class="flag-img" loading="lazy" onerror="this.style.display='none'">`;
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
  const logValues = values.map((value) => Math.log10(Math.max(value, 1)));
  const zMin = Math.min(...logValues);
  const zMax = Math.max(...logValues);
  const positiveValues = values.filter((value) => value > 0);
  const minPositiveValue = positiveValues.length
    ? Math.min(...positiveValues)
    : 1;
  const maxValue = positiveValues.length
    ? Math.max(...positiveValues)
    : 1;
  const minExponent = Math.floor(Math.log10(minPositiveValue));
  const maxExponent = Math.max(
    Math.ceil(Math.log10(maxValue)),
    minExponent
  );
  const tickExponents = [];
  for (let exponent = minExponent; exponent <= maxExponent; exponent += 1) {
    tickExponents.push(exponent);
  }
  const data = {
    type: "choropleth",
    locationmode: "ISO-3",
    locations: filtered.map((row) => row.iso_alpha3),
    z: logValues,
    text: filtered.map(
      (row) => `${row.country}：${formatNumber(row.values[metricKey])}`
    ),
    colorscale: "Viridis",
    colorbar: {
      title: state.currentMetric?.label || "",
      titleside: "top",
      tickvals: tickExponents,
      ticktext: tickExponents.map((exponent) =>
        Number(10 ** exponent).toLocaleString("ja-JP")
      ),
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
    geo: {
      showframe: false,
      showcoastlines: true,
      projection: {
        type: "natural earth",
        rotation: { lon: 180, lat: 0, roll: 0 },
      },
      center: { lon: 180, lat: 0 },
    },
    margin: { t: 8, l: 0, r: 0, b: 0 },
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
      <td class="flag-cell">${buildFlagMarkup(row.iso_alpha2)}</td>
      <td>${row.country}</td>
      <td>${row.region || "—"}</td>
      <td>${formatNumber(row.values[metricKey])}</td>
    `;
    rankingBody.appendChild(tr);
  });
}

function renderRegionChart(regions) {
  if (!regionChartContainer) {
    return;
  }
  const chartEntries = regions
    .map((entry) => ({
      region: entry.region,
      value: entry.totals.total ?? 0,
    }))
    .filter((entry) => entry.value > 0);

  if (!chartEntries.length) {
    regionChartContainer.innerHTML = `
      <p class="region-chart-empty">
        地域別の在留邦人数のデータがありません。
      </p>
    `;
    return;
  }

  regionChartContainer.innerHTML = "";

  const labels = chartEntries.map((entry) => entry.region);
  const values = chartEntries.map((entry) => entry.value);
  const formattedValues = chartEntries.map((entry) => formatNumber(entry.value));

  const data = [
    {
      type: "pie",
      labels,
      values,
      hole: 0.55,
      sort: false,
      textinfo: "label+percent",
      insidetextorientation: "radial",
      marker: { line: { color: "#fff", width: 1 } },
      hovertemplate: "%{label}: %{customdata}<extra></extra>",
      customdata: formattedValues,
    },
  ];

  const layout = {
    margin: { t: 0, l: 0, r: 0, b: 0 },
    showlegend: true,
    legend: {
      orientation: "h",
      xanchor: "center",
      x: 0.5,
      y: -0.08,
    },
  };
  Plotly.react(regionChartContainer, data, layout, { responsive: true });
}

async function init() {
  state.metrics = await fetchMetrics();
  buildMetricOptions();
  metricSelect.addEventListener("change", () => updateMetric(metricSelect.value));
  const regionData = await fetchRegions();
  renderRegionChart(regionData);
  await updateMetric(metricSelect.value || state.metrics[0]?.name);
}

document.addEventListener("DOMContentLoaded", init);
