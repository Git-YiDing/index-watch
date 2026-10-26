"""Build the initial, explicitly sourced preview snapshot. Not a live collector."""
from pathlib import Path
import json

ROOT=Path(__file__).resolve().parents[1]
STAMP='2026-10-26'
AGG='https://qdii.qinguanghui.com/'
FAMILIES=[
 ('sp500','摩根','摩根标普500指数','index',[('A','017641'),('C','019305')]),
 ('sp500','博时','博时标普500ETF联接','feeder',[('A','050025'),('C','006075'),('E','018738')]),
 ('sp500','国泰','国泰标普500ETF发起联接','feeder',[('A','017028'),('C','017030')]),
 ('sp500','华夏','华夏标普500ETF发起式联接','feeder',[('A','018064'),('C','018065')]),
 ('sp500','易方达','易方达标普500指数','index',[('A','161125'),('C','012860')]),
 ('sp500','天弘','天弘标普500发起','fof',[('A','007721'),('C','007722'),('D','022523')]),
 ('nasdaq100','摩根','摩根纳斯达克100指数','index',[('A','019172'),('C','019173')]),
 ('nasdaq100','南方','南方纳斯达克100指数发起','index',[('A','016452'),('C','016453'),('I','021000')]),
 ('nasdaq100','宝盈','宝盈纳斯达克100指数发起','index',[('A','019736'),('C','019737')]),
 ('nasdaq100','万家','万家纳斯达克100指数发起式','index',[('A','019441'),('C','019442')]),
 ('nasdaq100','华泰柏瑞','华泰柏瑞纳斯达克100ETF发起式联接','feeder',[('A','019524'),('C','019525'),('I','022664')]),
 ('nasdaq100','大成','大成纳斯达克100ETF联接','feeder',[('A','000834'),('C','008971')]),
 ('nasdaq100','建信','建信纳斯达克100指数','index',[('A','539001'),('C','012752'),('D','023422')]),
 ('nasdaq100','天弘','天弘纳斯达克100指数发起','index',[('A','018043'),('C','018044'),('D','022525')]),
 ('nasdaq100','广发','广发纳斯达克100ETF联接','feeder',[('A','270042'),('C','006479')]),
 ('nasdaq100','华夏','华夏纳斯达克100ETF发起式联接','feeder',[('A','015299'),('C','015300')]),
 ('nasdaq100','易方达','易方达纳斯达克100ETF联接','feeder',[('A','161130'),('C','012870')]),
 ('nasdaq100','嘉实','嘉实纳斯达克100ETF发起联接','feeder',[('A','016532'),('C','016533'),('I','021838')]),
 ('nasdaq100','博时','博时纳斯达克100ETF发起式联接','feeder',[('A','016055'),('C','016057')]),
 ('nasdaq100','招商','招商纳斯达克100ETF发起式联接','feeder',[('A','019547'),('C','019548')]),
 ('nasdaq100','汇添富','汇添富纳斯达克100ETF发起式联接','feeder',[('A','018966'),('C','018967'),('E','021773')]),
 ('nasdaq100','华安','华安纳斯达克100ETF联接','feeder',[('A','040046'),('C','014978')]),
 ('nasdaq100','国泰','国泰纳斯达克100指数','index',[('A','160213')]),
]
# Numerical facts from the publicly readable 2026-10-26 aggregation. No fee
# breakdown is inferred from an annual total. No amount is called Alipay-verified.
TOTALS={
 '017641':.65,'019305':.95,'022523':1.05,
 '019172':.60,'019173':.90,'016452':.65,'016453':.75,'021000':.66,
 '019736':.65,'019737':.90,'019441':.65,'019442':.85,
 '019524':.65,'019525':.90,'022664':.75,'000834':1.00,'008971':1.30,
 '539001':1.00,'012752':1.30,'023422':1.30,'022525':.80}
