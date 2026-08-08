"""
record_rtsp.py
==============
Quay 1 (hoặc nhiều) nguồn RTSP/HTTP, mỗi lần quay ra 1 file MP4 duy nhất.
- Lấy fps + độ phân giải thực tế từ chính camera (không ép fps).
- Chất lượng H.264 chỉnh bằng --crf (mặc định 23, giống x264 mặc định).
- Tự dừng sau --duration; không truyền → chạy tới khi bấm Ctrl+C.

Cách dùng:
    python scripts/record_rtsp.py --url "rtsp://admin:Htmp%402019@10.0.7.47:554/Streaming/Channels/101"
    python scripts/record_rtsp.py --camera-id machine_07 --duration 5min
    python scripts/record_rtsp.py --url "rtsp://..." --output-dir D:/Videos --crf 18
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import signal
import sys
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional

# Project root + env cho ConfigLoader
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault("CONFIG_PATH", str(PROJECT_ROOT / "config" / "config.yaml"))
os.environ.setdefault("SOP_DEFINITIONS_DIR", str(PROJECT_ROOT / "config" / "sop_definitions"))

# Hạn chế CPU
import cv2  # noqa: E402

cv2.setNumThreads(0)
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

import imageio  # noqa: E402

from shared.rtsp_manager import RTSPStream  # noqa: E402
from shared.services.config_loader import ConfigLoader  # noqa: E402

logger = logging.getLogger("record_rtsp")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def setup_logging(log_file: Optional[str]) -> None:
    handlers = [logging.StreamHandler(sys.stdout)]
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
    logging.basicConfig(level=logging.INFO, format=fmt, handlers=handlers, force=True)


def parse_duration(value: str) -> int:
    """'30s' | '5min' | '2h' | '1d' → giây. Số nguyên → giây."""
    s = str(value).strip().lower()
    if not s:
        raise argparse.ArgumentTypeError("duration rỗng")
    if s.isdigit():
        return int(s)
    m = re.match(r"^(\d+(?:\.\d+)?)\s*([a-z]+)$", s)
    if not m:
        raise argparse.ArgumentTypeError(f"duration không hợp lệ: '{value}' (vd: 30s, 5min, 2h, 1d)")
    n = float(m.group(1))
    mult = {
        "s": 1, "sec": 1, "secs": 1, "second": 1, "seconds": 1,
        "m": 60, "min": 60, "mins": 60, "minute": 60, "minutes": 60,
        "h": 3600, "hr": 3600, "hour": 3600, "hours": 3600,
        "d": 86400, "day": 86400, "days": 86400,
    }
    unit = m.group(2)
    if unit not in mult:
        raise argparse.ArgumentTypeError(f"đơn vị không hợp lệ: '{unit}' (dùng s/min/h/d)")
    return int(n * mult[unit])


def human_duration(secs: int) -> str:
    return f"{secs // 60}min" if secs >= 60 else f"{secs}s"


# ---------------------------------------------------------------------------
# Interactive prompt
# ---------------------------------------------------------------------------

def _isatty() -> bool:
    try:
        return sys.stdin.isatty()
    except Exception:
        return False


def ask(question: str, default: Optional[str] = None) -> str:
    suffix = f" [{default}]" if default is not None else ""
    sys.stdout.write(f"{question}{suffix}: ")
    sys.stdout.flush()
    try:
        line = input().strip()
    except EOFError:
        line = ""
    return line if line else (default or "")


def ask_choice(question: str, choices: List[str], default: Optional[str] = None) -> str:
    default = default if default in choices else (choices[0] if choices else None)
    while True:
        rendered = "/".join(f"[{c}]" if c == default else c for c in choices)
        ans = ask(f"{question} ({rendered})", default=default)
        if ans in choices:
            return ans
        sys.stdout.write(f"  → Vui lòng chọn một trong: {choices}\n")
        sys.stdout.flush()


def interactive_setup(args) -> None:
    """Hỏi nguồn / thư mục / thời lượng / tên / crf khi user chưa truyền flag."""
    if args.no_prompt:
        return
    if not _isatty():
        return

    args.camera_id = args.camera_id or []
    args.url = args.url or []
    args.name = args.name or []

    sys.stdout.write("\n=== Thiết lập nhanh (Enter = mặc định) ===\n")

    # 1) Nguồn
    if not args.camera_id and not args.url:
        while True:
            kind = ask_choice(
                "Loại nguồn (Enter để bỏ qua nếu không cần)",
                choices=["url", "camera-id", "stop"],
                default="stop",
            )
            if kind == "stop":
                if not args.camera_id and not args.url:
                    sys.stdout.write("  → Chưa có nguồn nào. Thử lại.\n")
                    sys.stdout.flush()
                    continue
                break
            if kind == "url":
                val = ask("  Nhập RTSP/HTTP URL", default="")
                if val:
                    args.url.append(val)
                    sys.stdout.write(f"  → Đã thêm URL: {val}\n")
            else:
                cfg = ConfigLoader.load_config() or {}
                ids = [c.get("id", "") for c in cfg.get("cameras", []) if c.get("id")]
                if ids:
                    shown = ", ".join(ids[:5]) + ("…" if len(ids) > 5 else "")
                    sys.stdout.write(f"  Camera IDs: {shown}\n")
                val = ask("  Nhập camera-id", default="")
                if val:
                    args.camera_id.append(val)
            sys.stdout.flush()
            # Hỏi thêm nguồn
            again = ask_choice("  Thêm nguồn nữa?", choices=["stop", "url", "camera-id"], default="stop")
            if again == "stop":
                break
            # hack: đẩy lại vòng lặp bằng cách set kind
            if again == "url":
                val = ask("  Nhập RTSP/HTTP URL", default="")
                if val:
                    args.url.append(val)
            else:
                val = ask("  Nhập camera-id", default="")
                if val:
                    args.camera_id.append(val)
            sys.stdout.flush()

    # 2) Thư mục
    if args.output_dir_was_default:
        val = ask("Thư mục lưu video", default=args.output_dir)
        if val:
            args.output_dir = val

    # 3) Thời lượng
    while True:
        raw = ask("Thời lượng quay (vd 30s, 5min, 2h, 1d) — Enter = vô hạn", default="")
        if not raw:
            args.duration = None
            break
        try:
            args.duration = parse_duration(raw)
            break
        except argparse.ArgumentTypeError as e:
            sys.stdout.write(f"  → {e}\n")
            sys.stdout.flush()

    # 4) crf
    raw_crf = ask("Chất lượng H.264 (crf 0-51, 0=nét nhất, mặc định 23)", default=str(args.crf))
    try:
        if raw_crf:
            args.crf = max(0, min(51, int(raw_crf)))
    except ValueError:
        sys.stdout.write("  → crf không hợp lệ, dùng mặc định 23\n")

    # 5) Tên video
    if args.name:
        default_name = args.name[0]
    elif args.camera_id:
        default_name = args.camera_id[0]
    elif args.url:
        default_name = args.url[0].rsplit("/", 1)[-1] or "recording"
    else:
        default_name = "recording"

    val = ask("Tên video (không cần .mp4)", default=default_name)
    if val:
        args.name = [val]
    sys.stdout.write("=============================================\n\n")


# ---------------------------------------------------------------------------
# Nguồn + writer
# ---------------------------------------------------------------------------

def resolve_camera_config(camera_id: str) -> Dict:
    cfg = ConfigLoader.load_config() or {}
    for cam in cfg.get("cameras", []):
        if cam.get("id") == camera_id:
            return cam
    raise SystemExit(f"[record_rtsp] Không tìm thấy camera id='{camera_id}' trong config.yaml")


def make_writer(output_path: Path, fps: float, width: int, height: int, crf: int):
    # width/height hiện không được dùng (imageio tự suy từ frame đầu), nhưng
    # vẫn khai báo để caller đọc code thấy ngay output size.
    del width, height
    output_path.parent.mkdir(parents=True, exist_ok=True)
    return imageio.get_writer(
        str(output_path),
        fps=fps,
        codec="libx264",
        quality=None,
        ffmpeg_params=["-preset", "veryfast", "-crf", str(crf)],
        pixelformat="yuv420p",
        macro_block_size=1,
    )


# ---------------------------------------------------------------------------
# Recorder
# ---------------------------------------------------------------------------

class CameraRecorder:
    """Quay 1 nguồn → 1 file MP4 duy nhất, fps + size lấy từ camera."""

    def __init__(
        self,
        camera_cfg: Dict,
        output_path: Path,
        crf: int,
        duration_seconds: Optional[int],
    ) -> None:
        self.cam_id = camera_cfg["id"]
        self.output_path = output_path
        self.crf = crf
        self.duration_seconds = duration_seconds

        # fps_cap đặt rất cao để RTSPStream không throttle — ta sẽ lấy fps
        # thực từ cap và pacing theo wall-clock sau.
        self.stream = RTSPStream(
            camera_id=self.cam_id,
            rtsp_url=camera_cfg["rtsp_url"],
            fps_cap=60,
            target_width=camera_cfg.get("target_width", 1280),
            target_height=camera_cfg.get("target_height", 720),
        )

        self.fps: float = 25.0
        self.width: int = 1280
        self.height: int = 720

        self._writer = None
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.total_frames = 0

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self.stream.start()
        self._thread = threading.Thread(target=self._run, name=f"Recorder-{self.cam_id}", daemon=True)
        self._thread.start()
        logger.info("[%s] Recorder started. → %s", self.cam_id, self.output_path.name)

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
        self.stream.stop()
        self._close_writer()
        logger.info("[%s] Recorder stopped. Total frames=%d", self.cam_id, self.total_frames)

    def _close_writer(self) -> None:
        if self._writer is not None:
            try:
                self._writer.close()
            except Exception as e:
                logger.warning("[%s] Writer close error: %s", self.cam_id, e)
            self._writer = None

    def _run(self) -> None:
        # Đợi frame đầu tiên để biết fps + size thực
        wait_start = time.time()
        while not self._stop_event.is_set():
            frame = self.stream.get_frame()
            if frame is not None:
                # Cố lấy fps + size từ OpenCV nếu RTSPStream có giữ cap
                if getattr(self.stream, "cap", None) is not None:
                    try:
                        cap = self.stream.cap
                        f = cap.get(cv2.CAP_PROP_FPS)
                        if f and f > 0:
                            self.fps = float(f)
                        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                        if w > 0 and h > 0:
                            self.width, self.height = w, h
                    except Exception:
                        pass
                # Fallback: lấy size từ frame
                self.height, self.width = frame.shape[:2]
                break
            if time.time() - wait_start > 15:
                logger.warning("[%s] No frame from stream yet (15s). Retrying...", self.cam_id)
                wait_start = time.time()
            time.sleep(0.1)

        if self._stop_event.is_set():
            return

        # Mở writer
        self._writer = make_writer(self.output_path, self.fps, self.width, self.height, self.crf)
        logger.info("[%s] Writing: fps=%.2f, size=%dx%d, crf=%d",
                    self.cam_id, self.fps, self.width, self.height, self.crf)

        frame_period = 1.0 / max(self.fps, 1.0)
        next_due = time.time()
        deadline = time.time() + self.duration_seconds if self.duration_seconds else None
        last_log = time.time()

        while not self._stop_event.is_set():
            if deadline and time.time() >= deadline:
                logger.info("[%s] Reached duration, stopping.", self.cam_id)
                break

            now = time.time()
            if now < next_due:
                time.sleep(min(0.05, next_due - now))
                continue
            if next_due < now - frame_period * 2:
                next_due = now  # chống burst nếu loop bị stall
            next_due += frame_period

            frame = self.stream.get_frame()
            if frame is None:
                continue

            try:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                self._writer.append_data(rgb)
                self.total_frames += 1
            except Exception as e:
                logger.exception("[%s] Write frame error: %s", self.cam_id, e)
                self._close_writer()
                time.sleep(0.5)
                return

            if now - last_log >= 10:
                size_mb = self.output_path.stat().st_size / (1024 * 1024) if self.output_path.exists() else 0
                logger.info("[%s] frames=%d, size=%.1fMB",
                            self.cam_id, self.total_frames, size_mb)
                last_log = now


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Record RTSP to a single MP4 file.")
    src = p.add_mutually_exclusive_group(required=False)
    src.add_argument("--camera-id", action="append", help="Camera id từ config.yaml (lặp lại được).")
    src.add_argument("--url", action="append", help="RTSP/HTTP URL (lặp lại được).")
    p.add_argument(
        "--output-dir",
        default=os.getenv("RECORDINGS_DIR", str(PROJECT_ROOT / "data" / "recordings")),
        help="Thư mục lưu video (mặc định: <project_root>/data/recordings).",
    )
    p.add_argument("--no-prompt", action="store_true", help="Tắt hỏi tương tác.")
    p.add_argument(
        "--duration", type=parse_duration, default=None,
        help="Thời gian quay tối đa (vd: 30s, 5min, 2h). Mặc định: chạy tới Ctrl+C.",
    )
    p.add_argument(
        "--crf", type=int, default=23,
        help="Chất lượng H.264 (0-51, 0=nét nhất, mặc định 23).",
    )
    p.add_argument("--name", action="append", help="Tên file (không cần .mp4).")
    p.add_argument("--log-file", default=None, help="File log.")
    return p.parse_args()


def collect_sources(args) -> List[Dict]:
    sources: List[Dict] = []
    if args.camera_id:
        for cid in args.camera_id:
            sources.append(resolve_camera_config(cid))
    if args.url:
        for idx, url in enumerate(args.url):
            name = (args.name[idx] if args.name and idx < len(args.name) else f"stream_{idx + 1}")
            sources.append({"id": name, "rtsp_url": url})
    if not sources:
        raise SystemExit("[record_rtsp] Cần truyền ít nhất một --camera-id hoặc --url.")
    return sources


def build_output_path(out_dir: Path, source: Dict, suffix: str = "") -> Path:
    ts = time.strftime("%Y%m%d_%H%M%S", time.localtime())
    return out_dir / f"{source['id']}_{ts}{suffix}.mp4"


def main() -> int:
    raw_argv = sys.argv[1:]
    args = parse_args()
    setup_logging(args.log_file)

    args.output_dir_was_default = not any(
        a == "--output-dir" or a.startswith("--output-dir=") for a in raw_argv
    )
    interactive_setup(args)

    sources = collect_sources(args)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    recorders: Dict[str, CameraRecorder] = {}
    for cfg in sources:
        suffix = f"_{human_duration(args.duration)}" if args.duration else ""
        out_path = build_output_path(out_dir, cfg, suffix=suffix)
        rec = CameraRecorder(
            camera_cfg=cfg,
            output_path=out_path,
            crf=args.crf,
            duration_seconds=args.duration,
        )
        recorders[cfg["id"]] = rec
        rec.start()

    def _shutdown(signum, frame):
        logger.info("Shutdown signal (%s). Stopping recorders...", signum)
        for rec in recorders.values():
            rec.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    logger.info("Recording %d source(s) into '%s'. Ctrl+C to stop.", len(sources), out_dir)

    # Đợi: nếu có duration thì đợi tới deadline / Ctrl+C; nếu không thì chờ Ctrl+C
    try:
        if args.duration:
            deadline = time.time() + args.duration
            while time.time() < deadline:
                time.sleep(0.5)
            for rec in recorders.values():
                rec.stop()
            logger.info("Đã quay đủ %s. Kết thúc.", human_duration(args.duration))
        else:
            while True:
                time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        for rec in recorders.values():
            rec.stop()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())