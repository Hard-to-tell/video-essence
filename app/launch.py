"""双击入口：复用已有服务，等待真正就绪，再打开Edge独立窗口。"""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
URL='http://127.0.0.1:8765/'


def ready():
    try:
        with urllib.request.urlopen(URL+'api/status',timeout=2) as response: data=json.load(response)
        if data.get('application')!='bili-summary': raise RuntimeError('8765端口被其它服务占用，请关闭占用程序后再启动')
        return data.get('backend')=='ready'
    except urllib.error.URLError: return False


def main():
    if not ready():
        logs=ROOT/'data'; logs.mkdir(exist_ok=True)
        with (logs/'server.out.log').open('ab') as out,(logs/'server.err.log').open('ab') as err:
            child=subprocess.Popen([sys.executable,str(ROOT/'app/server.py'),'--no-open'],cwd=ROOT,
                                   stdout=out,stderr=err,env={**os.environ,'PYTHONIOENCODING':'utf-8'},
                                   creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        deadline=time.monotonic()+30
        while not ready():
            if child.poll() is not None: raise RuntimeError('服务启动失败，详情在项目data/server.err.log')
            if time.monotonic()>deadline: raise RuntimeError('服务30秒内未就绪，详情在项目data/server.err.log')
            time.sleep(.3)
    candidates=[Path(os.environ.get(k,''))/'Microsoft/Edge/Application/msedge.exe' for k in ('ProgramFiles(x86)','ProgramFiles','LOCALAPPDATA')]
    edge=next((p for p in candidates if p.is_file()),None)
    if edge is None: raise RuntimeError('未找到Microsoft Edge，请安装后重试')
    subprocess.Popen([str(edge),'--app='+URL,'--window-size=1280,860'])


if __name__=='__main__':
    if '--check' in sys.argv:
        print(ready()); sys.exit()
    try: main()
    except Exception as exc:
        import tkinter
        from tkinter import messagebox
        root=tkinter.Tk(); root.withdraw()
        messagebox.showerror('视频提炼启动失败',str(exc)); root.destroy()
