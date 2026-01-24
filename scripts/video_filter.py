import os
import shutil
import asyncio
import concurrent.futures
import subprocess
import json
from pathlib import Path

def get_video_metadata(video_path):
    """
    Extracts metadata using ffprobe.
    Returns a dict with duration, total_bitrate (kbps), audio_bitrate (kbps), and size (MB).
    """
    try:
        cmd = [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_format", "-show_streams", video_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        data = json.loads(result.stdout)
        
        format_info = data.get("format", {})
        metadata = {
            "duration": float(format_info.get("duration", 0)),
            "total_bitrate": int(format_info.get("bit_rate", 0)) / 1000, # to kbps
            "audio_bitrate": 0,
            "file_size_mb": os.path.getsize(video_path) / (1024 * 1024)
        }
        
        for stream in data.get("streams", []):
            if stream.get("codec_type") == "audio":
                a_bitrate = int(stream.get("bit_rate", 0))
                if a_bitrate > 0:
                    metadata["audio_bitrate"] = a_bitrate / 1000 # to kbps
                break # Usually take first audio stream

        return metadata
    except Exception as e:
        return None

def filter_and_move(video_path, destination_folder, dry_run, log_lines):
    metadata = get_video_metadata(video_path)
    if not metadata:
        log_lines.append(f"[Error] Could not extract metadata: {video_path}")
        return "error"

    duration_s = metadata["duration"]
    file_size_mb = metadata["file_size_mb"]
    total_bitrate = metadata["total_bitrate"]
    audio_bitrate = metadata["audio_bitrate"]
    
    # Computations
    duration_m = duration_s / 60 if duration_s > 0 else 0
    mb_per_minute = file_size_mb / duration_m if duration_m > 0 else 0
    estimated_video_bitrate = total_bitrate - audio_bitrate

    # Classification Criteria (ANY)
    # 1. duration < 360 seconds AND MB_per_minute > 18
    # 2. duration < 360 seconds AND estimated_video_bitrate > 2500 kbps
    # 3. duration < 420 seconds AND file_size_MB > 100
    
    reasons = []
    if duration_s < 360 and mb_per_minute > 18:
        reasons.append(f"Short & Dense (Dur < 360s & {mb_per_minute:.2f} MB/min > 18)")
    if duration_s < 360 and estimated_video_bitrate > 2500:
        reasons.append(f"High Bitrate (Dur < 360s & {estimated_video_bitrate:.0f} kbps > 2500)")
    if duration_s < 420 and file_size_mb > 100:
        reasons.append(f"Large Short Video (Dur < 420s & {file_size_mb:.1f} MB > 100)")
    
    match = len(reasons) > 0

    if match:
        filename = Path(video_path).name
        log_lines.append(f"[MATCH] {filename}")
        log_lines.append(f"  Path: {video_path}")
        log_lines.append(f"  Duration: {duration_s:.1f}s ({duration_m:.2f}m)")
        log_lines.append(f"  Size: {file_size_mb:.2f} MB")
        log_lines.append(f"  MB/min: {mb_per_minute:.2f}")
        log_lines.append(f"  Est. Video Bitrate: {estimated_video_bitrate:.0f} kbps")
        log_lines.append(f"  Reasons: {' | '.join(reasons)}")
        
        try:
            destination_path = Path(destination_folder) / filename
            if Path(video_path).parent == Path(destination_folder):
                log_lines.append(f"  [Skipped] Already in target folder.")
                return "skipped"

            if dry_run:
                log_lines.append(f"  [Dry Run] Would move to: {destination_path}")
                return "dry_run"

            shutil.move(video_path, destination_path)
            log_lines.append(f"  [Moved] Successfully.")
            return "moved"
        except Exception as e:
            log_lines.append(f"  [Error] Moving failed: {e}")
            return "error"
    else:
        return "skipped"

async def run_video_filtering(source_folder, dry_run=False, log_path=None):
    current_folder_name = os.path.basename(source_folder.rstrip(os.sep))
    destination_folder = os.path.join(source_folder, f"hd_vids_{current_folder_name}")

    os.makedirs(destination_folder, exist_ok=True)

    extensions = ("*.mp4", "*.mkv", "*.avi", "*.mov", "*.flv", "*.wmv")
    video_files = []
    for ext in extensions:
        video_files.extend([str(file) for file in Path(source_folder).rglob(ext)])
        
    log_lines = []
    log_lines.append(f"Video Filtering Report - {source_folder}")
    log_lines.append("-" * 50)

    if not video_files:
        log_lines.append("No video files found.")
    
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)
    loop = asyncio.get_running_loop()

    tasks = [
        loop.run_in_executor(executor, filter_and_move, video, destination_folder, dry_run, log_lines)
        for video in video_files
    ]
    results = await asyncio.gather(*tasks)
    executor.shutdown()

    moved_count = results.count("moved")
    skipped_count = results.count("skipped")
    error_count = results.count("error")
    dry_run_count = results.count("dry_run")

    log_lines.append(f"\nSummary:")
    log_lines.append(f"Total matched & moved: {moved_count}")
    if dry_run:
        log_lines.append(f"Total would-be moved (Dry Run): {dry_run_count}")
    log_lines.append(f"Total skipped: {skipped_count}")
    log_lines.append(f"Total errors: {error_count}")

    if log_path:
        with open(log_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(log_lines))
    
    return {
        "moved_total": moved_count if not dry_run else dry_run_count,
        "skipped_total": skipped_count
    }
