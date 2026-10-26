#!/usr/bin/env python3
"""Refresh public reference data, never treating it as an Alipay quotation.

Sources: public fee/transaction pages of a distributor. Alipay observations are
accepted ONLY from an operator-configured authorized feed or dated manual record.
Network/parser failures retain the original observations and dates.
"""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from datetime import datetime, timedelta
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import re
import time
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser
from zoneinfo import ZoneInfo

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parents[1]
TZ=ZoneInfo('Asia/Shanghai')
SOURCE='https://fundf10.eastmoney.com'
USER_AGENT='IndexWatch/0.1 (+public-fund-facts; two-daily-checks)'
BANNED=('等权','增强','杠杆','反向','科技精选','生物科技','低波','红利','ESG','Equal Weight','Enhanced','Leveraged')
VALID_STATUS={'limited','open','paused','unknown'}


def read_json(path:Path, default=None):
    if not path.exists(): return default
    return json.loads(path.read_text(encoding='utf-8'))


def atomic_json(path:Path, data):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    tmp.replace(path)


def make_session():
    s=requests.Session()
    s.headers.update({'User-Agent':USER_AGENT,'Accept':'text/html,application/json;q=0.9','Accept-Language':'zh-CN,zh;q=0.9'})
    retries=Retry(total=1,connect=1,read=1,backoff_factor=1,status_forcelist=(429,500,502,503,504),allowed_methods=frozenset({'GET'}),respect_retry_after_header=True)
    s.mount('https://',HTTPAdapter(max_retries=retries))
    return s


def normalize(value:str):
    return re.sub(r'\s+','',value).replace('\u3000','').replace('％','%')


def label_value(soup:BeautifulSoup,label:str):
    target=normalize(label)
    for cell in soup.find_all(['th','td','dt']):
        if normalize(cell.get_text('',strip=True)).rstrip(':：')==target:
            sibling=cell.find_next_sibling(['td','th','dd'])
            if sibling is not None: return sibling.get_text(' ',strip=True)
    return None


def amount(value:str|None):
    """Return (CNY amount or None, explicitly_unlimited). Never infer unlimited."""
    if value is None:return None,False
    text=normalize(value).replace(',','').replace('，','')
    if text in {'不限','不限额','无限额','无上限'}:return None,True
    if text in {'','---','--','—','未披露','未知','暂无'}:return None,False
    m=re.fullmatch(r'(\d+(?:\.\d+)?)(万|亿)?(?:元|人民币)?',text)
    if not m:raise ValueError('Unrecognized CNY amount')
    result=float(m.group(1))*{'万':10000,'亿':100000000,None:1}[m.group(2)]
    if not math.isfinite(result) or result<0:raise ValueError('Invalid amount')
    return result,False


def percent(value:str|None):
    if value is None:return None
    match=re.search(r'(?<![\d.])(\d+(?:\.\d+)?)\s*%',value.replace('％','%'))
    if not match:return None
    result=float(match.group(1))
    if not 0<=result<=5:raise ValueError('Unexpected recurring fee rate')
    return result


def parse_status(value:str|None):
    if value is None:return None
    text=normalize(value)
    if text in {'限大额','暂停大额申购','限制大额申购','大额限购'}:return 'limited'
    if text in {'暂停申购','停止申购','封闭期','不开放申购'}:return 'paused'
    if text in {'开放申购','正常申购','可申购'}:return 'open'
    return None


def subscription_first_tier(soup:BeautifulSoup):
    # Extract only the ORIGINAL rate from the first subscription bracket.
    # The distributor discount is intentionally not exported as an Alipay fee.
    for h in soup.find_all(['h3','h4','h5','div']):
        if normalize(h.get_text('',strip=True))=='申购费率':
            table=h.find_next('table')
            if not table:return None
            for tr in table.find_all('tr'):
                cells=tr.find_all('td',recursive=False)
                if len(cells)>=2:
                    val=percent(cells[1].get_text(' ',strip=True))
                    if val is not None:return val
            return None
    return None


