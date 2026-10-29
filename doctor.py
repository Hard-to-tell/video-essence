"""Read-only installation check; never loads account files."""
import importlib.util
from pathlib import Path
import shutil
import sys
from runtime_config import MODEL, media_tool

def main():
    checks = {name: importlib.util.find_spec(name) is not None
              for name in ('faster_whisper', 'yt_dlp', 'PIL', 'qrcode')}
    checks.update({name: bool(shutil.which(media_tool(name))) for name in ('ffmpeg','ffprobe')})
    checks['Whisper model'] = (Path(MODEL)/'model.bin').is_file()
    for name, ok in checks.items():
        print(f'{"OK" if ok else "MISSING"}: {name}')
    sys.path.insert(0,str(Path(__file__).parent/'app'))
    from summary_engine import executable
    try:
        executable()
        print('OK: Codex executable (login/model access not checked)')
    except RuntimeError:
        print('OPTIONAL: Codex CLI missing; needed for app summaries, not inline skill summaries')
    return 0 if all(checks.values()) else 1

if __name__ == '__main__':
    raise SystemExit(main())
