# BTC Basis live-chart fix

The chart issue comes from two coupled faults: the page fetches `data/nodes/btc_basis.json`, which often fails when the page is opened as `file://`, and the fallback branch in `createBasisChart()` is syntactically broken (`labels = ;`, `spotData = ;`, etc.), which stops all chart rendering when live fetch is unavailable.[file:3][file:4]

The rewrite below makes the page render charts in both modes: served with live node JSON, or local-file fallback using embedded data. It also fixes numeric parsing so valid zero values are not overwritten by defaults.[file:4]

## Replace the broken script block

```html
<script>
  let chartRegistry = {};

  const numOr = (value, fallback) => {
    const n = Number.parseFloat(value);
    return Number.isFinite(n) ? n : fallback;
  };

  let btcBasisData = {
    as_of: "2026-07-16",
    cme_front: {
      spot: 63425,
      futures: 64450,
      basis_dollars: 1025,
      basis_pct: 1.62,
      basis_annualized_simple: 19.71,
      basis_annualized_industry: 19.44,
      quartiles: { "30d": "Q1", "60d": "Q2", "90d": "Q1", "1y": "Q3", "3y": "Q2", "since_2020": "Q1" }
    },
    cme_second: {
      spot: 63425,
      futures: 62195,
      basis_dollars: -1230,
      basis_pct: -1.94,
      basis_annualized_simple: -11.80,
      basis_annualized_industry: -11.64,
      quartiles: { "30d": "Q2", "60d": "Q2", "90d": "Q2", "1y": "Q3", "3y": "Q2", "since_2020": "Q2" }
    },
    perp: {
      spot: 63425,
      futures: 63425,
      basis_dollars: 0,
      basis_pct: 0,
      basis_annualized_simple: 0,
      basis_annualized_industry: null,
      quartiles: { "30d": "Q1", "60d": "Q1", "90d": "Q1", "1y": "Q2", "3y": "Q1", "since_2020": "Q1" }
    },
    history: []
  };

  async function loadRealDataFromNodes() {
    try {
      const res = await fetch('data/nodes/btc_basis.json', { cache: 'no-store' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      const node = await res.json();
      const curr = node.current || {};
      const hist = Array.isArray(node.history) ? node.history : [];
      const rawDate = curr.date || node.timestamp || '';
      const asof = rawDate.split(/T| /)[0] || btcBasisData.as_of;

      const spot = numOr(curr.spot, btcBasisData.cme_front.spot);
      const futFront = numOr(curr.futures_front ?? curr.futures, btcBasisData.cme_front.futures);
      const bpctFront = numOr(curr.basis_pct_front ?? curr.basis_pct, btcBasisData.cme_front.basis_pct);
      const basisDolFront = numOr(curr.basis_dollar_front ?? curr.basis_dollar, futFront - spot);

      const futSecond = numOr(curr.futures_second, btcBasisData.cme_second.futures);
      const bpctSecond = numOr(curr.basis_pct_second, btcBasisData.cme_second.basis_pct);
      const basisDolSecond = numOr(curr.basis_dollar_second, futSecond - spot);

      const bpctPerp = numOr(curr.basis_pct_perp, btcBasisData.perp.basis_pct);

      btcBasisData = {
        as_of: asof,
        cme_front: {
          spot,
          futures: futFront,
          basis_dollars: basisDolFront,
          basis_pct: bpctFront,
          basis_annualized_simple: bpctFront * (365 / 30),
          basis_annualized_industry: bpctFront * (360 / 30),
          quartiles: curr.quartiles_front || btcBasisData.cme_front.quartiles
        },
        cme_second: {
          spot,
          futures: futSecond,
          basis_dollars: basisDolSecond,
          basis_pct: bpctSecond,
          basis_annualized_simple: bpctSecond * (365 / 60),
          basis_annualized_industry: bpctSecond * (360 / 60),
          quartiles: curr.quartiles_second || btcBasisData.cme_second.quartiles
        },
        perp: {
          spot,
          futures: spot,
          basis_dollars: 0,
          basis_pct: bpctPerp,
          basis_annualized_simple: bpctPerp * 365,
          basis_annualized_industry: null,
          quartiles: curr.quartiles_perp || btcBasisData.perp.quartiles
        },
        history: hist.map(h => ({
          date: h.date,
          spot: numOr(h.spot, spot),
          futures: numOr(h.futures ?? h.futures_front, futFront),
          basis_pct: numOr(h.basis_pct, bpctFront)
        })).filter(h => h.date),
      };

      console.log(`[BTC Basis] Loaded ${btcBasisData.history.length} rows | Front basis: ${btcBasisData.cme_front.basis_pct.toFixed(2)}%`);
    } catch (e) {
      console.warn('[BTC Basis DIG] JSON unavailable — using embedded fallback', e);
    }
  }

  function buildFallbackSeries(data) {
    const labels = ['T-6', 'T-5', 'T-4', 'T-3', 'T-2', 'T-1', 'Now'];
    return {
      labels,
      spotData: Array(labels.length).fill(data.spot),
      futData: Array(labels.length).fill(data.futures),
      bpData: Array(labels.length).fill(data.basis_pct)
    };
  }

  function createBasisChart(canvasId, key, data, label, history = []) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;

    if (chartRegistry[key]) {
      chartRegistry[key].destroy();
    }

    let labels, spotData, futData, bpData;

    if (Array.isArray(history) && history.length > 0) {
      const recent = history.slice(-30);
      labels = recent.map(h => {
        const d = h.date || '';
        return d.length >= 10 ? d.slice(5, 10) : d;
      });
      spotData = recent.map(h => h.spot);
      futData = recent.map(h => Number.isFinite(h.futures) ? h.futures : data.futures);
      bpData = recent.map(h => Number.isFinite(h.basis_pct) ? h.basis_pct : data.basis_pct);
    } else {
      ({ labels, spotData, futData, bpData } = buildFallbackSeries(data));
    }

    chartRegistry[key] = new Chart(canvas, {
      type: 'line',
      data: {
        labels,
        datasets: [
          {
            label: 'Spot Price',
            data: spotData,
            borderColor: '#4ade80',
            backgroundColor: 'rgba(74, 222, 128, 0.08)',
            borderWidth: 2,
            pointRadius: 0,
            pointHoverRadius: 3,
            tension: 0.25,
            yAxisID: 'y'
          },
          {
            label,
            data: futData,
            borderColor: '#0A4D2E',
            backgroundColor: 'rgba(10, 77, 46, 0.08)',
            borderWidth: 2,
            pointRadius: 0,
            pointHoverRadius: 3,
            tension: 0.25,
            yAxisID: 'y'
          },
          {
            label: 'Basis %',
            data: bpData,
            borderColor: '#ff9800',
            backgroundColor: 'rgba(255, 152, 0, 0.10)',
            borderWidth: 2,
            pointRadius: 0,
            pointHoverRadius: 3,
            tension: 0.25,
            yAxisID: 'y1'
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        scales: {
          y: {
            type: 'linear',
            position: 'left',
            title: { display: true, text: 'Price (USD)' }
          },
          y1: {
            type: 'linear',
            position: 'right',
            title: { display: true, text: 'Basis %' },
            grid: { drawOnChartArea: false }
          }
        },
        plugins: {
          legend: { display: true },
          tooltip: {
            callbacks: {
              label(context) {
                if (context.dataset.label === 'Basis %') {
                  const ann = data.basis_annualized_industry ?? 'N/A (Perp)';
                  return `Basis: ${Number(context.raw).toFixed(2)}% | Ann. Simple: ${Number(data.basis_annualized_simple).toFixed(2)}% | Industry: ${ann}`;
                }
                return `${context.dataset.label}: $${Number(context.raw).toLocaleString()}`;
              }
            }
          }
        }
      }
    });
  }

  function populateSnapshot(elementId, data) {
    const el = document.getElementById(elementId);
    if (!el) return;
    el.innerHTML = `
      <div>Spot:</div><div class="value">$${Number(data.spot).toLocaleString()}</div>
      <div>Futures:</div><div class="value">$${Number(data.futures).toLocaleString()}</div>
      <div>Basis $:</div><div class="value">$${Number(data.basis_dollars).toLocaleString()}</div>
      <div>Basis %:</div><div class="value">${Number(data.basis_pct).toFixed(2)}%</div>
    `;
  }

  function populateQuartileTable(elementId, quartiles) {
    const el = document.getElementById(elementId);
    if (!el) return;

    const order = ['30d', '60d', '90d', '1y', '3y', 'since_2020'];
    let html = '<tr><th>Lookback</th><th>Quartile</th></tr>';
    for (const period of order) {
      const q = quartiles?.[period] ?? '—';
      html += `<tr><td>${period}</td><td>${q}</td></tr>`;
    }
    el.innerHTML = html;
  }

  function initCharts() {
    const h = btcBasisData.history || [];

    createBasisChart('chart-cme-front', 'cme-front', btcBasisData.cme_front, 'CME Front Month', h);
    populateSnapshot('snapshot-cme-front', btcBasisData.cme_front);
    populateQuartileTable('table-cme-front', btcBasisData.cme_front.quartiles);

    createBasisChart('chart-cme-second', 'cme-second', btcBasisData.cme_second, 'CME Second Month', h);
    populateSnapshot('snapshot-cme-second', btcBasisData.cme_second);
    populateQuartileTable('table-cme-second', btcBasisData.cme_second.quartiles);

    createBasisChart('chart-perp', 'perp', btcBasisData.perp, 'Perpetual Futures', h);
    populateSnapshot('snapshot-perp', btcBasisData.perp);
    populateQuartileTable('table-perp', btcBasisData.perp.quartiles);

    const stampEl = document.getElementById('data-as-of');
    if (stampEl) stampEl.textContent = `Data as of ${btcBasisData.as_of}`;
  }

  document.addEventListener('DOMContentLoaded', async () => {
    await loadRealDataFromNodes();
    initCharts();
  });
</script>
```

## Why this version works

- It removes the invalid fallback assignments that currently break parsing, so Chart.js can initialize even when the live JSON request fails.[file:4]
- It preserves valid zeros by using a helper instead of `parseFloat(x) || fallback`, which matters for perp and negative/flat basis states.[file:4]
- It supports both intended modes: served app with `data/nodes/btc_basis.json` as the live source, or local-file open with embedded fallback data, which your build notes already imply is necessary for verification.[file:3]

## Browser use

Open this markdown file directly in the browser, or copy the code block into `btc-basis.html` and serve the page from the project root so the JSON fetch resolves cleanly. The attached review notes identify `data/nodes/btc_basis.json` as the target live source for this DIG page.[file:3][file:2]
