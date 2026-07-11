# -*- coding: utf-8 -*-
"""
內容擷取模組：給一個網址，自動判斷是網頁還是圖片還是影片，抓出裡面的文字。

- 網頁（PTT/Dcard/新聞/部落格等）：抓正文文字
- 圖片（截圖、迷因圖等）：用 OCR 辨識圖片裡的文字（免費、不用API key）
- 影片：下載後用語音轉文字(faster-whisper)取得逐字稿，運算較重，
  在 main.py 會用背景任務處理，不會卡住API回應

效率優化：
- 影片長度預判：短片用高精度模型(small)，長片自動降級(base)+截斷處理時間，避免單支超長影片吃光資源
- 多個Whisper模型依大小分開快取，不重複載入
"""

import io
import os
import json
import subprocess
import tempfile
import shutil
import re
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0"}

IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp")
VIDEO_EXTENSIONS = (".mp4", ".mov", ".avi", ".mkv")
VIDEO_DOMAINS = ("youtube.com", "youtu.be", "tiktok.com", "instagram.com/reel", "facebook.com/watch")

# 依大小分開快取模型，避免重複載入拖慢速度
_whisper_models = {}


def _get_whisper_model(model_size: str):
    if model_size not in _whisper_models:
        from faster_whisper import WhisperModel
        _whisper_models[model_size] = WhisperModel(model_size, device="cpu", compute_type="int8")
    return _whisper_models[model_size]


def _choose_strategy(duration_seconds):
    """
    依影片長度決定 whisper模型大小 與 是否截斷處理時間，兼顧速度與準確度：
    - 3分鐘內：精度優先(small)，反正短，跑久也不會太久
    - 3-15分鐘：平衡(base)，速度快很多，中文準確度仍可接受
    - 超過15分鐘：只處理前15分鐘，避免單支超長影片把系統資源整個吃滿
    - 抓不到長度（例如某些平台metadata拿不到）：保守用base+上限15分鐘
    """
    default_size = os.environ.get("WHISPER_MODEL_SIZE", "base")
    if duration_seconds is None:
        return {"model_size": default_size, "max_seconds": 900}
    if duration_seconds <= 180:
        return {"model_size": "small", "max_seconds": None}
    elif duration_seconds <= 900:
        return {"model_size": "base", "max_seconds": None}
    else:
        return {"model_size": "base", "max_seconds": 900}


def _ffprobe_duration(path: str):
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", path],
            capture_output=True, timeout=15,
        )
        return float(result.stdout.decode().strip())
    except Exception:
        return None


def _probe_duration_ytdlp(url: str):
    """只抓metadata(不下載影片本體)取得時長，讓長片能在下載前就決定要不要截斷"""
    try:
        result = subprocess.run(
            ["yt-dlp", "--no-check-certificate", "--dump-json", "--no-warnings", url],
            capture_output=True, timeout=30,
        )
        if result.returncode != 0:
            return None
        info = json.loads(result.stdout.decode(errors="ignore").splitlines()[0])
        return info.get("duration")
    except Exception:
        return None


def detect_url_type(url: str) -> str:
    """回傳 'image' / 'video' / 'webpage'"""
    path = urlparse(url).path.lower()
    domain = urlparse(url).netloc.lower()

    if path.endswith(IMAGE_EXTENSIONS):
        return "image"
    if path.endswith(VIDEO_EXTENSIONS):
        return "video"
    if any(v in domain for v in VIDEO_DOMAINS) or any(v in url for v in VIDEO_DOMAINS):
        return "video"
    return "webpage"


def extract_webpage_text(url: str, max_chars: int = 1500) -> dict:
    """抓網頁標題與正文，回傳 {'title':..., 'content':...}"""
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")

    title_tag = soup.find("title")
    title = title_tag.get_text().strip() if title_tag else ""

    for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
        tag.decompose()

    main = soup.find("article") or soup.find("main") or soup.find(id="main-content") or soup
    paragraphs = main.find_all("p")
    text = "\n".join(p.get_text().strip() for p in paragraphs if p.get_text().strip())

    if not text:
        text = main.get_text(separator="\n").strip()

    text = re.sub(r"\n{3,}", "\n\n", text)
    return {"title": title, "content": text[:max_chars]}


