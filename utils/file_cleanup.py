import os
import time
import threading

def cleanup_temp_files(temp_dir):
    """Deletes files in TEMP_DIR older than 1 hour."""
    now = time.time()
    cutoff = 3600 # 1 hour
    
    if not os.path.exists(temp_dir):
        return

    for filename in os.listdir(temp_dir):
        file_path = os.path.join(temp_dir, filename)
        try:
            if os.path.isfile(file_path):
                if now - os.path.getmtime(file_path) > cutoff:
                    os.remove(file_path)
                    print(f"Cleaned up old temp file: {filename}")
        except Exception as e:
            print(f"Error cleaning {filename}: {e}")

def run_scheduler(temp_dir):
    while True:
        cleanup_temp_files(temp_dir)
        time.sleep(600) # Check every 10 mins

def start_cleanup_thread(temp_dir):
    threading.Thread(target=run_scheduler, args=(temp_dir,), daemon=True).start()
