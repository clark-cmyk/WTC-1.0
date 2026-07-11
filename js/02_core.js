// js/02_core.js
const WTC_BUILD = 'WTC-1.0-CORE-20260710';

let dataCache = {};
let config = null;

async function loadConfig() {
    if (config) return config;
    try {
        const res = await fetch('data/01_config.json', { cache: 'no-store' });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        config = await res.json();
        console.log("✅ Loaded data/01_config.json", config);
        return config;
    } catch (e) {
        console.error("Failed to load config", e);
        return null;
    }
}

async function loadData(type) {
    console.log(`Attempting to load ${type}`);
    const cfg = await loadConfig();
    if (!cfg || !cfg.data_paths[type]) {
        console.error(`No path for ${type}`);
        return null;
    }
    if (dataCache[type]) return dataCache[type];

    try {
        const path = cfg.data_paths[type];
        console.log(`Fetching: ${path}`);
        const res = await fetch(path, { cache: 'no-store' });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        dataCache[type] = data;
        console.log(`✅ Loaded ${type}`);
        return data;
    } catch (e) {
        console.error(`Failed to load ${type}`, e);
        return null;
    }
}

function getData(type) {
    return dataCache[type] || null;
}

window.WTC_Core = { loadData, getData, BUILD: WTC_BUILD };
console.log("✅ WTC Core 02 initialized");