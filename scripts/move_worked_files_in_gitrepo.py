
import os
import shutil
import asyncio
from datetime import datetime
from pathlib import Path

# Try importing git, handle if missing
try:
    import git
    from git import Repo, Exc
except ImportError:
    git = None

def log_message(log_lines: list, message: str):
    """Helper to append to log lines list."""
    log_lines.append(message)

def copy_files(file_list: list, source_root: Path, dest_dir: Path, log_lines: list, label: str):
    """
    Copies a list of files from source to destination, preserving relative structure if needed
    or just flat copy? The user's script did flat copy, but flat copy is risky for name collisions.
    User's script: shutil.copy(os.path.join(folder_path, item), untracked_dir) -> Flat copy.
    I will stick to flat copy for now to match user intent, but maybe add safety?
    """
    if not file_list:
        return 0

    if not dest_dir.exists():
        dest_dir.mkdir(parents=True, exist_ok=True)
        log_lines.append(f"Created directory: {dest_dir}")

    count = 0
    for file_rel_path in file_list:
        # file_rel_path is relative to git root
        src_file = source_root / file_rel_path
        
        # Flatten structure: just filename.
        # Warning: if src is 'a/foo.txt' and 'b/foo.txt', one wins.
        # User's original script didn't handle this. I will keep it simple but safe.
        dest_file = dest_dir / Path(file_rel_path).name 
        
        try:
            if src_file.exists():
                shutil.copy2(src_file, dest_file)
                count += 1
            else:
                 log_lines.append(f"⚠️ Source file missing (deleted?): {src_file}")
        except Exception as e:
            log_lines.append(f"❌ Error copying {file_rel_path}: {e}")

    log_lines.append(f"✅ Copied {count} {label} files to {dest_dir.name}")
    return count

def move_worked_files_sync(repo_path_str: str, output_base_dir: str = None, log_lines: list = None):
    """
    Sync function to process git repo changes.
    """
    if log_lines is None:
        log_lines = []

    if git is None:
        msg = "❌ Error: 'GitPython' library is missing. Please install it using: pip install GitPython"
        log_lines.append(msg)
        return {'moved_total': 0, 'skipped_total': 0, 'error': msg}

    repo_path = Path(repo_path_str).resolve()
    
    # Default output dir to CWD if not specified? 
    # User script: base_dir = os.getcwd() -> module_name dir.
    # We should probably put it in usage context. simpler to put it inside the repo or specific folder?
    # User script put it in os.getcwd()/module_name.
    # We will use the provided output_base_dir or CWD.
    
    if not output_base_dir:
        output_base_dir = os.getcwd()
    
    log_lines.append(f"Analyzing Git Repository: {repo_path}")

    try:
        repo = Repo(repo_path)
        
        # Check if empty repo
        if repo.bare:
            log_lines.append("❌ Repository is bare.")
            return {'moved_total': 0, 'skipped_total': 0}

        try:
            active_branch_name = repo.active_branch.name
        except TypeError:
            active_branch_name = "detached_head"

        timestamp = datetime.now().strftime('%d%b%y_%H%M')
        folder_name = f"{active_branch_name}_{timestamp}"
        
        module_name = repo_path.name
        backup_root = Path(output_base_dir) / f"{module_name}_Backups" / folder_name
        
        log_lines.append(f"Backup target: {backup_root}")

        total_copied = 0
        
        # 1. Untracked Files
        untracked = repo.untracked_files
        if untracked:
            log_lines.append(f"Found {len(untracked)} untracked files.")
            total_copied += copy_files(untracked, repo_path, backup_root / "untracked", log_lines, "untracked")
        else:
            log_lines.append("No untracked files found.")

        # 2. Modified (Changed) Files
        # index.diff(None) compares index to working tree (modified unstaged)
        # We also might want staged files? HEAD.diff(None)?
        # User script: repo.index.diff(None) -> Unstaged changes.
        changed_items = repo.index.diff(None)
        changed_files = [item.a_path for item in changed_items]
        
        if changed_files:
            log_lines.append(f"Found {len(changed_files)} modified files.")
            total_copied += copy_files(changed_files, repo_path, backup_root / "changed", log_lines, "modified")
        else:
            log_lines.append("No modified files found.")
            
        return {'moved_total': total_copied, 'skipped_total': 0, 'backup_path': str(backup_root)}

    except git.exc.InvalidGitRepositoryError:
        msg = f"❌ '{repo_path}' is not a valid Git repository."
        log_lines.append(msg)
        return {'moved_total': 0, 'skipped_total': 0, 'error': msg}
    except Exception as e:
        msg = f"❌ Unexpected Error: {e}"
        log_lines.append(msg)
        return {'moved_total': 0, 'skipped_total': 0, 'error': msg}


async def backup_git_work(repo_path, log_path=None):
    """
    Async wrapper.
    """
    log_lines = []
    
    # We'll use the parent of repo_path as the place to put the backup folder "RepoName_Backups"
    # Or maybe inside the "logs" ref? No, backups should be separate.
    # Let's put backups in "Backups" folder relative to where script runs (FileGenie root) or near repo?
    # User preference check: "base_dir = os.getcwd()" implies where the script runs.
    # Let's define a 'Backups' folder in the FileGenie project root for consistency.
    output_base = Path(os.getcwd()) / "Backups"
    
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None, 
        move_worked_files_sync, 
        repo_path, 
        str(output_base), 
        log_lines
    )

    if log_path:
        # Also append the logs to the specific log file
        try:
             with open(log_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(log_lines))
        except Exception:
            pass

    return result

if __name__ == "__main__":
    if git is None:
        print("Please install GitPython: pip install GitPython")
    else:
        path = input("Enter Repo Path: ").strip()
        log_lines = []
        res = move_worked_files_sync(path, log_lines=log_lines)
        print("\n".join(log_lines))
