
import os
import time
import concurrent.futures
from datetime import datetime
from pathlib import Path
import asyncio

# Supported image formats
VALID_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp')

def change_modified_date(image_path, new_timestamp):
    """
    Change the modified time of an image file.
    Returns: (success, message, original_ts, new_ts)
    """
    try:
        original_mtime = os.path.getmtime(image_path)
        
        # Change the modified time (and access time to same)
        os.utime(image_path, times=(new_timestamp, new_timestamp))
        
        return True, f"Updated: {os.path.basename(image_path)}", original_mtime, new_timestamp
    except Exception as e:
        return False, f"Error updating {os.path.basename(image_path)}: {e}", None, None

def process_dates_sync(input_folder, new_date_str, dry_run=False, log_lines=None):
    """
    Sync function to process images.
    new_date_str: String in ISO format or datetime object.
    """
    if log_lines is None:
        log_lines = []

    input_folder = Path(input_folder)
    if not input_folder.exists():
        log_lines.append(f"Error: Input folder '{input_folder}' does not exist")
        return {'moved_total': 0, 'skipped_total': 0}

    # Parse date if string
    if isinstance(new_date_str, str):
        try:
            # HTML datetime-local format: 'YYYY-MM-DDTHH:MM'
            dt_obj = datetime.strptime(new_date_str, '%Y-%m-%dT%H:%M')
        except ValueError:
             try:
                dt_obj = datetime.fromisoformat(new_date_str)
             except ValueError:
                log_lines.append(f"Error: Invalid date format '{new_date_str}'")
                return {'moved_total': 0, 'skipped_total': 0}
    else:
        dt_obj = new_date_str

    timestamp = dt_obj.timestamp()
    
    # Collect files
    files_to_process = []
    for root, _, files in os.walk(input_folder):
        for file in files:
            if file.lower().endswith(VALID_EXTENSIONS):
                files_to_process.append(os.path.join(root, file))

    if not files_to_process:
        log_lines.append("No images found to modify.")
        return {'moved_total': 0, 'skipped_total': 0}

    log_lines.append(f"Found {len(files_to_process)} images. Target Date: {dt_obj}")

    if dry_run:
        log_lines.append("[Dry Run] simulating date modification...")
        for f in files_to_process:
            log_lines.append(f"[Dry Run] Would update: {os.path.basename(f)} -> {dt_obj}")
        return {'moved_total': len(files_to_process), 'skipped_total': 0}

    success_count = 0
    error_count = 0

    # Process
    for file_path in files_to_process:
        success, msg, orig, new = change_modified_date(file_path, timestamp)
        log_lines.append(msg)
        if success:
            success_count += 1
        else:
            error_count += 1
            
    return {'moved_total': success_count, 'skipped_total': error_count}

async def modify_image_dates(input_folder, new_date_str, dry_run=False, log_path=None):
    """
    Async wrapper.
    """
    log_lines = [f"Starting Image Date Modification in: {input_folder}"]
    
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None, 
        process_dates_sync, 
        input_folder, 
        new_date_str, 
        dry_run, 
        log_lines
    )

    if log_path:
        with open(log_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(log_lines))

    return result
