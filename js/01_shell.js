// js/01_shell.js

let currentModule = 4;

const modules = [
    { id: 1, code: "ART", name: "Articulate" },
    { id: 2, code: "ARK", name: "Ark" },
    { id: 3, code: "BAS", name: "Basis" },
    { id: 4, code: "BBD", name: "Bang Bang Da" },
    { id: 5, code: "COM", name: "Compute" },
    { id: 6, code: "RCV", name: "Risk Curve" },
    { id: 7, code: "SQ3", name: "SQ3" }
];

function renderTabs() {
    const container = document.getElementById('module-tabs');
    container.innerHTML = modules.map(m => `
        <div class="tab" data-id="${m.id}" onclick="switchModule(${m.id})">
            ${m.id}. ${m.code}
        </div>
    `).join('');
}

async function switchModule(id) {
    currentModule = id;
    
    // Update active tab
    document.querySelectorAll('.tab').forEach(tab => {
        tab.classList.toggle('active', parseInt(tab.dataset.id) === id);
    });

    const content = document.getElementById('main-content');
    const mod = modules.find(m => m.id === id);

    if (id === 6) {
        // Load Risk Curve module
        content.innerHTML = renderRiskCurve ? renderRiskCurve() : `<h2>${mod.name} (${mod.code})</h2><p>Loading Risk Curve...</p>`;
    } else {
        content.innerHTML = `
            <h2>${mod.name} (${mod.code})</h2>
            <p>Module content loads here.</p>
        `;
    }
}

function refreshData() {
    alert("Data refreshed");
}

function articulate() {
    alert("Articulate snapshot copied");
}

// Keyboard shortcuts 1-7
document.addEventListener('keydown', (e) => {
    if (e.key >= '1' && e.key <= '7') {
        switchModule(parseInt(e.key));
    }
});

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    renderTabs();
    switchModule(4); // Start on Bang Bang Da
});