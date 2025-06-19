import os
import re
import shutil
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

YEAR_PATTERN = re.compile(r'\b(19|20)\d{2}\b')
executor = ThreadPoolExecutor()

def extract_year_from_filename(name: str) -> int | None:
    match = YEAR_PATTERN.search(name)
    return int(match.group()) if match else None

def get_file_modified_year(path: Path) -> int:
    mtime = path.stat().st_mtime
    return datetime.fromtimestamp(mtime).year

def ensure_folder_exists(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)

def move_file_to_year_folder(file_path: Path, year: int, base_path: Path, dry_run: bool, log_lines: list):
    target_dir = base_path / str(year)
    target_file = target_dir / file_path.name

    if file_path.parent.name == str(year):
        log_lines.append(f"Skipped (already in {year}): {file_path.name}")
        return 'skipped'

    if dry_run:
        log_lines.append(f"[Dry Run] Would move: {file_path.name} -> {target_dir}")
        return 'moved'

    ensure_folder_exists(target_dir)
    shutil.move(str(file_path), str(target_file))
    log_lines.append(f"Moved: {file_path.name} -> {target_dir}")
    return 'moved'

async def process_file(file_path: Path, base_path: Path, dry_run: bool, log_lines: list):
    mod_year = get_file_modified_year(file_path)
    name_year = extract_year_from_filename(file_path.name)
    target_year = name_year if name_year == mod_year else mod_year

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        executor, move_file_to_year_folder, file_path, target_year, base_path, dry_run, log_lines
    )
    return result

async def segregate_files_by_year(input_path: str, dry_run: bool = False, log_path: str = None):
    base_path = Path(input_path).resolve()
    if not base_path.is_dir():
        raise Exception(f"❌ '{base_path}' is not a valid directory.")

    files = [f for f in base_path.iterdir() if f.is_file()]
    log_lines = [f"Starting segregation by year in: {base_path}", f"Dry Run: {dry_run}"]

    tasks = [process_file(f, base_path, dry_run, log_lines) for f in files]
    results = await asyncio.gather(*tasks)

    moved = results.count('moved')
    skipped = results.count('skipped')

    log_lines.append(f"\n✅ Completed. Moved: {moved}, Skipped: {skipped}")

    if log_path:
        with open(log_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(log_lines))

    return {
        'moved_total': moved,
        'skipped_total': skipped,
        'log_lines': log_lines
    }

if __name__ == "__main__":
    user_input = input("Enter the full path to the directory: ").strip()
    try:
        asyncio.run(segregate_files_by_year(user_input, dry_run=True))
    except Exception as e:
        print("❌ Exception occurred:", e)