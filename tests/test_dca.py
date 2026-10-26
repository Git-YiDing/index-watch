"""Synthetic NAV ledgers and calendar boundaries for the rolling DCA column."""
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from test_returns import fixture, daily, TZ
import update_returns as returns
from validate import validate_dca, collection_complete


class DcaTests(unittest.TestCase):
    def calculate(self, points, today=date(2026,10,26), period='all'):
        record=returns.calculate_returns(fixture(points),'017641',datetime.combine(today,datetime.min.time(),TZ))
        return record['dca']['periods'][period]

    def test_today_is_anchor_even_when_last_nav_lags(self):
        points=daily(date(2022,1,1),date(2026,10,23))
        result=returns.calculate_returns(fixture(points),'017641',datetime(2026,10,26,tzinfo=TZ))
        for years in (1,2,3):
            item=result['dca']['periods'][f'{years}y']
            self.assertEqual(item['requested_start'],f'{2026-years}-10-26')
            self.assertEqual(item['requested_end'],'2026-10-26')
            self.assertEqual(item['valuation_date'],'2026-10-23')
        self.assertEqual(result['dca']['periods']['1y']['first_contribution'],'2025-10-27')
        validate_dca(result)

    def test_rolling_window_moves_each_calendar_day(self):
        points=daily(date(2024,1,1),date(2026,10,23),lambda i:1+i*.001)
        a=self.calculate(points,date(2026,10,27),'1y')
        b=self.calculate(points,date(2026,10,28),'1y')
        self.assertEqual(a['requested_start'],'2025-10-27')
        self.assertEqual(b['requested_start'],'2025-10-28')
        self.assertEqual(a['contribution_count']-b['contribution_count'],1)
        self.assertNotEqual(a['profit'],b['profit'])

    def test_only_weekdays_with_nav_count_and_endpoints_are_included(self):
        points=daily(date(2026,10,19),date(2026,10,26))
        points=[p for p in points if p[0]!=date(2026,10,21)]
        item=self.calculate(points)
        self.assertEqual(item['contribution_count'],5)
        self.assertEqual(item['invested'],500)
        self.assertEqual(item['market_value'],500)
        self.assertEqual(item['value'],0)
        self.assertEqual(item['last_contribution'],'2026-10-26')

    def test_independent_share_ledger_matches_increasing_and_falling_nav(self):
        for values in ([1,2,4],[4,2,1]):
            points=[(date(2026,10,19)+timedelta(days=i),v,v,'') for i,v in enumerate(values)]
            item=self.calculate(points)
            expected=sum(100/v for v in values)*values[-1]
            self.assertAlmostEqual(item['market_value'],expected,places=2)
            self.assertAlmostEqual(item['value'],(expected/300-1)*100,places=5)

    def test_new_deposit_does_not_receive_same_day_return_or_dividend(self):
        points=[(date(2026,10,19),1,1,''),
                (date(2026,10,20),.9,1.1,'分红：每10份派现金2元'),
                (date(2026,10,21),1.8,2,'')]
        item=self.calculate(points)
        # Day one:100; day two:100*1.1+100=210; day three:210*2+100=520.
        self.assertEqual(item['market_value'],520)
        self.assertEqual(item['profit'],220)
        self.assertAlmostEqual(item['value'],220/300*100,places=5)

    def test_all_uses_own_history_and_initial_nav_can_be_two(self):
        points=[(date(2026,10,19),2,2,''),(date(2026,10,20),4,4,'')]
        item=self.calculate(points)
        self.assertEqual(item['requested_start'],'2026-10-19')
        self.assertEqual(item['market_value'],300)
        self.assertEqual(item['value'],50)

    def test_young_share_is_unknown_for_full_year(self):
        item=self.calculate(daily(date(2026,1,1),date(2026,10,23)),period='1y')
        self.assertEqual(item['reason'],'历史不足')
        self.assertIsNone(item['value'])
        self.assertIsNone(item['invested'])

    def test_leap_day_uses_calendar_anniversary(self):
        item=self.calculate(daily(date(2022,1,1),date(2024,2,28)),date(2024,2,29),'1y')
        self.assertEqual(item['requested_start'],'2023-02-28')
        self.assertEqual(item['requested_end'],'2024-02-29')

    def test_anchor_uses_shanghai_date_for_utc_input(self):
        record=returns.calculate_returns(fixture(daily(date(2022,1,1),date(2026,10,23))),
                                        '017641',datetime(2026,10,25,17,tzinfo=timezone.utc))
        self.assertEqual(record['dca']['basis_date'],'2026-10-26')

    def test_unresolved_actions_and_large_gaps_are_unknown(self):
        for points in [[(date(2026,10,19),2,2,''),(date(2026,10,20),1,1,'份额拆分')],
                       [(date(2026,1,1),1,1,''),(date(2026,3,2),2,2,'')]]:
            item=self.calculate(points)
            self.assertIsNone(item['value'])
            self.assertTrue(item['reason'])

    def test_unknown_action_before_first_deposit_does_not_invalidate_later_window(self):
        points=daily(date(2025,1,1),date(2026,10,23))
        points[100]=(points[100][0],1,1,'份额拆分')
        item=self.calculate(points,period='1y')
        self.assertEqual(item['value'],0)

    def test_no_weekday_nav_is_unknown(self):
        points=daily(date(2026,10,24),date(2026,10,25))
        self.assertEqual(self.calculate(points)['reason'],'区间内无可用工作日净值')

    def test_failed_refresh_retains_original_dca_basis_and_amounts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'config').mkdir();(root/'site/data').mkdir(parents=True)
            (root/'config/catalog.json').write_text('[{"code":"017641"}]')
            record=returns.calculate_returns(fixture(daily(date(2024,1,1),date(2026,10,23))),
                                             '017641',datetime(2026,10,26,tzinfo=TZ))
            (root/'site/data/returns.json').write_text(json.dumps({'funds':{'017641':record}}))
            with patch.object(returns,'ROOT',root),patch.object(returns.requests,'get',side_effect=RuntimeError('offline')):
                refreshed=returns.refresh()['funds']['017641']
            self.assertEqual(refreshed['dca'],record['dca'])
            self.assertTrue(refreshed['error'])

    def test_validation_rejects_fixed_start_date_or_inconsistent_cash(self):
        record=returns.calculate_returns(fixture(daily(date(2024,1,1),date(2026,10,23))),
                                         '017641',datetime(2026,10,26,tzinfo=TZ))
        validate_dca(record)
        record['dca']['periods']['1y']['requested_start']='2024-01-01'
        with self.assertRaises(AssertionError):validate_dca(record)
        record['dca']['periods']['1y']['requested_start']='2025-10-26'
        record['dca']['periods']['1y']['profit']+=100
        with self.assertRaises(AssertionError):validate_dca(record)

    def test_missing_dca_fails_new_schema_health_check(self):
        result={'meta':{'dca_schema_version':1,'success_count':1,'total_count':1},
                'funds':{'017641':{'error':None}}}
        self.assertFalse(collection_complete({'status':'ok'},result))
