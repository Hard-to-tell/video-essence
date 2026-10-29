"""抖音链接→完整媒体→既有分段听写。只使用正常下载接口及用户提供的登录文件。"""
from runtime_config import media_tool
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'vendor'))


def validate_url(value):
    parsed=urlsplit(value.strip())
    if parsed.scheme!='https' or parsed.username or parsed.password:
        raise ValueError('请提供HTTPS抖音视频链接')
    if parsed.hostname=='v.douyin.com' and re.fullmatch(r'/[A-Za-z0-9]+/?',parsed.path): return value.strip()
    if parsed.hostname in ('www.douyin.com','douyin.com') and re.fullmatch(r'/video/\d+/?',parsed.path): return value.strip()
    raise ValueError('请提供抖音视频详情链接或v.douyin.com分享链接')


def main():
    from yt_dlp import YoutubeDL
    ap=argparse.ArgumentParser()
    ap.add_argument('link'); ap.add_argument('--lang',default='auto')
    ap.add_argument('--output-dir',type=Path,default=ROOT/'transcripts')
    ap.add_argument('--chunk-minutes',type=int,default=10); ap.add_argument('--device',default='auto')
    args=ap.parse_args(); url=validate_url(args.link)
    media_dir=args.output_dir/'douyin-media'; media_dir.mkdir(parents=True,exist_ok=True)
    class Logger:
        def debug(self,msg): pass
        def warning(self,msg): self.error(msg)
        def error(self,msg):
            clean=re.sub(r'https?://\S+','[媒体地址]',str(msg))
            print(clean[:300],file=sys.stderr,flush=True)
    last_percent=-1
    def download_progress(event):
        nonlocal last_percent
        total=event.get('total_bytes') or event.get('total_bytes_estimate') or 0
        if event.get('status')=='downloading' and total:
            percent=int(100*event.get('downloaded_bytes',0)/total)
            if percent==last_percent: return
            last_percent=percent
            print(json.dumps({'stage':'content','progress':min(1,event.get('downloaded_bytes',0)/total),
                              'message':f"下载抖音媒体 {event.get('downloaded_bytes',0)/total:.0%}"},ensure_ascii=False),file=sys.stderr,flush=True)
    options={'noplaylist':True,'quiet':True,'logger':Logger(),'socket_timeout':15,'retries':0,'fragment_retries':0,
             'progress_hooks':[download_progress],
             'format':'best[ext=mp4]/best','outtmpl':str(media_dir/'%(id)s.%(ext)s'),
             'ffmpeg_location':media_tool('ffmpeg')}
    cookies=ROOT/'douyin-cookies.txt'
    if cookies.is_file(): options['cookiefile']=str(cookies)
    print('读取抖音视频信息与完整媒体…',file=sys.stderr,flush=True)
    try:
        with YoutubeDL(options) as downloader:
            match=re.search(r'/video/(\d+)',url)
            if match:
                from douyin_api import DouyinClient
                from yt_dlp.extractor.tiktok import DouyinIE
                detail=DouyinClient().detail(match.group(1))
                parsed=DouyinIE(downloader)._parse_aweme_video_app(detail)
                parsed.update(webpage_url=url,extractor='Douyin',extractor_key='Douyin')
                info=downloader.process_ie_result(parsed,download=True)
            else:
                info=downloader.extract_info(url,download=True)
            media=Path(downloader.prepare_filename(info))
    except Exception:
        raise RuntimeError('抖音正文获取失败：接口拒绝、登录失效或媒体下载失败；已停止，不使用简介代替正文。') from None
    if not media.is_file(): raise RuntimeError('下载器未返回完整媒体文件')
    # 用既有听写入口统一执行分段、断点和显存降级。
    command=[sys.executable,str(ROOT/'bili.py'),'--file',str(media),'--output-dir',str(args.output_dir),
             '--lang',args.lang,'--chunk-minutes',str(args.chunk_minutes),'--device',args.device]
    completed=subprocess.run(command,stdout=subprocess.PIPE,text=True,encoding='utf-8',check=True)
    transcript=Path(completed.stdout.strip().splitlines()[-1])
    record=transcript.with_name('content.json'); content=json.loads(record.read_text(encoding='utf-8'))
    expected=info.get('duration')
    if expected and content['duration']<float(expected)*.96:
        raise RuntimeError('抖音媒体短于原视频，拒绝将不完整内容作为正文')
    content.update(title=info.get('title') or content['title'],uploader=info.get('uploader') or '',
                   webpage_url=info.get('webpage_url') or url,platform='douyin')
    temporary=record.with_suffix('.tmp'); temporary.write_text(json.dumps(content,ensure_ascii=False,indent=2),encoding='utf-8'); os.replace(temporary,record)
    print(transcript)


if __name__=='__main__':
    try: main()
    except Exception as exc:
        print(str(exc),file=sys.stderr); sys.exit(1)
