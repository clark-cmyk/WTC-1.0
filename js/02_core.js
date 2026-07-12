// js/02_core.js
window.ARK = {
    get: function(key) {
        if (key === 'risk_curve') {
            return {
                as_of: "2026-07-11",
                nodes: {
                    "Liquidity": {
                        score: 81,
                        status: "Strong",
                        quartile: "Q1",
                        description: "Abundant market and funding liquidity",
                        regime: "Risk-on liquidity expansion • 14 days in current regime",
                        scoreReason: "Tight funding spreads and elevated order book depth across major venues.",
                        inputs: "Macro: Stable central bank reserves • Micro: Dealer balance sheet expansion",
                        quantOutputs: "Funding spread -12bps, Depth Index 94th %ile, Turnover +31%",
                        lookback: "Q1 vs 1D/30D/60D | Q1 vs 90D | Q2 vs 1Y | Q1 vs 3Y (+18% depth improvement)"
                    },
                    "Credit": {
                        score: 44,
                        status: "Elevated",
                        quartile: "Q4",
                        description: "Rising pressure in credit markets",
                        regime: "Late-cycle credit tightening • 41 days in regime",
                        scoreReason: "Spread widening due to leverage concerns and heavy refinancing calendar.",
                        inputs: "Macro: Policy uncertainty • Micro: Corporate debt wall",
                        quantOutputs: "HY Spread +72bps, Z-score +2.4, Default prob +1.6%",
                        lookback: "Q4 vs 1D/30D | Q3 vs 60D | Q4 vs 90D/1Y | Q3 vs 3Y"
                    },
                    "EquityBreadth": {
                        score: 67,
                        status: "Moderate",
                        quartile: "Q2",
                        description: "Improving but still concentrated participation",
                        regime: "Mega-cap leadership with broadening attempts • 9 days",
                        scoreReason: "Advance-decline line improving but market cap concentration remains high.",
                        inputs: "Macro: Rotation signals • Micro: Sector dispersion rising",
                        quantOutputs: "Breadth Ratio 58%, McClellan +42, % above 200DMA 64%",
                        lookback: "Q2 vs 1D/30D | Q1 vs 60D | Q2 vs 90D/1Y | Q2 vs 3Y"
                    },
                    "HighBeta": {
                        score: 52,
                        status: "Monitor",
                        quartile: "Q3",
                        description: "High-beta names under relative pressure",
                        regime: "Late-cycle beta compression • 27 days",
                        scoreReason: "Sensitivity to growth expectations and rising rate volatility.",
                        inputs: "Macro: Higher for longer bias • Micro: Growth rotation out of tech",
                        quantOutputs: "Beta to SPX 1.48, Relative vol +22%, Momentum -0.9σ",
                        lookback: "Q3 vs 1D/30D/60D | Q4 vs 90D | Q3 vs 1Y | Q2 vs 3Y"
                    },
                    "BTCBasis": {
                        score: 79,
                        status: "Strong",
                        quartile: "Q1",
                        description: "Positive and stable basis environment",
                        regime: "Institutional accumulation phase • 22 days",
                        scoreReason: "Strong futures premium supported by ETF inflows and spot demand.",
                        inputs: "Macro: Risk-on sentiment • Crypto: Institutional + ETF demand",
                        quantOutputs: "Perp Basis +180bps | CME Basis +165bps | Funding Rate +0.042%",
                        lookback: "Q1 vs all periods | +24% basis strength vs 90D"
                    }
                }
            };
        }
        return null;
    }
};

console.log("✅ ARK Core Loaded with enhanced BTCBasis data");