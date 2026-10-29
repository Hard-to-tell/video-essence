"""Portable runtime settings; environment overrides are optional."""
import os
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parent
PYTHON = os.environ.get('VIDEO_ESSENCE_PYTHON', sys.executable)
MODEL = os.environ.get('VIDEO_ESSENCE_MODEL_DIR', str(ROOT/'models/large-v3-turbo'))
FFMPEG_DIR = os.environ.get('VIDEO_ESSENCE_FFMPEG_DIR', '')

def media_tool(name):
    suffix = '.exe' if os.name == 'nt' else ''
    if FFMPEG_DIR:
        return str(Path(FFMPEG_DIR)/(name+suffix))
    candidate = Path(sys.prefix)/'Library/bin'/(name+suffix)
    return str(candidate) if candidate.is_file() else (shutil.which(name) or name)
