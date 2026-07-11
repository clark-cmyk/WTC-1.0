// js/02_core.js
const WTC_BUILD = 'WTC-1.0-CORE-20260710';

const DATA_CONFIG = {
    hydration: 'data/hydration/latest.json',
    curve:     'data/barchart/v1/barchart_curve_history.json',
    bbdm:      'bang_bang_da/bang_bang_da_report.json',
    coinglass: 'bang_bang_da/litmus/crypto_market.json'
};

let dataCache = {};

async function loadData(type) {
    if (!DATA_CONFIG[type]) return null;
    if (dataCache[type]) return dataCache[type];

    try {
        const res = await fetch(DATA_CONFIG[type], { cache: 'no-store' });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        dataCache[type] = data;
        console.log(`✅ Loaded ${type}`);
        return data;
    } catch (e) {
        console.error(`Failed ${type}`, e);
        return null;
    }
}

function getData(type) {
    return dataCache[type] || null;
}

window.WTC_Core = { loadData, getData, BUILD: WTC_BUILD };