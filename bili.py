"""B站链接 -> 字幕/听写稿；无口语视频 -> 带时间点画面。由聊天中的 Codex 读取并总结。"""
import argparse
import json
import math
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "vendor"))
# ctranslate2 需要 cuBLAS/cuDNN,这个环境里 torch 自带,把它的 lib 目录加入 DLL 搜索路径
_torch_lib = Path(sys.prefix) / "Lib" / "site-packages" / "torch" / "lib"
if os.name == "nt" and _torch_lib.exists():
    _dll_handle = os.add_dll_directory(str(_torch_lib))
    os.environ["PATH"] = str(_torch_lib) + os.pathsep + os.environ["PATH"]

from bili_api import BiliClient, BiliError, meaningful  # noqa: E402

from runtime_config import MODEL, media_tool
MODEL_DIR = Path(MODEL)
OUT_DIR = ROOT / "transcripts"
FFMPEG_DIR = str(Path(media_tool("ffmpeg")).parent)
CHUNK_SEC = 30
PIPELINE_VERSION = 4


def ts(sec):
    sec = int(sec)
    h, m, s = sec // 3600, sec % 3600 // 60, sec % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def media_duration(path):
    result = subprocess.run([media_tool("ffprobe"), "-v", "error", "-show_entries",
                             "format=duration", "-of", "json", str(path)], capture_output=True, check=True)
    return float(json.loads(result.stdout)["format"]["duration"])


def pack(segments, chunk=CHUNK_SEC):
    """(start, end, text) 列表 -> 每 chunk 秒一段,带段首时间戳。"""
    out, buf, start = [], [], None
    for s, e, t in segments:
        t = t.strip()
        if not t:
            continue
        if start is None:
            start = s
        buf.append(t)
        if e - start >= chunk:
            out.append(f"[{ts(start)}] " + " ".join(buf))
            buf, start = [], None
    if buf:
        out.append(f"[{ts(start)}] " + " ".join(buf))
    return out


def asr(audio, args):
    from asr_chunks import transcribe
    return transcribe(audio,args,MODEL_DIR,FFMPEG_DIR,meaningful)


def legacy_asr(audio, args):
    from faster_whisper import WhisperModel
    try:
        model = WhisperModel(str(MODEL_DIR), device="cuda", compute_type="float16")
        dev = "GPU"
    except Exception:  # 显卡不可用时退回 CPU
        print("GPU 加载失败，改用 CPU，耗时会增加", file=sys.stderr)
        model = WhisperModel(str(MODEL_DIR), device="cpu", compute_type="int8")
        dev = "CPU"
    seg_iter, meta = model.transcribe(
        str(audio), language=args.lang, vad_filter=True, beam_size=5,
        condition_on_previous_text=False,
        initial_prompt="以下是普通话的句子,使用简体中文。" if args.lang == "zh" else None)
    print(f"听写中({dev},语言={meta.language},时长={ts(meta.duration)})...", file=sys.stderr)
    segs, next_progress = [], 0
    for s in seg_iter:
        if meaningful(s.text):
            segs.append((s.start, s.end, s.text.strip()))
        if s.end >= next_progress:
            print(f"\r  {ts(s.end)} / {ts(meta.duration)}", end="", file=sys.stderr, flush=True)
            next_progress = s.end + 30
    print(file=sys.stderr)
    return f"Whisper large-v3-turbo 听写({dev}),可能有错字和专有名词错误", segs


