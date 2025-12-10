import os
import shutil
import sys
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from colorama import Fore, Back, Style


def sort_move_files(path, operation_value, dest_path=None, dry_run=False, log_path=None):
    """
    Sort and move files by extension type into organized subdirectories.
    
    Args:
        path: Source directory path
        operation_value: '1' for new folder, '2' for same folder, '3' for different path
        dest_path: Destination path (required if operation_value='3')
        dry_run: If True, only simulate the operations without actual file movements
        log_path: Path to log file for recording operations
    
    Returns:
        Dictionary with 'moved_total' and 'skipped_total' counts
    """
    log_lines = []
    
    # Validate source path
    if not os.path.isdir(path):
        log_lines.append(f"{Fore.RED}Source folder path doesn't exist: {path}")
        if log_path:
            with open(log_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(log_lines))
        return {'moved_total': 0, 'skipped_total': 0}
    
    # Determine destination based on operation mode
    if operation_value == '1':  # New folder with timestamp
        subdir = f"Downloads_bkp_{datetime.now().strftime('%d_%b_%y')}"
        dest = os.path.join(path, subdir)
        if not os.path.exists(dest):
            if not dry_run:
                os.mkdir(dest)
            log_lines.append(f"Created backup folder: {dest}")
    elif operation_value == '2':  # Same folder
        dest = path
        log_lines.append(f"Organizing in same folder: {dest}")
    elif operation_value == '3':  # Different path
        if not dest_path:
            log_lines.append(f"{Fore.RED}Destination path is required for operation mode 3")
            if log_path:
                with open(log_path, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(log_lines))
            return {'moved_total': 0, 'skipped_total': 0}
        
        if not os.path.isdir(dest_path):
            log_lines.append(f"{Fore.RED}Destination folder path doesn't exist: {dest_path}")
            if log_path:
                with open(log_path, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(log_lines))
            return {'moved_total': 0, 'skipped_total': 0}
        dest = dest_path
        log_lines.append(f"Using custom destination: {dest}")
    else:
        log_lines.append(f"{Fore.RED}Wrong operation selected: {operation_value}")
        if log_path:
            with open(log_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(log_lines))
        return {'moved_total': 0, 'skipped_total': 0}

    # Get list of files and folders to process
    list_ = []
    try:
        list_ = os.listdir(path)
    except Exception as e:
        log_lines.append(f"{Fore.RED}Error reading directory: {e}")
        if log_path:
            with open(log_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(log_lines))
        return {'moved_total': 0, 'skipped_total': 0}

    # Process files and folders with thread pool
    moved_count = 0
    skipped_count = 0
    
    tasks = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        for item in list_:
            source_item_path = os.path.join(path, item)
            
            # Handle folders separately
            if os.path.isdir(source_item_path):
                tasks.append(executor.submit(
                    move_folder_to_fof,
                    source_item_path,
                    dest,
                    path,
                    dry_run,
                    log_lines
                ))
            else:
                # Handle files
                tasks.append(executor.submit(
                    move_file_by_extension, 
                    source_item_path, 
                    dest, 
                    path,
                    dry_run, 
                    log_lines
                ))
        
        for future in as_completed(tasks):
            result = future.result()
            if result == "moved":
                moved_count += 1
            elif result == "skipped":
                skipped_count += 1

    # Summary
    log_lines.append(f"\n{Fore.GREEN}=== Summary ===")
    log_lines.append(f"Total files moved: {moved_count}")
    log_lines.append(f"Total files skipped: {skipped_count}")
    log_lines.append(f"Files moved from {path} to {dest}")

    # Write log file
    if log_path:
        with open(log_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(log_lines))

    return {'moved_total': moved_count, 'skipped_total': skipped_count}


