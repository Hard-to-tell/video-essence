"""B站官方扫码流程；凭证仅留在本机CookieJar。"""
import base64
import http.cookiejar
import io
import json
import os
from pathlib import Path
import sys
import threading
import time
import urllib.parse
import urllib.request
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'vendor'))


def import_douyin_cookies(text,destination=None):
    """只接收用户在本机选择的Netscape文件，不返回其中的凭证。"""
    if not isinstance(text,str) or len(text)>200000:
        raise ValueError('登录文件必须是小于200KB的Netscape文本文件')
    destination=Path(destination or ROOT/'douyin-cookies.txt')
    with tempfile.TemporaryDirectory(dir=destination.parent) as tmp:
        lines=[]
        for line in text.splitlines():
            fields=line.split('\t')
            if len(fields)==7 and fields[4]=='0':
                fields[4]=''  # 常见导出器以0表示当前浏览器会话。
                line='\t'.join(fields)
            lines.append(line)
        source=Path(tmp)/'cookies.txt'; source.write_text('\n'.join(lines)+'\n',encoding='utf-8')
        jar=http.cookiejar.MozillaCookieJar(str(source))
        try: jar.load(ignore_discard=True,ignore_expires=False)
        except Exception: raise ValueError('无法读取Netscape登录文件；原有登录未改变') from None
        selected=http.cookiejar.MozillaCookieJar()
        for cookie in jar:
            if cookie.domain.lstrip('.')=='douyin.com' or cookie.domain.endswith('.douyin.com'):
                selected.set_cookie(cookie)
        if not any(c.name in ('sessionid','sessionid_ss','sid_tt') and c.value for c in selected):
            raise ValueError('文件没有有效的抖音登录会话，原有登录未改变')
        output=Path(tmp)/'filtered.txt'; selected.save(str(output),ignore_discard=True,ignore_expires=False)
        os.replace(output,destination)
    return {'ok':True,'message':'抖音登录文件已保存到本机。可以提交稍后再看或视频链接，实际请求成功后确认连接有效。'}


class BiliLogin:
    def __init__(self,accounts):
        self.accounts=accounts
        self.lock=threading.Lock()
        self.pending=None

    def start(self):
        import qrcode
        with self.lock:
            if self.pending and time.monotonic()<self.pending['expires']:
                return self.pending['response']
            jar=http.cookiejar.MozillaCookieJar(str(ROOT/'cookies.txt'))
            opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
            def get(path):
                request=urllib.request.Request('https://passport.bilibili.com'+path,headers={'User-Agent':'bili-summary/2.0','Referer':'https://www.bilibili.com/'})
                with opener.open(request,timeout=20) as response: value=json.load(response)
                if value.get('code')!=0: raise RuntimeError('B站登录服务暂不可用')
                return value['data']
            data=get('/x/passport-login/web/qrcode/generate')
            image=io.BytesIO(); qrcode.make(data['url']).save(image,format='PNG')
            response={'ok':True,'message':'请用B站手机App扫码，并在手机上确认登录','qr_image':'data:image/png;base64,'+base64.b64encode(image.getvalue()).decode()}
            pending={'expires':time.monotonic()+180,'response':response}
            self.pending=pending
            def poll():
                try:
                    while time.monotonic()<pending['expires']:
                        time.sleep(2)
                        result=get('/x/passport-login/web/qrcode/poll?'+urllib.parse.urlencode({'qrcode_key':data['qrcode_key']}))
                        code=result.get('code')
                        if code==0:
                            if not any(c.name=='SESSDATA' and c.domain.lstrip('.')=='bilibili.com' for c in jar):
                                raise RuntimeError('登录响应未包含有效凭证')
                            temporary=str(ROOT/'cookies.login.tmp')
                            jar.save(temporary,ignore_discard=True,ignore_expires=True)
                            os.replace(temporary,ROOT/'cookies.txt')
                            self.accounts['bilibili']={'logged_in':True}
                            return
                        if code==86038: return
                except Exception:
                    pass  # 不记录包含扫码key或cookie的异常URL。
                finally:
                    with self.lock:
                        if self.pending is pending: self.pending=None
            threading.Thread(target=poll,daemon=True).start()
            return response
