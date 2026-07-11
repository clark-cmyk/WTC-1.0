// js/01_shell.js

let currentModule = 6;

const modules = [
    { id: 1, code: "ART", name: "Articulate" },
    { id: 2, code: "ARK", name: "Ark" },
    { id: 3, code: "BAS", name: "Basis" },
    { id: 4, code: "BBD", name: "Bang Bang Da" },
    { id: 5, code: "COM", name: "Compute" },
    { id: 6, code: "RCV", name: "Risk Curve" },
    { id: 7, code: "SQ3", name: "SQ3" },
    { id: 8, code: "DICT", name: "Data Dictionary" }
];

function renderTabs() {
    const container = document.getElementById('tabs');
    container.innerHTML = modules.map(m => `
        <div class="tab" onclick="switchModule(${m.id})">${m.id}. ${m.code}</div>
    `).join('');
}

aasync function switchModule(id) {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab')[id-1].classList.add('active');
    
    const content = document.getElementById('mainContent');
    
    if (id === 6) {
        content.innerHTML = `<h2>Risk Curve (RCV) — Loading from Ark...</h2>`;
        
        const curveData = await window.WTC_Core.loadData('curve');
        
        if (curveData) {
            content.innerHTML = `
                <h2>Risk Curve (RCV)</h2>
                <p>Data loaded from Ark (${curveData.as_of || 'unknown'})</p>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 16px; margin-top: 20px;">
                    <div style="background:var(--bg-card);padding:20px;border-radius:8px;border:1px solid var(--border);">
                        <h3>Liquidity</h3>
                        <div style="font-size:42px;font-weight:700;color:#0A4D2E;">78</div>
                        <div style="color:#0A4D2E;">Q3 • Good</div>
                        <p style="margin-top:8px;font-size:13px;">SOFR vs Fed Funds</p>
                        <button onclick="articulate()" style="margin-top:8px;">A</button>
                    </div>
                    <div style="background:var(--bg-card);padding:20px;border-radius:8px;border:1px solid var(--border);">
                        <h3>Credit</h3>
                        <div style="font-size:42px;font-weight:700;color:#8B6F00;">45</div>
                        <div style="color:#8B6F00;">Q2 • Neutral</div>
                        <p style="margin-top:8px;font-size:13px;">Corporate spreads</p>
                        <button onclick="articulate()" style="margin-top:8px;">A</button>
                    </div>
                    <div style="background:var(--bg-card);padding:20px;border-radius:8px;border:1px solid var(--border);">
                        <h3>Equity Depth</h3>
                        <div style="font-size:42px;font-weight:700;color:#0A4D2E;">62</div>
                        <div style="color:#0A4D2E;">Q3 • Good</div>
                        <p style="margin-top:8px;font-size:13px;">Market breadth</p>
                        <button onclick="articulate()" style="margin-top:8px;">A</button>
                    </div>
                    <div style="background:var(--bg-card);padding:20px;border-radius:8px;border:1px solid var(--border);">
                        <h3>High Beta</h3>
                        <div style="font-size:42px;font-weight:700;color:#6B1E1E;">29</div>
                        <div style="color:#6B1E1E;">Q1 • Weak</div>
                        <p style="margin-top:8px;font-size:13px;">High beta performance</p>
                        <button onclick="articulate()" style="margin-top:8px;">A</button>
                    </div>
                    <div style="background:var(--bg-card);padding:20px;border-radius:8px;border:1px solid var(--border);">
                        <h3>Bitcoin Basis</h3>
                        <div style="font-size:42px;font-weight:700;color:#0A4D2E;">85</div>
                        <div style="color:#0A4D2E;">Q4 • Strong</div>
                        <p style="margin-top:8px;font-size:13px;">Spot vs Futures</p>
                        <button onclick="articulate()" style="margin-top:8px;">A</button>
                    </div>
                </div>
            `;
        } else {
            content.innerHTML = `<h2>Risk Curve (RCV)</h2><p>Failed to load curve data. Showing dummy cards.</p>`;
        }
    } else if (id === 8) {
        console.log("DICT tab clicked, id = " + id);
        content.innerHTML = `
            <h2>Data Dictionary (DICT)</h2>
            <p>Data dictionary content will go here.</p>
            <button onclick="downloadCSV()" style="padding:8px 16px;font-size:14px;">Download CSV</button>
        `;
    } else {
        const mod = modules.find(m => m.id === id);
        content.innerHTML = `<h2>${mod.name} (${mod.code})</h2><p>Module content loads here.</p>`;
    }
}

    } else {
        const mod = modules.find(m => m.id === id);
        content.innerHTML = `<h2>${mod.name} (${mod.code})</h2><p>Module content loads here.</p>`;
    }
}

function refreshData() { 
    alert("Data refreshed");
    location.reload(true); 
}
function articulate() { alert("Articulate snapshot copied"); }
function toggleTheme() {
    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    document.documentElement.setAttribute('data-theme', isDark ? 'light' : 'dark');
}
function downloadCSV() {
    const curveData = window.WTC_Core.getData('curve');
    if (!curveData) {
        alert("No data to download");
        return;
    }
    const csv = "date,close\n" + curveData.records[0].points.map(p => `${p.date},${p.close}`).join("\n");
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'curve_data.csv';
    a.click();
}

document.addEventListener('keydown', e => {
    if (e.key >= '1' && e.key <= '8') switchModule(parseInt(e.key));
});

renderTabs();
switchModule(6);