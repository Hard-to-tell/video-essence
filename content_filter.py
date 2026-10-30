"""Conservative metadata filter for unattended batches, before media retrieval."""
import re

def skip_reason(meta):
    title = str(meta.get('title') or '')
    tags = [str(t) for t in meta.get('tags', [])]
    # A tutorial about streaming is different from a streamer reaction clip.
    teaching = re.search(r'教程|教学|科普|课程|原理|算法|编程|神经网络|论文|技术讲解', title)
    live = r'直播切片|直播录像|直播录播|直播回放|直播实录|直播精华|直播区切片|录播回放|直播|录播'
    signal = next((t for t in [title]+tags if re.search(live, t)), None)
    if signal and not teaching:
        return '默认跳过直播内容：标题或标签含“'+re.search(live, signal).group()+'”；指定链接或点“仍然总结”可处理'
    short = 0 < float(meta.get('duration') or 0) <= 600
    entertainment = next((t for t in tags if t in ('搞笑','娱乐','娱乐剪辑','整活','沙雕','搞笑剪辑')), None)
    clip = re.search(r'高燃剪辑|搞笑剪辑|整活|爆笑|名场面|神回', title)
    if short and not teaching and (entertainment or clip):
        return '默认跳过短娱乐内容：10分钟内，命中“'+(entertainment or clip.group())+'”；指定链接或点“仍然总结”可处理'
    return None

def metadata(item, root):
    if item['platform'] == 'bilibili':
        from bili_api import BiliClient
        client = BiliClient(str(root/'cookies.txt'))
        bv, page = client.resolve(item['url'])
        meta = client.info(bv, page)
        try:
            meta['tags'] = [t.get('tag_name','') for t in client.api('/x/tag/archive/tags', bvid=bv)]
        except Exception:
            meta['tags'] = []  # Missing tags are not evidence of entertainment.
        return meta
    if item['platform'] == 'douyin':
        from douyin_api import DouyinClient
        match = re.search(r'/video/(\d+)', item['url'])
        if not match: return {}
        detail = DouyinClient().detail(match.group(1))
        return {'title':detail.get('desc',''), 'duration':(detail.get('duration') or 0)/1000,
                'tags':[t.get('hashtag_name','') for t in detail.get('text_extra',[])]}
    return {}
