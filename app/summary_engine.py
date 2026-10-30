"""有界分批精华提炼。使用本机已登录的 Codex CLI，不读取或复制登录凭证。"""
import shutil
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from process_utils import stop_process

ROOT = Path(__file__).resolve().parents[1]
POINT = {"type":"object","properties":{"t":{"type":["number","null"]},"text":{"type":"string"}},"required":["t","text"],"additionalProperties":False}
SCHEMA = {"type":"object","properties":{
    "verdict":{"type":"string","enum":["essence","some","none"]},"one_line":{"type":"string"},
    "points":{"type":"array","items":POINT},"highlights":{"type":"array","items":POINT},
    "audience":{"type":"string"},"skip_note":{"type":"string"}},
    "required":["verdict","one_line","points","highlights","audience","skip_note"],"additionalProperties":False}
POLICY = (Path(__file__).with_name('summary_policy.txt')).read_text(encoding='utf-8')

def executable():
    configured = os.environ.get("VIDEO_ESSENCE_CODEX")
    if configured: return configured
    installed = shutil.which("codex")
    if installed and not installed.endswith(".cmd"): return installed
    local=list((ROOT/'vendor/codex-runtime/node_modules/@openai').glob('codex-win32-*/vendor/*/bin/codex.exe'))
    if local: return str(local[0])
    base = Path(os.environ.get('APPDATA','')) / 'npm/node_modules/@openai/codex/node_modules'
    matches = list(base.glob('@openai/codex-win32-*/vendor/*/bin/codex.exe'))
    if not matches:
        raise RuntimeError('未找到 Codex CLI，请先安装并登录后再生成摘要')
    return str(matches[0])

def run_model(payload, images, canceled):
    work = ROOT / 'data/model-work'
    work.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=work) as td:
        schema = Path(td)/'schema.json'
        result = Path(td)/'result.json'
        schema.write_text(json.dumps(SCHEMA), encoding='utf-8')
        cmd = [executable(),'exec','--ignore-user-config','-m',os.environ.get('VIDEO_ESSENCE_SUMMARY_MODEL','gpt-6-astra'),'--ephemeral','--skip-git-repo-check',
               '-s','read-only','--output-schema',str(schema),'-o',str(result),'-C',td,'--color','never']
        for image in images:
            cmd += ['-i',str(image)]
        cmd += ['-']
        with tempfile.TemporaryFile() as logs:
            process = subprocess.Popen(cmd,stdin=subprocess.PIPE,stdout=logs,stderr=logs,
                                       creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            process.stdin.write((POLICY+'\n'+json.dumps(payload,ensure_ascii=False)).encode('utf-8'))
            process.stdin.close()
            deadline = time.monotonic()+600
            while process.poll() is None:
                if canceled() or time.monotonic()>deadline:
                    stop_process(process)
                    raise RuntimeError('已取消' if canceled() else '模型响应超过10分钟；可重试，已完成分段会保留')
                time.sleep(.3)
            if process.returncode or not result.is_file():
                raise RuntimeError('摘要模型调用失败；请检查 Codex CLI 登录、额度或网络后重试')
            summary = json.loads(result.read_text(encoding='utf-8'))
    if summary['verdict']=='none':
        summary['points']=[]
    if not summary.get('one_line'):
        raise RuntimeError('模型返回空摘要，请重试')
    return summary

def summarize(content, settings, progress, canceled):
    segments = content.get('segments',[])
    chunks, current, size = [], [], 0
    # 按正文字符而不是时长限制输入，所有段都会处理。
    for segment in segments:
        for offset in range(0,len(segment['text']) or 1,10000):
            piece={**segment,'text':segment['text'][offset:offset+10000]}
            length=len(piece['text'])+80
            if current and size+length>14000:
                chunks.append(current); current=[]; size=0
            current.append(piece); size+=length
    if current or not chunks:
        chunks.append(current)
    cache = ROOT/'data/summary-parts'
    cache.mkdir(parents=True,exist_ok=True)
    base={k:content.get(k) for k in ('title','duration','source','mode','warnings')}
    base['style']=settings['summary_style']
    base['skip_rules']=settings.get('skip_rules',{})
    results=[]
    for i,chunk in enumerate(chunks):
        if canceled(): raise RuntimeError('已取消')
        progress('summarize',i/len(chunks),f'提炼正文第 {i+1}/{len(chunks)} 批')
        payload={**base,'segments':chunk,'part':i+1,'parts':len(chunks)}
        images=content.get('storyboards',[]) if i==0 else []
        signature=json.dumps(payload,sort_keys=True,ensure_ascii=False)+POLICY
        for im in images:
            signature+=hashlib.sha256(Path(im).read_bytes()).hexdigest()
        path=cache/(hashlib.sha256(signature.encode()).hexdigest()+'.json')
        try: result=json.loads(path.read_text(encoding='utf-8'))
        except (OSError,ValueError):
            result=run_model(payload,images,canceled)
            temporary=path.with_suffix('.tmp')
            temporary.write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8')
            os.replace(temporary,path)
        results.append(result)
    while len(results)>1:
        merged=[]
        for start in range(0,len(results),4):
            if canceled(): raise RuntimeError('已取消')
            progress('summarize',.95,'合并各段结论，去重并保留关键依据')
            payload={**base,'task':'整合这些分段精华，保留全片重要细节与原时间点','parts':results[start:start+4]}
            path=cache/(hashlib.sha256((json.dumps(payload,sort_keys=True,ensure_ascii=False)+POLICY).encode()).hexdigest()+'.json')
            try: result=json.loads(path.read_text(encoding='utf-8'))
            except (OSError,ValueError):
                result=run_model(payload,[],canceled)
                temporary=path.with_suffix('.tmp')
                temporary.write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8'); os.replace(temporary,path)
            merged.append(result)
        results=merged
    result=results[0]
    for point in result['points']+result['highlights']:
        if point['t'] is not None and not 0<=point['t']<=content.get('duration',0):
            point['t']=None
    return result
