async function triggerDroneWars(arkData) {
    const response = await fetch('/api/drone_wars', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(arkData)
    });
    const report = await response.json();
    // Pass to ART
    articulateDroneWars(report);
}

function articulateDroneWars(report) {
    alert("Drone Wars report ready for ART commentary.");
    console.log("Drone Wars report:", report);
}
