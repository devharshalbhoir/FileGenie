import os
import sys
import subprocess
import asyncio
from flask import Flask, render_template, request, flash, send_file, redirect, url_for
from datetime import datetime

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

app = Flask(__name__)
app.secret_key = 'abcde'
LOG_DIR = os.path.join(os.getcwd(), 'logs')
os.makedirs(LOG_DIR, exist_ok=True)


@app.route('/', methods=['GET', 'POST'])
def index():
    print(request.method)
    summary_data = {}

    if request.method == 'POST':
        folder_path = request.form.get('folder_path')
        operations = request.form.getlist('operations')  # ✅ updated key
        is_dry_run = request.form.get('dry_run') == 'yes'
        print("Running:", operations, "→", folder_path, "Dry run:", is_dry_run)

        if not folder_path and not operations:
             flash('❌ Please select an operation.', 'warning')
        else:
            # Smart Validation Logic
            URL_ONLY_OPERATIONS = {'scrape_images', 'download_playlist'}
            # For OCR, folder_path can be a FILE path.
            FILE_OR_DIR_OPERATIONS = {'extract_text'}
            
            has_source_ops = any(op not in URL_ONLY_OPERATIONS for op in operations)
            
            # Default path logic for URL operations if empty
            if not folder_path and not has_source_ops and operations:
                folder_path = os.path.join(os.getcwd(), 'downloads')
                flash(f"ℹ️ No path provided. Defaulting to: {folder_path}", 'info')
            
            # Validation
            if not folder_path: # Still empty and needed
                flash('❌ Please enter a valid path.', 'danger')
            elif not os.path.exists(folder_path):
                 if not has_source_ops and operations:
                    try:
                        os.makedirs(folder_path, exist_ok=True)
                        flash(f"✅ Created output directory: {folder_path}", 'success')
                    except Exception as e:
                        flash(f"❌ Could not create directory: {e}", 'danger')
                        folder_path = None # Invalid
                 else:
                    flash('❌ Target path does not exist.', 'danger')
                    folder_path = None # Invalid
            
            # Extra Check: if path is file but operation requires folder (e.g., sort_move)
            # We assume most ops require folder unless specified.
            if folder_path and os.path.isfile(folder_path):
                 # logic to prevent incompatible ops on file could go here, but for now we trust user
                 pass

            if folder_path:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

            if 'segregate_by_year' in operations:
                try:
                    log_file = os.path.join(LOG_DIR, f'year_log_{timestamp}.txt')
                    result = asyncio.run(segregate_files_by_year(folder_path, dry_run=is_dry_run, log_path=log_file))
                    flash(
                        f"✅ Year-based segregation done. {result['moved_total']} moved, {result['skipped_total']} skipped.",
                        'success')
                    summary_data['segregate_by_year'] = {'log_file': os.path.basename(log_file)}
                except Exception as e:
                    flash(f'❌ Error in year segregation: {e}', 'danger')

            if 'segregate_files_by_resolution' in operations:
                try:
                    log_file = os.path.join(LOG_DIR, f'year_log_{timestamp}.txt')
                    result = asyncio.run(
                        segregate_files_by_resolution(folder_path, dry_run=is_dry_run, log_path=log_file))
                    flash(
                        f"✅ Resolution-based segregation done. {result['moved_total']} moved, {result['skipped_total']} skipped.",
                        'success')
                    summary_data['segregate_files_by_resolution'] = {'log_file': os.path.basename(log_file)}
                except Exception as e:
                    flash(f'❌ Error in year segregation: {e}', 'danger')

            if 'segregate_files_by_height' in operations:
                try:
                    log_file = os.path.join(LOG_DIR, f'year_log_{timestamp}.txt')
                    result = asyncio.run(segregate_files_by_height(folder_path, dry_run=is_dry_run, log_path=log_file))
                    flash(
                        f"✅ Height Resolution-based segregation done. {result['moved_total']} moved, {result['skipped_total']} skipped.",
                        'success')
                    summary_data['segregate_files_by_height'] = {'log_file': os.path.basename(log_file)}
                except Exception as e:
                    flash(f'❌ Error in year segregation: {e}', 'danger')

            if 'compress_videos_in_folder' in operations:
                try:
                    log_file = os.path.join(LOG_DIR, f'year_log_{timestamp}.txt')
                    result = asyncio.run(compress_videos_in_folder(folder_path))
                    flash(
                        f"✅ Compressed videos done. {result['moved_total']} moved, {result['skipped_total']} skipped.",
                        'success')
                    summary_data['compress_videos_in_folder'] = {'log_file': os.path.basename(log_file)}
                except Exception as e:
                    flash(f'❌ Error in year segregation: {e}', 'danger')

            if 'compress_images' in operations:
                try:
                    log_file = os.path.join(LOG_DIR, f'compress_images_log_{timestamp}.txt')
                    result = asyncio.run(compress_images_in_folder(folder_path, dry_run=is_dry_run, log_path=log_file))
                    flash(
                        f"✅ Image compression done. {result['moved_total']} processed, {result['skipped_total']} failed.",
                        'success')
                    summary_data['compress_images'] = {'log_file': os.path.basename(log_file)}
                except Exception as e:
                    flash(f'❌ Error in image compression: {e}', 'danger')

            if 'detect_and_move_corrupt_files' in operations:
                try:
                    log_file = os.path.join(LOG_DIR, f'year_log_{timestamp}.txt')
                    result = asyncio.run(detect_and_move_corrupt_files(folder_path))
                    flash(
                        f"✅ Detect and move corrupt files done. {result['moved_total']} moved, {result['skipped_total']} skipped.",
                        'success')
                    summary_data['detect_and_move_corrupt_files'] = {'log_file': os.path.basename(log_file)}
                except Exception as e:
                    flash(f'❌ Error in year segregation: {e}', 'danger')

            if 'segregate_by_size' in operations:
                try:
                    log_file = os.path.join(LOG_DIR, f'size_log_{timestamp}.txt')
                    segregate_files_by_size(folder_path, dry_run=is_dry_run, log_path=log_file)
                    flash('✅ Size-based segregation completed.', 'success')
                    summary_data['segregate_by_size'] = {'log_file': os.path.basename(log_file)}
                except Exception as e:
                    flash(f'❌ Error in size segregation: {e}', 'danger')

            if 'move_long_videos' in operations:
                try:
                    log_file = os.path.join(LOG_DIR, f'video_log_{timestamp}.txt')
                    asyncio.run(find_and_move_long_videos(folder_path, dry_run=is_dry_run, log_path=log_file))
                    flash('✅ Long video segregation completed.', 'success')
                    summary_data['move_long_videos'] = {'log_file': os.path.basename(log_file)}
                except Exception as e:
                    flash(f'❌ Error in long video segregation: {e}', 'danger')

            if 'rename_files' in operations:
                try:
                    log_file = os.path.join(LOG_DIR, f'rename_ext_log_{timestamp}.txt')
                    rename_files(folder_path, dry_run=is_dry_run, log_path=log_file)
                    flash('✅ Extension-based renaming completed.', 'success')
                    summary_data['rename_files'] = {'log_file': os.path.basename(log_file)}
                except Exception as e:
                    flash(f'❌ Error in renaming files: {e}', 'danger')

            if 'smart_rename' in operations:
                try:
                    log_file = os.path.join(LOG_DIR, f'smart_rename_log_{timestamp}.txt')
                    rename_files_in_folder(folder_path, dry_run=is_dry_run, log_path=log_file)
                    flash('✅ Smart renaming completed.', 'success')
                    summary_data['smart_rename'] = {'log_file': os.path.basename(log_file)}
                except Exception as e:
                    flash(f'❌ Error during smart renaming: {e}', 'danger')

            if 'process_movies' in operations:
                try:
                    log_file = os.path.join(LOG_DIR, f'smart_rename_log_{timestamp}.txt')
                    process_movies(folder_path)
                    flash('✅ Smart renaming completed.', 'success')
                    summary_data['process_movies'] = {'log_file': os.path.basename(log_file)}
                except Exception as e:
                    flash(f'❌ Error during smart renaming: {e}', 'danger')

            if 'sort_move_files' in operations:
                try:
                    log_file = os.path.join(LOG_DIR, f'sort_move_log_{timestamp}.txt')
                    destination_mode = request.form.get('destination_mode', '2')
                    custom_dest_path = request.form.get('custom_dest_path', '')
                    
                    # For mode 3, validate custom destination path
                    dest_path = custom_dest_path if destination_mode == '3' else None
                    
                    result = sort_move_files(
                        folder_path, 
                        destination_mode, 
                        dest_path=dest_path,
                        dry_run=is_dry_run, 
                        log_path=log_file
                    )
                    flash(
                        f"✅ Sort & Move by extension completed. {result['moved_total']} moved, {result['skipped_total']} skipped.",
                        'success'
                    )
                    summary_data['sort_move_files'] = {'log_file': os.path.basename(log_file)}
                except Exception as e:
                    flash(f'❌ Error in sort & move files: {e}', 'danger')

            if 'modify_image_dates' in operations:
                try:
                    target_date = request.form.get('target_date')
                    if not target_date:
                        flash("❌ Please select a target date for image modification.", "warning")
                    else:
                        log_file = os.path.join(LOG_DIR, f'date_mod_log_{timestamp}.txt')
                        result = asyncio.run(modify_image_dates(folder_path, target_date, dry_run=is_dry_run, log_path=log_file))
                        flash(
                            f"✅ Date modification done. {result['moved_total']} processed, {result['skipped_total']} failed.",
                            'success'
                        )
                        summary_data['modify_image_dates'] = {'log_file': os.path.basename(log_file)}
                except Exception as e:
                    flash(f'❌ Error in date modification: {e}', 'danger')

            if 'download_playlist' in operations:
                try:
                    playlist_url = request.form.get('playlist_url')
                    resolution = request.form.get('playlist_resolution', '1080p')
                    
                    if not playlist_url:
                        flash("❌ Please enter a playlist URL.", "warning")
                    else:
                        log_file = os.path.join(LOG_DIR, f'playlist_log_{timestamp}.txt')
                        # Note: This might timeout for very large playlists if not async-detached, 
                        # but follows current pattern.
                        result = asyncio.run(download_playlist(playlist_url, folder_path, resolution, log_path=log_file))
                        
                        if result.get('error'):
                             flash(f"{result['error']}", 'danger')
                        else:
                             flash(f"✅ Playlist download task finished. Check logs.", 'success')
                        
                        summary_data['download_playlist'] = {'log_file': os.path.basename(log_file)}
                except Exception as e:
                    flash(f'❌ Error in playlist download: {e}', 'danger')

            if 'backup_git_work' in operations:
                try:
                    log_file = os.path.join(LOG_DIR, f'git_backup_log_{timestamp}.txt')
                    result = asyncio.run(backup_git_work(folder_path, log_path=log_file))
                    
                    if result.get('error'):
                         flash(f"{result['error']}", 'danger')
                    else:
                         flash(f"✅ Git Backup completed. {result['moved_total']} files backed up.", 'success')
                    
                    summary_data['backup_git_work'] = {'log_file': os.path.basename(log_file)}
                except Exception as e:
                    flash(f'❌ Error in Git backup: {e}', 'danger')

            if 'organize_media' in operations:
                try:
                    log_file = os.path.join(LOG_DIR, f'media_organizer_log_{timestamp}.txt')
                    result = asyncio.run(organize_media(folder_path, dry_run=is_dry_run, log_path=log_file))
                    flash(f"✅ Media organization completed. Check logs for details.", 'success')
                    summary_data['organize_media'] = {'log_file': os.path.basename(log_file)}
                except Exception as e:
                    flash(f'❌ Error in media organization: {e}', 'danger')

            if 'scrape_images' in operations:
                try:
                    urls_text = request.form.get('scraper_urls', '')
                    use_dynamic = request.form.get('scraper_dynamic') == 'yes'
                    
                    if not urls_text.strip():
                        flash("❌ No URLs provided for scraping.", "warning")
                    else:
                        urls = urls_text.splitlines()
                        log_file = os.path.join(LOG_DIR, f'scraper_log_{timestamp}.txt')
                        
                        # Run the task
                        result = asyncio.run(scrape_images_task(urls, folder_path, use_dynamic=use_dynamic, log_path=log_file))
                        
                        flash(f"✅ Scraping finished. Processed {result['total_processed']} URLs.", 'success')
                        summary_data['scrape_images'] = {'log_file': os.path.basename(log_file)}

                except Exception as e:
                    flash(f'❌ Error in image scraper: {e}', 'danger')

            if 'extract_text' in operations:
                try:
                     log_file = os.path.join(LOG_DIR, f'ocr_log_{timestamp}.txt')
                     # Allow folder_path to be a file path for this op
                     result = asyncio.run(extract_text_task(folder_path, dry_run=is_dry_run, log_path=log_file))
                     flash(f"✅ OCR completed. Processed {result['processed']} images.", 'success')
                     summary_data['extract_text'] = {'log_file': os.path.basename(log_file)}
                except EnvironmentError as e:
                    flash(f"❌ Dependency Error: {e}", 'danger')
                except Exception as e:
                    flash(f"❌ Error in OCR: {e}", 'danger')

    return render_template('index.html', summary_data=summary_data)


@app.route('/select_folder')
def select_folder():
    try:
        # Open directory dialog
        cmd = [sys.executable, "-c", "import tkinter as tk; from tkinter import filedialog; root = tk.Tk(); root.withdraw(); print(filedialog.askdirectory())"]
        path = subprocess.check_output(cmd).decode('utf-8').strip()
        return {"path": path}
    except Exception as e:
        return {"error": str(e)}

@app.route('/select_file')
def select_file():
    try:
        # Open file dialog
        cmd = [sys.executable, "-c", "import tkinter as tk; from tkinter import filedialog; root = tk.Tk(); root.withdraw(); print(filedialog.askopenfilename())"]
        path = subprocess.check_output(cmd).decode('utf-8').strip()
        return {"path": path}
    except Exception as e:
        return {"error": str(e)}


@app.route('/download_log/<logname>')
def download_log(logname):
    log_path = os.path.join(LOG_DIR, logname)
    if os.path.exists(log_path):
        return send_file(log_path, as_attachment=True)
    else:
        flash("❌ Log file not found.", "danger")
        return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(debug=True)
