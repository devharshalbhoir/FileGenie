import os
import subprocess
from pathlib import Path


def compress_video(input_file: str, output_file: str, crf: int = 28, preset: str = "medium"):
    """
    Compress a video using ffmpeg.

    Args:
        input_file (str): Path to the input video.
        output_file (str): Path to save the compressed video.
        crf (int): Constant Rate Factor (lower = better quality, bigger size). Recommended 23–28.
        preset (str): Speed/efficiency tradeoff (slower = better compression).
                      Options: ultrafast, superfast, veryfast, faster, fast, medium, slow, slower, veryslow
    """
    try:
        cmd = [
            "ffmpeg", "-i", input_file,
            "-c:v", "libx265", "-crf", str(crf), "-preset", preset,
            "-c:a", "aac", "-b:a", "128k",
            "-y",  # overwrite output if exists
            output_file
        ]
        print(f"⚡ Compressing: {input_file} → {output_file}")
        subprocess.run(cmd, check=True)
        print(f"✅ Done: {output_file}")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error compressing {input_file}: {e}")


def compress_videos_in_folder(input_folder: str, crf: int = 28, preset: str = "medium"):
    """
    Compress all videos in a folder and save them in a 'Compressed' subfolder.
    """
    input_path = Path(input_folder).resolve()
    if not input_path.is_dir():
        raise Exception(f"❌ '{input_path}' is not a valid directory.")

    output_folder = input_path / "Compressed"
    output_folder.mkdir(exist_ok=True)

    video_extensions = {".mp4", ".mkv", ".avi", ".mov", ".flv", ".wmv"}
    files = [f for f in input_path.iterdir() if f.suffix.lower() in video_extensions]

    if not files:
        print("⚠️ No video files found.")
        return

    for file in files:
        output_file = output_folder / file.name
        compress_video(str(file), str(output_file), crf=crf, preset=preset)


if __name__ == "__main__":
    folder = input("Enter the folder path with videos: ").strip()
    try:
        compress_videos_in_folder(folder, crf=28, preset="medium")
    except Exception as e:
        print("❌ Exception occurred:", e)
