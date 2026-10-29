"""小批量抖音请求验证：域隔离登录、签名、无自动重试。"""
import http.cookiejar
import json
from pathlib import Path
import sys
import urllib.error
import urllib.parse
import urllib.request

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'vendor'))
from douyin_signing.aBogus import ABogus
from douyin_signing.websign import normalize_query,sign

UA='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36'


class DouyinClient:
    def __init__(self):
        source=http.cookiejar.MozillaCookieJar(str(ROOT/'douyin-cookies.txt'))
        source.load(ignore_discard=True,ignore_expires=False)
        jar=http.cookiejar.CookieJar()
        for cookie in source:
            if cookie.domain.lstrip('.')=='douyin.com' or cookie.domain.endswith('.douyin.com'): jar.set_cookie(cookie)
        self.values={c.name:c.value for c in jar}
        self.opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

    def request(self,path,extra):
        if path not in ('aweme/detail','watchlater/list'): raise ValueError('不支持的抖音接口')
        params={'device_platform':'webapp','aid':'6383','channel':'channel_pc_web','update_version_code':'170400',
                'pc_client_type':'1','pc_libra_divert':'Mac','support_h265':'1','support_dash':'1',
                'version_code':'190500','version_name':'19.5.0','cookie_enabled':'true','screen_width':'1536',
                'screen_height':'864','browser_language':'zh-CN','browser_platform':'MacIntel','browser_name':'Chrome',
                'browser_version':'146.0.0.0','browser_online':'true','engine_name':'Blink','engine_version':'146.0.0.0',
                'os_name':'Mac OS','os_version':'10.15.7','cpu_core_num':'16','device_memory':'8','platform':'PC',
                'downlink':'10','effective_type':'4g','round_trip_time':'200','uifid':self.values.get('UIFID',self.values.get('uifid','')),
                'msToken':self.values.get('msToken','')}
        params.update(extra)
        query=urllib.parse.urlencode(params)
        protected=path=='aweme/detail'
        if params['uifid'] and protected: query=normalize_query(query)
        query+='&a_bogus='+urllib.parse.quote(ABogus(UA).get_value(query),safe='')
        if params['uifid'] and protected: query=sign(query,params['uifid'])[0]
        request=urllib.request.Request('https://www.douyin.com/aweme/v1/web/'+path+'/?'+query,
                                       headers={'User-Agent':UA,'Referer':'https://www.douyin.com/','Accept':'application/json'})
        try:
            with self.opener.open(request,timeout=30) as response: data=json.load(response)
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f'抖音返回HTTP {exc.code}；已停止，不自动重复请求') from None
        except Exception:
            raise RuntimeError('抖音未返回可读取的详情；登录或验证可能已失效') from None
        if data.get('status_code')!=0: raise RuntimeError('抖音接口未成功，可能需要重新登录或验证')
        return data

    def detail(self,video_id):
        if not str(video_id).isdigit(): raise ValueError('抖音视频编号无效')
        detail=self.request('aweme/detail',{'aweme_id':str(video_id)}).get('aweme_detail')
        if not detail or str(detail.get('aweme_id'))!=str(video_id):
            raise RuntimeError('抖音未返回对应视频正文信息，不能将其作为成功')
        return detail

    def watch_later(self,limit=5):
        if isinstance(limit,bool) or not isinstance(limit,int) or not 1<=limit<=9:
            raise ValueError('抖音每批请选择1~9条')
        data=self.request('watchlater/list',{'offset':0,'list_type':0,'operate_type':0})
        rows=data.get('items')
        if not isinstance(rows,list): raise RuntimeError('稍后再看响应格式变化，未导入任务')
        result=[]; seen=set()
        for row in rows:
            id=str(row.get('aweme_id',''))
            if id.isdigit() and id not in seen:
                seen.add(id); result.append(row)
            if len(result)>=limit: break
        return result


if __name__=='__main__':
    try:
        detail=DouyinClient().detail(sys.argv[1])
        print(json.dumps({'id':detail['aweme_id'],'title':detail.get('desc'),
                          'duration_ms':detail.get('video',{}).get('duration'),
                          'has_media':bool(detail.get('video',{}).get('play_addr',{}).get('url_list'))},ensure_ascii=False))
    except Exception as exc:
        print(str(exc),file=sys.stderr); sys.exit(1)
