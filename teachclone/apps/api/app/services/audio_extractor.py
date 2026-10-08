"""Audio extraction — YouTube/links via yt-dlp, video files via ffmpeg."""
import asyncio
import json
import logging
import os
import shutil
import sys
from pathlib import Path
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)


class YtDlpBotDetectionError(Exception):
    pass


def _yt_dlp_cmd() -> list[str]:
    """Prefer a ``yt-dlp`` executable on PATH, else run the installed module
    with the current interpreter so it works regardless of PATH / how the
    server was launched (the console script isn't always on PATH on Windows)."""
    exe = shutil.which("yt-dlp")
    return [exe] if exe else [sys.executable, "-m", "yt_dlp"]


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=30, max=180),
    retry=retry_if_exception_type(YtDlpBotDetectionError),
    reraise=True
)
async def download_youtube_audio(url: str, output_path: str) -> str:
    """Download YouTube audio with bot-detection retry."""
    import yt_dlp

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": output_path,
        "quiet": True,
        "no_warnings": True,
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
    }

    try:
        def _download():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

        await asyncio.to_thread(_download)
        return output_path
    except Exception as e:
        error_str = str(e).lower()
        if any(k in error_str for k in ["sign in", "bot", "429", "forbidden", "captcha"]):
            logger.warning(f"yt-dlp bot detection on {url}: {e}. Will retry.")
            raise YtDlpBotDetectionError(str(e))
        raise


class AudioExtractor:
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=30, max=180),
        retry=retry_if_exception_type(YtDlpBotDetectionError),
        reraise=True
    )
    async def from_youtube_url(self, url: str, output_dir: str) -> str:
        """Download a link's audio as WAV. Returns the .wav path."""
        template = os.path.join(output_dir, "%(id)s.%(ext)s")
        cmd = [
            *_yt_dlp_cmd(),
            "--format", "bestaudio/best",
            "--extract-audio", "--audio-format", "wav", "--audio-quality", "0",
            "--no-playlist", "--quiet", "--no-warnings",
            "--user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "--output", template, url,
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            err_msg = stderr.decode(errors="replace")
            err_lower = err_msg.lower()
            if any(k in err_lower for k in ["sign in", "bot", "429", "forbidden", "captcha"]):
                logger.warning(f"yt-dlp bot detection on {url}: {err_msg}. Will retry.")
                raise YtDlpBotDetectionError(err_msg)
            raise RuntimeError(f"yt-dlp failed: {err_msg[:500]}")
        wavs = list(Path(output_dir).glob("*.wav"))
        if not wavs:
            raise RuntimeError("No WAV output from yt-dlp")
        return str(wavs[0])

    async def from_video_file(self, input_path: str, output_dir: str) -> str:
        """Extract mono 16kHz WAV from a video/audio file via ffmpeg."""
        output_path = os.path.join(output_dir, "audio.wav")
        cmd = [
            "ffmpeg", "-i", input_path, "-vn",
            "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", "-y", output_path,
        ]
        proc = await asyncio.create_subprocess_exec(*cmd, stderr=asyncio.subprocess.PIPE)
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg failed: {stderr.decode()[:500]}")
        return output_path

    async def get_duration(self, file_path: str) -> float:
        cmd = [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_streams", file_path,
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await proc.communicate()
        try:
            data = json.loads(stdout)
            for stream in data.get("streams", []):
                if "duration" in stream:
                    return float(stream["duration"])
        except Exception:
            pass
        return 0.0


audio_extractor = AudioExtractor()
