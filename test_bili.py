"""针对真实失败模式的回归检查；网络和GPU路线另用真实视频验证。"""
import contextlib
from pathlib import Path
import tempfile
import unittest

from bili import text_overlap
from bili_api import BiliClient, BiliError, meaningful


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.client = BiliClient()
        self.info = {"id": "BV1iiLj62Egz", "aid": 116587893890837, "cid": 38393544757, "duration": 80}

    def player(self, body, **identity):
        self.client.api = lambda *a, **kw: {"bvid": self.info["id"], "cid": self.info["cid"],
                                          "subtitle": {"subtitles": [{"lan": "ai-zh", "subtitle_url": "https://example.test/sub"}]}, **identity}
        self.client.json = lambda *a: {"body": body}

    def test_reject_subtitle_from_longer_video(self):
        self.player([{"from": 1199, "to": 1202, "content": "另一个二十分钟视频"}])
        with self.assertRaisesRegex(BiliError, "时间轴"):
            self.client.subtitles(self.info)

    def test_reject_subtitle_wrong_cid(self):
        self.player([], cid=123)
        with self.assertRaisesRegex(BiliError, "编号不匹配"):
            self.client.subtitles(self.info)

    def test_music_is_not_a_transcript(self):
        self.player([{"from": 7, "to": 9, "content": "♪ 音乐 ♪", "music": 1}])
        self.assertIsNone(self.client.subtitles(self.info))
        self.assertFalse(meaningful("[Music]"))
        self.assertTrue(meaningful("音乐模型可以处理音频"))

    def test_valid_speech_caption_preserved(self):
        self.player([{"from": 1, "to": 4, "content": "从视频恢复三维结构"}])
        self.assertEqual(self.client.subtitles(self.info)[1], [(1.0, 4.0, "从视频恢复三维结构")])

    def test_share_url_keeps_selected_part(self):
        bvid, page = self.client.resolve("[视频](https://www.bilibili.com/video/BV1iiLj62Egz/?p=2\\&spm_id=abc)")
        self.assertEqual((bvid, page), ("BV1iiLj62Egz", 2))

    def test_short_preview_not_accepted(self):
        self.client.api = lambda *a, **kw: {"dash": {"audio": [{"bandwidth": 64000, "baseUrl": "https://example.test/audio"}]}}
        from io import BytesIO
        self.client.open = lambda *a: contextlib.closing(BytesIO(b"test"))
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(BiliError, "短于视频"):
                self.client.download(self.info, Path(tmp), lambda p: 30)

    def test_unrelated_subtitle_fails_audio_comparison(self):
        transcript = "三维高斯使用位置颜色透明度和旋转参数重建场景"
        unrelated = "日本女友今天要不要穿JK去商场逛街"
        self.assertLess(text_overlap(unrelated, transcript), .2)
        self.assertGreater(text_overlap(transcript, "三维高师使用位置颜色透明度和旋转参数重建场景"), .2)

    def test_wrong_longer_media_not_accepted(self):
        self.client.api = lambda *a, **kw: {"dash": {"audio": [{"bandwidth": 64000, "baseUrl": "https://example.test/audio"}]}}
        from io import BytesIO
        self.client.open = lambda *a: contextlib.closing(BytesIO(b"test"))
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(BiliError, "长于视频"):
                self.client.download(self.info, Path(tmp), lambda p: 1200)


if __name__ == "__main__":
    unittest.main()
