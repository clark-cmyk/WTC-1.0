// js/02_core.js — ARK: Single Source of Truth (WTC 1.0)

const WTC_BUILD = 'WTC-1.0-ARK-20260711';

window.ARK = {
    data: {},
    lastUpdated: null,

    init: function() {
        console.log("🚀 ARK initialized as Single Source of Truth");
        this.loadRiskCurveData();
    },

    loadRiskCurveData: function() {
        // Force synchronous load for reliability on refresh
        this.data.risk_curve = {
            as_of: new Date().toLocaleString('en-US', { hour12: false, timeZoneName: 'short' }),
            nodes: {
                liquidity:     { score: 78, quartile: "Q3", status: "Good", description: "SOFR vs Fed Funds" },
                credit:        { score: 45, quartile: "Q2", status: "Neutral", description: "Corporate spreads" },
                equityDepth:   { score: 62, quartile: "Q3", status: "Good", description: "Market breadth" },
                highBeta:      { score: 29, quartile: "Q1", status: "Weak", description: "High beta performance" },
                bitcoinBasis:  { score: 85, quartile: "Q4", status: "Strong", description: "Spot vs Futures" }
            }
        };
        this.lastUpdated = new Date();
        console.log("✅ ARK Risk Curve data ready");
    },

    get: function(key) {
        return this.data[key] || null;
    }
};

// Force immediate init (critical for refresh)
window.ARK.init();