def validate_catalog(catalog:list[dict]):
    codes=set()
    for f in catalog:
        if not re.fullmatch(r'\d{6}',f['code']) or f['code'] in codes:raise ValueError('Duplicate/invalid fund code')
        codes.add(f['code'])
        if f['index'] not in {'sp500','nasdaq100'} or f.get('currency')!='CNY':raise ValueError('Unsupported index/currency')
        if any(word.lower() in f['name'].lower() for word in BANNED):raise ValueError('Non-standard index excluded')
        expected='S&P 500' if f['index']=='sp500' else 'Nasdaq-100'
        if f.get('benchmark')!=expected:raise ValueError('Benchmark is not the approved standard index')
        if f['structure'] not in {'index','feeder','fof'}:raise ValueError('Exchange-traded or unsupported structure excluded')
        if f['code'] in {'096001','008401'}:raise ValueError('Equal-weight fund excluded')


def parse_page(html:str,fund:dict):
    soup=BeautifulSoup(html,'html.parser')
    title=soup.title.get_text(' ',strip=True) if soup.title else ''
    if fund['code'] not in title:raise ValueError('Page identity/code not verified')
    title_clean=normalize(title)
    if any(x.lower() in title_clean.lower() for x in BANNED):raise ValueError('Unexpected non-standard index page')
    needle='标普500' if fund['index']=='sp500' else '纳斯达克100'
    if needle not in title_clean and not (fund['index']=='nasdaq100' and '纳指100' in title_clean):raise ValueError('Index identity changed; manual review required')
    raw_status=label_value(soup,'申购状态')
    status=parse_status(raw_status)
    raw_amount=label_value(soup,'日累计申购限额')
    reference=None;errors=[]
    try:
        limit,unlimited=amount(raw_amount)
        if status:
            reference={'status':status,'daily_limit':0 if status=='paused' else limit,'unlimited':unlimited and status=='open','source_displayed_limit':limit,'raw_status':raw_status,'raw_limit':raw_amount}
            if status=='limited' and (limit is None or limit<=0):
                reference['daily_limit']=None;reference['unlimited']=False
        else:errors.append('Unrecognized subscription status')
    except ValueError:
        if status=='paused':
            reference={'status':'paused','daily_limit':0,'unlimited':False,'source_displayed_limit':None,'raw_status':raw_status,'raw_limit':raw_amount}
        else:errors.append('Unrecognized daily limit')
    fee_data=None
    try:
        parts=[percent(label_value(soup,k)) for k in ['管理费率','托管费率','销售服务费率']]
        if all(v is not None for v in parts):
            fee_data=dict(zip(['management','custody','sales'],parts))
            fee_data['total']=round(sum(parts),6)
            fee_data['subscription_standard']=subscription_first_tier(soup)
        else:errors.append('Incomplete recurring fee breakdown')
    except ValueError:errors.append('Unexpected recurring fee format/range')
    if reference is None and fee_data is None:raise ValueError('; '.join(errors))
    return {'reference':reference,'fees':fee_data,'warnings':errors,'source_sha256':sha256(html.encode('utf-8')).hexdigest()}


def robots_policy():
    """Honor a public provider's robots policy; do not bypass access controls."""
    with make_session() as s:
        r=s.get(SOURCE+'/robots.txt',timeout=(8,15))
        if r.status_code in (404,410):return None
        r.raise_for_status()
        if '<html' in r.text.lower():raise ValueError('Unexpected robots response')
        p=RobotFileParser();p.set_url(SOURCE+'/robots.txt');p.parse(r.text.splitlines())
        return p


def fetch_one(fund:dict,policy:RobotFileParser|None):
    target=f'{SOURCE}/jjfl_{fund["code"]}.html'
    if policy and not policy.can_fetch(USER_AGENT,target):raise PermissionError('Provider robots policy disallows this URL')
    delay=policy.crawl_delay(USER_AGENT) if policy else None
    request_rate=policy.request_rate(USER_AGENT) if policy else None
    rate_delay=request_rate.seconds/request_rate.requests if request_rate and request_rate.requests else 0
    time.sleep(max(.5,float(delay or 0),rate_delay))
    with make_session() as s:
        r=s.get(target,timeout=(8,18));r.raise_for_status()
        if len(r.content)>2_000_000:raise ValueError('Unexpectedly large source document')
        r.encoding=r.apparent_encoding or 'utf-8'
        return parse_page(r.text,fund)


def aware_time(value:str):
    if not isinstance(value,str):raise ValueError('Missing timestamp')
    dt=datetime.fromisoformat(value.replace('Z','+00:00'))
    if dt.tzinfo is None:raise ValueError('Timestamp must include timezone')
    return dt


