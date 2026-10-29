import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).parent/'app'))
from backend import Store
from asr_chunks import transcribe


class QueueTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.store=Store(Path(self.temp.name)/'state.json')
        self.store.create({'kind':'links','links':['BV1GKinBiEhJ']})
        self.id,self.run=self.store.tasks.get_nowait()

    def tearDown(self): self.temp.cleanup()

    def test_cancel_retry_invalidates_old_queue_entry(self):
        self.store.action(self.id,'cancel'); self.store.action(self.id,'retry')
        self.assertIsNone(self.store.claim(self.id,self.run))
        fresh=self.store.tasks.get_nowait()
        self.assertIsNotNone(self.store.claim(*fresh))
        self.assertIsNone(self.store.claim(*fresh))

    def test_stale_worker_cannot_overwrite_retry(self):
        self.store.claim(self.id,self.run)
        self.store.action(self.id,'cancel'); self.store.action(self.id,'retry')
        self.assertFalse(self.store.update_run(self.id,self.run,status='done'))
        self.assertEqual(self.store.find(self.id)['status'],'queued')

    def test_restart_preserves_done_and_marks_interrupted(self):
        self.store.claim(self.id,self.run)
        loaded=Store(self.store.path)
        self.assertEqual(loaded.find(self.id)['status'],'failed')
        self.assertIn('重试',loaded.find(self.id)['error'])

    def test_prompt_honors_count_and_skip_preference(self):
        rows=[{'bvid':'BV1GKinBiEhJ','add_at':1},{'bvid':'BV1iiLj62Egz','add_at':2}]
        with patch('backend.BiliClient') as client:
            client.return_value.api.return_value={'list':rows}
            self.store.create({'kind':'prompt','prompt':'总结B站最近稍后再看的一条，不要跳过','platform':'douyin','limit':10})
        batch=self.store.batches()[0]
        self.assertEqual(batch['total'],1)
        self.assertEqual(batch['items'][0]['url'],'https://www.bilibili.com/video/BV1iiLj62Egz/')
        self.assertFalse(batch['auto_skip'])

    def test_douyin_watch_later_uses_real_adapter_and_limit(self):
        with patch('douyin_api.DouyinClient') as client:
            client.return_value.watch_later.return_value=[{'aweme_id':'7695743028656476297'}]
            self.store.create({'kind':'prompt','prompt':'总结抖音稍后再看最近1条'})
            client.return_value.watch_later.assert_called_once_with(1)
        batch=self.store.batches()[0]
        self.assertEqual(batch['title'],'抖音稍后再看')
        self.assertEqual(batch['items'][0]['platform'],'douyin')


class ChunkTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name); self.audio=self.root/'audio.wav'
        self.audio.write_bytes(b'fake audio fixture')
        self.args=SimpleNamespace(output_dir=str(self.root),lang=None,chunk_minutes=1,device='auto')

    def tearDown(self): self.temp.cleanup()

    def run_asr(self,model,duration=120):
        def process(cmd,**kw):
            return SimpleNamespace(stdout=json.dumps({'format':{'duration':duration}}).encode())
        with patch.dict(sys.modules,{'faster_whisper':SimpleNamespace(WhisperModel=model)}),patch('asr_chunks.subprocess.run',side_effect=process):
            return transcribe(self.audio,self.args,self.root/'model',self.root,lambda s:bool(s.strip()))[1]

    def test_resume_keeps_completed_interval(self):
        calls=[]
        class FailSecond:
            def __init__(self,*a,**kw): pass
            def transcribe(self,*a,**kw):
                calls.append(1)
                if len(calls)==2: raise RuntimeError('network-like non GPU failure')
                return iter([SimpleNamespace(start=2,end=4,text='first')]),None
        with self.assertRaises(RuntimeError): self.run_asr(FailSecond)
        self.assertEqual(len(list(self.root.glob('.chunks/*/*.json'))),1)
        calls.clear()
        class Resume:
            def __init__(self,*a,**kw): pass
            def transcribe(self,*a,**kw):
                calls.append(1)
                return iter([SimpleNamespace(start=2,end=4,text='second')]),None
        result=self.run_asr(Resume)
        self.assertEqual(len(calls),1)
        self.assertEqual([s[2] for s in result],['first','second'])
        self.assertEqual(result[1][0],61)

    def test_gpu_oom_shrinks_then_falls_back(self):
        devices=[]
        class OOM:
            def __init__(self,*a,device,**kw): self.device=device; devices.append(device)
            def transcribe(self,*a,**kw):
                if self.device=='cuda': raise RuntimeError('CUDA out of memory')
                return iter([SimpleNamespace(start=2,end=4,text='CPU result')]),None
        self.args.chunk_minutes=2
        result=self.run_asr(OOM)
        self.assertEqual(devices,['cuda','cuda','cpu'])
        self.assertEqual(len(result),2)
        self.assertEqual(len(list(self.root.glob('.chunks/*/*.json'))),3)

    def test_fallback_releases_iterator_and_failed_model(self):
        import weakref
        live=weakref.WeakSet()
        class RetainedIterator:
            def __init__(self,owner): self.owner=owner
            def __iter__(self): return self
            def __next__(self): raise RuntimeError('CUDA out of memory')
        case=self
        class Model:
            def __init__(self,*a,device,**kw):
                if device=='cpu': case.assertFalse(any(m.device=='cuda' for m in live))
                self.device=device; live.add(self)
            def transcribe(self,*a,**kw):
                if self.device=='cuda': return RetainedIterator(self),None
                return iter([SimpleNamespace(start=2,end=4,text='recovered')]),None
        self.assertEqual(self.run_asr(Model,duration=30)[0][2],'recovered')


if __name__=='__main__': unittest.main()
