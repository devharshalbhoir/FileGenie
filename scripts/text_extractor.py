
import os
import pytesseract
from PIL import Image
from docx import Document
import logging

# Define supported image extensions
OCR_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp'}

def setup_logger(log_path):
    logger = logging.getLogger('TextExtractor')
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.FileHandler(log_path, encoding='utf-8')
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger

def configure_tesseract(logger=None):
    """
    Attempts to find Tesseract executable in common Windows paths 
    if not already in PATH.
    """
    # 1. Check PATH via shutil (standard check)
    import shutil
    if shutil.which("tesseract"):
        return True

    # 2. Check Standard Windows Installation Paths
    possible_paths = []
    
    # Program Files
    prog_files = os.environ.get("ProgramFiles", r"C:\Program Files")
    possible_paths.append(os.path.join(prog_files, "Tesseract-OCR", "tesseract.exe"))
    
    # Program Files (x86)
    prog_files_x86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    possible_paths.append(os.path.join(prog_files_x86, "Tesseract-OCR", "tesseract.exe"))
    
    # Local App Data (User specific install)
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        possible_paths.append(os.path.join(local_app_data, "Tesseract-OCR", "tesseract.exe"))
        possible_paths.append(os.path.join(local_app_data, "Programs", "Tesseract-OCR", "tesseract.exe"))

    if logger:
        logger.info(f"Searching for Tesseract in: {possible_paths}")
    
    for path in possible_paths:
        if os.path.exists(path):
            pytesseract.pytesseract.tesseract_cmd = path
            if logger:
                logger.info(f"✅ Tesseract found at: {path}")
            return True
            
    return False

def process_single_image(image_path, output_format='docx', logger=None):
    try:
        if logger:
            logger.info(f"Processing image: {image_path}")
        
        # Open image
        img = Image.open(image_path)
        
        # Extract Text
        text = pytesseract.image_to_string(img)
        
        if not text.strip():
            if logger:
                logger.warning(f"No text found in {image_path}")
            return False

        # Prepare output path
        base_name = os.path.splitext(image_path)[0]
        
        if output_format == 'docx':
            doc = Document()
            doc.add_paragraph(text)
            output_path = f"{base_name}_OCR.docx"
            doc.save(output_path)
        else:
            output_path = f"{base_name}_OCR.txt"
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(text)
                
        if logger:
            logger.info(f"Saved text to: {output_path}")
        return True

    except pytesseract.TesseractNotFoundError:
        msg = "Tesseract OCR binary not found. Please install Tesseract."
        if logger:
            logger.error(msg)
        raise EnvironmentError(msg)
    except Exception as e:
        if logger:
            logger.error(f"Failed to process {image_path}: {e}")
        return False

async def extract_text_task(target_path, output_format='docx', dry_run=False, log_path=None):
    """
    Extracts text from an image file or all images in a folder.
    """
    logger = setup_logger(log_path) if log_path else None
    
    if logger:
        logger.info(f"Starting OCR task on: {target_path}")
        logger.info(f"Dry Run: {dry_run}")
    
    # Configure Tesseract
    if not configure_tesseract(logger):
        msg = "Tesseract OCR binary not found. Please install Tesseract from https://github.com/UB-Mannheim/tesseract/wiki"
        if logger:
            logger.critical(msg)
        raise EnvironmentError(msg)
        
    results = {'processed': 0, 'failed': 0}

    # Identify files to process
    files_to_process = []
    if os.path.isfile(target_path):
        ext = os.path.splitext(target_path)[1].lower()
        if ext in OCR_IMAGE_EXTENSIONS:
            files_to_process.append(target_path)
    elif os.path.isdir(target_path):
        for root, _, files in os.walk(target_path):
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in OCR_IMAGE_EXTENSIONS:
                    files_to_process.append(os.path.join(root, file))
    
    if not files_to_process:
        if logger:
            logger.warning("No valid images found to process.")
        return results

    if dry_run:
        if logger:
            logger.info(f"[Dry Run] Would process {len(files_to_process)} images:")
            for f in files_to_process:
                logger.info(f"  - {f}")
        return {'processed': len(files_to_process), 'failed': 0}

    # Process files
    results['generated_files'] = []
    for file_path in files_to_process:
        try:
            output_path = process_single_image(file_path, output_format, logger)
            if output_path:
                results['processed'] += 1
                results['generated_files'].append(output_path)
            else:
                results['failed'] += 1
        except EnvironmentError as e:
             # Stop completely if Tesseract is missing
             if logger:
                 logger.critical(str(e))
             raise e
        except Exception:
            results['failed'] += 1
            
    return results
