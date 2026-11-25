from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from src.analyzer import analyze_python_code
from src.database import delete_scan, init_db, list_scans, save_scan
from src.github_client import fetch_python_files_from_github

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="RepoLens Static Code Analyzer", version="1.0.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


class SnippetAnalyzeRequest(BaseModel):
    filename: str = Field(default="snippet.py", max_length=120)
    source_code: str = Field(..., min_length=1)


class GitHubAnalyzeRequest(BaseModel):
    repo_url: str = Field(..., min_length=10)


@app.get("/")
def serve_dashboard():
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.post("/api/analyze")
def analyze_snippet(payload: SnippetAnalyzeRequest):
    try:
        report = analyze_python_code(payload.source_code, filename=payload.filename.strip() or "snippet.py")
        scan_id = save_scan(report, source_type="snippet")
        return {"scan_id": scan_id, **report}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/analyze-github")
def analyze_github_repo(payload: GitHubAnalyzeRequest):
    try:
        files = fetch_python_files_from_github(payload.repo_url)
        reports = []
        for file_obj in files:
            report = analyze_python_code(file_obj["source_code"], filename=file_obj["filename"])
            scan_id = save_scan(report, source_type="github")
            reports.append({"scan_id": scan_id, **report})
        return {"analyzed_files": len(reports), "reports": reports}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ConnectionError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/api/scans")
def get_scan_history():
    return {"scans": list_scans()}


@app.delete("/api/scans/{scan_id}")
def remove_scan(scan_id: int):
    if not delete_scan(scan_id):
        raise HTTPException(status_code=404, detail="Scan record not found.")
    return {"deleted": True, "scan_id": scan_id}