def validate_alipay_record(record:dict,now:datetime,allowed:set[str]):
    if record.get('code') not in allowed:raise ValueError('Fund not in whitelist')
    if record.get('scope')!='alipay':raise ValueError('Observation is not Alipay-specific')
    if record.get('status') not in VALID_STATUS-{'unknown'}:raise ValueError('Unsupported verified status')
    observed=aware_time(record.get('checked_at'));expires=aware_time(record.get('expires_at'))
    if observed>now+timedelta(minutes=5):raise ValueError('Future observation rejected')
    if expires<=observed or expires>observed+timedelta(hours=36):raise ValueError('Expiry must be within 36 hours')
    if now>expires or now-observed>timedelta(hours=36):raise ValueError('Expired Alipay evidence')
    evidence=record.get('evidence_url')
    if not isinstance(evidence,str) or urlparse(evidence).scheme!='https' or not urlparse(evidence).netloc:raise ValueError('HTTPS evidence URL required')
    limit=record.get('daily_limit')
    if limit is not None and (isinstance(limit,bool) or not isinstance(limit,(int,float)) or not math.isfinite(limit) or limit<0):raise ValueError('Invalid channel limit')
    if record['status']=='limited' and (limit is None or limit<=0):raise ValueError('Limited status requires positive limit')
    if record['status']=='paused' and limit not in (None,0):raise ValueError('Paused Alipay record cannot have buyable quota')
    accepted={k:record.get(k) for k in ['status','daily_limit','checked_at','expires_at','evidence_url','scope','note']}
    if accepted['status']=='paused':accepted['daily_limit']=0
    if len(str(accepted.get('note') or ''))>2000:raise ValueError('Unreasonably large note')
    return accepted


def read_alipay_records(now:datetime,allowed:set[str]):
    local=read_json(ROOT/'config/alipay-overrides.json',{'records':[]})
    records=local.get('records',[]);messages=[];configured=False
    feed=os.environ.get('ALIPAY_FEED_URL','')
    if feed:
        configured=True
        try:
            if urlparse(feed).scheme!='https':raise ValueError('HTTPS feed required')
            with make_session() as s:
                r=s.get(feed,timeout=(8,18));r.raise_for_status()
                if len(r.content)>2_000_000:raise ValueError('Oversized feed')
                payload=r.json()
            if payload.get('channel')!='alipay' or payload.get('schema_version')!=1 or not isinstance(payload.get('records'),list):raise ValueError('Unsupported feed schema')
            records=payload['records']+records
        except Exception:
            # Never log a private feed URL, its token or a response body.
            messages.append('Authorized Alipay feed unavailable or invalid; previous observations retained until expiry.')
    accepted={}
    for record in records:
        try:
            value=validate_alipay_record(record,now,allowed)
            old=accepted.get(record['code'])
            if old is None or aware_time(value['checked_at'])>aware_time(old['checked_at']):accepted[record['code']]=value
        except (ValueError,TypeError,KeyError):messages.append('A channel record failed validation or expired; ignored.')
    return accepted,messages,configured or bool(records)


def merge_result(fund:dict,result:dict,stamp:str):
    """Independent timestamps: only fields successfully parsed are refreshed."""
    target=f'{SOURCE}/jjfl_{fund["code"]}.html'
    fund['reference']['last_attempt_at']=stamp
    if result.get('reference') is not None:
        fund['reference'].update(result['reference'])
        fund['reference'].update(source_url=target,source_label='天天基金公开交易页',observed_at=stamp,verification='page',note='仅代表天天基金公开口径，非支付宝可买确认。暂停状态优先于页面残留旧限额。',error=None)
    else:fund['reference']['error']='申购状态未能解析；保留原始观察日期。'
    if result.get('fees') is not None:
        fund['fees'].update(result['fees'])
        fund['fees'].update(source_url=target,source_label='天天基金公开费率页',checked_at=stamp,verification='page',error=None)
    else:fund['fees']['error']='费率未完整解析；保留原值和原日期。'


def snapshot_change(old:dict,new:dict,stamp:str):
    changes=[]
    for key,title in [('reference','公开参考'),('fees','固定费率')]:
        fields=['status','daily_limit'] if key=='reference' else ['management','custody','sales','total']
        diff={f:{'before':old[key].get(f),'after':new[key].get(f)} for f in fields if old[key].get(f)!=new[key].get(f)}
        if diff:
            changes.append({'date':stamp,'type':key,'code':new['code'],'title':f'{new["code"]} {new["name"]} · {title}变化','description':'仅记录本来源字段变化，不代表支付宝已恢复或调整额度。' if key=='reference' else '公开页列示费率变化；请查看产品文件。','changes':diff})
    return changes


