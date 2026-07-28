"""
record_rtsp.py
==============
Script quay video liên tục từ một (hoặc nhiều) nguồn RTSP/HTTP/file,
sử dụng lại `shared.rtsp_manager.RTSPStream` để tận dụng auto-reconnect
và FPS cap có sẵn trong project. Video đầu ra được ghi dưới dạng MP4
(H.264 / yuv420p) — tương thích phát lại trên Windows Media Player,
trình duyệt và đa số phần mềm giám sát.

Cách dùng:
    # Quay 1 camera từ config mặc định
    python scripts/record_rtsp.py --camera-id machine_07

    # Quay 1 URL tùy ý
    python scripts/record_rtsp.py --url "rtsp://user:pass@10.0.7.47:554/Streaming/Channels/102"

    # Quay nhiều camera cùng lúc (đặt tên theo id trong config.yaml)
    python scripts/record_rtsp.py --camera-id machine_07 --camera-id machine_08

    # Ghi vào thư mục khác, mỗi segment 10 phút, tối đa ~500MB
    python scripts/record_rtsp.py --camera-id machine_07 \
        --output-dir D:/Videos/SOP \
        --segment-seconds 600 \
        --segment-max-mb 500

    # Ghi thử 30 giây rồi thoát (tiện cho CI/smoke-test)
    python scripts/record_rtsp.py --camera-id machine_07 --max-seconds 30
"""

from __future__ import annotations

import argparse
import logging
import os
import signal
import sys
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional

# Thêm project root vào sys.path để import được `shared.*`
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Giảm tải CPU tương tự main.py
import cv2  # noqa: E402

cv2.setNumThreads(0)
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

import imageio  # noqa: E402

from shared.rtsp_manager import RTSPStream  # noqa: E402
from shared.services.config_loader import ConfigLoader  # noqa: E402