def extract_image_text(url: str) -> dict:
    """下載圖片並用 OCR 辨識文字（繁中+簡中+英文）"""
    import pytesseract
    from PIL import Image

    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    img = Image.open(io.BytesIO(resp.content))

    text = pytesseract.image_to_string(img, lang="chi_tra+chi_sim+eng")
    text = text.strip()
    return {"title": "", "content": text}


# ---------- 影片：下載 + 語音轉文字 ----------

def _download_direct(url: str, dest_path: str) -> bool:
    """嘗試直接HTTP下載（適用CDN直鏈/.mp4結尾的網址，速度快、不依賴yt-dlp）"""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=60, stream=True)
        resp.raise_for_status()
        with open(dest_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        return os.path.getsize(dest_path) > 1000  # 太小代表下載到錯誤頁面而非影片
    except Exception:
        return False


def _download_via_ytdlp(url: str, dest_path: str) -> bool:
    """適用YouTube/TikTok等平台網址。注意：YouTube有反爬機制，可能不定期失敗，
    需要偶爾更新 yt-dlp 版本（pip install -U yt-dlp）"""
    try:
        cmd = ["yt-dlp", "--no-check-certificate", "-f", "best[ext=mp4]/best",
               "-o", dest_path, url]
        result = subprocess.run(cmd, capture_output=True, timeout=180)
        return result.returncode == 0 and os.path.exists(dest_path)
    except Exception:
        return False


def extract_video_transcript(url: str) -> dict:
    """
    下載影片 -> 抽音訊 -> 語音轉文字，回傳 {'title', 'content', 'duration_seconds', 'method', 'model_used', 'truncated'}
    失敗會拋出例外，讓 main.py 的背景任務標記為 failed 並記錄原因
    """
    workdir = tempfile.mkdtemp(prefix="video_")
    try:
        video_path = os.path.join(workdir, "video.mp4")
        method = "direct"
        duration_hint = None

        ok = _download_direct(url, video_path)
        if not ok:
            method = "yt-dlp"
            duration_hint = _probe_duration_ytdlp(url)  # 下載前先偷看時長，決定策略
            ok = _download_via_ytdlp(url, video_path)
        if not ok:
            raise RuntimeError(
                "影片下載失敗：直接下載與yt-dlp都無法取得檔案。"
                "常見原因：該平台網址需要登入/是分享頁面而非直接影片檔、"
                "或該平台有反爬蟲機制擋下請求（YouTube常見）。"
            )

        if duration_hint is None:
            duration_hint = _ffprobe_duration(video_path)

        strategy = _choose_strategy(duration_hint)

        audio_path = os.path.join(workdir, "audio.wav")
        cmd = ["ffmpeg", "-y", "-i", video_path]
        if strategy["max_seconds"]:
            cmd += ["-t", str(strategy["max_seconds"])]
        cmd += ["-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
                audio_path, "-loglevel", "error"]
        result = subprocess.run(cmd, capture_output=True, timeout=180)
        if result.returncode != 0 or not os.path.exists(audio_path):
            raise RuntimeError(f"音訊抽取失敗，影片可能沒有音軌或格式不支援：{result.stderr.decode(errors='ignore')[:200]}")

        model = _get_whisper_model(strategy["model_size"])
        segments, info = model.transcribe(audio_path, vad_filter=True)
        text_parts = [seg.text.strip() for seg in segments]
        transcript = " ".join(text_parts).strip()

        if not transcript:
            raise RuntimeError("轉錄結果為空，影片可能沒有語音內容（純音樂/靜音/畫面型內容）")

        return {
            "title": "",
            "content": transcript,
            "duration_seconds": duration_hint,
            "method": method,
            "model_used": strategy["model_size"],
            "truncated": strategy["max_seconds"] is not None,
        }
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def extract_content(url: str) -> dict:
    """
    統一入口（給網頁/圖片用，同步處理，速度快）：回傳 {'title', 'content', 'url_type'}
    影片請改用 extract_video_transcript()，因為耗時較長，main.py會用背景任務呼叫
    """
    url_type = detect_url_type(url)

    if url_type == "video":
        return {"title": "", "content": "", "url_type": "video"}

    if url_type == "image":
        result = extract_image_text(url)
    else:
        result = extract_webpage_text(url)

    result["url_type"] = url_type
    return result
