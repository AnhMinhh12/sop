"""
extract_frames.py
=================
Tách frame từ video MP4 thành ảnh JPG để gán nhãn cho training YOLO.

Mỗi lần chạy → 1 thư mục con theo `--class-name`, mỗi ảnh đặt tên theo
quy ước `img_<class>_NNNNNN.jpg` (6 chữ số, zero-pad) — tương thích với
`shared/tools/frame_extractor.py` và `projects/sop_monitoring/training/clean_dataset.py`.

Cách dùng:
    # Tách từ 1 video, mỗi 5 giây lấy 1 frame, lưu vào class "hand"
    python scripts/extract_frames.py --video data/recordings/12_20260728_143132_10min.mp4 --class-name hand

    # Tách nhiều video, mỗi video 1 class
    python scripts/extract_frames.py --video rec_hand.mp4 --video rec_sp.mp4 --class-name hand --class-name sp

    # Tách nhanh 50 frame đầu để test (10 giây @ 5s = 2 frame, nhưng max-frames ép)
    python scripts/extract_frames.py --video data/recordings/12_20260728_143132_10min.mp4 --class-name hand --max-frames 50

    # Không truyền gì → hỏi trên terminal
    python scripts/extract_frames.py
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import signal
import sys
import time
from pathlib import Path
from typing import List, Optional, Tuple

# Project root + env cho ConfigLoader (giống record_rtsp.py)
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

logger = logging.getLogger("extract_frames")


# ---------------------------------------------------------------------------
# Logging + helpers
# ---------------------------------------------------------------------------

def setup_logging(log_file: Optional[str]) -> None:
    handlers = [logging.StreamHandler(sys.stdout)]
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
    logging.basicConfig(level=logging.INFO, format=fmt, handlers=handlers, force=True)


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


def default_class_for(video_path: Path) -> str:
    """Lấy class từ tên file video: phần trước dấu '_' đầu tiên.

    vd: 12_20260728_143132_10min.mp4 → "12"
        machine_07_20260728_…mp4      → "machine_07"
    """
    stem = video_path.stem
    return stem.split("_", 1)[0] if "_" in stem else stem


def next_index(out_dir: Path, class_name: str) -> int:
    """Đếm file `img_<class>_NNNNNN.jpg` hiện có → trả về số bắt đầu kế tiếp (1-based)."""
    if not out_dir.exists():
        return 1
    pattern = re.compile(rf"^img_{re.escape(class_name)}_(\d{{6}})\.jpg$")
    max_n = 0
    for p in out_dir.iterdir():
        m = pattern.match(p.name)
        if m:
            max_n = max(max_n, int(m.group(1)))
    return max_n + 1


# ---------------------------------------------------------------------------
# Interactive discovery
# ---------------------------------------------------------------------------

def interactive_pick_videos() -> List[Path]:
    """Hỏi user đường dẫn video, hoặc quét data/recordings/*.mp4."""
    recordings = sorted((PROJECT_ROOT / "data" / "recordings").glob("*.mp4"))
    if recordings:
        names = [p.name for p in recordings]
        sys.stdout.write(f"  Tìm thấy {len(recordings)} video trong data/recordings/\n")
        for p in recordings:
            sys.stdout.write(f"    - {p.name}\n")
        sys.stdout.flush()
        kind = ask_choice(
            "Chọn cách nhập video",
            choices=["paste", "pick", "all"],
            default="paste",
        )
        if kind == "paste":
            while True:
                val = ask("  Đường dẫn video (Enter nhiều dòng, dòng trống để dừng)", default="")
                if not val:
                    return []
                p = Path(val.strip().strip('"'))
                if p.exists():
                    return [p]
                sys.stdout.write(f"  → Không thấy file: {p}\n")
                sys.stdout.flush()
        if kind == "pick":
            ans = ask_choice("  Chọn video", choices=names, default=names[0])
            return [PROJECT_ROOT / "data" / "recordings" / ans]
        # kind == "all"
        return recordings
    # Không có video nào
    while True:
        val = ask("Đường dẫn video (Enter nhiều dòng, dòng trống để dừng)", default="")
        if not val:
            return []
        p = Path(val.strip().strip('"'))
        if p.exists():
            return [p]
        sys.stdout.write(f"  → Không thấy file: {p}\n")
        sys.stdout.flush()


# ---------------------------------------------------------------------------
# Core: extract frames from 1 video
# ---------------------------------------------------------------------------

def extract(
    video_path: Path,
    out_dir: Path,
    class_name: str,
    interval_s: float,
    frame_step: int,
    max_frames: int,
    quality: int,
    resume: bool,
) -> int:
    """Tách frame từ `video_path` vào `out_dir`. Trả về số frame đã ghi."""
    if not video_path.exists():
        raise FileNotFoundError(f"Không tìm thấy video: {video_path}")

    out_dir.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        cap.release()
        raise RuntimeError(f"Không mở được video: {video_path}")

    fps = float(cap.get(cv2.CAP_PROP_FPS)) or 25.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration_s = total_frames / fps if fps > 0 else 0

    if frame_step > 0:
        frames_per_interval = frame_step
        desc_str = f"mỗi {frames_per_interval} frame lấy 1"
    else:
        if interval_s <= 0:
            cap.release()
            raise ValueError(f"--interval hoặc --frame-step phải lớn hơn 0")
        frames_per_interval = max(1, round(fps * interval_s))
        desc_str = f"interval={interval_s}s → mỗi {frames_per_interval} frame lấy 1"

    start_idx = next_index(out_dir, class_name) if resume else 1

    logger.info(
        "[%s] video=%s, fps=%.2f, total=%d frames (%.1fs). %s. start_idx=%d",
        class_name, video_path.name, fps, total_frames, duration_s,
        desc_str, start_idx,
    )

    # Cho phép Ctrl+C dừng gọn
    stop = {"flag": False}

    def _sigint(_sig, _frm):
        if stop["flag"]:
            sys.exit(1)
        stop["flag"] = True
        sys.stdout.write("\n  → Đang dừng…\n")
        sys.stdout.flush()

    prev = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, _sigint)

    written = 0
    idx = start_idx
    read_idx = 0
    last_log = time.time()
    encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), int(quality)]

    try:
        while True:
            if stop["flag"]:
                break
            if max_frames > 0 and written >= max_frames:
                break

            ok, frame = cap.read()
            if not ok or frame is None:
                break

            should_save = (read_idx % frames_per_interval == 0)
            if should_save:
                filename = f"img_{class_name}_{idx:06d}.jpg"
                out_path = out_dir / filename
                if cv2.imwrite(str(out_path), frame, encode_params):
                    written += 1
                    idx += 1

            read_idx += 1

            # Log mỗi ~2s hoặc mỗi 50 frame đã ghi
            now = time.time()
            if written > 0 and (now - last_log >= 2.0 or written % 50 == 0):
                pos_s = read_idx / fps if fps > 0 else 0
                logger.info(
                    "[%s] written=%d, pos=%.1fs/%.1fs (%.0f%%)",
                    class_name, written, pos_s, duration_s,
                    (pos_s / duration_s * 100) if duration_s > 0 else 0,
                )
                last_log = now
    finally:
        cap.release()
        signal.signal(signal.SIGINT, prev)

    logger.info(
        "[%s] Wrote %d frame(s) to %s",
        class_name, written, out_dir,
    )
    return written


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Extract frames from video(s) for YOLO labeling.",
    )
    p.add_argument(
        "--video", action="append", default=[],
        help="Đường dẫn video MP4 (lặp lại được cho nhiều video).",
    )
    p.add_argument(
        "--output-dir",
        default=os.getenv(
            "EXTRACT_FRAMES_DIR",
            str(PROJECT_ROOT / "data" / "training_collection" / "extracted_data"),
        ),
        help="Thư mục gốc lưu frame (mặc định: <project_root>/data/training_collection/extracted_data).",
    )
    p.add_argument(
        "--class-name", dest="class_name", action="append", default=[],
        help="Tên class (cũng là tên thư mục con). Lặp lại được; mặc định lấy từ tên video.",
    )
    p.add_argument(
        "--interval", type=float, default=5.0,
        help="Lấy 1 frame mỗi N giây (mặc định: 5).",
    )
    p.add_argument(
        "--frame-step", type=int, default=0,
        help="Lấy 1 frame mỗi N frame (mặc định: 0, ưu tiên hơn --interval nếu > 0).",
    )
    p.add_argument(
        "--max-frames", type=int, default=0,
        help="Giới hạn số frame xuất / video (0 = không giới hạn).",
    )
    p.add_argument(
        "--quality", type=int, default=90, choices=range(1, 101), metavar="N",
        help="JPG quality 1-100 (mặc định: 90).",
    )
    p.add_argument(
        "--resume", dest="resume", action="store_true", default=True,
        help="(Mặc định) Tiếp tục đếm số nếu thư mục đã có frame.",
    )
    p.add_argument(
        "--no-resume", dest="resume", action="store_false",
        help="Tắt resume — ghi đè đếm từ 000001.",
    )
    p.add_argument(
        "--no-prompt", action="store_true",
        help="Tắt hỏi tương tác trên terminal (dùng khi chạy từ script/CI).",
    )
    p.add_argument("--log-file", default=None, help="File log.")
    return p.parse_args()


def pair_videos_and_classes(
    videos: List[Path], classes: List[str]
) -> List[Tuple[Path, str]]:
    """Ghép video với class. Nếu số lượng không khớp thì class cuối dùng cho phần còn lại."""
    if not videos:
        return []
    pairs: List[Tuple[Path, str]] = []
    for i, v in enumerate(videos):
        if i < len(classes) and classes[i]:
            cls = classes[i]
        elif classes:
            cls = classes[-1]
        else:
            # Tên thư mục lưu ảnh giống tên file video + _pic
            cls = f"{v.stem}_pic"
        pairs.append((v, cls))
    return pairs


def main() -> int:
    args = parse_args()
    setup_logging(args.log_file)

    # TTY + chưa có --video và chưa --no-prompt → hỏi
    videos = [Path(v) for v in args.video]
    if not args.no_prompt and _isatty():
        if not videos:
            sys.stdout.write("\n=== Tách frame để gán nhãn ===\n")
            sys.stdout.flush()
            picked = interactive_pick_videos()
            videos = picked
            if not videos:
                sys.stdout.write("Không có video nào. Thoát.\n")
                return 1

        # Hỏi khoảng cách tách ảnh
        sys.stdout.write("\n=== Cấu hình khoảng cách tách ảnh ===\n")
        sys.stdout.flush()
        mode = ask_choice("Chọn đơn vị khoảng cách", choices=["giay", "frame"], default="giay")
        if mode == "giay":
            ans = ask("Nhập số giây giữa các frame", default="5.0")
            try:
                args.interval = float(ans)
                args.frame_step = 0
            except ValueError:
                sys.stdout.write("  → Giá trị không hợp lệ. Sử dụng mặc định 5.0 giây.\n")
                args.interval = 5.0
                args.frame_step = 0
        else:
            ans = ask("Nhập số frame giữa các ảnh", default="100")
            try:
                args.frame_step = int(ans)
                args.interval = 0.0
            except ValueError:
                sys.stdout.write("  → Giá trị không hợp lệ. Sử dụng mặc định 100 frame.\n")
                args.frame_step = 100
                args.interval = 0.0

    if not videos:
        raise SystemExit("[extract_frames] Cần ít nhất một --video.")

    out_root = Path(args.output_dir)
    out_root.mkdir(parents=True, exist_ok=True)

    pairs = pair_videos_and_classes(videos, args.class_name)

    logger.info(
        "Extract %d video(s) → %s (interval=%ss, frame_step=%d, max-frames=%d, resume=%s)",
        len(pairs), out_root, args.interval, args.frame_step, args.max_frames, args.resume,
    )

    total = 0
    for v, cls in pairs:
        out_dir = out_root / cls
        try:
            n = extract(
                video_path=v,
                out_dir=out_dir,
                class_name=cls,
                interval_s=args.interval,
                frame_step=args.frame_step,
                max_frames=args.max_frames,
                quality=args.quality,
                resume=args.resume,
            )
        except (FileNotFoundError, RuntimeError, ValueError) as e:
            logger.error("[%s] %s", cls, e)
            continue
        total += n

    logger.info("=== Done. Tổng %d frame được ghi ===", total)
    if total > 0:
        logger.info(
            "Để gán nhãn YOLO, mỗi ảnh cần file .txt cùng tên, format:\n"
            "  <class_id> <cx> <cy> <w> <h>   (chuẩn hóa 0..1)",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())