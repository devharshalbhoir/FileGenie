import os
from concurrent.futures import ThreadPoolExecutor, as_completed

def rename_file(old_path, new_path, dry_run, log_lines):
    try:
        if dry_run:
            log_lines.append(f"[Dry Run] Would rename: {old_path} -> {new_path}")
            return "dry_run"

        os.rename(old_path, new_path)
        log_lines.append(f"Renamed: {old_path} -> {new_path}")
        return "renamed"
    except Exception as e:
        log_lines.append(f"Error renaming file {old_path}: {e}")
        return "error"

def rename_files(directory, dry_run=False, log_path=None):
    log_lines = []
    tasks = []

    with ThreadPoolExecutor() as executor:
        for root, _, files in os.walk(directory):
            for file in files:
                old_path = os.path.join(root, file)
                new_path = None

                if '.' not in file:
                    new_path = old_path + ".zip"
                elif file.endswith(".@@@"):
                    new_path = os.path.join(root, file.rsplit('.', 1)[0] + ".mp4")
                elif file.endswith(".mpeg@@@"):
                    new_path = os.path.join(root, file.rsplit('.', 1)[0] + ".mpeg")
                elif file.endswith(".mpeg@"):
                    new_path = os.path.join(root, file.rsplit('.', 1)[0] + ".mpeg")
                elif file.endswith(".@@@mkv"):
                    new_path = os.path.join(root, file.rsplit('.', 1)[0] + ".mkv")

                if new_path and old_path != new_path:
                    tasks.append(executor.submit(rename_file, old_path, new_path, dry_run, log_lines))

        for future in as_completed(tasks):
            future.result()

    renamed_count = log_lines.count("renamed")
    log_lines.append(f"\nTotal files processed: {len(tasks)}")

    if log_path:
        with open(log_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(log_lines))
