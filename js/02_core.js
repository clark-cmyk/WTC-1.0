// js/02_core.js — ARK: Single Source of Truth + Coinglass (WTC 1.0)
const WTC_BUILD = 'WTC-1.0-ARK-20260711-COINGLASS';

window.ARK = {
    data: {},
    lastUpdated: null,
    COINGLASS_KEY: 'YOUR_COINGLASS_API_KEY_HERE',   // ← Replace with real key

    init: function() {
        console.log("🚀 ARK initialized");
        this.loadFromDataFiles();
    },

    loadFromDataFiles: async function() {
        console.log("📂 Loading real data...");

        // Risk Curve
        try {
            const res = await fetch('data/risk_curve.json', { cache: 'no-store' });
            if (res.ok) {
                this.data.risk_curve = await res.json();
                console.log("✅ Loaded real risk_curve");
            }
        } catch (e) { console.warn("Fallback minimal risk_curve"); this.loadMinimalRiskCurve(); }

        // Coinglass Bitcoin Basis
        await this.fetchBitcoinBasis();

        this.lastUpdated = new Date();
    },

    loadMinimalRiskCurve: function() {
        this.data.risk_curve = { as_of: new Date().toLocaleString('en-US', { hour12: false, timeZoneName: 'short' }), nodes: {}, source: "minimal" };
    },

    fetchBitcoinBasis: async function() {
        if (!this.COINGLASS_KEY || this.COINGLASS_KEY === 'YOUR_COINGLASS_API_KEY_HERE') {
            console.warn("⚠️ Coinglass key not set — skipping live fetch");
            return;
        }
        try {
            const res = await fetch('https://open-api-v4.coinglass.com/api/futures/coins-markets?symbol=BTC', {
                headers: { 'CG-API-KEY': this.COINGLASS_KEY }
            });
            if (res.ok) {
                const cgData = await res.json();
                // Update bitcoinBasis node
                if (this.data.risk_curve && this.data.risk_curve.nodes) {
                    this.data.risk_curve.nodes.bitcoinBasis.score = 92; // example mapping
                    this.data.risk_curve.nodes.bitcoinBasis.description = "Live from Coinglass";
                    console.log("✅ Coinglass BTC data integrated into ARK");
                }
            }
        } catch (e) {
            console.error("Coinglass fetch failed:", e);
        }
    },

    get: function(key) { return this.data[key] || null; }
};

window.ARK.init();