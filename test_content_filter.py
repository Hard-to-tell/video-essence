import copy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).parent/'app'))
from backend import Store
from content_filter import skip_reason

class FilterTests(unittest.TestCase):
    def test_live_tags_cover_long_and_short_clips(self):
        for tag,duration in [('直播录像',183),('直播切片',2001)]:
            self.assertIn('直播',skip_reason({'title':'reaction','tags':[tag],'duration':duration}))

    def test_short_entertainment_but_not_technical_video(self):
        self.assertIn('短娱乐',skip_reason({'title':'搞笑片段','tags':['搞笑'],'duration':120}))
        for meta in [{'title':'RNN递归神经网络是什么','tags':['学习'],'duration':500},
                     {'title':'直播推流技术教程','tags':['直播录像'],'duration':500},
                     {'title':'搞笑的神经网络原理','tags':['搞笑'],'duration':500}]:
            self.assertIsNone(skip_reason(meta))

    def test_bulk_skips_before_media_and_explicit_requests_override(self):
        with tempfile.TemporaryDirectory() as td:
            store=Store(Path(td)/'state.json')
            with patch('backend.BiliClient') as client:
                client.return_value.api.return_value={'list':[{'bvid':'BV1GKinBiEhJ','add_at':1}]}
                store.create({'kind':'watch_later'})
            id,run=store.tasks.get_nowait()
            item=store.claim(id,run)
            meta={'title':'直播片段','tags':['直播切片'],'duration':2001}
            with patch('backend.content_metadata',return_value=meta),patch('backend.subprocess.Popen') as media:
                self.assertTrue(store.skip_by_metadata(item,run))
                self.assertEqual(store.find(id)['status'],'skipped')
                media.assert_not_called()
            store.action(id,'summarize')
            id,run=store.tasks.get_nowait(); item=store.claim(id,run)
            with patch('backend.content_metadata') as fetch:
                self.assertFalse(store.skip_by_metadata(item,run))
                fetch.assert_not_called()
            store.create({'kind':'links','links':['BV1GKinBiEhJ']})
            id,run=store.tasks.get_nowait(); item=store.claim(id,run)
            self.assertTrue(item['explicit_request'])
            with patch('backend.content_metadata') as fetch:
                self.assertFalse(store.skip_by_metadata(item,run))
                fetch.assert_not_called()

    def test_disabled_filter_does_not_read_metadata(self):
        with tempfile.TemporaryDirectory() as td:
            store=Store(Path(td)/'state.json')
            store.create({'kind':'links','links':['BV1GKinBiEhJ']})
            id,run=store.tasks.get_nowait(); item=store.claim(id,run)
            item=copy.deepcopy(item); item['explicit_request']=False
            item['settings']['skip_rules']['live_entertainment']=False
            with patch('backend.content_metadata') as fetch:
                self.assertFalse(store.skip_by_metadata(item,run))
                fetch.assert_not_called()

if __name__ == '__main__': unittest.main()
