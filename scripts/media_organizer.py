
import os
import subprocess
import logging
from babelfish import Language
from subliminal import download_best_subtitles, region, save_subtitles, scan_video

def setup_logger(log_path):
    """Sets up a file logger."""
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger('MediaOrganizer')
    
    # Check if a file handler is already added to avoid duplicates
    if not any(isinstance(h, logging.FileHandler) for h in logger.handlers):
        handler = logging.FileHandler(log_path, encoding='utf-8')
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
    return logger

def run_mnamer(folder_path, dry_run=False, logger=None):
    """
    Runs mnamer in batch mode to organize media files.
    """
    cmd = ["mnamer", "--batch", "--recurse"]
    if not dry_run:
        # If it's not a dry run, we let mnamer do its thing.
        # But wait, mnamer by default might be interactive without --batch.
        # We specified --batch so it should be automatic.
        pass
    else:
        # mnamer has a --test or --dry-run equivalent? 
        # Checking docs: --test is used for dry run.
        cmd.append("--test")

    cmd.append(folder_path)

    if logger:
        logger.info(f"Running mnamer command: {' '.join(cmd)}")

    try:
        # mnamer writes to stdout/stderr
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
        if logger:
            logger.info("mnamer output:\n" + result.stdout)
            if result.stderr:
                logger.error("mnamer error output:\n" + result.stderr)
        
        return True
    except Exception as e:
        if logger:
            logger.error(f"Failed to run mnamer: {e}")
        return False

def download_subtitles(folder_path, languages={'en', 'hi'}, dry_run=False, logger=None):
    """
    Scans the folder for videos and downloads subtitles using subliminal.
    """
    if logger:
        logger.info(f"Scanning for videos in {folder_path} to download subtitles...")
    
    # Configure subliminal region
    region.configure('dogpile.cache.memory')

    videos = []
    # Recursively find video files
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            if file.lower().endswith(('.mp4', '.mkv', '.avi', '.mov', '.wmv')):
                videos.append(os.path.join(root, file))

    if not videos:
        if logger:
            logger.info("No video files found.")
        return

    # Convert language strings to babelfish Language objects
    langs = {Language(l) for l in languages}

    for video_path in videos:
        try:
            if logger:
                logger.info(f"Processing: {video_path}")
            
            if dry_run:
                if logger:
                    logger.info(f"  [Dry Run] Would search subtitles for {video_path} in {languages}")
                continue

            # Scan the video
            video = scan_video(video_path)
            
            # Download best subtitles
            subtitles = download_best_subtitles([video], langs)
            
            # Save them
            if video in subtitles and subtitles[video]:
                save_subtitles(video, subtitles[video])
                if logger:
                    logger.info(f"  Downloaded {len(subtitles[video])} subtitles for {os.path.basename(video_path)}")
            else:
                if logger:
                    logger.info(f"  No subtitles found for {os.path.basename(video_path)}")
                    
        except Exception as e:
            if logger:
                logger.error(f"  Error processing {video_path}: {e}")

async def organize_media(folder_path, dry_run=False, log_path=None):
    """
    Orchestrator function to run mnamer and then download subtitles.
    """
    logger = setup_logger(log_path)
    logger.info(f"Starting media organization for {folder_path}")
    logger.info(f"Dry Run: {dry_run}")
    
    counts = {'renamed': 0, 'subtitles': 0, 'skipped': 0}
    
    # 1. Run mnamer
    # We can't easily get the 'moved' count from mnamer CLI output parsable easily without complex regex,
    # so we'll just log the output.
    success = run_mnamer(folder_path, dry_run=dry_run, logger=logger)
    if not success:
        logger.error("mnamer execution failed to complete successfully.")
    
    # 2. Download subtitles
    # We do this AFTER renaming so we get subs for the clean filenames (usually better matching)
    download_subtitles(folder_path, dry_run=dry_run, logger=logger)
    
    logger.info("Media organization task completed.")
    
    # Since we can't get exact counts from mnamer easily, we return a generic success message
    return {'moved_total': 'See Log', 'skipped_total': 'See Log'}
