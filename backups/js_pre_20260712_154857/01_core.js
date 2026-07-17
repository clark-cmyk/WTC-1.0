// js/02_core.js
// WTC 1.0 - Clean Data Core (Single Source of Truth)

const WTC_BUILD = 'WTC-1.0-CORE-20260710';

const DATA_CONFIG = {
    hydration: 'data/hydration/latest.json',
    curve:     'data/barchart/v1/barchart_curve_history.json',
    bbdm:      'bang_bang_da/bang_bang_da_report.json',
    coinglass: 'bang_bang_da/litmus/crypto_market.json'
};

let dataCache = {};

// Load a specific data type
async function loadData(type) {
    if (!DATA_CONFIG[type]) {
        console.error(`Unknown data type: ${type}`);
        return null;
    }

    if (dataCache[type]) {
        return dataCache[type];
    }

    try {
        const res = await fetch(DATA_CONFIG[type], { cache: 'no-store' });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);

        const data = await res.json();
        dataCache[type] = data;
        console.log(`✅ Loaded ${type} data`);
        return data;
    } catch (err) {
        console.error(`Failed to load ${type}:`, err);
        return null;
    }
}

function getData(type) {
    return dataCache[type] || null;
}

function clearCache(type = null) {
    if (type) {
        dataCache[type] = null;
    } else {
        dataCache = {};
    }
}

// Public API
window.WTC_Core = {
    loadData,
    getData,
    clearCache,
    BUILD: WTC_BUILD,
    CONFIG: DATA_CONFIG
};

console.log('✅ WTC Core 02 initialized — Build', WTC_BUILD);