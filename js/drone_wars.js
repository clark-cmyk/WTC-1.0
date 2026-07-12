/**
 * js/drone_wars.js - UI Integration for Drone Wars
 * Triggered from RCV panels and main tab
 */

console.log("Drone Wars JS Loaded");

function triggerDroneWars() {
    const prompt = "Launch Drone Wars analysis on current Risk Curve. Focus on Credit elevated node and cross-asset contagion.";
    navigator.clipboard.writeText(prompt).then(() => {
        showToast("Drone Wars launched — Prompt copied to clipboard");
    }).catch(() => alert(prompt));
    
    // Future: Open modal, call core.py orchestrator, etc.
    console.log("[Drone Wars] Orchestrator triggered");
}

// Expose to global for HTML buttons
window.triggerDroneWars = triggerDroneWars;
