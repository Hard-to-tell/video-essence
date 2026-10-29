import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import runtime_config

class RuntimeTests(unittest.TestCase):
    def test_explicit_ffmpeg_directory_handles_spaces(self):
        with tempfile.TemporaryDirectory(prefix='media tools ') as directory:
            with patch.object(runtime_config,'FFMPEG_DIR',directory):
                expected = Path(directory)/('ffprobe.exe' if os.name=='nt' else 'ffprobe')
                self.assertEqual(runtime_config.media_tool('ffprobe'),str(expected))

    def test_path_discovery(self):
        with patch.object(runtime_config,'FFMPEG_DIR',''), patch('runtime_config.Path.is_file',return_value=False), patch('runtime_config.shutil.which',return_value='/tools/ffmpeg'):
            self.assertEqual(runtime_config.media_tool('ffmpeg'),'/tools/ffmpeg')

if __name__ == '__main__': unittest.main()
