"""Keep the personal library outside replaceable application checkouts."""
import json
import os
from pathlib import Path


def state_path(root):
    root = Path(root)
    base = Path(os.environ.get('VIDEO_ESSENCE_DATA_DIR') or
                (Path(os.environ.get('LOCALAPPDATA') or Path.home()/'.local/share')/'VideoEssence'))
    target = base/'state.json'
    if target.exists():
        return target
    # Import previous installations once; leave their original files intact.
    candidates = [root/'data/state.json'] + [
        root.parent/name/'data/state.json' for name in ('bili-summary', 'video-essence')]
    documents = []
    for source in dict.fromkeys(candidates):
        if source.is_file():
            data = json.loads(source.read_text(encoding='utf-8'))
            if not isinstance(data.get('batches'), list) or not isinstance(data.get('settings'), dict):
                raise ValueError(f'旧总结库格式不正确，请检查：{source}')
            documents.append(data)
    if documents:
        primary = max(documents, key=lambda d: sum(len(b['items']) for b in d['batches']))
        merged = dict(primary)
        batches = {}
        for document in [primary] + documents:
            for batch in document['batches']:
                batches.setdefault(batch['id'], batch)
        merged['batches'] = sorted(batches.values(), key=lambda b: b.get('created_at', ''), reverse=True)
        base.mkdir(parents=True, exist_ok=True)
        # Exclusive creation avoids replacing a library another instance just created.
        try:
            with target.open('x', encoding='utf-8') as handle:
                json.dump(merged, handle, ensure_ascii=False, indent=2)
        except FileExistsError:
            pass
    return target
