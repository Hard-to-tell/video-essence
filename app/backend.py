"""持久任务队列。真实状态和演示数据隔离，处理失败不会生成假摘要。"""
from collections import Counter
from datetime import datetime, timezone
import copy
import json
import os
from pathlib import Path
import queue
import re
import subprocess
import sys
import threading
import time
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from bili_api import BiliClient
from state_storage import state_path
from summary_engine import summarize
from process_utils import stop_process
from content_filter import metadata as content_metadata, skip_reason as metadata_skip_reason
from douyin import validate_url as douyin_url
from runtime_config import PYTHON as PY
DEFAULT={'summary_style':'essence','auto_skip':True,'skip_rules':{'min_seconds':0,'music':True,'ads':True,'live_entertainment':True},
         'asr_model':'large-v3-turbo','device':'auto','language':'auto','chunk_minutes':10,'max_parallel':1,
         'output_dir':str(ROOT/'transcripts')}
def now(): return datetime.now(timezone.utc).isoformat()

class Store:
    def __init__(self,path=None):
        self.path=Path(path) if path else state_path(ROOT); self.path.parent.mkdir(parents=True,exist_ok=True)
        self.lock=threading.RLock(); self.tasks=queue.Queue()
        self.douyin_connected=False
        self.state=json.loads(self.path.read_text(encoding='utf-8')) if self.path.exists() else {'settings':DEFAULT,'batches':[]}
        self.state['settings'].setdefault('skip_rules',{}).setdefault('live_entertainment',True)
        for batch in self.state['batches']:
            for item in batch['items']:
                item.setdefault('explicit_request',batch.get('kind') in ('links','files'))
                if item['status'] in ('queued','running'):
                    item.update(status='failed',error='上次运行中断，请重试；已完成的内容缓存会复用',message='等待重试')
        self.save()

    def save(self):
        with self.lock:
            temporary=self.path.with_suffix('.tmp')
            temporary.write_text(json.dumps(self.state,ensure_ascii=False,indent=2),encoding='utf-8')
            os.replace(temporary,self.path)

    def find(self,id):
        for batch in self.state['batches']:
            for item in batch['items']:
                if item['id']==id: return item
        raise ValueError('视频任务不存在')

    def update(self,id,**fields):
        with self.lock:
            item=self.find(id); item.update(fields)
            if fields.get('message'):
                item.setdefault('log',[]).append(now()[11:19]+' '+fields['message'])
                item['log']=item['log'][-150:]
            self.save()

    def batches(self):
        with self.lock:
            batches=copy.deepcopy(self.state['batches'])
        for batch in batches:
            batch['total']=len(batch['items']); counts=Counter(i['status'] for i in batch['items'])
            batch['counts']={s:counts[s] for s in ('done','skipped','failed','running','queued','canceled')}
            for item in batch['items']:
                item.pop('transcript',None); item.pop('log',None)
        return batches

    def create(self,body):
        body=copy.deepcopy(body)
        kind=body.get('kind','links'); platform=body.get('platform','bilibili')
        links=body.get('links',[])
        if kind=='prompt':
            prompt=body.get('prompt','')
            links=re.findall(r'https?://[^\s]+|BV[\da-zA-Z]{10}',prompt)
            if not links and '稍后' not in prompt: raise ValueError('请提供视频链接，或说“总结B站/抖音稍后再看”')
            kind='links' if links else 'watch_later'
            platform='douyin' if '抖音' in prompt else platform
            if 'B站' in prompt or 'b站' in prompt or '哔哩哔哩' in prompt: platform='bilibili'
            count=re.search(r'(\d+|一|二|两|三|四|五|六|七|八|九|十)\s*(?:条|个)',prompt)
            if count:
                word=count.group(1)
                body['limit']=int(word) if word.isdigit() else {'一':1,'二':2,'两':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9,'十':10}[word]
            elif '全部' in prompt or '所有' in prompt: body['limit']=0
            if any(word in prompt for word in ('不要跳过','不跳过','全部都总结')): body['auto_skip']=False
        if kind=='watch_later':
            if platform=='douyin':
                from douyin_api import DouyinClient
                rows=DouyinClient().watch_later(int(body.get('limit',5)))
                links=['https://www.douyin.com/video/'+r['aweme_id'] for r in rows]
                self.douyin_connected=True
            else:
                client=BiliClient(str(ROOT/'cookies.txt'))
                data=client.api('/x/v2/history/toview',ps=1000)
                rows=data.get('list') or []
                rows.sort(key=lambda x:x.get('add_at',0),reverse=True)
                limit=int(body.get('limit',10))
                if limit<0: raise ValueError('条数不能为负数')
                links=['https://www.bilibili.com/video/'+r['bvid']+'/' for r in (rows[:limit] if limit else rows)]
            if not links: raise ValueError('稍后再看列表为空，或当前登录无法读取列表')
        if kind=='files': links=body.get('files',[]); platform='local'
        if not isinstance(links,list) or not links: raise ValueError('请提供至少一个视频链接或本地文件路径')
        if len(links)>500: raise ValueError('单批最多500条，请分批处理')
        unique=list(dict.fromkeys(str(x).strip() for x in links if str(x).strip()))
        if sum('douyin.com' in link for link in unique)>9: raise ValueError('抖音每批最多9条')
        # 在入队前完整校验，避免部分入队后返回失败。
        for link in unique:
            if platform=='local':
                if not Path(link).is_file() or Path(link).suffix.lower() not in ('.mp4','.mkv','.mov','.mp3','.wav','.m4a','.flac','.webm'):
                    raise ValueError('本地路径必须是存在的音视频文件')
            else:
                if 'douyin.com' in link: douyin_url(link)
                else: BiliClient().resolve(link)
        batch={'id':uuid.uuid4().hex,'title':(('抖音' if platform=='douyin' else 'B站')+'稍后再看' if kind=='watch_later' else '视频提炼'),
               'platform':platform,'kind':kind,'created_at':now(),'auto_skip':bool(body.get('auto_skip',True)),'items':[]}
        for link in unique:
            item={'id':uuid.uuid4().hex,'batch_id':batch['id'],'platform':platform,'url':link,'title':Path(link).name if platform=='local' else link,
                  'uploader':'','duration':0,'cover':None,'added_at':now(),'status':'queued','stage':'meta','progress':0,
                  'chunk':None,'eta_sec':None,'message':'等待处理','source':None,'skip_reason':None,'error':None,'summary':None,'log':[],
                  'explicit_request':kind in ('links','files'),'auto_skip':batch['auto_skip'],'settings':copy.deepcopy(self.state['settings'])}
            batch['items'].append(item)
            if platform!='local': item['platform']='douyin' if 'douyin.com' in link else 'bilibili'
        with self.lock:
            self.state['batches'].insert(0,batch); self.save()
        for item in batch['items']: self.tasks.put((item['id'],item.get('run',0)))
        return {'batch_id':batch['id']}

    def action(self,id,action):
        with self.lock:
            item=self.find(id)
            if action=='cancel':
                if item['status'] not in ('queued','running'): return {'ok':True}
                self.update(id,run=item.get('run',0)+1,status='canceled',chunk=None,eta_sec=None,message='已取消')
            elif action in ('retry','summarize'):
                if item['status'] in ('queued','running'): raise ValueError('任务正在处理，无需重复提交')
                if action=='summarize':
                    item['auto_skip']=False
                    item['explicit_request']=True
                self.update(id,run=item.get('run',0)+1,status='queued',stage='meta',progress=0,chunk=None,eta_sec=None,error=None,skip_reason=None,summary=None,message='等待重试')
                self.tasks.put((id,item['run']))
            return {'ok':True}

    def current(self,id,run):
        with self.lock:
            item=self.find(id)
            return item.get('run',0)==run and item['status'] in ('queued','running')

    def update_run(self,id,run,**fields):
        with self.lock:
            if not self.current(id,run): return False
            self.update(id,**fields)
            return True

    def claim(self,id,run):
        with self.lock:
            item=self.find(id)
            if not self.current(id,run) or item['status']!='queued': return None
            self.update(id,status='running',stage='meta',progress=0,message='读取视频信息')
            return copy.deepcopy(item)

    def skip_by_metadata(self,item,run):
        if item.get('explicit_request') or not item['auto_skip'] or not item['settings'].get('skip_rules',{}).get('live_entertainment',True):
            return False
        if not self.current(item['id'],run): return True
        meta=content_metadata(item,ROOT)
        reason=metadata_skip_reason(meta)
        if not self.current(item['id'],run): return True
        if reason:
            self.update_run(item['id'],run,title=meta.get('title') or item['title'],duration=meta.get('duration',0),
                            status='skipped',stage='done',progress=1,skip_reason=reason,message=reason)
            return True
        return False

    def worker(self):
        while True:
            id,run=self.tasks.get()
            try:
                item=self.claim(id,run)
                if item is None: continue
                if self.skip_by_metadata(item,run): continue
                settings=item['settings']
                self.update_run(id,run,stage='content',progress=0,message='获取视频正文')
                script='douyin.py' if item['platform']=='douyin' else 'bili.py'
                cmd=[PY,str(ROOT/script),'--lang',settings['language'],'--output-dir',settings['output_dir'],
                     '--chunk-minutes',str(settings['chunk_minutes']),'--device',settings['device']]
                cmd+=['--file',item['url']] if item['platform']=='local' else [item['url']]
                env={**os.environ,'PYTHONIOENCODING':'utf-8'}
                process=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8',errors='replace',env=env,
                                         creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                lines=queue.Queue()
                def reader():
                    for line in process.stderr: lines.put(line.strip())
                threading.Thread(target=reader,daemon=True).start()
                deadline=time.monotonic()+6*3600
                while process.poll() is None:
                    if not self.current(id,run) or time.monotonic()>deadline:
                        stop_process(process)
                        raise RuntimeError('已取消' if not self.current(id,run) else '处理超过6小时，请拆分视频后重试')
                    while not lines.empty():
                        line=lines.get()
                        if line:
                            fields={'message':line[:240]}
                            try:
                                event=json.loads(line)
                                if isinstance(event,dict): fields.update({k:event[k] for k in ('stage','progress','message','chunk','eta_sec') if k in event})
                            except ValueError: pass
                            match=re.search(r'(\d+):(\d+) / (\d+):(\d+)',line)
                            if match:
                                a,b,c,d=map(int,match.groups()); fields['progress']=min(.99,(a*60+b)/max(1,c*60+d))
                            self.update_run(id,run,**fields)
                    time.sleep(.3)
                stdout=process.stdout.read()
                if process.returncode: raise RuntimeError('正文获取失败；请检查链接、登录或网络，详细进度见处理过程')
                transcript=Path(stdout.strip().splitlines()[-1]); content=json.loads(transcript.with_name('content.json').read_text(encoding='utf-8'))
                if not self.current(id,run): continue
                self.update_run(id,run,title=content['title'],uploader=content.get('uploader',''),duration=content['duration'],
                            transcript=content.get('segments',[]),source=content['source'],stage='judge',progress=0,chunk=None,eta_sec=None,message='核对信息价值和证据')
                def progress(stage,p,message): self.update_run(id,run,stage=stage,progress=p,message=message)
                minimum=settings.get('skip_rules',{}).get('min_seconds',0)
                if item['auto_skip'] and content['duration']<minimum:
                    reason=f'按你的规则跳过：视频短于 {minimum} 秒；未据此判断内容没有价值'
                    self.update_run(id,run,status='skipped',stage='done',progress=1,skip_reason=reason,message=reason)
                    continue
                summary=summarize(content,settings,progress,lambda:not self.current(id,run))
                if not self.current(id,run): continue
                skip=summary['verdict']=='none' and item['auto_skip']
                self.update_run(id,run,status='skipped' if skip else 'done',stage='done',progress=1,chunk=None,eta_sec=None,summary=summary,
                            skip_reason=summary['one_line'] if skip else None,message='没有可提炼精华，已说明原因' if skip else '提炼完成')
            except Exception as exc:
                self.update_run(id,run,status='failed',chunk=None,eta_sec=None,error=str(exc),message='处理失败，可以重试')
            finally: self.tasks.task_done()

