import os
import sys
import subprocess
from flask import Flask, render_template, request, flash, send_file, redirect, url_for, send_from_directory, session, jsonify

# Services & Utils
from utils.file_cleanup import start_cleanup_thread
from services.operations import OperationService

app = Flask(__name__)
app.secret_key = 'abcde'

# Config
LOG_DIR = os.path.join(os.getcwd(), 'logs')
TEMP_DIR = os.path.join(os.getcwd(), 'temp_downloads')
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

# Start Background Cleanup
start_cleanup_thread(TEMP_DIR)

# Initialize Service
operation_service = OperationService(LOG_DIR, TEMP_DIR)

@app.route('/', methods=['GET', 'POST'])
def index():
    summary_data = session.pop('summary_data', {})

    if request.method == 'POST':
        folder_path = request.form.get('folder_path')
        operations = request.form.getlist('operations')
        is_dry_run = request.form.get('dry_run') == 'yes'
        
        print("Running operations:", operations, "DryRun:", is_dry_run)

        # Smart Validation Logic
        URL_ONLY_OPERATIONS = {'scrape_images', 'download_playlist'}
        FILE_OR_DIR_OPERATIONS = {'extract_text'}
        has_source_ops = any(op not in URL_ONLY_OPERATIONS for op in operations)

        # Default path logic for URL operations if empty
        if not folder_path and not has_source_ops and operations:
            folder_path = os.path.join(os.getcwd(), 'downloads')
            flash(f"ℹ️ No path provided. Defaulting to: {folder_path}", 'info')

        # Basic path validation
        if not folder_path and has_source_ops:
             flash('❌ Please enter a valid path.', 'danger')
             operations = [] # Skip
        elif folder_path and not os.path.exists(folder_path):
             if not has_source_ops and operations:
                try:
                    os.makedirs(folder_path, exist_ok=True)
                    flash(f"✅ Created output directory: {folder_path}", 'success')
                except Exception as e:
                    flash(f"❌ Could not create directory: {e}", 'danger')
                    operations = []
             else:
                flash('❌ Target path does not exist.', 'danger')
                operations = []

        # Execute Operations
        if operations:
            for op in operations:
                try:
                    success_msg, summary_entry = operation_service.execute(op, folder_path, request.form, is_dry_run)
                    if success_msg:
                        flash(success_msg, 'success' if 'Error' not in success_msg else 'danger')
                    if summary_entry:
                        summary_data[op] = summary_entry
                except Exception as e:
                    flash(f"❌ Error in {op}: {e}", 'danger')
            
            session['summary_data'] = summary_data
            return redirect(url_for('index'))
        elif not operations and request.method == 'POST':
             # Only show warning if no ops were valid/selected (and we didn't just fail validation)
             if not flash: 
                 flash('❌ Please select an operation.', 'warning')

    return render_template('index.html', summary_data=summary_data)


@app.route('/select_folder')
def select_folder():
    try:
        cmd = [sys.executable, "-c", "import tkinter as tk; from tkinter import filedialog; root = tk.Tk(); root.withdraw(); print(filedialog.askdirectory())"]
        path = subprocess.check_output(cmd).decode('utf-8').strip()
        return {"path": path}
    except Exception as e:
        return {"error": str(e)}

@app.route('/select_file')
def select_file():
    try:
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


@app.route('/download_file/<filename>')
def download_file(filename):
    """Serves files from the temp_downloads directory."""
    try:
        safe_name = os.path.basename(filename)
        return send_from_directory(TEMP_DIR, safe_name, as_attachment=True)
    except Exception as e:
        return str(e), 404

@app.route('/api/logs', methods=['GET'])
def list_logs():
    """Lists recent log files (newest first)."""
    try:
        logs = sorted(
            [f for f in os.listdir(LOG_DIR) if f.endswith('.txt')],
            key=lambda x: os.path.getmtime(os.path.join(LOG_DIR, x)),
            reverse=True
        )
        return jsonify({'logs': logs})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/logs/content/<logname>', methods=['GET'])
def get_log_content(logname):
    """Returns content of a specific log file."""
    try:
        log_path = os.path.join(LOG_DIR, logname)
        if not os.path.exists(log_path):
            return jsonify({'error': 'Log not found'}), 404
            
        with open(log_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return jsonify({'content': content})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/logs/delete/<logname>', methods=['DELETE'])
def delete_log(logname):
    try:
        log_path = os.path.join(LOG_DIR, logname)
        if os.path.exists(log_path):
            os.remove(log_path)
            return jsonify({'status': 'success', 'message': f'Deleted {logname}'})
        else:
            return jsonify({'status': 'error', 'message': 'Log file not found'}), 404
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
