import os
import subprocess
import tempfile
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from starlette.background import BackgroundTask

app = FastAPI(title="MomentClip")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/", response_class=HTMLResponse)
def index():
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/health")
def health():
    return {"status": "ok", "cookies_configured": bool(os.environ.get("YT_COOKIES", "").strip())}

@app.get("/clip")
def download_clip(
    video_id: str = Query(..., min_length=11, max_length=11),
    start: int = Query(0, ge=0),
    end: int = Query(..., gt=0),
    quality: str = Query("highest"),
):
    if end <= start:
        raise HTTPException(status_code=400, detail="end must be greater than start")

    fmt = (
        "bv*[height<=1080]+ba/b[height<=1080]/b"
        if quality == "1080"
        else "bv*[height<=720]+ba/b[height<=720]/b"
        if quality == "720"
        else "bv*+ba/b"
    )

    def fmt_ts(sec: int) -> str:
        h, rem = divmod(sec, 3600)
        m, s = divmod(rem, 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

    tmpdir = tempfile.mkdtemp()
    out_path = os.path.join(tmpdir, f"clip_{video_id}_{start}_{end}.mp4")

    cmd = [
        "yt-dlp",
        "--remote-components", "ejs:github",
        "--download-sections", f"*{fmt_ts(start)}-{fmt_ts(end)}",
        "--force-keyframes-at-cuts",
        "-f", fmt,
        "--merge-output-format", "mp4",
        "-o", out_path,
    ]

    yt_cookies = os.environ.get("YT_COOKIES", "").strip()
    if yt_cookies:
        cookies_path = os.path.join(tmpdir, "cookies.txt")
        with open(cookies_path, "w", encoding="utf-8") as cf:
            cf.write(yt_cookies + "\n")
        cmd.extend(["--cookies", cookies_path])

    cmd.append(f"https://www.youtube.com/watch?v={video_id}")

    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if proc.returncode != 0 or not os.path.exists(out_path):
        os.system(f"rm -rf {tmpdir}")
        raise HTTPException(status_code=500, detail=proc.stderr[-500:] or "yt-dlp failed")

    return FileResponse(
        out_path,
        media_type="video/mp4",
        filename=f"moment_{video_id}_{start}s_{end}s.mp4",
        background=BackgroundTask(lambda: os.system(f"rm -rf {tmpdir}")),
    )
