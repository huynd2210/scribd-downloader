"""
FastAPI Server for Scribd Downloader Web Application
===================================================
Provides REST API & Server-Sent Events (SSE) / WebSocket endpoints for managing Scribd PDF downloads.
"""

import asyncio
import json
import os
import re
import threading
import uuid
from typing import Dict, Any, List

from fastapi import FastAPI, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import scribd_downloader_core as core

app = FastAPI(title="Scribd Downloader Web API", version="2.0.0")

# Task storage: task_id -> task_info dict
tasks_db: Dict[str, Dict[str, Any]] = {}
active_websockets: Dict[str, List[WebSocket]] = {}


class DownloadRequest(BaseModel):
    url: str = Field(..., description="Scribd document URL")
    scroll_delay: float = Field(0.15, ge=0.01, le=5.0)
    cdp_timeout: int = Field(600, ge=10, le=3600)
    settle_timeout: int = Field(30, ge=1, le=300)
    headless: bool = Field(True)


@app.post("/api/validate-url")
def validate_url(data: Dict[str, str]):
    url = data.get("url", "").strip()
    converted = core.convert_scribd_link(url)
    filename = core.get_filename_from_url(url) if converted != "Invalid Scribd URL" else ""
    return {
        "valid": converted != "Invalid Scribd URL",
        "embed_url": converted,
        "filename": filename,
    }


def broadcast_task_update(task_id: str):
    """Notify active WebSocket listeners of a task update."""
    if task_id in active_websockets:
        task_data = tasks_db.get(task_id, {})
        data_str = json.dumps(task_data)
        for ws in active_websockets[task_id]:
            try:
                asyncio.run_coroutine_threadsafe(ws.send_text(data_str), asyncio.get_event_loop())
            except Exception:
                pass


def run_download_task(task_id: str, req: DownloadRequest):
    task = tasks_db[task_id]

    def status_callback(stage: str):
        task["stage"] = stage

    def progress_callback(current: int, total: int):
        task["current_page"] = current
        task["total_pages"] = total
        task["progress_percent"] = round((current / total) * 100, 1) if total > 0 else 0

    def log_callback(msg: str):
        task["logs"].append(msg)

    try:
        result = core.download_document(
            input_url=req.url,
            scroll_delay=req.scroll_delay,
            cdp_timeout=req.cdp_timeout,
            settle_timeout=req.settle_timeout,
            headless=req.headless,
            status_cb=status_callback,
            progress_cb=progress_callback,
            log_cb=log_callback,
        )
        task["status"] = "COMPLETED"
        task["stage"] = "COMPLETED"
        task["progress_percent"] = 100.0
        task["result"] = result
    except Exception as exc:
        task["status"] = "FAILED"
        task["stage"] = "ERROR"
        task["error"] = str(exc)


@app.post("/api/download")
def start_download(req: DownloadRequest):
    url = req.url.strip()
    if core.convert_scribd_link(url) == "Invalid Scribd URL":
        raise HTTPException(status_code=400, detail="Invalid Scribd URL format.")

    task_id = str(uuid.uuid4())[:8]
    tasks_db[task_id] = {
        "task_id": task_id,
        "url": url,
        "filename": core.get_filename_from_url(url),
        "status": "RUNNING",
        "stage": "INITIALIZING",
        "current_page": 0,
        "total_pages": 0,
        "progress_percent": 0.0,
        "logs": [],
        "result": None,
        "error": None,
    }

    thread = threading.Thread(target=run_download_task, args=(task_id, req), daemon=True)
    thread.start()

    return {"task_id": task_id, "status": "RUNNING", "filename": tasks_db[task_id]["filename"]}


@app.get("/api/status/{task_id}")
def get_task_status(task_id: str):
    if task_id not in tasks_db:
        raise HTTPException(status_code=404, detail="Task not found")
    return tasks_db[task_id]


@app.get("/api/events/{task_id}")
async def stream_task_events(task_id: str):
    if task_id not in tasks_db:
        raise HTTPException(status_code=404, detail="Task not found")

    async def event_generator():
        last_log_count = 0
        while True:
            if task_id not in tasks_db:
                break
            task = tasks_db[task_id]
            current_log_count = len(task["logs"])
            new_logs = task["logs"][last_log_count:]
            last_log_count = current_log_count

            payload = {
                "task_id": task_id,
                "status": task["status"],
                "stage": task["stage"],
                "current_page": task["current_page"],
                "total_pages": task["total_pages"],
                "progress_percent": task["progress_percent"],
                "new_logs": new_logs,
                "result": task.get("result"),
                "error": task.get("error"),
            }
            yield f"data: {json.dumps(payload)}\n\n"

            if task["status"] in ("COMPLETED", "FAILED"):
                break
            await asyncio.sleep(0.5)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/api/downloads")
def list_downloads():
    os.makedirs(core.OUTPUT_DIR, exist_ok=True)
    files = []
    
    # Parse tracker if present
    tracker_info = {}
    tracker_path = os.path.join(os.path.dirname(__file__), "downloads_tracker.md")
    if os.path.exists(tracker_path):
        try:
            with open(tracker_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("| 20"):
                        parts = [p.strip() for p in line.split("|")[1:-1]]
                        if len(parts) >= 6:
                            # date, title, url, filename, file_url, pages, size
                            filename_match = re.search(r"`([^`]+\.pdf)`", parts[2]) or re.search(r"`([^`]+\.pdf)`", parts[3])
                            fname = filename_match.group(1) if filename_match else parts[3].replace("`", "")
                            tracker_info[fname] = {
                                "date": parts[0],
                                "title": parts[1],
                                "url": parts[2].replace("`", ""),
                                "pages": parts[5],
                            }
        except Exception:
            pass

    for fname in os.listdir(core.OUTPUT_DIR):
        if fname.lower().endswith(".pdf"):
            full_path = os.path.join(core.OUTPUT_DIR, fname)
            stat = os.stat(full_path)
            meta = tracker_info.get(fname, {})
            files.append({
                "filename": fname,
                "title": meta.get("title", fname.replace(".pdf", "").replace("_", " ")),
                "url": meta.get("url", ""),
                "pages": meta.get("pages", "N/A"),
                "size_bytes": stat.st_size,
                "size_mb": round(stat.st_size / (1024 * 1024), 2),
                "created_at": meta.get("date", os.path.getmtime(full_path)),
            })

    files.sort(key=lambda x: str(x["created_at"]), reverse=True)
    return {"downloads": files, "count": len(files)}


@app.get("/api/downloads/{filename}")
def get_pdf_file(filename: str):
    safe_name = os.path.basename(filename)
    file_path = os.path.join(core.OUTPUT_DIR, safe_name)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path, media_type="application/pdf", filename=safe_name)


@app.delete("/api/downloads/{filename}")
def delete_pdf_file(filename: str):
    safe_name = os.path.basename(filename)
    file_path = os.path.join(core.OUTPUT_DIR, safe_name)
    if os.path.exists(file_path):
        os.remove(file_path)
        return {"success": True, "message": f"Deleted {safe_name}"}
    raise HTTPException(status_code=404, detail="File not found")


# Mount static web app directory
static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