def register(route,ApiError):
    store=Store(); threading.Thread(target=store.worker,daemon=True).start()
    accounts={'bilibili':{'logged_in':False},'douyin':{'logged_in':False}}
    from account_login import BiliLogin, import_douyin_cookies
    bili_login=BiliLogin(accounts)
    def check_accounts():
        while True:
            try:
                data=BiliClient(str(ROOT/'cookies.txt')).api('/x/web-interface/nav')
                accounts['bilibili']={'logged_in':bool(data.get('isLogin')),'name':data.get('uname','')}
            except Exception: accounts['bilibili']={'logged_in':False}
            time.sleep(60)
    threading.Thread(target=check_accounts,daemon=True).start()
    @route('GET',r'/api/status')
    def status(m,b):
        accounts['douyin']={'logged_in':store.douyin_connected}
        return {'application':'bili-summary','backend':'ready','gpu':None,'model':'large-v3-turbo + Codex','accounts':copy.deepcopy(accounts),
                'running':any(i['status']=='running' for x in store.batches() for i in x['items'])}
    @route('GET',r'/api/batches')
    def batches(m,b): return store.batches()
    @route('POST',r'/api/jobs')
    def jobs(m,b):
        try: return store.create(b)
        except Exception as exc: raise ApiError(400,str(exc))
    @route('GET',r'/api/items/(?P<id>[a-f0-9]+)')
    def item(m,b):
        with store.lock: return copy.deepcopy(store.find(m['id']))
    @route('POST',r'/api/items/(?P<id>[a-f0-9]+)/(?P<action>retry|cancel|summarize)')
    def action(m,b): return store.action(m['id'],m['action'])
    @route('POST',r'/api/batches/(?P<id>[a-f0-9]+)/cancel')
    def cancel_batch(m,b):
        for batch in store.batches():
            if batch['id']==m['id']:
                for item in batch['items']: store.action(item['id'],'cancel')
        return {'ok':True}
    @route('GET',r'/api/library')
    def library(m,b): return [i for batch in store.batches() for i in batch['items'] if i['status'] in ('done','skipped')]
    @route('GET',r'/api/settings')
    def settings(m,b): return copy.deepcopy(store.state['settings'])
    @route('PUT',r'/api/settings')
    def save_settings(m,b):
        if b.get('asr_model')!='large-v3-turbo' or b.get('device') not in ('auto','cuda','cpu') or not isinstance(b.get('chunk_minutes'),int) or not 1<=b['chunk_minutes']<=30 or b.get('max_parallel')!=1:
            raise ApiError(400,'当前支持 large-v3-turbo、1~30分钟分段、单任务；其它模型尚未安装')
        if b.get('summary_style') not in ('essence','detailed','brief') or b.get('language') not in ('auto','zh','en'):
            raise ApiError(400,'摘要风格或语言不正确')
        rules=b.get('skip_rules',{})
        if not isinstance(rules,dict) or not isinstance(rules.get('min_seconds'),(int,float)) or not 0<=rules['min_seconds']<=86400 or any(not isinstance(rules.get(k),bool) for k in ('music','ads')) or not isinstance(rules.get('live_entertainment',True),bool):
            raise ApiError(400,'跳过规则无效；最短时长须为0~86400秒')
        if Path(b.get('output_dir','')).resolve()!= (ROOT/'transcripts').resolve(): raise ApiError(400,'缓存统一保存在项目 transcripts 目录')
        with store.lock: store.state['settings']={k:b.get(k,DEFAULT[k]) for k in DEFAULT}; store.save()
        return settings(m,b)
    @route('POST',r'/api/accounts/(?P<platform>bilibili|douyin)/login')
    def login(m,b):
        if m['platform']=='bilibili': return bili_login.start()
        return {'ok':False,'import_cookies':True,'message':'选择本机已有的抖音Netscape登录文件。仅保留抖音域的登录信息；不支持直接读取Chrome登录。'}
    @route('POST',r'/api/accounts/douyin/import')
    def import_douyin(m,b): return import_douyin_cookies(b.get('text'))
    return store
