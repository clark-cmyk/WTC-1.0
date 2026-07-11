// js/02_core.js — ARK: Single Source of Truth
const WTC_BUILD = 'WTC-1.0-ARK-20260711-FIXED';

window.ARK = {
    data: {},
    lastUpdated: null,

    init: function() {
        console.log("🚀 ARK initialized");
        this.loadRiskCurveData();
    },

    loadRiskCurveData: function() {
        this.data.risk_curve = {
            as_of: new Date().toLocaleString('en-US', { hour12: false, timeZoneName: 'short' }),
            nodes: {
                liquidity:     { score: 82, quartile: "Q3", status: "Good", description: "SOFR vs Fed Funds spread stable" },
                credit:        { score: 51, quartile: "Q2", status: "Neutral", description: "Corporate spreads tightening" },
                equityDepth:   { score: 68, quartile: "Q3", status: "Good", description: "Market breadth improving" },
                highBeta:      { score: 24, quartile: "Q1", status: "Weak", description: "High beta under pressure" },
                bitcoinBasis:  { score: 91, quartile: "Q4", status: "Strong", description: "Spot vs Futures basis positive" }
            }
        };
        this.lastUpdated = new Date();
        console.log("✅ ARK Risk Curve ready");
    },

    get: function(key) {
        return this.data[key] || null;
    }
};

window.ARK.init();