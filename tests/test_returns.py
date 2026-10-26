"""Financial calculation edge cases; all fixture NAVs are synthetic."""
from datetime import datetime, date, timedelta
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import update_returns as returns

TZ = ZoneInfo('Asia/Shanghai')
NOW = datetime(2026, 10, 26, tzinfo=TZ)


def fixture(points, published='', code='017641'):
    # points = (date, unit NAV, accumulated NAV, action description)
    nav, ac = [], []
    for day, value, accumulated, action in points:
        stamp = int(datetime.combine(day, datetime.min.time(), TZ).timestamp()*1000)
        nav.append(dict(x=stamp, y=value, unitMoney=action))
        ac.append([stamp, accumulated])
    return ''.join(f'var {key}={json.dumps(value)};' for key, value in {
        'fS_code': code, 'Data_netWorthTrend': nav,
        'Data_ACWorthTrend': ac, 'syl_1n': published,
    }.items())


def daily(first, last, value=lambda i: 1.0):
    return [(first+timedelta(days=i), value(i), value(i), '')
            for i in range((last-first).days+1)]


class ReturnCalculationTests(unittest.TestCase):
    def test_calendar_year_and_nonannualized_return(self):
        data = daily(date(2023, 10, 22), date(2026, 10, 22), lambda i: 1+i/1000)
        result = returns.calculate_returns(fixture(data), '017641', NOW)
        year = result['periods']['2y']
        self.assertEqual(year['start_date'], '2024-10-22')
        self.assertAlmostEqual(year['value'], (data[-1][1]/data[366][1]-1)*100, places=5)
        self.assertIsNone(result['periods']['4y']['value'])
        self.assertEqual(result['periods']['4y']['reason'], '历史不足')

    def test_dividends_reinvest_instead_of_accumulated_nav_ratio(self):
        data = [(date(2026, 1, 1), 1, 1, ''),
                (date(2026, 1, 2), .9, 1.1, '分红：每10份派现金元'),
                (date(2026, 1, 3), 1.8, 2, '')]
        result = returns.calculate_returns(fixture(data), '017641', NOW)
        self.assertAlmostEqual(result['periods']['all']['value'], 120)

    def test_new_share_uses_own_first_nav_not_one_yuan(self):
        data = [(date(2026, 1, 1), 2, 2, ''), (date(2026, 1, 2), 3, 3, '')]
        result = returns.calculate_returns(fixture(data), '017641', NOW)
        self.assertEqual(result['periods']['all']['value'], 50)
        self.assertIsNone(result['periods']['1y']['value'])

    def test_zero_and_negative_returns_are_known_values(self):
        for end, expected in [(1, 0), (.8, -20)]:
            data = [(date(2026, 1, 1), 1, 1, ''), (date(2026, 1, 2), end, end, '')]
            self.assertAlmostEqual(returns.calculate_returns(fixture(data), '017641', NOW)['periods']['all']['value'], expected)

    def test_unknown_share_split_is_not_reported_as_a_loss(self):
        data = [(date(2026, 1, 1), 2, 2, ''), (date(2026, 1, 2), 1, 1, '份额拆分')]
        result = returns.calculate_returns(fixture(data), '017641', NOW)['periods']['all']
        self.assertIsNone(result['value'])
        self.assertEqual(result['reason'], '份额变动待核验')

    def test_missing_dividend_amount_is_unknown(self):
        data = [(date(2026, 1, 1), 1, 1, ''), (date(2026, 1, 2), .9, .9, '分红：每10份派现金元')]
        self.assertIsNone(returns.calculate_returns(fixture(data), '017641', NOW)['periods']['all']['value'])

    def test_unmarked_adjustment_and_data_gaps_are_unknown(self):
        for data in [[(date(2026, 1, 1), 1, 1, ''), (date(2026, 1, 2), .9, 1.1, '')],
                     [(date(2026, 1, 1), 1, 1, ''), (date(2026, 3, 1), 1.1, 1.1, '')]]:
            self.assertIsNone(returns.calculate_returns(fixture(data), '017641', NOW)['periods']['all']['value'])

    def test_leap_day_clamps_to_february_28(self):
        self.assertEqual(returns.years_before(date(2024, 2, 29), 1), date(2023, 2, 28))

    def test_nontrading_anniversary_uses_prior_nav(self):
        data = daily(date(2024, 1, 1), date(2026, 1, 5))
        data = [p for p in data if p[0] != date(2025, 1, 5)]
        result = returns.calculate_returns(fixture(data, '0'), '017641', NOW)
        self.assertEqual(result['periods']['1y']['start_date'], '2025-01-04')

    def test_provider_one_year_crosscheck_rejects_inconsistent_history(self):
        data = daily(date(2024, 1, 1), date(2026, 1, 1))
        with self.assertRaises(ValueError):
            returns.calculate_returns(fixture(data, '15'), '017641', NOW)

    def test_wrong_code_future_dates_and_invalid_values_rejected(self):
        data = [(date(2026, 1, 1), 1, 1, ''), (date(2026, 1, 2), 1, 1, '')]
        for text in [fixture(data, code='000001'), fixture(data[::-1]),
                     fixture([(date(2027, 1, 1), 1, 1, ''), (date(2027, 1, 2), 1, 1, '')]),
                     fixture([(date(2026, 1, 1), 0, 0, ''), data[1]])]:
            with self.assertRaises(ValueError):
                returns.calculate_returns(text, '017641', NOW)

    def test_failed_refresh_retains_values_and_original_date(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'config').mkdir()
            (root/'site/data').mkdir(parents=True)
            (root/'config/catalog.json').write_text('[{"code":"017641"}]')
            previous = {'funds': {'017641': {'as_of': '2026-01-01', 'checked_at': '2026-01-02',
                        'periods': {'1y': {'value': 10}}}}}
            (root/'site/data/returns.json').write_text(json.dumps(previous))
            with patch.object(returns, 'ROOT', root), patch.object(returns.requests, 'get', side_effect=RuntimeError('offline')):
                record = returns.refresh()['funds']['017641']
            self.assertEqual(record['periods']['1y']['value'], 10)
            self.assertEqual(record['as_of'], '2026-01-01')
            self.assertEqual(record['checked_at'], '2026-01-02')
            self.assertTrue(record['error'])


if __name__ == '__main__':
    unittest.main()
