import os
import json
import uuid
import time
import shutil
import signal
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any

import yaml
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles


def load_config() -> Dict[str, Any]:
    cfg_path = Path(__file__).parent / "config.yaml"
    with cfg_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


CFG = load_config()

APP_DIR = Path(__file__).parent.resolve()
RUNS_ROOT = (APP_DIR / CFG["runs_root"]).resolve()
WORK_ROOT = (APP_DIR / CFG["work_root"]).resolve()

NEXTFLOW_CMD = CFG["nextflow_cmd"]
PIPELINE_PATH = str((APP_DIR / CFG["pipeline_path"]).resolve())
PARAM_NAME = CFG.get("param_name", "reads")
MULTIQC_HTML_RELPATH = CFG.get("multiqc_html_relpath", "multiqc/multiqc_report.html")

RUNS_ROOT.mkdir(parents=True, exist_ok=True)
WORK_ROOT.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="QC Web PoC (FastAPI + Nextflow + MultiQC)")

# Minimal CORS for local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost", "http://127.0.0.1", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def run_dir(run_id: str) -> Path:
    return RUNS_ROOT / run_id
app.mount("/runs", StaticFiles(directory=str(RUNS_ROOT), html=True), name="runs")

def meta_path(run_id: str) -> Path:
    return run_dir(run_id) / "meta.json"


def load_meta(run_id: str) -> Dict[str, Any]:
    p = meta_path(run_id)
    if not p.exists():
        raise HTTPException(status_code=404, detail="run_id not found")
    return json.loads(p.read_text(encoding="utf-8"))


def save_meta(run_id: str, meta: Dict[str, Any]) -> None:
    p = meta_path(run_id)
    p.write_text(json.dumps(meta, indent=2), encoding="utf-8")


def safe_tail(path: Path, max_bytes: int = 50_000) -> str:
    if not path.exists():
        return ""
    size = path.stat().st_size
    start = max(0, size - max_bytes)
    with path.open("rb") as f:
        f.seek(start)
        data = f.read()
    try:
        return data.decode("utf-8", errors="replace")
    except Exception:
        return data.decode(errors="replace")


def is_process_alive(pid: Optional[int]) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/api/runs")
def create_run():
    run_id = uuid.uuid4().hex[:12]
    rd = run_dir(run_id)
    uploads = rd / "uploads"
    results = rd / "results"
    logs = rd / "logs"
    uploads.mkdir(parents=True, exist_ok=True)
    results.mkdir(parents=True, exist_ok=True)
    logs.mkdir(parents=True, exist_ok=True)

    meta = {
        "run_id": run_id,
        "created_at": int(time.time()),
        "status": "created",
        "fastq_filename": None,
        "fastq_path": None,
        "nextflow_pid": None,
        "exit_code": None,
        "started_at": None,
        "finished_at": None,
        "pipeline_path": PIPELINE_PATH,
        "param_name": PARAM_NAME,
        "outdir": str(results),
        "workdir": str(WORK_ROOT),
        "multiqc_html": None,
        "error": None,
    }
    save_meta(run_id, meta)
    return meta


@app.post("/api/runs/{run_id}/upload")
async def upload_fastq(run_id: str, file: UploadFile = File(...)):
    meta = load_meta(run_id)
    if meta["status"] not in ["created", "uploaded", "failed", "done"]:
        raise HTTPException(status_code=400, detail=f"cannot upload in status={meta['status']}")

    filename = Path(file.filename).name
    if not (filename.endswith(".fastq") or filename.endswith(".fq") or filename.endswith(".fastq.gz") or filename.endswith(".fq.gz")):
        raise HTTPException(status_code=400, detail="only .fastq/.fq (optionally .gz) allowed")

    rd = run_dir(run_id)
    dest = rd / "uploads" / filename

    # Stream to disk (no memory blowups)
    with dest.open("wb") as out:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            out.write(chunk)

    meta["status"] = "uploaded"
    meta["fastq_filename"] = filename
    meta["fastq_path"] = str(dest)
    meta["error"] = None
    save_meta(run_id, meta)
    return meta