def move_folder_to_fof(source_folder_path, dest, original_path, dry_run, log_lines):
    """
    Move a folder to the FoF (Folder of Folders) directory.
    
    Args:
        source_folder_path: Full path to source folder
        dest: Base destination directory
        original_path: Original source path
        dry_run: If True, only simulate the operation
        log_lines: List to append log messages
    
    Returns:
        'moved', 'skipped', or 'error' status
    """
    try:
        folder_name = os.path.basename(source_folder_path)
        
        # Create FoF directory
        fof_path = os.path.join(dest, "FoF")
        
        # Skip if folder is already in FoF or is the FoF folder itself
        if os.path.dirname(source_folder_path) == fof_path or folder_name == "FoF":
            log_lines.append(f"[Skipped] Already in FoF or is FoF folder: {source_folder_path}")
            return "skipped"
        
        # Skip extension-based folders and special folders
        if os.path.dirname(source_folder_path) == dest and folder_name != "FoF":
            # Check if this is not one of the extension folders we just created
            parent_items = os.listdir(original_path)
            # Only move folders that existed in the original source
            if folder_name not in parent_items or folder_name == "no_extension":
                log_lines.append(f"[Skipped] System folder: {source_folder_path}")
                return "skipped"
        
        if not dry_run:
            os.makedirs(fof_path, exist_ok=True)
        
        dest_folder_path = os.path.join(fof_path, folder_name)
        
        # Handle duplicate folder names
        if os.path.exists(dest_folder_path):
            i = 1
            while True:
                new_folder_name = f"{folder_name}_{i}"
                new_dest_path = os.path.join(fof_path, new_folder_name)
                if not os.path.exists(new_dest_path):
                    dest_folder_path = new_dest_path
                    break
                i += 1
            
            if dry_run:
                log_lines.append(f"[Dry Run] Would rename duplicate folder: {source_folder_path} -> {dest_folder_path}")
            else:
                log_lines.append(f"Renamed duplicate folder: {folder_name} -> {os.path.basename(dest_folder_path)}")
        
        if dry_run:
            log_lines.append(f"[Dry Run] Would move folder: {source_folder_path} -> {dest_folder_path}")
            return "dry_run"
        else:
            shutil.move(source_folder_path, dest_folder_path)
            log_lines.append(f"{Fore.GREEN}Moved folder: {source_folder_path} -> {dest_folder_path}")
            return "moved"
    
    except Exception as e:
        log_lines.append(f"{Fore.RED}Error moving folder {source_folder_path}: {e}")
        return "error"


def move_file_by_extension(source_file_name, dest, original_path, dry_run, log_lines):
    """
    Move a single file to its extension-based subdirectory.
    
    Args:
        source_file_name: Full path to source file
        dest: Base destination directory
        original_path: Original source path (to avoid moving files in newly created ext folders)
        dry_run: If True, only simulate the operation
        log_lines: List to append log messages
    
    Returns:
        'moved', 'skipped', or 'error' status
    """
    try:
        file_ = os.path.basename(source_file_name)
        name, ext = os.path.splitext(file_)
        ext = ext[1:] if ext else ''  # Remove leading dot

        # Handle files with no extension
        if ext == '':
            ext = 'no_extension'

        # Create extension-based folder
        dest_path = os.path.join(dest, ext)
        
        # Skip if file is already in the correct extension folder
        if os.path.dirname(source_file_name) == dest_path:
            log_lines.append(f"[Skipped] Already in correct folder: {source_file_name}")
            return "skipped"
        
        if not dry_run:
            os.makedirs(dest_path, exist_ok=True)

        dest_file_name = os.path.join(dest_path, file_)

        # Handle duplicate filenames
        if os.path.exists(dest_file_name):
            i = 1
            while True:
                new_name = f"{name}_{i}{('.' + ext) if ext else ''}"
                new_dest_path = os.path.join(dest_path, new_name)
                if not os.path.exists(new_dest_path):
                    dest_file_name = new_dest_path
                    break
                i += 1
            
            if dry_run:
                log_lines.append(f"[Dry Run] Would rename duplicate: {source_file_name} -> {dest_file_name}")
            else:
                log_lines.append(f"Renamed duplicate: {file_} -> {os.path.basename(dest_file_name)}")

        if dry_run:
            log_lines.append(f"[Dry Run] Would move: {source_file_name} -> {dest_file_name}")
            return "dry_run"
        else:
            shutil.move(source_file_name, dest_file_name)
            log_lines.append(f"{Fore.GREEN}Moved: {source_file_name} -> {dest_file_name}")
            return "moved"

    except Exception as e:
        log_lines.append(f"{Fore.RED}Error moving {source_file_name}: {e}")
        return "error"


if __name__ == '__main__':
    file_path = input("Enter the source file path : \n")
    if not os.path.isdir(file_path):
        print(f"{Fore.RED}Folder Path Doesn't Exist")
        sys.exit(1)
    
    operation = input("Select any operation :\n "
                      "1. New Folder :\n"
                      "2. Same Folder:\n"
                      "3. Different Path:\n")
    
    dest_path = None
    if operation == '3':
        dest_path = input("Enter the Destination file path : \n")
        if not os.path.isdir(dest_path):
            print(f"{Fore.RED}Destination Folder Path Doesn't Exist")
            sys.exit(1)
    
    result = sort_move_files(file_path, operation, dest_path=dest_path)
    print(f"\n{Fore.GREEN}Operation completed!")
    print(f"Files moved: {result['moved_total']}")
    print(f"Files skipped: {result['skipped_total']}")
