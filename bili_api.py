"""普通 B站接口访问；不依赖网页脚本结构或浏览器指纹伪装。"""
import gzip
import http.cookiejar
import json
from pathlib import Path
import re
import shutil
import urllib.error
import urllib.parse
import urllib.request

HEADERS = {"User-Agent": "bili-summary/2.0", "Referer": "https://www.bilibili.com/"}


class BiliError(RuntimeError):
    pass


def meaningful(text):
    text = text.strip()
    noise = r"[\s♪♫♬🎵\[\]【】（）()]*?(?:音乐|音樂|music|background music|背景音乐|掌声|笑声|静音|silence)[\s♪♫♬🎵\[\]【】（）()]*"
    return bool(re.search(r"\w", text)) and not re.fullmatch(noise, text, re.I)


class BiliClient:
    def __init__(self, cookies=None, browser=None):
        jar = http.cookiejar.CookieJar()
        if cookies:
            jar = http.cookiejar.MozillaCookieJar(cookies)
            try:
                jar.load(ignore_discard=True, ignore_expires=False)
            except (OSError, http.cookiejar.LoadError) as exc:
                raise BiliError("无法读取 cookie 文件，请检查 Netscape 格式和路径") from exc
        elif browser:
            from yt_dlp.cookies import extract_cookies_from_browser
            jar = extract_cookies_from_browser(browser)
        # CookieJar 按域发送凭证，不把 B站 cookie 转发给媒体 CDN。
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

    def open(self, url):
        if url.startswith("//"):
            url = "https:" + url
        try:
            return self.opener.open(urllib.request.Request(url, headers=HEADERS), timeout=45)
        except urllib.error.HTTPError as exc:
            raise BiliError(f"请求返回 HTTP {exc.code}，未取得完整内容") from exc
        except urllib.error.URLError as exc:
            raise BiliError(f"网络连接失败：{exc.reason}") from exc

    def json(self, url):
        with self.open(url) as response:
            body = response.read()
        if body[:2] == b"\x1f\x8b":
            body = gzip.decompress(body)
        try:
            return json.loads(body)
        except (ValueError, UnicodeDecodeError) as exc:
            raise BiliError("接口未返回有效 JSON，可能是网络拦截页面") from exc

    def api(self, path, **query):
        data = self.json("https://api.bilibili.com" + path + "?" + urllib.parse.urlencode(query))
        if data.get("code") != 0:
            raise BiliError(f"B站接口错误 {data.get('code')}：{data.get('message', '')}")
        return data.get("data") or {}

    def resolve(self, text):
        text = text.strip()
        if re.fullmatch(r"BV[0-9A-Za-z]{10}", text):
            return text, 1
        match = re.search(r"https?://[^\s<>\])]+", text)
        if not match:
            raise BiliError("请提供 B站视频链接、b23.tv 分享链接或 BV号")
        parsed = urllib.parse.urlsplit(match.group().replace("\\&", "&"))
        if parsed.hostname == "b23.tv":
            with self.open(parsed.geturl()) as response:
                parsed = urllib.parse.urlsplit(response.url)
        host = (parsed.hostname or "").lower()
        if host != "bilibili.com" and not host.endswith(".bilibili.com"):
            raise BiliError("仅支持 bilibili.com 视频或 b23.tv 分享链接")
        match = re.search(r"/video/(BV[0-9A-Za-z]{10})(?:/|$)", parsed.path)
        if not match:
            raise BiliError("链接中没有找到有效 BV号")
        try:
            page = int(urllib.parse.parse_qs(parsed.query).get("p", ["1"])[0])
        except ValueError as exc:
            raise BiliError("分P编号必须是整数") from exc
        return match.group(1), page

    def info(self, bvid, page):
        data = self.api("/x/web-interface/view", bvid=bvid)
        pages = data.get("pages") or [{"cid": data["cid"], "duration": data["duration"]}]
        if not 1 <= page <= len(pages):
            raise BiliError(f"视频共有 {len(pages)} P，无法读取第 {page} P")
        part = pages[page - 1]
        return {"id": bvid, "aid": data["aid"], "page": page, "pages": len(pages), "cid": part["cid"],
                "title": data["title"], "part": part.get("part", ""),
                "duration": part["duration"], "uploader": (data.get("owner") or {}).get("name", ""),
                "description": data.get("desc", ""),
                "webpage_url": f"https://www.bilibili.com/video/{bvid}/?p={page}"}

    def subtitles(self, info):
        player = self.api("/x/player/v2", bvid=info["id"], aid=info["aid"], cid=info["cid"])
        if player.get("cid") != info["cid"] or player.get("bvid") != info["id"]:
            raise BiliError("字幕接口返回的视频编号不匹配，改用音频核验")
        if player.get("is_ugc_pay_preview"):
            raise BiliError("当前账号只能试看此视频，不能当作完整正文")
        subs = (player.get("subtitle") or {}).get("subtitles") or []
        subs.sort(key=lambda s: (not (s.get("lan", "").startswith("zh") or s.get("lan") == "ai-zh"),
                                 s.get("lan", "").startswith("ai"), s.get("lan", "")))
        for sub in subs:
            if not sub.get("subtitle_url"):
                continue
            try:
                body = self.json(sub["subtitle_url"]).get("body") or []
            except BiliError:
                continue
            # 某些缓存/字幕地址可能返回别的视频；不能接受超过全片时长的稿子。
            if any(s.get("from", -1) < 0 or s.get("to", 0) < s.get("from", 0)
                   or s.get("to", 0) > info["duration"] + max(3, info["duration"] * .02) for s in body):
                raise BiliError("字幕时间轴超出视频时长，拒绝使用，改用音频核验")
            segments = [(float(s["from"]), float(s["to"]), s["content"].strip())
                        for s in body if s.get("music", 0) < .8 and meaningful(s["content"])]
            if segments:
                note = "；AI生成，可能有错字" if sub.get("lan", "").startswith("ai") else ""
                return f"B站字幕（{sub.get('lan', '未知')}{note}）", segments
        return None

    def download(self, info, tmp, duration_fn, video=False):
        data = self.api("/x/player/playurl", bvid=info["id"], cid=info["cid"], qn=64, fnval=4048, fourk=0)
        if data.get("is_preview") or data.get("is_ugc_pay_preview"):
            raise BiliError("播放接口只返回试看，无法取得完整内容")
        streams = (data.get("dash") or {}).get("video" if video else "audio") or []
        if streams:
            if video:
                suitable = [s for s in streams if s.get("height", 0) <= 720] or streams
                stream = max(suitable, key=lambda s: (s.get("height", 0), -s.get("bandwidth", 0)))
            else:
                stream = min(streams, key=lambda s: s.get("bandwidth", 0))
            urls = [stream.get("baseUrl") or stream.get("base_url")]
            urls += stream.get("backupUrl") or stream.get("backup_url") or []
            dest = tmp / ("video.mp4" if video else "audio.m4a")
        else:
            parts = data.get("durl") or []
            if len(parts) != 1:
                raise BiliError("接口未返回可用媒体流，可能需要登录或没有权限")
            urls = [parts[0].get("url")] + (parts[0].get("backup_url") or [])
            dest = tmp / "media.flv"
        last_error = "没有媒体地址"
        for url in urls:
            if not url:
                continue
            try:
                with self.open(url) as response, dest.open("wb") as output:
                    shutil.copyfileobj(response, output)
                duration = duration_fn(dest)
                if abs(duration - info["duration"]) > max(3, info["duration"] * .02):
                    relation = "短于" if duration < info["duration"] else "长于"
                    raise BiliError(f"媒体为 {duration:.1f} 秒，{relation}视频的 {info['duration']} 秒；拒绝当作完整视频")
                info.setdefault("media_checks", []).append({"kind": "video" if video else "audio",
                                                            "duration": duration, "expected_duration": info["duration"]})
                return dest
            except (BiliError, OSError) as exc:
                last_error = str(exc)
        raise BiliError("媒体下载失败：" + last_error)