@app.post("/api/runs/{run_id}/start")
def start_run(run_id: str):
    meta = load_meta(run_id)
    if meta["status"] not in ["uploaded", "failed", "done"]:
        raise HTTPException(status_code=400, detail=f"cannot start in status={meta['status']}")
    if not meta["fastq_path"] or not Path(meta["fastq_path"]).exists():
        raise HTTPException(status_code=400, detail="fastq not uploaded")

    rd = run_dir(run_id)
    logs_dir = rd / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    nf_log = logs_dir / "nextflow.log"

    outdir = Path(meta["outdir"])
    outdir.mkdir(parents=True, exist_ok=True)

    # Build command
    # Example: nextflow run main.nf --reads <fastq> --outdir <outdir> -work-dir <work> -resume
    cmd = [
        NEXTFLOW_CMD,
        "run",
        PIPELINE_PATH,
        f"--{PARAM_NAME}",
        meta["fastq_path"],
        "--outdir",
        str(outdir),
        "-work-dir",
        str(WORK_ROOT),
        "-resume",
        "-ansi-log",
        "false",
    ]

    # Launch process
    with nf_log.open("wb") as logf:
        proc = subprocess.Popen(
            cmd,
            cwd=str(rd),
            stdout=logf,
            stderr=subprocess.STDOUT,
            env={**os.environ},
        )

    meta["status"] = "running"
    meta["nextflow_pid"] = proc.pid
    meta["started_at"] = int(time.time())
    meta["exit_code"] = None
    meta["finished_at"] = None
    meta["error"] = None
    save_meta(run_id, meta)
    return meta


@app.post("/api/runs/{run_id}/stop")
def stop_run(run_id: str):
    meta = load_meta(run_id)
    pid = meta.get("nextflow_pid")
    if meta["status"] != "running" or not pid:
        raise HTTPException(status_code=400, detail="run is not running")

    try:
        os.kill(pid, signal.SIGTERM)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"failed to stop: {e}")

    meta["status"] = "stopping"
    save_meta(run_id, meta)
    return meta


def refresh_status(meta: Dict[str, Any]) -> Dict[str, Any]:
    # If running, check if it ended
    if meta["status"] in ["running", "stopping"]:
        pid = meta.get("nextflow_pid")
        alive = is_process_alive(pid)
        if not alive:
            # Attempt to infer exit code by parsing nextflow log last lines is unreliable.
            # Mark as finished and let MultiQC presence decide done vs failed.
            meta["finished_at"] = int(time.time())

            multiqc_html = Path(meta["outdir"]) / MULTIQC_HTML_RELPATH
            if multiqc_html.exists() and multiqc_html.stat().st_size > 0:
                meta["status"] = "done"
                meta["multiqc_html"] = str(multiqc_html)
                meta["exit_code"] = 0
                meta["error"] = None
            else:
                meta["status"] = "failed"
                meta["exit_code"] = 1
                meta["error"] = "MultiQC report not found at expected path. Check nextflow.log or config.yaml."

    return meta

@app.get("/api/status")
def status():
    return "Running"

@app.get("/api/runs/{run_id}")
def get_run(run_id: str):
    meta = load_meta(run_id)
    meta = refresh_status(meta)
    save_meta(run_id, meta)

    nf_log = run_dir(run_id) / "logs" / "nextflow.log"
    meta["log_tail"] = safe_tail(nf_log)
    return meta


@app.get("/api/runs/{run_id}/multiqc")
def get_multiqc(run_id: str):
    meta = load_meta(run_id)
    meta = refresh_status(meta)
    save_meta(run_id, meta)

    multiqc_html = None
    if meta.get("multiqc_html"):
        multiqc_html = Path(meta["multiqc_html"])
    else:
        candidate = Path(meta["outdir"]) / MULTIQC_HTML_RELPATH
        if candidate.exists():
            multiqc_html = candidate

    if not multiqc_html or not multiqc_html.exists():
        raise HTTPException(status_code=404, detail="MultiQC report not available yet")

    return FileResponse(str(multiqc_html), media_type="text/html")


# Serve run outputs (MultiQC assets live under multiqc_data/)
# This exposes /outputs/<run_id>/... to the browser.
app.mount("/outputs", StaticFiles(directory=str(RUNS_ROOT), html=False), name="outputs")


@app.delete("/api/runs/{run_id}")
def delete_run(run_id: str):
    rd = run_dir(run_id)
    if not rd.exists():
        return JSONResponse({"ok": True})
    shutil.rmtree(rd, ignore_errors=True)
    return {"ok": True}