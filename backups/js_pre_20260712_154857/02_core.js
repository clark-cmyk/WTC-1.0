/**
 * js/02_core.js
 * ARK - Single Source of Truth for WTC 1.0
 * Blackboard Pattern + Hydration + Risk Curve Engine
 * Version: 1.8 (Real Fetch Examples - 2026-07-11)
 */
'use strict';

// ==================== BLACKBOARD (Central State) ====================
window.BLACKBOARD = {
    state: {},
    subscribers: {},
    _clone: function(value) {
        if (typeof structuredClone === 'function') {
            try { return structuredClone(value); } 
            catch (e) { console.warn('[BLACKBOARD] structuredClone failed', e.message); }
        }
        if (typeof value === 'object' && value !== null) {
            return JSON.parse(JSON.stringify(value));
        }
        return value;
    },
    setState: function(key, value) {
        if (typeof key !== 'string' || key.trim() === '') {
            console.error('[BLACKBOARD] Key must be a non-empty string');
            return;
        }
        this.state[key] = this._clone(value);
        console.log(`[BLACKBOARD] ${key} updated`);
        this.notify(key);
    },
    getState: function(key) {
        return this.state[key];
    },
    subscribe: function(key, callback) {async function refreshData() {
        if (typeof callback !== 'function') {
            console.error('[BLACKBOARD] Subscriber must be a function');
            return () => {};
        }
        if (!this.subscribers[key]) this.subscribers[key] = [];
        if (this.subscribers[key].some(cb => cb === callback)) {
            console.warn(`[BLACKBOARD] Duplicate subscriber for ${key}`);
            return () => {};
        }
        this.subscribers[key].push(callback);
        const current = this.state[key];
        if (current !== undefined) callback(current);
        return () => this.unsubscribe(key, callback);
    },
    unsubscribe: function(key, callback) {
        if (this.subscribers[key]) {
            this.subscribers[key] = this.subscribers[key].filter(cb => cb !== callback);
            if (this.subscribers[key].length === 0) delete this.subscribers[key];
        }
    },
    notify: function(key) {
        if (this.subscribers[key]) {
            const value = this.state[key];
            this.subscribers[key].forEach(cb => {
                try { cb(value); } catch (e) {
                    console.error(`[BLACKBOARD] Subscriber error for ${key}:`, e);
                }
            });
        }
    },
    reset: function(key) {
        if (key) delete this.state[key];
        else this.state = {};
    }
};

// ==================== ARK (Domain Orchestrator) ====================
window.ARK = {
    hydrationStatus: {
        barchart: { timestamp: null, success: 0, error: null },
        koyfin: { timestamp: null, success: 0, error: null },
        coinglass: { timestamp: null, success: 0, error: null },
        risk_curve: { timestamp: null, success: 0, error: null }
    },
    config: {
        apiKeys: {
            barchart: 'YOUR_BARCHART_API_KEY_HERE',
            coinglass: 'YOUR_COINGLASS_API_KEY_HERE'
        },
        endpoints: {
            barchart: 'https://ondemand.websol.barchart.com',
            coinglass: 'https://open-api-v4.coinglass.com'
        },
        cacheDurationMs: 300000 // 5 minutes
    },
    lastRiskCurveUpdate: null,

    get: function(key) {
        const data = window.BLACKBOARD.getState(key);
        if (data !== undefined) return data;
        if (key === 'risk_curve') {
            this._loadRiskCurveAsync().catch(e => console.error('[ARK] Background load failed:', e));
            return this._getFallbackRiskCurve();
        }
        console.warn(`[ARK] No handler for key: ${key}`);
        return null;
    },

    _loadRiskCurveAsync: async function(force = false) {
        const now = Date.now();
        if (!force && this.lastRiskCurveUpdate && (now - this.lastRiskCurveUpdate < this.config.cacheDurationMs)) {
            console.log("[ARK] Using cached risk_curve");
            return window.BLACKBOARD.getState('risk_curve');
        }

        console.log("[ARK] Starting hydration...");
        const updateTs = new Date().toISOString();

        try {
            const [liqRaw, creditRaw, equityRaw, highBetaRaw, btcRaw] = await Promise.allSettled([
                this._fetchLiquidity(),
                this._fetchCredit(),
                this._fetchEquityBreadth(),
                this._fetchHighBeta(),
                this._fetchBTCBasis()
            ]);

            const nodes = {
                "Liquidity": this._mapToLiquidityNode(liqRaw.status === 'fulfilled' ? liqRaw.value : null),
                "Credit": this._mapToCreditNode(creditRaw.status === 'fulfilled' ? creditRaw.value : null),
                "EquityBreadth": this._mapToEquityBreadthNode(equityRaw.status === 'fulfilled' ? equityRaw.value : null),
                "HighBeta": this._mapToHighBetaNode(highBetaRaw.status === 'fulfilled' ? highBetaRaw.value : null),
                "BTCBasis": this._mapToBTCBasisNode(btcRaw.status === 'fulfilled' ? btcRaw.value : null)
            };

            const data = { as_of: new Date().toISOString().split('T')[0], nodes };
            window.BLACKBOARD.setState('risk_curve', data);
            this.lastRiskCurveUpdate = now;

            this.hydrationStatus.risk_curve = { timestamp: updateTs, success: 1, error: null };
            console.log("[ARK] Hydration completed");
            return data;
        } catch (err) {
            console.error("[ARK] Hydration failed:", err);
            this.hydrationStatus.risk_curve = { timestamp: updateTs, success: 0, error: err.message };
            const fb = this._getFallbackRiskCurve();
            window.BLACKBOARD.setState('risk_curve', fb);
            return fb;
        }
    },

    _fetchLiquidity: async function() {
        console.log("[ARK] _fetchLiquidity (mock)");
        return { fundingSpreadBps: -12, depthPercentile: 94, turnoverPct: 31 };
    },

    _fetchBTCBasis: async function() {
        try {
            const key = this.config.apiKeys.coinglass;
            if (key === 'YOUR_COINGLASS_API_KEY_HERE') {
                console.warn("[ARK] Coinglass API key not set - using mock");
                return { perpBasisBps: 180, cmeBasisBps: 165 };
            }
            const url = `${this.config.endpoints.coinglass}/api/futures/basis?exchange=CME&pair=BTC`;
            const res = await fetch(url, { 
                headers: { 'CG-API-KEY': key }
            });
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const json = await res.json();
            console.log("[ARK] Coinglass BTC Basis fetched");
            return json.data?.[0] || { perpBasisBps: 180, cmeBasisBps: 165 };
        } catch (e) {
            console.error("[ARK] Coinglass fetch failed:", e.message);
            return { perpBasisBps: 180, cmeBasisBps: 165 };
        }
    },

    _fetchCredit: async function() {
        console.log("[ARK] _fetchCredit (mock)");
        return { hySpreadBps: 72, zScore: 2.4 };
    },

    _fetchEquityBreadth: async function() {
        console.log("[ARK] _fetchEquityBreadth (mock)");
        return { breadthRatio: 58, percentAbove200dma: 64 };
    },

    _fetchHighBeta: async function() {
        console.log("[ARK] _fetchHighBeta (mock)");
        return { betaToSPX: 1.48, momentumSigma: -0.9 };
    },

    _mapToLiquidityNode: function(raw = {}) {
        return {
            score: 81, status: "Strong", quartile: "Q1",
            description: "Abundant market and funding liquidity",
            metricDefinition: "Measures availability and cost of short term capital across venues",
            metricInsight: "Shows how easily participants can enter or exit positions",
            role: "Foundational layer of the risk curve",
            adjacent: "Tightening here raises Credit spreads and compresses BTC Basis. Expansion supports Equity Breadth and High Beta.",
            regime: "Risk-on liquidity expansion",
            scoreReason: "Tight funding spreads and strong order book depth.",
            inputs: "Macro: Stable reserves. Micro: Dealer balance sheet expansion.",
            quantOutputs: `Funding spread ${raw.fundingSpreadBps || -12}bps, Depth Index ${raw.depthPercentile || 94}th percentile, Turnover +${raw.turnoverPct || 31}%`,
            lookback: "Q1 versus 1D, 30D, 60D. Q1 versus 90D. Q2 versus 1Y. Q1 versus 3Y."
        };
    },

    _mapToCreditNode: function(raw = {}) {
        return {
            score: 44, status: "Elevated", quartile: "Q4",
            description: "Rising pressure in credit markets",
            metricDefinition: "Tracks corporate and high yield bond spread widening",
            metricInsight: "Early signal of credit deterioration and risk aversion",
            role: "Core stress indicator for corporate health",
            adjacent: "Affected by Liquidity. Widening Credit suppresses Equity Breadth and High Beta.",
            regime: "Late cycle credit tightening",
            scoreReason: "Spread widening due to leverage and refinancing risks.",
            inputs: "Macro: Policy uncertainty. Micro: Corporate debt wall.",
            quantOutputs: `HY Spread +${raw.hySpreadBps || 72}bps, Z-score +${raw.zScore || 2.4}`,
            lookback: "Q4 versus 1D and 30D. Q3 versus 60D. Q4 versus 90D and 1Y. Q3 versus 3Y."
        };
    },

    _mapToEquityBreadthNode: function(raw = {}) {
        return {
            score: 67, status: "Moderate", quartile: "Q2",
            description: "Improving but still concentrated participation",
            metricDefinition: "Measures market participation through advance decline and sector dispersion",
            metricInsight: "Shows whether rallies are broad based or concentrated",
            role: "Key gauge of equity risk premium health",
            adjacent: "Supported by Liquidity. Influences High Beta performance.",
            regime: "Mega cap leadership with broadening attempts",
            scoreReason: "Advance decline improving but concentration remains high.",
            inputs: "Macro: Rotation signals. Micro: Sector dispersion rising.",
            quantOutputs: `Breadth Ratio ${raw.breadthRatio || 58} percent, Percent above 200DMA ${raw.percentAbove200dma || 64} percent`,
            lookback: "Q2 versus 1D and 30D. Q1 versus 60D. Q2 versus 90D and 1Y. Q2 versus 3Y."
        };
    },

    _mapToHighBetaNode: function(raw = {}) {
        return {
            score: 52, status: "Monitor", quartile: "Q3",
            description: "High beta names under relative pressure",
            metricDefinition: "Tracks performance of volatile, high sensitivity assets",
            metricInsight: "Reflects current risk appetite and leverage positioning",
            role: "Amplifier of moves across the risk curve",
            adjacent: "Sensitive to Liquidity and Equity Breadth. Weakness can precede Credit widening.",
            regime: "Late cycle beta compression",
            scoreReason: "Sensitivity to growth expectations and rate volatility.",
            inputs: "Macro: Higher for longer bias. Micro: Growth rotation.",
            quantOutputs: `Beta to SPX ${raw.betaToSPX || 1.48}, Momentum ${raw.momentumSigma || -0.9} sigma`,
            lookback: "Q3 versus 1D, 30D, and 60D. Q4 versus 90D. Q3 versus 1Y. Q2 versus 3Y."
        };
    },

    _mapToBTCBasisNode: function(raw = {}) {
        return {
            score: 79, status: "Strong", quartile: "Q1",
            description: "Positive and stable basis environment",
            metricDefinition: "Measures futures spot premium and funding rates in crypto",
            metricInsight: "Indicates institutional conviction and leverage direction",
            role: "Crypto risk appetite barometer and early liquidity signal",
            adjacent: "Supported by Liquidity. Positive basis reinforces High Beta and Equity sentiment.",
            regime: "Institutional accumulation phase",
            scoreReason: "Strong futures premium supported by ETF inflows and spot demand.",
            inputs: "Macro: Risk on sentiment. Crypto: Institutional and ETF demand.",
            quantOutputs: `Perp Basis +${raw.perpBasisBps || 180}bps. CME BT*0 +${raw.cmeBasisBps || 165}bps.`,
            lookback: "Q1 versus all periods. +24 percent basis strength versus 90D."
        };
    },

    _getFallbackRiskCurve: function() {
        return {
            as_of: new Date().toISOString().split('T')[0],
            nodes: {
                "Liquidity": { score: 81, status: "Strong", quartile: "Q1", description: "Abundant market and funding liquidity", metricDefinition: "Measures availability and cost of short term capital across venues", metricInsight: "Shows how easily participants can enter or exit positions", role: "Foundational layer of the risk curve", adjacent: "Tightening here raises Credit spreads and compresses BTC Basis. Expansion supports Equity Breadth and High Beta.", regime: "Risk-on liquidity expansion", scoreReason: "Tight funding spreads and strong order book depth.", inputs: "Macro: Stable reserves. Micro: Dealer balance sheet expansion.", quantOutputs: "Funding spread -12bps, Depth Index 94th percentile, Turnover +31%", lookback: "Q1 versus 1D, 30D, 60D. Q1 versus 90D. Q2 versus 1Y. Q1 versus 3Y." },
                "Credit": { score: 44, status: "Elevated", quartile: "Q4", description: "Rising pressure in credit markets", metricDefinition: "Tracks corporate and high yield bond spread widening", metricInsight: "Early signal of credit deterioration and risk aversion", role: "Core stress indicator for corporate health", adjacent: "Affected by Liquidity. Widening Credit suppresses Equity Breadth and High Beta.", regime: "Late cycle credit tightening", scoreReason: "Spread widening due to leverage and refinancing risks.", inputs: "Macro: Policy uncertainty. Micro: Corporate debt wall.", quantOutputs: "HY Spread +72bps, Z-score +2.4, Default probability +1.6%", lookback: "Q4 versus 1D and 30D. Q3 versus 60D. Q4 versus 90D and 1Y. Q3 versus 3Y." },
                "EquityBreadth": { score: 67, status: "Moderate", quartile: "Q2", description: "Improving but still concentrated participation", metricDefinition: "Measures market participation through advance decline and sector dispersion", metricInsight: "Shows whether rallies are broad based or concentrated", role: "Key gauge of equity risk premium health", adjacent: "Supported by Liquidity. Influences High Beta performance.", regime: "Mega cap leadership with broadening attempts", scoreReason: "Advance decline improving but concentration remains high.", inputs: "Macro: Rotation signals. Micro: Sector dispersion rising.", quantOutputs: "Breadth Ratio 58 percent, McClellan Oscillator +42, Percent above 200DMA 64 percent", lookback: "Q2 versus 1D and 30D. Q1 versus 60D. Q2 versus 90D and 1Y. Q2 versus 3Y." },
                "HighBeta": { score: 52, status: "Monitor", quartile: "Q3", description: "High beta names under relative pressure", metricDefinition: "Tracks performance of volatile, high sensitivity assets", metricInsight: "Reflects current risk appetite and leverage positioning", role: "Amplifier of moves across the risk curve", adjacent: "Sensitive to Liquidity and Equity Breadth. Weakness can precede Credit widening.", regime: "Late cycle beta compression", scoreReason: "Sensitivity to growth expectations and rate volatility.", inputs: "Macro: Higher for longer bias. Micro: Growth rotation.", quantOutputs: "Beta to SPX 1.48, Relative volatility +22 percent, Momentum -0.9 sigma", lookback: "Q3 versus 1D, 30D, and 60D. Q4 versus 90D. Q3 versus 1Y. Q2 versus 3Y." },
                "BTCBasis": { score: 79, status: "Strong", quartile: "Q1", description: "Positive and stable basis environment", metricDefinition: "Measures futures spot premium and funding rates in crypto", metricInsight: "Indicates institutional conviction and leverage direction", role: "Crypto risk appetite barometer and early liquidity signal", adjacent: "Supported by Liquidity. Positive basis reinforces High Beta and Equity sentiment.", regime: "Institutional accumulation phase", scoreReason: "Strong futures premium supported by ETF inflows and spot demand.", inputs: "Macro: Risk on sentiment. Crypto: Institutional and ETF demand.", quantOutputs: "Perp Basis +180bps. CME BT*0 +165bps. CME BT*1 +142bps. CME BT*2 +98bps.", lookback: "Q1 versus all periods. +24 percent basis strength versus 90D." }
            }
        };
    },

    refresh: async function() {
        console.log("[ARK] refresh() started");
        Object.keys(this.hydrationStatus).forEach(k => {
            this.hydrationStatus[k].timestamp = new Date().toISOString();
            this.hydrationStatus[k].success = 0;
            this.hydrationStatus[k].error = null;
        });
        return await this._loadRiskCurveAsync(true);
    },

    getHydrationStatus: function() {
        return { ...this.hydrationStatus };
    }
};

console.log("✅ ARK + BLACKBOARD Core v1.8 Loaded Successfully.");