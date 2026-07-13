/**
 * js/03_risk_curve.js
 * Chunk 5: RCV JSON Mapping from barchart_core_history
 * Goldman Prop Desk Standards
 */

'use strict';

// Register with ARK
window.ARK.getRiskCurve = function() {
    const core = window.ARK.get('barchart_core_history') || { records: [] };
    const nodes = {};

    const riskNodesConfig = {
        "^BTCUSD": { display: "Bitcoin Exposure" },
        "IBIT":    { display: "BTC ETF Flow" },
        "GCY00":   { display: "Gold Hedge" },
        "DXY00":   { display: "Dollar Strength" },
        "ASHR":    { display: "China A-Shares" }
    };

    // Legacy fallback nodes
    const legacy = {
        "Liquidity": { /* full legacy object from your file */ },
        "Credit": { /* full */ },
        "EquityBreadth": { /* full */ },
        "HighBeta": { /* full */ },
        "BTCBasis": { /* full */ }
    };

    // Dynamic mapping
    core.records.forEach(record => {
        const config = riskNodesConfig[record.raw_symbol];
        if (config) {
            const latest = record.latest || {};
            const baseScore = Math.min(99, Math.max(10, Math.round((latest.close || 50000) / 1000) || 50));
            nodes[record.raw_symbol] = {
                score: baseScore,
                quartile: baseScore >= 75 ? "Q1" : baseScore >= 60 ? "Q2" : baseScore >= 40 ? "Q3" : "Q4",
                status: latest.pct_change >= 0 ? "Strong" : "Elevated",
                description: `${config.display} | ${record.canonical_id || record.raw_symbol}`,
                color: baseScore >= 75 ? "#0A4D2E" : baseScore >= 60 ? "#4CAF50" : "#FF9800",
                // ... add other fields
            };
        }
    });

    const curveData = { as_of: core.as_of, nodes: {...legacy, ...nodes} };
    window.ARK.set('risk_curve', curveData);
    return curveData;
};

console.log("RCV Mapping Module Loaded (Chunk 5)");