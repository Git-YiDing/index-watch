"""Validate the public snapshot and prohibit accidental index contamination."""
from pathlib import Path
import json
import math
import sys
from datetime import date
from update import validate_catalog
ROOT=Path(__file__).resolve().parents[1]

def collection_complete(health, returns):
    meta=returns.get('meta',{})
    funds=returns.get('funds',{})
    total=meta.get('total_count',0)
    return (health.get('status')=='ok' and total>0
            and meta.get('success_count')==total and len(funds)==total
            and all(not f.get('error') for f in funds.values()))

def validate():
    catalog=json.loads((ROOT/'config/catalog.json').read_text(encoding='utf-8'))
    validate_catalog(catalog)
    data=json.loads((ROOT/'site/data/funds.json').read_text(encoding='utf-8'))
    assert len(data['funds'])==len(catalog)
    assert {f['code'] for f in data['funds']}=={f['code'] for f in catalog}
    for f in data['funds']:
        assert f['reference']['status'] in {'open','limited','paused','unknown'}
        assert f['alipay']['status'] in {'open','limited','paused','unknown'}
        fees=f['fees'];parts=[fees.get(x) for x in ['management','custody','sales']]
        for p in parts+[fees['total']]:assert p is None or isinstance(p,(int,float)) and math.isfinite(p) and 0<=p<=10
        if all(p is not None for p in parts):assert fees['total'] is not None and abs(sum(parts)-fees['total'])<1e-5
        if f['reference']['status']=='paused':assert f['reference']['daily_limit'] in (None,0)
        if f['reference']['status']=='unknown':assert f['reference']['daily_limit'] is None
        if f['alipay']['status']!='unknown':
            assert all(f['alipay'].get(x) for x in ['checked_at','expires_at','evidence_url','scope'])
            assert f['alipay']['scope']=='alipay'
    returns_path=ROOT/'site/data/returns.json'
    if returns_path.exists():
        returns=json.loads(returns_path.read_text())
        assert returns['meta']['schema_version']==1
        assert set(returns['funds'])=={f['code'] for f in catalog}
        for code,record in returns['funds'].items():
            assert record['code']==code
            for period in ('1y','2y','3y','4y','5y','all'):
                item=record.get('periods',{}).get(period,{})
                value=item.get('value')
                if value is not None:
                    assert isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value) and value>=-100
                    assert date.fromisoformat(item['start_date'])<=date.fromisoformat(item['end_date'])
                    assert item['end_date']==record['as_of']
                    assert record['source_url'].startswith('https://fund.eastmoney.com/')
        print('Validated dated cumulative return periods.')
    print(f'Validated {len(data["funds"])} standard-index share classes.')

if __name__=='__main__':
    validate()
    if '--health' in sys.argv:
        health=json.loads((ROOT/'site/data/health.json').read_text(encoding='utf-8'))
        returns=json.loads((ROOT/'site/data/returns.json').read_text(encoding='utf-8'))
        if not collection_complete(health,returns):
            print('Quota, fee or return collection incomplete: truthful status published; review workflow and provider availability.',file=sys.stderr)
            sys.exit(1)
