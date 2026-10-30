"""Editorial changes must invalidate both extraction and merge caches."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent/'app'))
import summary_engine as engine

class SummaryCacheTests(unittest.TestCase):
    def test_policy_change_rebuilds_parts_and_merge(self):
        content = {'title':'test','duration':30,'segments':[
            {'start':0,'end':10,'text':'a'*9000},
            {'start':10,'end':20,'text':'b'*9000}]}
        result = {'verdict':'essence','one_line':'test','points':[],
                  'highlights':[],'audience':'','skip_note':''}
        with tempfile.TemporaryDirectory() as td, patch.object(engine,'ROOT',Path(td)), patch.object(engine,'run_model',side_effect=lambda *a:copy.deepcopy(result)) as model:
            def run(): return engine.summarize(content,{'summary_style':'essence'},lambda *a:None,lambda:False)
            run()
            self.assertEqual(model.call_count,3)  # Two parts and their merge.
            run()
            self.assertEqual(model.call_count,3)
            with patch.object(engine,'POLICY',engine.POLICY+'\nnew editorial policy'):
                run()
            self.assertEqual(model.call_count,6)

if __name__ == '__main__': unittest.main()
