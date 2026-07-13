from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import sys
from pathlib import Path

# Add parent directory to path so we can import the wrapper
sys.path.append(str(Path(__file__).parent.parent))

from whinfell_pipeline.agent_wrapper import run_pipeline, collect_data, run_full_daily

app = FastAPI(title="WTC 1.0 Backend", version="1.0")

class CollectionRequest(BaseModel):
    command: str = "daily"          # daily, collect, hydrate
    source: str = "all"             # koyfin, barchart, all
    priority: str = "normal"        # normal, high

@app.get("/")
def health_check():
    return {"status": "ok", "message": "WTC 1.0 Backend running"}

@app.post("/api/trigger-collection")
def trigger_collection(req: CollectionRequest):
    """
    Main endpoint for Orchestrator / Collection Captain to trigger data collection.
    """
    try:
        if req.command == "daily":
            result = run_full_daily()
        elif req.command == "collect":
            result = collect_data(source=req.source)
        elif req.command == "hydrate":
            result = run_pipeline("hydrate")
        else:
            result = run_pipeline(req.command, source=req.source)

        return {
            "success": result.get("success", False),
            "command": req.command,
            "source": req.source,
            "result": result
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)