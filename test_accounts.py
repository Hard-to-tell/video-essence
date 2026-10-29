from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).parent/'app'))
from account_login import import_douyin_cookies


class ImportTests(unittest.TestCase):
    def test_filters_other_sites_and_preserves_old_on_error(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'cookies.txt'
            data='# Netscape HTTP Cookie File\n.douyin.com\tTRUE\t/\tTRUE\t0\tsessionid\tsynthetic-test\n.example.com\tTRUE\t/\tTRUE\t0\tsecret\tunrelated\n'
            self.assertTrue(import_douyin_cookies(data,path)['ok'])
            saved=path.read_text(); self.assertIn('douyin.com',saved); self.assertNotIn('example.com',saved)
            with self.assertRaises(ValueError): import_douyin_cookies('not a cookie file',path)
            self.assertEqual(path.read_text(),saved)

    def test_reject_expired_or_fake_domain(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'cookies.txt'
            for domain,expiry in [('.douyin.com',1),('.evildouyin.com',0)]:
                data=f'# Netscape HTTP Cookie File\n{domain}\tTRUE\t/\tTRUE\t{expiry}\tsessionid\tsynthetic\n'
                with self.assertRaises(ValueError): import_douyin_cookies(data,path)
                self.assertFalse(path.exists())


if __name__=='__main__': unittest.main()