def update(workers=2,fixture_dir:Path|None=None):
    now=datetime.now(TZ);stamp=now.isoformat(timespec='seconds')
    path=ROOT/'site/data/funds.json';dataset=read_json(path)
    catalog=read_json(ROOT/'config/catalog.json');validate_catalog(catalog)
    expected={x['code'] for x in catalog}
    if {x['code'] for x in dataset['funds']}!=expected:raise ValueError('Snapshot/catalog mismatch: curate new entries before collecting')
    oldhealth=read_json(ROOT/'site/data/health.json',{})
    funds={f['code']:f for f in dataset['funds']};before=deepcopy(funds)
    results={};errors={};policy=None
    if fixture_dir is None:
        try:policy=robots_policy()
        except Exception:errors={f['code']:'Provider robots policy could not be checked; fetching stopped.' for f in catalog}
    if not errors:
        def task(f):
            if fixture_dir is not None:return parse_page((fixture_dir/f'{f["code"]}.html').read_text(encoding='utf-8'),f)
            return fetch_one(f,policy)
        concurrency=1 if policy and (policy.crawl_delay(USER_AGENT) or policy.request_rate(USER_AGENT)) else max(1,min(workers,2))
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            futures={pool.submit(task,f):f['code'] for f in catalog}
            for future in as_completed(futures):
                code=futures[future]
                try:results[code]=future.result()
                except Exception as e:errors[code]=f'{type(e).__name__}: source unavailable or parser rejected page; prior timestamps retained.'
    changes=[]
    for code,fund in funds.items():
        fund['reference']['last_attempt_at']=stamp
        if code in results:merge_result(fund,results[code],stamp)
        else:
            fund['reference']['error']=errors.get(code,'No validated response')
            fund['fees']['error']='最近采集失败；保留原值和原费率日期。'
        changes.extend(snapshot_change(before[code],fund,stamp))
    channel,messages,channel_configured=read_alipay_records(now,expected)
    for code,value in channel.items():
        current=funds[code].get('alipay',{})
        try:newer=not current.get('checked_at') or aware_time(value['checked_at'])>=aware_time(current['checked_at'])
        except ValueError:newer=True
        if newer:funds[code]['alipay']=value
    complete=sum(r.get('reference') is not None and r.get('fees') is not None for r in results.values())
    observed=sum(r.get('reference') is not None for r in results.values())
    status='ok' if complete==len(catalog) else 'partial' if results else 'failed'
    if results:dataset['meta']['snapshot_date']=now.date().isoformat()
    dataset['meta'].update(generated_at=stamp,mode='collected',schedule_active=os.environ.get('SCHEDULE_ENABLED')=='true')
    dataset['funds']=list(funds.values())
    health=dict(mode='collected',status=status,last_attempt_at=stamp,last_success_at=stamp if status=='ok' else oldhealth.get('last_success_at'),source='eastmoney',succeeded=complete,partial=len(results)-complete,failed=len(errors),total=len(catalog),reference_updated=observed,alipay_status='configured' if channel_configured else 'not_connected',alipay_records_accepted=len(channel),message=f'公开来源：完整成功 {complete}/{len(catalog)}，部分成功 {len(results)-complete}，失败 {len(errors)}。支付宝记录单独核验；未知不会自动变成可买。',warnings=messages,errors=errors)
    evidence={'checked_at':stamp,'source':SOURCE,'facts':{code:{'sha256':r['source_sha256'],'reference':r['reference'],'fees':r['fees'],'warnings':r['warnings']} for code,r in results.items()}}
    hist=read_json(ROOT/'site/data/history.json',[])
    run={'date':stamp,'type':'run','title':'公开数据检查完成' if status=='ok' else '公开数据检查存在缺失','description':health['message']}
    atomic_json(path,dataset);atomic_json(ROOT/'site/data/health.json',health)
    atomic_json(ROOT/'site/data/history.json',([run]+changes+hist)[:500])
    atomic_json(ROOT/'evidence/latest.json',evidence)
    print(health['message'])
    # Publishing the truthful failure state is intentional. The workflow checks
    # health after publication and then raises an alert without faking freshness.
    return health


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workers',type=int,default=2);p.add_argument('--fixtures',type=Path,help='Offline parser fixtures for testing, never a live-data substitute')
    a=p.parse_args();update(a.workers,a.fixtures)