logger = logging.getLogger("record_rtsp")


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def setup_logging(log_file: Optional[str]) -> None:
    """Cấu hình logging ra console + file."""
    handlers = [logging.StreamHandler(sys.stdout)]
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
    logging.basicConfig(level=logging.INFO, format=fmt, handlers=handlers, force=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def resolve_camera_config(camera_id: str) -> Dict:
    """Tìm cấu hình camera theo `id` trong `config.yaml`."""
    cfg = ConfigLoader.load_config() or {}
    for cam in cfg.get("cameras", []):
        if cam.get("id") == camera_id:
            return cam
    raise SystemExit(
        f"[record_rtsp] Không tìm thấy camera id='{camera_id}' trong config.yaml"
    )


def build_stream(camera_cfg: Dict, fps_cap: int, width: int, height: int) -> RTSPStream:
    """Tạo `RTSPStream` với các tham số đã chuẩn hóa."""
    return RTSPStream(
        camera_id=camera_cfg["id"],
        rtsp_url=camera_cfg["rtsp_url"],
        fps_cap=fps_cap,
        target_width=width,
        target_height=height,
    )


def make_writer(output_path: Path, fps: int, width: int, height: int):
    """Tạo imageio writer (libx264 ultrafast) cho 1 segment."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    return imageio.get_writer(
        str(output_path),
        fps=fps,
        codec="libx264",
        quality=None,
        ffmpeg_params=["-preset", "ultrafast", "-crf", "28"],
        pixelformat="yuv420p",
        macro_block_size=1,
        # Kích thước cố định giúp imageio set đúng size cho libx264
        # (tránh warning nếu frame đầu tiên chưa về)
    )


def open_new_segment(out_dir: Path, camera_id: str, fps: int, w: int, h: int):
    """Mở file segment mới (theo timestamp hiện tại)."""
    ts = time.strftime("%Y%m%d_%H%M%S", time.localtime())
    filename = f"{camera_id}_{ts}.mp4"
    path = out_dir / filename
    logger.info("[%s] New segment: %s", camera_id, path.name)
    return path, make_writer(path, fps, w, h)


# ---------------------------------------------------------------------------
# Recorder
# ---------------------------------------------------------------------------

class CameraRecorder:
    """Ghi liên tục từ 1 nguồn RTSP, tự rotate file theo thời gian/kích thước."""

    def __init__(
        self,
        camera_cfg: Dict,
        output_dir: Path,
        fps: int,
        width: int = 640,
        height: int = 480,
        segment_seconds: int = 600,        # 10 phút / segment
        segment_max_mb: float = 1024.0,    # ~1GB / segment
    ) -> None:
        self.cam_id = camera_cfg["id"]
        self.camera_cfg = camera_cfg
        self.output_dir = output_dir
        self.fps = fps
        self.width = width
        self.height = height
        self.segment_seconds = segment_seconds
        self.segment_max_bytes = int(segment_max_mb * 1024 * 1024)

        self.stream = build_stream(camera_cfg, fps, width, height)

        self._writer = None
        self._current_path: Optional[Path] = None
        self._segment_start_ts: float = 0.0
        self._frames_written: int = 0

        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

        # Thống kê
        self.total_frames = 0
        self.total_segments = 0

    # -- public ------------------------------------------------------------
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self.stream.start()
        self._thread = threading.Thread(target=self._run, name=f"Recorder-{self.cam_id}", daemon=True)
        self._thread.start()
        logger.info("[%s] Recorder started.", self.cam_id)

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
        self.stream.stop()
        self._close_writer()
        logger.info(
            "[%s] Recorder stopped. Total frames=%d, segments=%d",
            self.cam_id, self.total_frames, self.total_segments
        )

    # -- segment handling -------------------------------------------------
    def _maybe_rotate(self) -> None:
        """Rotate nếu quá segment_seconds HOẶC file vượt segment_max_bytes."""
        if self._writer is None:
            return
        elapsed = time.time() - self._segment_start_ts
        size = self._current_path.stat().st_size if self._current_path and self._current_path.exists() else 0
        if elapsed >= self.segment_seconds or size >= self.segment_max_bytes:
            logger.info(
                "[%s] Rotating segment (elapsed=%.1fs, size=%.1fMB)",
                self.cam_id, elapsed, size / (1024 * 1024)
            )
            self._close_writer()
            self.total_segments += 1

    def _close_writer(self) -> None:
        if self._writer is not None:
            try:
                self._writer.close()
            except Exception as e:  # pragma: no cover - defensive
                logger.warning("[%s] Writer close error: %s", self.cam_id, e)
            self._writer = None

    # -- main loop --------------------------------------------------------
    def _run(self) -> None:
        """Vòng lặp chính: đợi stream sẵn sàng → ghi frame → rotate khi cần."""
        # Chờ stream có frame đầu tiên (để biết kích thước thực tế)
        wait_start = time.time()
        while not self._stop_event.is_set():
            frame = self.stream.get_frame()
            if frame is not None:
                self.height, self.width = frame.shape[:2]
                break
            if time.time() - wait_start > 15:
                logger.warning("[%s] No frame from stream yet (waited 15s). Retrying...", self.cam_id)
                wait_start = time.time()
            time.sleep(0.1)

        if self._stop_event.is_set():
            return

        last_log = time.time()
        while not self._stop_event.is_set():
            self._maybe_rotate()

            frame = self.stream.get_frame()
            if frame is None:
                time.sleep(0.05)
                continue

            if self._writer is None:
                self._current_path, self._writer = open_new_segment(
                    self.output_dir, self.cam_id, self.fps, self.width, self.height
                )
                self._segment_start_ts = time.time()
                self._frames_written = 0

            try:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                self._writer.append_data(rgb)
                self._frames_written += 1
                self.total_frames += 1
            except Exception as e:
                logger.exception("[%s] Write frame error: %s", self.cam_id, e)
                self._close_writer()
                time.sleep(0.5)

            # Log trạng thái mỗi 10s
            now = time.time()
            if now - last_log >= 10:
                size_mb = (
                    self._current_path.stat().st_size / (1024 * 1024)
                    if self._current_path and self._current_path.exists() else 0.0
                )
                logger.info(
                    "[%s] frames=%d, segment_frames=%d, size=%.1fMB, elapsed=%.0fs",
                    self.cam_id, self.total_frames, self._frames_written, size_mb,
                    now - self._segment_start_ts
                )
                last_log = now


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Record RTSP stream(s) to MP4 continuously.")
    src = p.add_mutually_exclusive_group(required=False)
    src.add_argument(
        "--camera-id",
        action="append",
        help="ID camera trong config.yaml. Có thể truyền nhiều lần. Bỏ trống nếu dùng --url.",
    )
    src.add_argument(
        "--url",
        action="append",
        help="RTSP/HTTP/file URL trực tiếp. Có thể truyền nhiều lần.",
    )
    p.add_argument(
        "--output-dir",
        default=os.getenv("RECORDINGS_DIR", "data/recordings"),
        help="Thư mục lưu video (mặc định: data/recordings)",
    )
    p.add_argument("--fps", type=int, default=15, help="FPS ghi (mặc định: 15)")
    p.add_argument("--width", type=int, default=640, help="Chiều rộng (mặc định: 640)")
    p.add_argument("--height", type=int, default=480, help="Chiều cao (mặc định: 480)")
    p.add_argument("--segment-seconds", type=int, default=600, help="Thời gian tối đa / segment (giây)")
    p.add_argument("--segment-max-mb", type=float, default=1024.0, help="Dung lượng tối đa / segment (MB)")
    p.add_argument("--max-seconds", type=int, default=0, help="Dừng sau N giây (0 = chạy vô hạn)")
    p.add_argument(
        "--name",
        action="append",
        help="Tên hiển thị cho mỗi nguồn (khi dùng --url). Mặc định: stream_1, stream_2, ...",
    )
    p.add_argument("--log-file", default=None, help="File log (mặc định: chỉ in ra console)")
    return p.parse_args()


def collect_sources(args) -> List[Dict]:
    """Kết hợp --camera-id và --url thành danh sách camera_cfg-like dicts."""
    sources: List[Dict] = []
    if args.camera_id:
        for cid in args.camera_id:
            cfg = resolve_camera_config(cid)
            sources.append(cfg)
    if args.url:
        for idx, url in enumerate(args.url):
            name = (args.name[idx] if args.name and idx < len(args.name) else f"stream_{idx + 1}")
            sources.append({"id": name, "rtsp_url": url})
    if not sources:
        raise SystemExit("[record_rtsp] Cần truyền ít nhất một --camera-id hoặc --url.")
    return sources


def main() -> int:
    args = parse_args()
    setup_logging(args.log_file)

    sources = collect_sources(args)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    recorders: Dict[str, CameraRecorder] = {}
    for cfg in sources:
        rec = CameraRecorder(
            camera_cfg=cfg,
            output_dir=out_dir,
            fps=args.fps,
            width=args.width,
            height=args.height,
            segment_seconds=args.segment_seconds,
            segment_max_mb=args.segment_max_mb,
        )
        recorders[cfg["id"]] = rec
        rec.start()

    # Graceful shutdown: Ctrl+C
    def _shutdown(signum, frame):
        logger.info("Shutdown signal (%s) received. Stopping recorders...", signum)
        for rec in recorders.values():
            rec.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    logger.info("Recording %d source(s) into '%s'. Press Ctrl+C to stop.", len(sources), out_dir)

    if args.max_seconds and args.max_seconds > 0:
        # Chế độ chạy có thời hạn — phù hợp smoke-test
        deadline = time.time() + args.max_seconds
        try:
            while time.time() < deadline:
                time.sleep(0.5)
        except KeyboardInterrupt:
            pass
        finally:
            for rec in recorders.values():
                rec.stop()
    else:
        # Chế độ chạy vô hạn
        try:
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
