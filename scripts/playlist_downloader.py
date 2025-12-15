
import os
import asyncio
import logging
from pathlib import Path

# Try importing yt_dlp, handle if missing
try:
    import yt_dlp
except ImportError:
    yt_dlp = None

def download_playlist_sync(playlist_url, output_folder, resolution="1080p", log_lines=None):
    if log_lines is None:
        log_lines = []

    if yt_dlp is None:
        msg = "❌ Error: 'yt-dlp' library is missing. Please install it using: pip install yt-dlp"
        log_lines.append(msg)
        return {'moved_total': 0, 'skipped_total': 0, 'error': msg}

    # Extract height number from resolution string (e.g., "1080p" -> 1080)
    try:
        height_target = int(''.join(filter(str.isdigit, resolution)))
    except ValueError:
        height_target = 1080  # Default fallback

    log_lines.append(f"Starting playlist download: {playlist_url}")
    log_lines.append(f"Target Resolution: {resolution} (approx height: {height_target})")

    # Configure yt-dlp options
    # We want to download best video <= target height + best audio, merge them.
    # Format selector: "bestvideo[height<=?1080]+bestaudio/best[height<=?1080]"
    
    ydl_opts = {
        'format': f'bestvideo[height<={height_target}]+bestaudio/best[height<={height_target}]',
        'outtmpl': f'{output_folder}/%(playlist_title)s/%(title)s.%(ext)s',
        'merge_output_format': 'mp4',
        'ignoreerrors': True,  # Skip errors (fail-proof)
        'no_warnings': True,
        'quiet': True,         # We will capture progress via logger if needed, but keeping it simple for now
        'nocheckcertificate': True,
    }

    # Custom logger to capture logs
    class MyLogger:
        def debug(self, msg):
            if not msg.startswith('[debug] '):
                # log_lines.append(f"[DEBUG] {msg}") # Too verbose?
                pass
        def info(self, msg):
           pass 
        def warning(self, msg):
            log_lines.append(f"[WARNING] {msg}")
        def error(self, msg):
            log_lines.append(f"[ERROR] {msg}")

    ydl_opts['logger'] = MyLogger()
    
    # Progress hook
    def progress_hook(d):
        if d['status'] == 'finished':
            filename = os.path.basename(d['filename'])
            log_lines.append(f"✅ Downloaded: {filename}")
        elif d['status'] == 'downloading':
            # print(f"Downloading: {d['_percent_str']}") # Optional: too spammy for static log
            pass

    ydl_opts['progress_hooks'] = [progress_hook]

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Extract info first to get video count (optional, adds time)
            # info = ydl.extract_info(playlist_url, download=False)
            # log_lines.append(f"Found playlist: {info.get('title', 'Unknown')}")
            
            # Download
            ydl.download([playlist_url])
            
        log_lines.append("\n✅ Playlist processing completed.")
        return {'moved_total': 1, 'skipped_total': 0} # simplified stats
    except Exception as e:
        log_lines.append(f"❌ Critical Error: {str(e)}")
        return {'moved_total': 0, 'skipped_total': 1}

async def download_playlist(playlist_url, output_folder, resolution="1080p", log_path=None):
    """
    Async wrapper for playlist downloader.
    """
    log_lines = []
    
    loop = asyncio.get_event_loop()
    # Run blocking download in executor
    result = await loop.run_in_executor(
        None, 
        download_playlist_sync, 
        playlist_url, 
        output_folder, 
        resolution, 
        log_lines
    )

    if log_path:
        with open(log_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(log_lines))

    return result

if __name__ == "__main__":
    if yt_dlp is None:
        print("Please install yt-dlp: pip install yt-dlp")
    else:
        url = input("Playlist URL: ").strip()
        res = input("Resolution (e.g. 1080p): ").strip() or "1080p"
        folder = input("Output Folder: ").strip() or "."
        log_lines = []
        download_playlist_sync(url, folder, res, log_lines)
        print("\n".join(log_lines))
