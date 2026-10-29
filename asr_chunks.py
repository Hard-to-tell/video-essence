"""有界音频解码、区间断点、显存失败缩段与CPU降级。"""
from runtime_config import media_tool
import gc
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

def transcribe(audio,args,model_dir,ffmpeg_dir,meaningful):
    from faster_whisper import WhisperModel
    digest=hashlib.sha256()
    with open(audio,'rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''): digest.update(block)
    signature=f'{digest.hexdigest()}:{model_dir}:{args.lang}:{args.chunk_minutes}:v2'
    cache=Path(args.output_dir)/'.chunks'/hashlib.sha256(signature.encode()).hexdigest()
    cache.mkdir(parents=True,exist_ok=True)
    probe=subprocess.run([media_tool('ffprobe'),'-v','error','-show_entries','format=duration','-of','json',str(audio)],capture_output=True,check=True)
    duration=float(json.loads(probe.stdout)['format']['duration'])
    if not math.isfinite(duration) or duration<=0: raise ValueError('音频时长无效')
    span=args.chunk_minutes*60; total=max(1,math.ceil(duration/span))
    model=None; device='cpu' if args.device=='cpu' else 'cuda'
    measured_audio=0; measured_time=0

    def interval(start,end):
        nonlocal model,device,measured_audio,measured_time
        checkpoint=cache/f'{start:.3f}-{end:.3f}.json'
        try:
            saved=json.loads(checkpoint.read_text(encoding='utf-8'))
            if not isinstance(saved,list): raise ValueError()
            return saved
        except (OSError,ValueError): pass
        began=time.monotonic()
        # 两侧各留一秒上下文；按片段中点归属避免重叠段重复。
        offset=max(0,start-1); finish=min(duration,end+1)
        with tempfile.TemporaryDirectory(prefix='chunk_',dir=cache) as tmp:
            wave=Path(tmp)/'part.wav'
            subprocess.run([media_tool('ffmpeg'),'-v','error','-y','-ss',str(offset),'-i',str(audio),
                            '-t',str(finish-offset),'-ac','1','-ar','16000',str(wave)],capture_output=True,check=True)
            iterator=None; gpu_failure=None
            try:
                if model is None:
                    model=WhisperModel(str(model_dir),device=device,compute_type='int8' if device=='cpu' else 'int8_float16')
                iterator,_=model.transcribe(str(wave),language=args.lang,vad_filter=True,beam_size=3,condition_on_previous_text=False)
                segments=[]
                for s in iterator:
                    midpoint=(s.start+s.end)/2+offset
                    if start<=midpoint<end and meaningful(s.text):
                        segments.append((max(0,s.start+offset),min(s.end+offset,duration),s.text.strip()))
                measured_audio+=end-start; measured_time+=time.monotonic()-began
            except RuntimeError as exc:
                if device=='cpu' or not any(w in str(exc).lower() for w in ('cuda','cublas','cudnn','out of memory','alloc')): raise
                gpu_failure=str(exc).lower()
            # 离开except后再重试，避免异常traceback持有旧模型与解码缓存。
            if gpu_failure is not None:
                if iterator is not None and hasattr(iterator,'close'): iterator.close()
                iterator=None
                model=None; gc.collect()
                if end-start>60 and ('memory' in gpu_failure or 'alloc' in gpu_failure):
                    middle=(start+end)/2
                    print('显存不足，将当前段拆成两段重试；已完成区间保留',file=sys.stderr,flush=True)
                    segments=interval(start,middle)+interval(middle,end)
                else:
                    device='cpu'
                    print('GPU不可用或缩段后仍失败，当前区间改用CPU；已完成区间保留',file=sys.stderr,flush=True)
                    segments=interval(start,end)
        temporary=checkpoint.with_suffix('.tmp')
        temporary.write_text(json.dumps(segments,ensure_ascii=False),encoding='utf-8'); os.replace(temporary,checkpoint)
        return segments

    all_segments=[]
    for index in range(total):
        eta=round((duration-index*span)*measured_time/measured_audio) if measured_audio else None
        print(json.dumps({'stage':'content','progress':index/total,'message':f'听写第 {index+1}/{total} 段',
                          'chunk':{'index':index+1,'total':total},'eta_sec':eta},ensure_ascii=False),file=sys.stderr,flush=True)
        all_segments.extend(interval(index*span,min(duration,(index+1)*span)))
    print(json.dumps({'stage':'content','progress':1,'message':f'听写完成，{total} 段均已保存',
                      'chunk':{'index':total,'total':total},'eta_sec':0},ensure_ascii=False),file=sys.stderr,flush=True)
    return 'Whisper large-v3-turbo 分段听写（含边界上下文；可能有同音及专有名词错误）',all_segments
