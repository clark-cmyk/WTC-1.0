// modules/01_risk_curve/risk_curve.js

const riskNodes = [
    {
        id: "liquidity",
        name: "Liquidity",
        score: 78,
        signal: "good",
        quartile: "Q3",
        description: "SOFR vs Fed Funds spread"
    },
    {
        id: "credit",
        name: "Credit",
        score: 45,
        signal: "neutral",
        quartile: "Q2",
        description: "Corporate spreads and credit conditions"
    },
    {
        id: "equity",
        name: "Equity Depth",
        score: 62,
        signal: "good",
        quartile: "Q3",
        description: "Market breadth and participation"
    },
    {
        id: "highbeta",
        name: "High Beta",
        score: 29,
        signal: "bad",
        quartile: "Q1",
        description: "High beta stocks performance"
    },
    {
        id: "btc",
        name: "Bitcoin Basis",
        score: 85,
        signal: "good",
        quartile: "Q4",
        description: "BTC spot vs futures basis"
    }
];

function renderRiskCurve() {
    let html = `<h2>Risk Curve</h2><div class="risk-nodes-grid">`;

    riskNodes.forEach(node => {
        const signalClass = node.signal;
        html += `
            <div class="risk-node-card ${signalClass}" onclick="expandRiskNode('${node.id}')">
                <div class="node-header">
                    <span class="node-name">${node.name}</span>
                    <span class="node-quartile">Q${node.quartile}</span>
                </div>
                <div class="node-score">${node.score}</div>
                <button class="node-articulate" onclick="event.stopImmediatePropagation(); articulateRiskNode('${node.name}')">A</button>
                <div class="node-desc">${node.description}</div>
            </div>`;
    });

    html += `</div>`;
    return html;
}

// Placeholder functions for expand and articulate
function expandRiskNode(id) {
    alert(`Deep dive for ${id} node would open in full page`);
}

function articulateRiskNode(name) {
    alert(`Articulate prompt for ${name} copied to clipboard`);
}

// Make available globally
window.renderRiskCurve = renderRiskCurve;