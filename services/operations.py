import os
import asyncio
import time
import zipfile
import shutil
from datetime import datetime

# Script Imports
from scripts.compress_videos_in_folder import compress_videos_in_folder
from scripts.compress_images import compress_images_in_folder
from scripts.detect_and_move_corrupt_files import detect_and_move_corrupt_files
from scripts.search_movie_on_imdb import process_movies
from scripts.segregate_by_year import segregate_files_by_year
from scripts.segregate_by_size import segregate_files_by_size
from scripts.move_long_videos import find_and_move_long_videos
from scripts.segregate_by_resolution import segregate_files_by_resolution
from scripts.segregate_by_height_res import segregate_files_by_height
from scripts.rename_files import rename_files
from scripts.smart_rename import rename_files_in_folder
from scripts.image_date_modifier import modify_image_dates
from scripts.sort_move_files import sort_move_files
from scripts.playlist_downloader import download_playlist
from scripts.move_worked_files_in_gitrepo import backup_git_work
from scripts.media_organizer import organize_media
from scripts.image_scraper import scrape_images_task
from scripts.text_extractor import extract_text_task


class OperationService:
    def __init__(self, log_dir, temp_dir):
        self.log_dir = log_dir
        self.temp_dir = temp_dir

    def execute(self, operation, folder_path, form_data, is_dry_run):
        """
        Executes a single operation.
        Returns: (success_message, summary_data_entry)
        Raises: Exception if failure
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_file = None
        
        # --- Organization ---
        if operation == 'segregate_by_year':
            log_file = os.path.join(self.log_dir, f'year_log_{timestamp}.txt')
            result = asyncio.run(segregate_files_by_year(folder_path, dry_run=is_dry_run, log_path=log_file))
            msg = f"✅ Year-based segregation done. {result['moved_total']} moved, {result['skipped_total']} skipped."
            return msg, {'log_file': os.path.basename(log_file)}

        elif operation == 'sort_move_files':
            log_file = os.path.join(self.log_dir, f'sort_move_log_{timestamp}.txt')
            destination_mode = form_data.get('destination_mode', '2')
            custom_dest_path = form_data.get('custom_dest_path', '')
            dest_path = custom_dest_path if destination_mode == '3' else None
            
            result = sort_move_files(folder_path, destination_mode, dest_path=dest_path, dry_run=is_dry_run, log_path=log_file)
            msg = f"✅ Sort & Move by extension completed. {result['moved_total']} moved, {result['skipped_total']} skipped."
            return msg, {'log_file': os.path.basename(log_file)}
        
        elif operation == 'segregate_by_size':
            log_file = os.path.join(self.log_dir, f'size_log_{timestamp}.txt')
            segregate_files_by_size(folder_path, dry_run=is_dry_run, log_path=log_file)
            return '✅ Size-based segregation completed.', {'log_file': os.path.basename(log_file)}

        elif operation == 'process_movies':
            log_file = os.path.join(self.log_dir, f'smart_rename_log_{timestamp}.txt')
            process_movies(folder_path) # Warning: This script seems to not support log_path/dry_run based on previous code
            return '✅ Movie processing completed.', {'log_file': os.path.basename(log_file)}

        elif operation == 'organize_media':
            log_file = os.path.join(self.log_dir, f'media_organizer_log_{timestamp}.txt')
            asyncio.run(organize_media(folder_path, dry_run=is_dry_run, log_path=log_file))
            return f"✅ Media organization completed. Check logs for details.", {'log_file': os.path.basename(log_file)}

        # --- Videos ---
        elif operation == 'download_playlist':
            playlist_url = form_data.get('playlist_url')
            resolution = form_data.get('playlist_resolution', '1080p')
            if not playlist_url:
                raise ValueError("❌ Please enter a playlist URL.")
            
            log_file = os.path.join(self.log_dir, f'playlist_log_{timestamp}.txt')
            result = asyncio.run(download_playlist(playlist_url, folder_path, resolution, log_path=log_file))
            
            if result.get('error'):
                return f"{result['error']}", {'log_file': os.path.basename(log_file)}
            return f"✅ Playlist download task finished. Check logs.", {'log_file': os.path.basename(log_file)}

        elif operation == 'compress_videos_in_folder':
            log_file = os.path.join(self.log_dir, f'compress_video_log_{timestamp}.txt')
            asyncio.run(compress_videos_in_folder(folder_path)) 
            return f"✅ Compressed videos done.", {'log_file': os.path.basename(log_file)}

        elif operation == 'move_long_videos':
            log_file = os.path.join(self.log_dir, f'video_log_{timestamp}.txt')
            asyncio.run(find_and_move_long_videos(folder_path, dry_run=is_dry_run, log_path=log_file))
            return '✅ Long video segregation completed.', {'log_file': os.path.basename(log_file)}

        elif operation == 'segregate_files_by_resolution':
            log_file = os.path.join(self.log_dir, f'res_log_{timestamp}.txt')
            result = asyncio.run(segregate_files_by_resolution(folder_path, dry_run=is_dry_run, log_path=log_file))
            msg = f"✅ Resolution-based segregation done. {result['moved_total']} moved."
            return msg, {'log_file': os.path.basename(log_file)}
            
        elif operation == 'segregate_files_by_height':
            log_file = os.path.join(self.log_dir, f'height_log_{timestamp}.txt')
            result = asyncio.run(segregate_files_by_height(folder_path, dry_run=is_dry_run, log_path=log_file))
            msg = f"✅ Height Resolution-based segregation done. {result['moved_total']} moved."
            return msg, {'log_file': os.path.basename(log_file)}

        # --- Images ---
        elif operation == 'compress_images':
            log_file = os.path.join(self.log_dir, f'compress_images_log_{timestamp}.txt')
            result = asyncio.run(compress_images_in_folder(folder_path, dry_run=is_dry_run, log_path=log_file))
            msg = f"✅ Image compression done. {result['moved_total']} processed."
            return msg, {'log_file': os.path.basename(log_file)}

        elif operation == 'modify_image_dates':
            target_date = form_data.get('target_date')
            if not target_date:
                raise ValueError("❌ Please select a target date.")
            log_file = os.path.join(self.log_dir, f'date_mod_log_{timestamp}.txt')
            result = asyncio.run(modify_image_dates(folder_path, target_date, dry_run=is_dry_run, log_path=log_file))
            msg = f"✅ Date modification done. {result['moved_total']} processed."
            return msg, {'log_file': os.path.basename(log_file)}

        elif operation == 'scrape_images':
            urls_text = form_data.get('scraper_urls', '')
            use_dynamic = form_data.get('scraper_dynamic') == 'yes'
            if not urls_text.strip():
                raise ValueError("❌ No URLs provided for scraping.")
            
            urls = urls_text.splitlines()
            log_file = os.path.join(self.log_dir, f'scraper_log_{timestamp}.txt')
            result = asyncio.run(scrape_images_task(urls, folder_path, use_dynamic=use_dynamic, log_path=log_file))
            
            summary_entry = {'log_file': os.path.basename(log_file)}
            
            # Zip Logic
            if result.get('output_dir') and os.path.exists(result['output_dir']):
                has_files = any(f for _, _, f in os.walk(result['output_dir']) if f)
                if has_files:
                    zip_name = f"Scraped_Images_{int(time.time())}.zip"
                    zip_path = os.path.join(self.temp_dir, zip_name)
                    with zipfile.ZipFile(zip_path, 'w') as zipf:
                        for root, dirs, files in os.walk(result['output_dir']):
                            for file in files:
                                file_path = os.path.join(root, file)
                                arcname = os.path.relpath(file_path, result['output_dir'])
                                zipf.write(file_path, arcname)
                    summary_entry['download_link'] = zip_name
                    msg = f"✅ Scraping finished. Processed {result['total_processed']} URLs."
                else:
                    msg = f"⚠️ Scraper ran but no images were saved."
            else:
                 msg = f"✅ Scraping finished. Processed {result['total_processed']} URLs."
                 
            return msg, summary_entry

        elif operation == 'extract_text':
             log_file = os.path.join(self.log_dir, f'ocr_log_{timestamp}.txt')
             result = asyncio.run(extract_text_task(folder_path, dry_run=is_dry_run, log_path=log_file))
             summary_entry = {'log_file': os.path.basename(log_file)}
             
             if result.get('generated_files'):
                files = result['generated_files']
                if len(files) == 1:
                    src = files[0]
                    filename = os.path.basename(src)
                    dst = os.path.join(self.temp_dir, filename)
                    shutil.copy2(src, dst)
                    summary_entry['download_link'] = filename
                else:
                    zip_name = f"OCR_Results_{int(time.time())}.zip"
                    zip_path = os.path.join(self.temp_dir, zip_name)
                    with zipfile.ZipFile(zip_path, 'w') as zipf:
                        for f in files:
                            zipf.write(f, os.path.basename(f))
                    summary_entry['download_link'] = zip_name
             
             return f"✅ OCR completed. Processed {result['processed']} images.", summary_entry

        # --- Maintenance ---
        elif operation == 'detect_and_move_corrupt_files':
            log_file = os.path.join(self.log_dir, f'corrupt_log_{timestamp}.txt')
            result = asyncio.run(detect_and_move_corrupt_files(folder_path))
            return f"✅ Detect and move corrupt files done. {result['moved_total']} moved.", {'log_file': os.path.basename(log_file)}

        elif operation == 'rename_files':
            log_file = os.path.join(self.log_dir, f'rename_ext_log_{timestamp}.txt')
            rename_files(folder_path, dry_run=is_dry_run, log_path=log_file)
            return '✅ Extension-based renaming completed.', {'log_file': os.path.basename(log_file)}

        elif operation == 'smart_rename':
            log_file = os.path.join(self.log_dir, f'smart_rename_log_{timestamp}.txt')
            rename_files_in_folder(folder_path, dry_run=is_dry_run, log_path=log_file)
            return '✅ Smart renaming completed.', {'log_file': os.path.basename(log_file)}

        elif operation == 'backup_git_work':
            log_file = os.path.join(self.log_dir, f'git_backup_log_{timestamp}.txt')
            result = asyncio.run(backup_git_work(folder_path, log_path=log_file))
            if result.get('error'):
                 return f"{result['error']}", {'log_file': os.path.basename(log_file)}
            return f"✅ Git Backup completed. {result['moved_total']} files backed up.", {'log_file': os.path.basename(log_file)}

        else:
            raise ValueError(f"Unknown operation: {operation}")
