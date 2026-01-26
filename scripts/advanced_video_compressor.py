import argparse
import subprocess
import json
import shutil
import sys
import time
from pathlib import Path
from datetime import datetime

FFPROBE = "ffprobe"
FFMPEG = "ffmpeg"


class VideoCompressionConfig:
    def __init__(self, directory, dry_run=False, threads=0, crf=29, preset="veryfast", 
                 profile="baseline", max_bitrate="800k", bufsize="1600k",
                 scale_width=854, scale_height=480):
        self.directory = Path(directory)
        self.dry_run = dry_run
        self.threads = threads
        self.crf = crf
        self.preset = preset
        self.profile = profile
        self.max_bitrate = max_bitrate
        self.bufsize = bufsize
        self.scale_width = scale_width
        self.scale_height = scale_height


def run_cmd(cmd, dry_run=False):
    if dry_run:
        print("DRY RUN:", " ".join(cmd))
        return None
    # Ensure all cmd parts are strings
    cmd = [str(c) for c in cmd]
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def get_metadata(video_path):
    cmd = [
        FFPROBE,
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries",
        "format=size,duration,bit_rate:stream=width,height",
        "-of", "json",
        str(video_path)
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed for {video_path}: {result.stderr.decode('utf-8')}")

    try:
        data = json.loads(result.stdout)
        fmt = data["format"]
        stream = data["streams"][0]

        size_mb = int(fmt["size"]) / (1024 * 1024)
        duration = float(fmt["duration"])
        bitrate = int(fmt.get("bit_rate", 0)) / 1000
        width = stream["width"]
        height = stream["height"]

        mb_per_min = size_mb / (duration / 60) if duration > 0 else 0

        return {
            "size_mb": size_mb,
            "duration": duration,
            "bitrate": bitrate,
            "width": width,
            "height": height,
            "mb_per_min": mb_per_min
        }
    except (KeyError, IndexError, ValueError, TypeError) as e:
         print(f"Skipping {video_path}: Could not extract metadata ({e})")
         return None


def is_candidate(meta, target_height=480):
    if not meta:
        return False
    
    # Logic simplified to ensure no videos are arbitrarily skipped unless they are already too small.
    # We skip videos strictly smaller than target_height because upscaling/reprocessing them suggests diminishing returns or quality loss.
    if meta["height"] < target_height:
        return False

    # Previous logic had heuristics (size > 50MB, mb_per_min > 15) which caused some videos to be skipped.
    # We now accept all candidates that meet the height requirement.
    return True


def build_ffmpeg_cmd(src, dst, args):
    # scale filter using -2 avoids odd-dimension errors (e.g. 853x480)
    scale_filter = f"scale=-2:{args.scale_height}"
    
    return [
        FFMPEG,
        "-y",
        "-i", str(src),
        "-map_metadata", "0",
        "-vf", scale_filter,
        "-c:v", "libx264",
        "-preset", args.preset,
        "-profile:v", args.profile,
        "-crf", str(args.crf),
        "-pix_fmt", "yuv420p",
        "-maxrate", args.max_bitrate,
        "-bufsize", args.bufsize,
        "-movflags", "+faststart",
        "-threads", str(args.threads),
        "-c:a", "aac",
        "-b:a", "128k",
        "-ac", "2",
        "-ar", "44100",
        str(dst)
    ]


def compress_video(src, root, args, log_func):
    meta = get_metadata(src)

    if not is_candidate(meta, args.scale_height):
        # log_func(f"Skipping {src.name} (Not a candidate: {meta['height']}p, {meta['size_mb']:.2f}MB)")
        return

    rel_path = src.relative_to(root)
    # Define output filename pattern
    # Determine extension based on source or enforce mp4
    dst = src.with_name(f"{src.stem}_{args.scale_height}p_compressed.mp4")

    start = time.time()
    cmd = build_ffmpeg_cmd(src, dst, args)
    result = run_cmd(cmd, args.dry_run)
    end = time.time()

    if not args.dry_run:
        # Check return code
        if result.returncode != 0:
            err_msg = result.stderr.decode('utf-8', errors='replace')
            log_func(f"ERROR: {rel_path} - Compression failed.\nSTDERR: {err_msg}\n")
            return

        if dst.exists() and dst.stat().st_size > 0:
            new_size = dst.stat().st_size / (1024 * 1024)
            ratio = meta["size_mb"] / new_size if new_size else 0
            log_func(
                f"{rel_path}\n"
                f"Original: {meta['size_mb']:.2f} MB | "
                f"Compressed: {new_size:.2f} MB | "
                f"Ratio: {ratio:.2f}x | "
                f"Time: {end - start:.1f}s\n"
            )
        else:
             log_func(f"ERROR: {rel_path} - Destination file not created or empty.\n")
    else:
        log_func(f"[DRY RUN] Would compress {rel_path} ({meta['size_mb']:.2f} MB)\n")


def process_videos(config, log_path=None):
    """
    Main entry point for external calls.
    config: VideoCompressionConfig object
    log_path: Path to log file (string or Path)
    """
    
    # If no log path, write to stdout/dummy
    if log_path:
        f = open(log_path, "w", encoding="utf-8")
        def log_func(msg):
            f.write(msg + "\n")
            f.flush()
    else:
        f = None
        def log_func(msg):
            print(msg.strip())

    try:
        root = config.directory
        videos = list(root.rglob("*.mp4")) + list(root.rglob("*.mkv")) + list(root.rglob("*.mov"))
        
        log_func(f"Starting compression in {root}")
        log_func(f"Found {len(videos)} potential video files.")
        log_func(f"Config: CRF={config.crf}, Preset={config.preset}, Resolution={config.scale_height}p")
        log_func("-" * 40)

        count = 0
        for video in videos:
            try:
                # Avoid re-processing already compressed files if they follow the naming convention
                if "_compressed" in video.name:
                    continue
                    
                compress_video(video, root, config, log_func)
                count += 1
            except Exception as e:
                log_func(f"FAILED: {video} | {e}")
        
        log_func("-" * 40)
        log_func(f"Completed. Processed {count} videos.")

    finally:
        if f:
            f.close()
    
    return count


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--threads", type=int, default=0)
    parser.add_argument("--crf", type=int, default=29)
    parser.add_argument("--preset", default="veryfast")
    parser.add_argument("--profile", default="baseline")
    parser.add_argument("--max-bitrate", default="800k")
    parser.add_argument("--bufsize", default="1600k")

    args = parser.parse_args()

    if not shutil.which(FFMPEG):
        sys.exit("FFmpeg not found")

    config = VideoCompressionConfig(
        directory=args.directory,
        dry_run=args.dry_run,
        threads=args.threads,
        crf=args.crf,
        preset=args.preset,
        profile=args.profile,
        max_bitrate=args.max_bitrate,
        bufsize=args.bufsize
    )

    # Auto-generate log file for standalone run
    log_name = f"compression_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    process_videos(config, log_path=log_name)


if __name__ == "__main__":
    main()
