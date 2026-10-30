import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from state_storage import state_path


class LibraryMigrationTests(unittest.TestCase):
    def test_installations_share_merged_history_and_preserve_originals(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            old, new = base/'bili-summary', base/'video-essence'
            for root, ids in [(old, ['old']), (new, ['new'])]:
                (root/'data').mkdir(parents=True)
                (root/'data/state.json').write_text(json.dumps({'settings': {}, 'batches': [
                    {'id': id, 'items': [{'status': 'done', 'summary': {'one_line': id}}]}
                    for id in ids]}), encoding='utf-8')
            original = (old/'data/state.json').read_bytes()
            with patch.dict('os.environ', {'VIDEO_ESSENCE_DATA_DIR': str(base/'shared')}):
                target = state_path(new)
                self.assertEqual(target, state_path(old))
                self.assertEqual({b['id'] for b in json.loads(target.read_text())['batches']}, {'old', 'new'})
                saved = target.read_bytes()
                self.assertEqual(state_path(new).read_bytes(), saved)
            self.assertEqual((old/'data/state.json').read_bytes(), original)

    def test_invalid_old_library_is_not_silently_replaced(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)/'app'
            (root/'data').mkdir(parents=True)
            (root/'data/state.json').write_text('{broken', encoding='utf-8')
            with patch.dict('os.environ', {'VIDEO_ESSENCE_DATA_DIR': str(Path(directory)/'shared')}):
                with self.assertRaises(json.JSONDecodeError):
                    state_path(root)