def verify_subtitles(audio, got, info, args, tmp):
    """用一段实际音频核对字幕，避免把CDN串稿当成视频正文。"""
    segments = got[1]
    center = segments[len(segments) // 3][0]
    start = max(0, min(center - 10, info["duration"] - 45))
    length = min(45, info["duration"] - start)
    sample = tmp / "subtitle_check.wav"
    subprocess.run([media_tool("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y",
                    "-ss", str(start), "-i", str(audio), "-t", str(length), "-ar", "16000", "-ac", "1",
                    str(sample)], capture_output=True, check=True)
    actual = asr(sample, args)[1]
    reference = " ".join(t for s, e, t in segments if e >= start and s <= start + length)
    observed = " ".join(t for s, e, t in actual)
    score = text_overlap(reference, observed)
    print(f"字幕音频核对：相似度={score:.2f}", file=sys.stderr)
    return bool(observed) and score >= .2


def text_overlap(reference, observed):
    from collections import Counter
    def grams(text):
        normalized = re.sub(r"[^\w]", "", text.lower())
        return Counter(normalized[i:i + 2] for i in range(len(normalized) - 1))
    expected, actual = grams(reference), grams(observed)
    return sum((expected & actual).values()) / max(1, sum(actual.values()))


def extract_frames(video, output, duration):
    from PIL import Image, ImageDraw
    folder = output / "frames"
    folder.mkdir(parents=True, exist_ok=True)
    step = max(5, duration / 24)
    times = [round(min(.5 + i * step, max(0, duration - .2)), 2)
             for i in range(max(1, math.ceil(duration / step)))]
    # 单次解码覆盖全片，避免每张图都重新启动解码器。
    first = times[0]
    pattern = folder / "sample_%02d.jpg"
    subprocess.run([media_tool("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y",
                    "-i", str(video), "-vf", f"select='gte(t,{first}+{step}*selected_n)',scale=1280:-2",
                    "-fps_mode", "vfr", "-frames:v", str(len(times)), "-q:v", "2", str(pattern)],
                   capture_output=True, check=True)
    frames = []
    for i, at in enumerate(times):
        dest = folder / f"{i + 1:02d}_{at:07.2f}s.jpg"
        (folder / f"sample_{i + 1:02d}.jpg").replace(dest)
        frames.append({"time": at, "path": str(dest.resolve())})
    sheets = []
    for start in range(0, len(frames), 8):
        group = frames[start:start + 8]
        sheet = Image.new("RGB", (1280, 390 * math.ceil(len(group) / 2)), "#eeeeee")
        draw = ImageDraw.Draw(sheet)
        for i, frame in enumerate(group):
            with Image.open(frame["path"]) as picture:
                picture.thumbnail((640, 360))
                x, y = i % 2 * 640, i // 2 * 390
                sheet.paste(picture, (x, y + 26))
                draw.text((x + 8, y + 6), ts(frame["time"]), fill="black")
        dest = output / f"storyboard_{start // 8 + 1}.jpg"
        sheet.save(dest, quality=90)
        sheets.append(str(dest.resolve()))
    return frames, sheets


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("link", nargs="?", help="B站链接或BV号;用 --file 时可省略")
    ap.add_argument("--file", help="本地音频/视频文件,直接听写,不访问 B 站")
    auth = ap.add_mutually_exclusive_group()
    auth.add_argument("--cookies", help="Netscape 格式 cookies.txt")
    auth.add_argument("--browser", help="从浏览器读 cookie,如 edge / chrome")
    ap.add_argument("--force-asr", action="store_true", help="不找字幕,直接听写")
    ap.add_argument("--lang", default="auto", help="听写语言，默认自动检测；可指定 zh/en")
    ap.add_argument("--refresh", action="store_true", help="重新获取，忽略已完成缓存")
    ap.add_argument("--frames", action="store_true", help="有正文时也采样画面；无正文时自动采样")
    ap.add_argument("--output-dir", type=Path, default=OUT_DIR)
    ap.add_argument('--chunk-minutes',type=int,choices=range(1,31),default=10)
    ap.add_argument('--device',choices=['auto','cuda','cpu'],default='auto')
    args = ap.parse_args(argv)
    if args.lang == "auto":
        args.lang = None

    if args.file:
        import hashlib
        f = Path(args.file).resolve()
        if not f.is_file():
            raise BiliError("本地文件不存在")
        stat = f.stat()
        key = "local_" + hashlib.sha256(f"{f}:{stat.st_size}:{stat.st_mtime_ns}".encode()).hexdigest()[:16]
        info = {"title": f.stem, "id": "local", "webpage_url": str(f), "uploader": "",
                "duration": media_duration(f), "description": "", "page": 1, "pages": 1, "part": ""}
        client = None
    else:
        if not args.link:
            ap.error("需要提供链接,或使用 --file")
        cookies = args.cookies
        if not cookies and not args.browser and (ROOT / "cookies.txt").is_file():
            cookies = str(ROOT / "cookies.txt")
        client = BiliClient(cookies, args.browser)
        bvid, page = client.resolve(args.link)
        key, info = f"{bvid}_p{page}", None

    output = args.output_dir.resolve() / key
    record = output / "content.json"
    if record.is_file() and not (args.refresh or args.force_asr or args.frames):
        cached = json.loads(record.read_text(encoding="utf-8"))
        assets = [cached.get("transcript_path", "")] + [f["path"] for f in cached.get("frames", [])] + cached.get("storyboards", [])
        if cached.get("pipeline_version") == PIPELINE_VERSION and all(Path(p).is_file() for p in assets):
            print("读取已完成的正文缓存（--refresh 可重新获取）", file=sys.stderr)
            print(cached["transcript_path"])
            return
    if info is None:
        info = client.info(bvid, page)
    output.mkdir(parents=True, exist_ok=True)
    record.unlink(missing_ok=True)
    print(f"{info['title']}（P{info['page']}，{ts(info['duration'])}）", file=sys.stderr)
    warnings, sampled, sheets = [], [], []

    with tempfile.TemporaryDirectory(prefix="bili_") as t:
        tmp = Path(t)
        got, audio = None, None
        if client and not args.force_asr:
            try:
                got = client.subtitles(info)
            except BiliError as exc:
                warnings.append(str(exc))
                print("字幕不可用，尝试音频路线", file=sys.stderr)
        if got:
            print("下载音频抽样核对字幕是否属于本视频…", file=sys.stderr, flush=True)
            audio = client.download(info, tmp, media_duration)
            if not verify_subtitles(audio, got, info, args, tmp):
                warnings.append("字幕与音频抽样不一致或无法核实，已丢弃字幕并对完整音频重新听写。")
                got = None
        if got is None:
            print("读取完整音频并听写…", file=sys.stderr, flush=True)
            if audio is None:
                audio = f if args.file else client.download(info, tmp, media_duration)
            got = asr(audio, args)
        source, segs = got
        if args.frames or not segs:
            if not segs:
                warnings.append("未取得有效口语文字，可能是纯音乐或无声视频；必须读取画面，不能把简介当作正文。")
            print("读取完整视频并提取带时间点的画面…", file=sys.stderr, flush=True)
            video = f if args.file else client.download(info, tmp, media_duration, video=True)
            sampled, sheets = extract_frames(video, output, info["duration"])
    mode = "speech-and-frames" if segs and sampled else "speech" if segs else "visual"

    head = [
        f"# {info['title']}",
        f"- 链接: {info['webpage_url']}",
        f"- UP主: {info.get('uploader', '')}",
        f"- 时长: {ts(info.get('duration') or 0)}",
        f"- 分P: {info['page']}/{info['pages']} {info['part']}",
        f"- 文字来源: {source}", f"- 内容模式: {mode}",
        *[f"- 注意: {w}" for w in warnings],
        "", "## 文字稿", "",
    ]
    lines = head + (pack(segs) if segs else ["没有有效口语文字，请读取下方画面。"])
    if sampled:
        lines += ["", "## 视频画面采样", "", "以下画面均匀采样覆盖全片范围，不是逐帧检查。"]
        lines += [f"- [{ts(frame['time'])}] {frame['path']}" for frame in sampled]
        lines += ["", "### 联系表"] + [f"- {sheet}" for sheet in sheets]
    lines += ["", "## 简介（背景资料，不是视频逐字稿）", "", info.get("description") or "（无）"]
    out = output / "transcript.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    data = {"pipeline_version": PIPELINE_VERSION, **info, "mode": mode, "source": source,
            "warnings": warnings, "segments": [{"start": s, "end": e, "text": t} for s, e, t in segs],
            "frames": sampled, "storyboards": sheets, "transcript_path": str(out)}
    record.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"完成：{len(segs)}条正文，{len(sampled)}张画面；模式={mode}", file=sys.stderr)
    print(out)


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or b"").decode("utf-8", errors="replace")[-1500:]
        print(f"媒体处理失败：{detail}", file=sys.stderr)
        sys.exit(1)
    except (BiliError, OSError, ValueError) as exc:
        print(f"失败：{exc}", file=sys.stderr)
        sys.exit(1)
