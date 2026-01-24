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
    Returns a dict with duration, width, height, frame_rate, video_bitrate, audio_bitrate, size.
    """
    try:
        cmd = [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_format", "-show_streams", video_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        data = json.loads(result.stdout)
        
        metadata = {
            "duration": 0,
            "width": 0,
            "height": 0,
            "frame_rate": 0,
            "video_bitrate": 0,
            "audio_bitrate": 0,
            "size": os.path.getsize(video_path)
        }
        
        # Format info
        format_info = data.get("format", {})
        metadata["duration"] = float(format_info.get("duration", 0))
        
        # Streams info
        for stream in data.get("streams", []):
            codec_type = stream.get("codec_type")
            if codec_type == "video":
                metadata["width"] = int(stream.get("width", 0))
                metadata["height"] = int(stream.get("height", 0))
                
                # Bitrate - sometimes in stream, sometimes in format
                v_bitrate = int(stream.get("bit_rate", 0))
                if v_bitrate > 0:
                    metadata["video_bitrate"] = v_bitrate / 1000 # to kbps
                
                # Frame rate (e.g., "30/1" or "24000/1001")
                avg_frame_rate = stream.get("avg_frame_rate", "0/0")
                if "/" in avg_frame_rate:
                    num, den = map(int, avg_frame_rate.split("/"))
                    if den != 0:
                        metadata["frame_rate"] = num / den
                        
            elif codec_type == "audio":
                a_bitrate = int(stream.get("bit_rate", 0))
                if a_bitrate > 0:
                    metadata["audio_bitrate"] = a_bitrate / 1000 # to kbps

        # Fallback for video bitrate if stream doesn't have it
        if metadata["video_bitrate"] == 0:
            total_bitrate = int(format_info.get("bit_rate", 0)) / 1000
            if total_bitrate > metadata["audio_bitrate"]:
                metadata["video_bitrate"] = total_bitrate - metadata["audio_bitrate"]
            else:
                metadata["video_bitrate"] = total_bitrate

        return metadata
    except Exception as e:
        return None

def analyze_and_move(video_path, destination_folder, dry_run, log_lines):
    metadata = get_video_metadata(video_path)
    if not metadata:
        log_lines.append(f"[Error] Could not extract metadata: {video_path}")
        return "error"

    duration = metadata["duration"]
    width = metadata["width"]
    height = metadata["height"]
    fps = metadata["frame_rate"]
    v_bitrate = metadata["video_bitrate"]
    a_bitrate = metadata["audio_bitrate"]
    size_bytes = metadata["size"]
    
    total_pixels = width * height
    
    # Bits per pixel per second
    # Formula: video_bitrate (bps) / (width * height * frame_rate)
    # v_bitrate is in kbps, so convert to bps
    bppps = 0
    if total_pixels > 0 and fps > 0:
        bppps = (v_bitrate * 1000) / (total_pixels * fps)

    # Classification Criteria
    # - duration < 180 seconds
    # - video_bitrate > 4000 kbps
    # - (total pixels > 900,000 OR bppps > 0.08)
    
    is_short = duration < 180
    is_high_bitrate = v_bitrate > 4000
    is_high_res_or_density = (total_pixels > 900000) or (bppps > 0.08)
    
    match = is_short and is_high_bitrate and is_high_res_or_density
    
    metrics_str = (
        f"Dur: {duration:.1f}s, Res: {width}x{height}, Bitrate: {v_bitrate:.0f}kbps, "
        f"FPS: {fps:.2f}, Pixels: {total_pixels}, BPPPS: {bppps:.4f}, Size: {size_bytes / (1024*1024):.1f}MB"
    )

    if match:
        reason = []
        if total_pixels > 900000: reason.append("High Resolution (>900k px)")
        if bppps > 0.08: reason.append("High Bit Density (>0.08 bppps)")
        reason_str = " + ".join(reason)
        
        log_lines.append(f"[MATCH] {video_path}")
        log_lines.append(f"  Reason: {reason_str}")
        log_lines.append(f"  Metrics: {metrics_str}")
        
        try:
            destination_path = Path(destination_folder) / Path(video_path).name
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
        # log_lines.append(f"[Ignored] {video_path} - {metrics_str}")
        return "skipped"

async def analyze_video_directory(source_folder, dry_run=False, log_path=None):
    current_folder_name = os.path.basename(source_folder.rstrip(os.sep))
    destination_folder = os.path.join(source_folder, f"hd_vids_{current_folder_name}")

    os.makedirs(destination_folder, exist_ok=True)

    extensions = ("*.mp4", "*.mkv", "*.avi", "*.mov", "*.flv", "*.wmv")
    video_files = []
    for ext in extensions:
        video_files.extend([str(file) for file in Path(source_folder).rglob(ext)])
        
    log_lines = []
    log_lines.append(f"Video Analysis Report - {source_folder}")
    log_lines.append(f"Criteria: Duration < 180s AND Bitrate > 4000kbps AND (Pixels > 900k OR BPPPS > 0.08)\n")

    if not video_files:
        log_lines.append("No video files found.")
    
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)
    loop = asyncio.get_running_loop()

    tasks = [
        loop.run_in_executor(executor, analyze_and_move, video, destination_folder, dry_run, log_lines)
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
