
import os
import time
import concurrent.futures
from PIL import Image
from pathlib import Path
import asyncio

# Supported image formats
VALID_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.bmp', '.tiff')


def compress_image(input_path, output_path, quality=85, max_size=(1920, 1080)):
    """
    Compress a single image with near-lossless quality and save it to the output path.
    """
    try:
        # Open the image
        with Image.open(input_path) as img:
            # Convert to RGB if needed (JPEG doesn't support RGBA)
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')

            # Resize while maintaining aspect ratio
            img.thumbnail(max_size, Image.Resampling.LANCZOS)

            # Ensure output directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            # Save compressed image with higher quality
            img.save(output_path, 'JPEG', quality=quality, optimize=True)
            return True, f"Compressed: {os.path.basename(input_path)} -> {os.path.basename(output_path)}"

    except Exception as e:
        return False, f"Error compressing {input_path}: {str(e)}"


def process_images_sync(input_folder, output_folder, quality=85, max_size=(1920, 1080), max_workers=4, log_lines=None):
    """
    Process all images in the input folder using multiple threads.
    Returns a dict with statistics.
    """
    if log_lines is None:
        log_lines = []

    # Convert to Path objects
    input_folder = Path(input_folder)
    output_folder = Path(output_folder)

    if not input_folder.exists():
        msg = f"Error: Input folder '{input_folder}' does not exist"
        log_lines.append(msg)
        return {'moved_total': 0, 'skipped_total': 0, 'errors': 1}

    # Collect all image files
    image_files = []
    for root, _, files in os.walk(input_folder):
        for file in files:
            if file.lower().endswith(VALID_EXTENSIONS):
                input_path = os.path.join(root, file)
                # Create relative path for output to maintain structure if needed, 
                # or just flat? User's script did relative path structure.
                rel_path = os.path.relpath(input_path, input_folder)
                output_path = output_folder / rel_path
                output_path = output_path.with_suffix('.jpg')
                image_files.append((input_path, output_path))

    if not image_files:
        log_lines.append("No images found to compress.")
        return {'moved_total': 0, 'skipped_total': 0}

    log_lines.append(f"Found {len(image_files)} images to compress.")
    
    start_time = time.time()
    success_count = 0
    error_count = 0

    # Use ThreadPoolExecutor for parallel processing
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(compress_image, input_path, output_path, quality, max_size): input_path
            for input_path, output_path in image_files
        }

        for future in concurrent.futures.as_completed(futures):
            success, msg = future.result()
            log_lines.append(msg)
            if success:
                success_count += 1
            else:
                error_count += 1

    end_time = time.time()
    duration = end_time - start_time
    log_lines.append(f"\nCompression completed in {duration:.2f} seconds")
    
    return {
        'moved_total': success_count, # Using 'moved_total' to map to the UI's expectation of 'files processed'
        'skipped_total': error_count
    }


async def compress_images_in_folder(input_folder, dry_run=False, log_path=None):
    """
    Async wrapper for the image compression logic.
    """
    input_path = Path(input_folder).resolve()
    # Create an output folder named "Compressed_Images" inside the input folder
    output_path = input_path / "Compressed_Images"
    
    log_lines = [f"Starting image compression in: {input_folder}", f"Output: {output_path}"]

    if dry_run:
        log_lines.append("[Dry Run] Would compress images...")
        # Just count potential files
        count = 0
        for root, _, files in os.walk(input_path):
            for file in files:
                if file.lower().endswith(VALID_EXTENSIONS):
                    count += 1
        log_lines.append(f"Found {count} images eligible for compression.")
        
        if log_path:
            with open(log_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(log_lines))
        
        return {'moved_total': count, 'skipped_total': 0}

    loop = asyncio.get_event_loop()
    # Run the blocking sync function in an executor
    result = await loop.run_in_executor(
        None, 
        process_images_sync, 
        input_path, 
        output_path, 
        85, 
        (1920, 1080), 
        4, 
        log_lines
    )

    if log_path:
        with open(log_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(log_lines))

    return result

if __name__ == "__main__":
    # Allow running directly for testing
    folder = input("Enter input folder: ").strip()
    out = input("Enter output folder: ").strip()
    res = process_images_sync(folder, out, log_lines=[])
    print(res)
