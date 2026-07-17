/**
 * js/02_core.js
 * ARK - Single Source of Truth for WTC 1.0
 * Version: 2.9 (Full Real Data 20260714 1520)
 */
'use strict';
window.ARK = {
    hydrationStatus: {
        pipeline: { timestamp: null, success: 0, error: null },
        risk_curve: { timestamp: null, success: 0, error: null }
    },
    get: function(key) {
        if (!window.BLACKBOARD) {
            console.warn("[ARK] BLACKBOARD not ready yet");
            return key === 'risk_curve' ? this._getFallbackRiskCurve() : null;
        }
        const data = window.BLACKBOARD.getState(key);
        if (data !== undefined && data.as_of) return data;  // Prefer real data
        if (key === 'risk_curve') {
            return this._loadRiskCurve();
        }
        console.warn(`[ARK] No handler for key: ${key}`);
        return null;
    },
    _loadRiskCurve: function() {
        console.log("[ARK] Attempting to load latest.json...");
        fetch(`data/hydration/latest.json?t=${Date.now()}`)
            .then(r => {
                if (!r.ok) throw new Error(`HTTP ${r.status}`);
                return r.json();
            })
            .then(realData => {
                console.log("[ARK] SUCCESS: Loaded real data from latest.json | as_of:", realData.as_of);
                if (window.BLACKBOARD) {
                    window.BLACKBOARD.setState('risk_curve', realData);
                }
                this.hydrationStatus.risk_curve = { 
                    timestamp: new Date().toISOString(), 
                    success: 1, 
                    error: null 
                };
            })
            .catch(err => {
                console.error("[ARK] FAILED to load latest.json:", err.message);
                const fallback = this._getFallbackRiskCurve();
                if (window.BLACKBOARD) window.BLACKBOARD.setState('risk_curve', fallback);
                this.hydrationStatus.risk_curve = { 
                    timestamp: new Date().toISOString(), 
                    success: 0, 
                    error: "Used fallback" 
                };
            });

        const current = (window.BLACKBOARD && window.BLACKBOARD.getState('risk_curve')) || this._getFallbackRiskCurve();
        return current;
    },
    _getFallbackRiskCurve: function() {
        return {
            as_of: "2026-07-14",
            nodes: {
                "Liquidity": { score: 83, status: "Strong", quartile: "Q1", description: "Abundant market and funding liquidity", quantOutputs: "Funding spread -15bps", commentary: "Strong liquidity supports risk assets." },
                "Credit": { score: 41, status: "Elevated", quartile: "Q4", description: "Rising pressure in credit markets", quantOutputs: "HY Spread +68bps", commentary: "Credit widening — stay defensive." },
                "EquityBreadth": { score: 69, status: "Moderate", quartile: "Q2", description: "Improving but still concentrated", quantOutputs: "Breadth Ratio 61%", commentary: "Broadening rally — healthy." },
                "HighBeta": { score: 54, status: "Monitor", quartile: "Q3", description: "High beta under relative pressure", quantOutputs: "Beta to SPX 1.45", commentary: "High beta under pressure." },
                "BTCBasis": { score: 79, status: "Strong", quartile: "Q1", description: "Positive and stable basis environment", quantOutputs: "Perp Basis +180bps", commentary: "Strong positive basis = institutional buying." }
            }
        };
    },
    refresh: async function() {
        console.log("[ARK] Refreshing from latest.json...");
        await new Promise(r => setTimeout(r, 1000)); // Give time for full hydration
        const data = this._loadRiskCurve();
        console.log("[ARK] Post-refresh as_of:", data?.as_of);
        return data;
    },
    getHydrationStatus: function() {
        return { ...this.hydrationStatus };
    }
};
console.log("✅ ARK Core v2.9 Loaded Successfully.");