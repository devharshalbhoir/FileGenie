import os
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed

FOLDERS = {
    "FOLDER_10": (0, 10),
    "FOLDER_30": (10, 30),
    "FOLDER_60": (30, 60),
    "FOLDER_90": (60, 90),
    "FOLDER_120": (90, 120),
    "FOLDER_150": (120, 150),
    "FOLDER_240": (150, 240)
}

def get_size_in_mb(file_path):
    try:
        size_bytes = os.path.getsize(file_path)
        return size_bytes / (1024 * 1024)
    except Exception as e:
        return None

def determine_folder(file_size_mb, base_directory):
    for folder_name, (min_size, max_size) in FOLDERS.items():
        if min_size <= file_size_mb < max_size:
            return os.path.join(base_directory, folder_name)
    return os.path.join(base_directory, f"folder_{int(file_size_mb // 30) * 30 + 30}")

def move_file(file_path, base_directory, dry_run, log_lines):
    file_size_mb = get_size_in_mb(file_path)
    if file_size_mb is None:
        log_lines.append(f"[Skipped] Size error for {file_path}")
        return "skipped"

    folder_path = determine_folder(file_size_mb, base_directory)
    destination = os.path.join(folder_path, os.path.basename(file_path))

    if os.path.dirname(file_path) == folder_path:
        log_lines.append(f"[Skipped] Already in correct folder: {file_path}")
        return "skipped"

    if dry_run:
        log_lines.append(f"[Dry Run] Would move: {file_path} -> {folder_path}")
        return "dry_run"

    try:
        os.makedirs(folder_path, exist_ok=True)
        shutil.move(file_path, destination)
        log_lines.append(f"Moved: {file_path} -> {folder_path}")
        return "moved"
    except Exception as e:
        log_lines.append(f"Error moving {file_path} to {folder_path}: {e}")
        return "error"

def segregate_files_by_size(directory, dry_run=False, log_path=None, max_workers=8):
    log_lines = []
    if not os.path.exists(directory):
        log_lines.append(f"The directory '{directory}' does not exist.")
        if log_path:
            with open(log_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(log_lines))
        return

    files_to_process = [
        os.path.join(root, file)
        for root, _, files in os.walk(directory)
        for file in files
    ]

    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(move_file, file_path, directory, dry_run, log_lines): file_path
            for file_path in files_to_process
        }
        for future in as_completed(futures):
            result = future.result()
            results.append(result)

    moved_count = results.count("moved")
    skipped_count = results.count("skipped")

    log_lines.append(f"\nTotal files moved: {moved_count}")
    log_lines.append(f"Total files skipped: {skipped_count}")

    if log_path:
        with open(log_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(log_lines))