"""Validate the public snapshot and prohibit accidental index contamination."""
from pathlib import Path
import json
import math
import sys
from datetime import date
from update import validate_catalog
from update_returns import years_before, DCA_PERIODS
ROOT=Path(__file__).resolve().parents[1]

def collection_complete(health, returns):
    meta=returns.get('meta',{})
    funds=returns.get('funds',{})
    total=meta.get('total_count',0)
    return (health.get('status')=='ok' and total>0
            and meta.get('success_count')==total and len(funds)==total
            and all(not f.get('error') for f in funds.values())
            and (meta.get('dca_schema_version') != 1 or all(f.get('dca') for f in funds.values())))

def validate_dca(record):
    dca=record.get('dca')
    if not dca:
        assert record.get('error'), 'Missing DCA result without an error marker'
        return
    assert dca['schema_version']==1 and dca['daily_amount']==100
    assert dca['timezone']=='Asia/Shanghai'
    basis=date.fromisoformat(dca['basis_date'])
    assert set(dca['periods'])==set(DCA_PERIODS)
    for key,item in dca['periods'].items():
        expected=date.fromisoformat(record['history_start']) if key=='all' else years_before(basis,int(key[0]))
        assert date.fromisoformat(item['requested_start'])==expected
        assert item['requested_end']==basis.isoformat()
        assert item['valuation_date']==record['as_of']
        assert date.fromisoformat(item['valuation_date'])<=basis
        if item['value'] is None:
            assert item['reason']
            assert all(item[k] is None for k in ('profit','invested','market_value','contribution_count'))
            continue
        assert item['reason'] is None
        assert all(isinstance(item[k],(int,float)) and not isinstance(item[k],bool) and math.isfinite(item[k])
                   for k in ('value','profit','invested','market_value'))
        assert isinstance(item['contribution_count'],int) and not isinstance(item['contribution_count'],bool) and item['contribution_count']>0
        assert item['invested']==100*item['contribution_count']
        assert item['value']>=-100 and item['market_value']>=0
        assert abs(item['market_value']-item['invested']-item['profit'])<.011
        assert abs(item['profit']/item['invested']*100-item['value'])<.006
        first=date.fromisoformat(item['first_contribution']);last=date.fromisoformat(item['last_contribution'])
        assert expected<=first<=last<=date.fromisoformat(record['as_of'])
        assert first.weekday()<5 and last.weekday()<5

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
            if returns['meta'].get('dca_schema_version')==1:
                validate_dca(record)
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
