// js/02_core.js — ARK: Single Source of Truth (WTC 1.0)
// WTC_BUILD updated for real data priority

const WTC_BUILD = 'WTC-1.0-ARK-20260711-REAL-v2';

window.ARK = {
    data: {},
    lastUpdated: null,

    init: function() {
        console.log("🚀 ARK initialized as Single Source of Truth");
        this.loadFromDataFiles();
    },

    loadFromDataFiles: async function() {
        console.log("📂 ARK attempting real load from data/ (Parquet/JSON priority)");

        let loaded = false;

        // Primary: Risk Curve from real file
        try {
            const res = await fetch('data/risk_curve.json', { cache: 'no-store' });
            if (res.ok) {
                const realData = await res.json();
                this.data.risk_curve = realData;
                console.log("✅ ARK SUCCESS: Loaded real risk_curve from data/risk_curve.json");
                loaded = true;
            }
        } catch (e) {
            console.warn("⚠️ Real risk_curve.json load failed:", e.message);
        }

        if (!loaded) {
            console.warn("⚠️ Falling back to minimal ARK structure (no hardcoded scores)");
            this.loadMinimalRiskCurve();
        }

        this.lastUpdated = new Date();
    },

    loadMinimalRiskCurve: function() {
        // Minimal structure ONLY — scores come from real data or external pipeline
        this.data.risk_curve = {
            as_of: new Date().toLocaleString('en-US', { hour12: false, timeZoneName: 'short' }),
            nodes: {
                liquidity:     { score: null, quartile: "Q?", status: "Pending", description: "Awaiting real data load" },
                credit:        { score: null, quartile: "Q?", status: "Pending", description: "Awaiting real data load" },
                equityDepth:   { score: null, quartile: "Q?", status: "Pending", description: "Awaiting real data load" },
                highBeta:      { score: null, quartile: "Q?", status: "Pending", description: "Awaiting real data load" },
                bitcoinBasis:  { score: null, quartile: "Q?", status: "Pending", description: "Coinglass / real feed pending" }
            },
            source: "fallback-minimal"
        };
        console.log("✅ ARK minimal structure ready — populate via real files");
    },

    get: function(key) {
        return this.data[key] || null;
    },

    getBuild: function() {
        return WTC_BUILD;
    }
};

// Critical: Force init for refresh stability
window.ARK.init();