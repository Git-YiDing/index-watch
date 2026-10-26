#!/usr/bin/env python3
"""Dated cumulative fund returns from public NAV history, with cash reinvestment.

Never execute provider JavaScript. Unknown corporate actions invalidate affected
periods, and failed refreshes keep the previous observation and its date.
"""
from __future__ import annotations

import argparse
from bisect import bisect_right
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import date, datetime, timedelta
from hashlib import sha256
import json
import math
from pathlib import Path
import re
from zoneinfo import ZoneInfo

import requests

ROOT = Path(__file__).resolve().parents[1]
TZ = ZoneInfo('Asia/Shanghai')
PERIODS = ('1y', '2y', '3y', '4y', '5y', 'all')


def assignment(text, name):
    match = re.search(r'\bvar\s+' + re.escape(name) + r'\s*=\s*(.*?);', text, re.S)
    if not match:
        raise ValueError(f'Missing provider field: {name}')
    return json.loads(match[1])


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def years_before(day, years):
    try:
        return day.replace(year=day.year-years)
    except ValueError:
        return day.replace(year=day.year-years, day=28)


def calculate_returns(text, code, now=None):
    now = now or datetime.now(TZ)
    if assignment(text, 'fS_code') != code:
        raise ValueError('Provider fund code mismatch')
    nav = assignment(text, 'Data_netWorthTrend')
    accumulated = assignment(text, 'Data_ACWorthTrend')
    if not isinstance(nav, list) or len(nav) < 2:
        raise ValueError('Insufficient NAV history')
    ac = {row[0]: row[1] for row in accumulated
          if isinstance(row, list) and len(row) == 2 and finite(row[0]) and finite(row[1])}
    dates = []
    for point in nav:
        if not isinstance(point, dict) or not finite(point.get('x')) or not finite(point.get('y')) or point['y'] <= 0:
            raise ValueError('Invalid NAV point')
        day = datetime.fromtimestamp(point['x']/1000, TZ).date()
        if (dates and day <= dates[-1]) or day > now.date():
            raise ValueError('Unordered, duplicated or future NAV dates')
        dates.append(day)

    # Each step is (post-distribution NAV + cash per share) / previous NAV.
    # Accumulated NAV is used only to recover a cash amount at a marked dividend,
    # never as a ratio: such a ratio would mishandle dividend reinvestment.
    factors = [1.0]
    errors = [None]
    for i in range(1, len(nav)):
        point, prev = nav[i], nav[i-1]
        action = str(point.get('unitMoney') or '')
        cash, error = 0.0, None
        before = ac.get(prev['x'])
        after = ac.get(point['x'])
        delta = ((after-point['y'])-(before-prev['y'])) if before is not None and after is not None else None
        if (dates[i]-dates[i-1]).days > 31:
            error = '净值历史不完整'
        if action:
            if '分红' in action and '派现金' in action and not re.search(r'折算|拆分|合并', action):
                # Provider sometimes omits the amount in its dividend label.
                if delta is not None and delta > 0:
                    cash = delta
                else:
                    error = '分红金额待核验'
            else:
                error = '份额变动待核验'
        elif delta is not None and abs(delta) > 0.000002:
            error = '净值调整待核验'
        factors.append((point['y']+cash)/prev['y'])
        errors.append(error)

    periods = {}
    for period in PERIODS:
        target = dates[0] if period == 'all' else years_before(dates[-1], int(period[0]))
        start = bisect_right(dates, target)-1
        item = {'value': None, 'start_date': None, 'end_date': dates[-1].isoformat(), 'reason': None}
        if start < 0:
            item['reason'] = '历史不足'
        elif (target-dates[start]).days > 14:
            item['reason'] = '区间起点缺失'
        elif any(errors[start+1:]):
            item['reason'] = next(x for x in errors[start+1:] if x)
        else:
            value = (math.prod(factors[start+1:])-1)*100
            if not math.isfinite(value) or value < -100:
                raise ValueError('Invalid calculated return')
            item.update(value=round(value, 6), start_date=dates[start].isoformat())
        periods[period] = item

    # Independent provider-published one-year return catches parsing/action bugs.
    published = assignment(text, 'syl_1n')
    try:
        published = float(published)
    except (TypeError, ValueError):
        published = None
    computed = periods['1y']['value']
    if published is not None and (not math.isfinite(published) or computed is not None and abs(published-computed) > 0.06):
        raise ValueError('One-year return disagrees with provider')
    return {
        'code': code,
        'source_label': '天天基金公开净值历史',
        'source_url': f'https://fund.eastmoney.com/{code}.html',
        'data_url': f'https://fund.eastmoney.com/pingzhongdata/{code}.js',
        'source_sha256': sha256(text.encode('utf-8')).hexdigest(),
        'checked_at': now.isoformat(timespec='seconds'),
        'as_of': dates[-1].isoformat(),
        'history_start': dates[0].isoformat(),
        'method': 'nav_cash_reinvestment',
        'provider_one_year': published,
        'periods': periods,
        'error': None,
    }


def refresh(cache_directory=None):
    catalog = json.loads((ROOT/'config/catalog.json').read_text())
    target = ROOT/'site/data/returns.json'
    previous = json.loads(target.read_text()) if target.exists() else {'funds': {}}
    now = datetime.now(TZ)

    def collect(fund):
        code = fund['code']
        try:
            cached = cache_directory/f'{code}.js' if cache_directory else None
            if cached and cached.exists():
                text = cached.read_text(encoding='utf-8-sig')
            else:
                res = requests.get(f'https://fund.eastmoney.com/pingzhongdata/{code}.js',
                                   headers={'User-Agent': 'IndexWatch/0.2 (public-fund-NAV)'}, timeout=(10, 25))
                res.raise_for_status()
                text = res.content.decode('utf-8-sig')
            return code, calculate_returns(text, code, now)
        except Exception:
            old = deepcopy(previous.get('funds', {}).get(code, {}))
            old.update(code=code, error='最近收益数据读取或校验失败，保留原始日期', last_attempt_at=now.isoformat(timespec='seconds'))
            return code, old

    with ThreadPoolExecutor(max_workers=4) as pool:
        funds = dict(pool.map(collect, catalog))
    result = {
        'meta': {
            'schema_version': 1, 'last_attempt_at': now.isoformat(timespec='seconds'),
            'return_type': 'cumulative', 'currency': 'CNY',
            'method_note': '区间累计收益率（非年化），现金分红按除息日净值再投资；未计个人申购赎回费用。年份相对各份额最新净值日回溯，起点取当日或之前最近一次净值。全部为最早可得净值日起算，未必等于基金法律成立日。',
            'success_count': sum(not f.get('error') for f in funds.values()),
            'total_count': len(catalog),
        },
        'funds': funds,
    }
    temp = target.with_suffix('.json.tmp')
    temp.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    temp.replace(target)
    print(f"Return history validated: {result['meta']['success_count']}/{len(catalog)} shares")
    for period in PERIODS:
        print(period, sum(f.get('periods', {}).get(period, {}).get('value') is not None for f in funds.values()))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--cache-directory', type=Path, help='Reuse source bytes collected during this run')
    args = parser.parse_args()
    refresh(args.cache_directory)