LIMITS={c:10 for c in ['017641','019305','019172','019173','016452','016453','019736','019737','000834','008971','539001','012752','023422']}
LIMITS.update({c:5 for c in ['019441','019442','019524','019525','022664']})
# These pages were individually opened during this build. Paused status takes
# priority over any obsolete numerical limit still visible on the source page.
DIRECT={
 '017641': {'fees':[.50,.15,.00],'status':'limited','limit':10,'subscribe':1.20},
 '019172': {'fees':[.50,.10,.00],'status':'limited','limit':10,'subscribe':1.20},
 '050025': {'fees':[.60,.20,.00],'status':'paused','limit':0,'subscribe':1.20},
 '017028': {'fees':[.60,.15,.00],'status':'paused','limit':0,'subscribe':1.00},
 '018064': {'fees':[.60,.15,.00],'status':'paused','limit':0,'subscribe':1.20},
 '161125': {'fees':[.80,.20,.00],'status':'paused','limit':0,'subscribe':1.20},
 '016532': {'fees':[.50,.10,.00],'status':'paused','limit':0,'subscribe':1.00},
}
# Aggregate explicitly lists these paused share classes by code.
AGG_PAUSED={'016532','018043','161130','016055','018966','019547','021838','017028','018064','021773'}
CONFLICT={'019441','019442','022523','022525'}
rows=[];catalog=[]
for index,manager,base,structure,classes in FAMILIES:
 for cls,code in classes:
  url=f'https://fundf10.eastmoney.com/jjfl_{code}.html'
  info=f'https://fundf10.eastmoney.com/jbgk_{code}.html'
  entry=dict(code=code,name=f'{base} {cls}',manager=manager,index=index,share_class=cls,structure=structure,currency='CNY',benchmark='S&P 500' if index=='sp500' else 'Nasdaq-100',profile_url=info,fee_url=url)
  catalog.append(entry.copy())
  fees=dict(management=None,custody=None,sales=None,total=TOTALS.get(code),subscription_standard=None,subscription_alipay=None,source_url=AGG if code in TOTALS else None,source_label='公开汇总 · 待逐项复核' if code in TOTALS else '待核验',checked_at=STAMP if code in TOTALS else None,verification='aggregate' if code in TOTALS else 'unknown')
  ref=dict(status='unknown',daily_limit=None,source_url=None,source_label='首版目录 · 待复核',observed_at=None,verification='unknown',note='已收录该份额；当前申购状态尚未完成独立核验。',last_attempt_at=None,error=None)
  if code in LIMITS:
   ref.update(status='limited',daily_limit=LIMITS[code],source_url=AGG,source_label='公开额度汇总',observed_at=STAMP,verification='aggregate',note='第三方公开汇总，非支付宝实时交易确认。')
  elif code in AGG_PAUSED:
   ref.update(status='paused',daily_limit=0,source_url=AGG,source_label='公开额度汇总',observed_at=STAMP,verification='aggregate',note='公开汇总列为暂停；支付宝渠道仍需核验。')
  elif code not in TOTALS:
   # These are earlier conversation records, not new live observations.
   ref.update(status='paused',daily_limit=0,source_label='前次查询记录 · 待复核',verification='historical',note='沿用前次查询的暂停记录，仅用于首版展示；未在本次读取到完整的新来源。')
  if code in CONFLICT:
   ref.update(status='unknown',daily_limit=None,source_url=AGG,source_label='公开来源存在冲突',observed_at=STAMP,verification='conflicting',note='此前不同公开来源的状态/额度不一致，暂不判定可买；不得将未知显示为不限购。')
  if code=='021000':
   ref.update(source_url=AGG,source_label='公开汇总 · 额度未披露',observed_at=STAMP,verification='aggregate',note='汇总未披露限额，未知不等于不限购。')
  if code in DIRECT:
   d=DIRECT[code]
   fees.update(management=d['fees'][0],custody=d['fees'][1],sales=d['fees'][2],total=round(sum(d['fees']),4),subscription_standard=d['subscribe'],source_url=url,source_label='天天基金公开费率页',checked_at=STAMP,verification='page')
   ref.update(status=d['status'],daily_limit=d['limit'],source_url=url,source_label='天天基金公开交易页',observed_at=STAMP,verification='page',note='此为天天基金渠道状态，不能直接替代支付宝。暂停时忽略页面残留旧额度。')
  entry.update(fees=fees,reference=ref,alipay=dict(status='unknown',daily_limit=None,checked_at=None,expires_at=None,evidence_url=None,scope=None,note='未接入支付宝已授权数据；需在支付宝搜索基金代码核验。'),quota_group=None)
  if structure=='feeder': entry['fee_note']='联接基金存在目标ETF相关费用及计提豁免；列示三项费率不是穿透后的实际总费用率，不能机械双加。'
  elif structure=='fof': entry['fee_note']='FOF底层基金费用可能另有影响；此处三项费率不是穿透后的总费用率。'
  else: entry['fee_note']='三项固定费率合计不含交易成本、税费及一次性申购赎回费用。'
  rows.append(entry)
meta=dict(version='0.1.0',snapshot_date=STAMP,generated_at=STAMP,mode='preview',title='指数观察',source_note='首版公开快照；支付宝渠道尚未核验。部分暂停记录来自前次查询，已独立标注。',schedule_timezone='Asia/Shanghai',schedule_times=['08:17','14:17'],schedule_active=False,reference_ttl_hours=36,fee_ttl_days=90,catalog_count=len(rows),coverage_note='首版人工白名单，不承诺穷尽市场；按份额代码计数。')
(ROOT/'config/catalog.json').write_text(json.dumps(catalog,ensure_ascii=False,indent=2)+'\n')
(ROOT/'config/alipay-overrides.json').write_text('{"records": []}\n')
(ROOT/'site/data/funds.json').write_text(json.dumps(dict(meta=meta,funds=rows),ensure_ascii=False,indent=2)+'\n')
(ROOT/'site/data/health.json').write_text(json.dumps(dict(mode='preview',status='not_deployed',last_attempt_at=None,last_success_at=None,source='eastmoney',succeeded=0,failed=0,alipay_status='not_connected',message='预览快照；每日更新工作流已提供，尚未部署或启用。'),ensure_ascii=False,indent=2)+'\n')
(ROOT/'site/data/history.json').write_text(json.dumps([dict(date=STAMP,type='initial',title='首版数据目录建立',description=f'收录 {len(rows)} 个人民币份额；排除等权重、增强、行业主题和场内ETF。首版不包含真实额度变更历史。')],ensure_ascii=False,indent=2)+'\n')
print('Created',len(rows),'fund classes;',sum(f['fees']['total'] is not None for f in rows),'known fee totals.')
