import os
import re
import concurrent.futures
import time
from pathlib import Path

def rename_file(input_path, existing_names, dry_run, log_lines):
    try:
        directory = input_path.parent
        filename = input_path.name

        filename_no_parens = re.sub(r'\(\d+\)', '', filename).strip()
        base, ext = os.path.splitext(filename_no_parens)
        base_with_underscores = re.sub(r'\s+', '_', base.strip())
        base_cleaned = re.sub(r'[^a-zA-Z0-9_]', '', base_with_underscores)
        new_filename_base = f"{base_cleaned}{ext}"

        if new_filename_base == filename:
            log_lines.append(f"[Skipped] No change needed: {filename}")
            return "skipped"

        new_filename = new_filename_base
        output_path = directory / new_filename
        counter = 1

        while str(output_path) in existing_names or output_path.exists():
            base, ext = os.path.splitext(new_filename_base)
            new_filename = f"{base}_{counter}{ext}"
            output_path = directory / new_filename
            counter += 1

        existing_names.add(str(output_path))

        if dry_run:
            log_lines.append(f"[Dry Run] Would rename: {filename} -> {new_filename}")
            return "dry_run"

        input_path.rename(output_path)
        log_lines.append(f"Renamed: {filename} -> {new_filename}")
        return "renamed"

    except Exception as e:
        log_lines.append(f"Error renaming {input_path}: {str(e)}")
        return "error"

def rename_files_in_folder(folder_path, dry_run=False, log_path=None, max_workers=4):
    folder_path = Path(folder_path)
    log_lines = []

    if not folder_path.exists():
        log_lines.append(f"Error: Folder '{folder_path}' does not exist")
        return

    files = [f for f in folder_path.rglob('*') if f.is_file()]
    if not files:
        log_lines.append("No files found in the specified folder")
        return

    existing_names = set(str(f) for f in files)
    start_time = time.time()

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(rename_file, file, existing_names, dry_run, log_lines)
            for file in files
        ]
        concurrent.futures.wait(futures)

    end_time = time.time()
    log_lines.append(f"\nRenaming completed in {end_time - start_time:.2f} seconds")
    log_lines.append(f"Total files processed: {len(files)}")

    if log_path:
        with open(log_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(log_lines))
