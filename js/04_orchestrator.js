/**
 * js/04_orchestrator.js
 * Advanced Orchestrator Logic
 */

window.ORCHESTRATOR = {
    version: "1.0",
    status: "initializing",

    captains: {
        collection: null,
        cleaning: null,
        analysis: null
    },

    init: function() {
        console.log(" ORCHESTRATOR v1.0 Starting...");

        this.captains.collection = {
            name: "Collection Captain",
            status: "ready",
            
            run: async function(priority = "normal") {
                console.log(` Collection Captain running (priority: ${priority})`);
                
                // Call the Python script
                const result = await this._callPythonDownloader();
                
                if (result.success) {
                    BLACKBOARD.setState('data_last_updated', new Date().toISOString());
                    console.log(" Data collection completed successfully.");
                    return result;
                } else {
                    console.error(" Collection failed:", result.message);
                    return result;
                }
            },

            _callPythonDownloader: async function() {
                // This will call your run_csv_download.py via your backend
                try {
                    const response = await fetch('/api/collect-data', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ source: 'all' })
                    });
                    return await response.json();
                } catch (err) {
                    return { success: false, message: err.message };
                }
            }
        };

        this.status = "ready";
        console.log(" Orchestrator fully initialized.");
        
        // Expose globally
        window.Orchestrator = this;
        return this;
    }
};

// Initialize
ORCHESTRATOR.init();