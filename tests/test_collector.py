import copy
from datetime import datetime,timedelta
from pathlib import Path
import sys
import unittest
from zoneinfo import ZoneInfo
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from update import amount,percent,parse_page,parse_status,validate_catalog,validate_alipay_record,merge_result

# Synthetic structure fixtures reproduce the source's documented table labels.
# They are unit tests, not a claimed live provider integration test.
FUND=dict(code='017641',index='sp500',name='摩根标普500指数 A',benchmark='S&P 500',currency='CNY',structure='index')
def fixture(status='限大额',limit='10.00元',management='0.50%',custody='0.15%',sales='0.00%'):
    return f'''<html><head><title>摩根标普500指数(QDII)人民币A(017641)基金费率</title></head><body>
    <table><tr><td>申购状态</td><td>{status}</td><td>赎回状态</td><td>开放赎回</td></tr>
    <tr><td>日累计申购限额</td><td>{limit}</td></tr></table>
    <table><tr><td>管理费率</td><td>{management}（每年）</td><td>托管费率</td><td>{custody}（每年）</td><td>销售服务费率</td><td>{sales}（每年）</td></tr></table>
    <h4>申购费率</h4><table><tr><th>适用金额</th><th>原费率|优惠费率</th></tr><tr><td>小于50万元</td><td><s>1.20%</s> 0.12%</td></tr></table>
    </body></html>'''

class AmountTests(unittest.TestCase):
    def test_yuan(self):self.assertEqual(amount('10.00元'),(10.,False))
    def test_ten_thousand(self):self.assertEqual(amount('1.00万元'),(10000.,False))
    def test_hundred_million(self):self.assertEqual(amount('0.01亿元'),(1000000.,False))
    def test_commas(self):self.assertEqual(amount('1,234.50元'),(1234.5,False))
    def test_unknown_not_unlimited(self):self.assertEqual(amount('---'),(None,False));self.assertEqual(amount(None),(None,False))
    def test_unlimited_explicit(self):self.assertEqual(amount('无限额'),(None,True))
    def test_unsupported_currency(self):
        with self.assertRaises(ValueError):amount('10美元')
    def test_zero_fee_not_missing(self):self.assertEqual(percent('0.00%（每年）'),0)
    def test_fee_missing(self):self.assertIsNone(percent('---'))
    def test_fee_outlier(self):
        with self.assertRaises(ValueError):percent('99.0%')

class ParserTests(unittest.TestCase):
    def test_normal(self):
        p=parse_page(fixture(),FUND);self.assertEqual(p['reference']['daily_limit'],10);self.assertEqual(p['fees']['total'],.65)
    def test_pause_overrides_old_quota(self):
        p=parse_page(fixture(status='暂停申购',limit='100.00元'),FUND);self.assertEqual(p['reference']['daily_limit'],0);self.assertEqual(p['reference']['source_displayed_limit'],100)
    def test_partial_fee_never_zero_filled(self):self.assertIsNone(parse_page(fixture(sales='---'),FUND)['fees'])
    def test_unknown_status_no_open_inference(self):self.assertIsNone(parse_page(fixture(status='维护中'),FUND)['reference'])
    def test_limited_without_amount_not_unlimited(self):
        p=parse_page(fixture(limit='无限额'),FUND)['reference'];self.assertIsNone(p['daily_limit']);self.assertFalse(p['unlimited'])
    def test_discount_not_alipay(self):self.assertEqual(parse_page(fixture(),FUND)['fees']['subscription_standard'],1.2)
    def test_wrong_code_rejected(self):
        with self.assertRaises(ValueError):parse_page(fixture().replace('017641','096001'),FUND)
    def test_flavor_rejected(self):
        with self.assertRaises(ValueError):parse_page(fixture().replace('标普500指数','标普500等权重指数'),FUND)
    def test_pause_large_is_limited(self):self.assertEqual(parse_status('暂停大额申购'),'limited')
    def test_missing_timestamp_retained(self):
        f={'code':'017641','reference':{'observed_at':'2026-01-01'},'fees':{'checked_at':'2026-01-01','total':.65}}
        p=parse_page(fixture(status='维护中'),FUND);merge_result(f,p,'2026-10-26T12:00:00+08:00')
        self.assertEqual(f['reference']['observed_at'],'2026-01-01');self.assertEqual(f['fees']['checked_at'],'2026-10-26T12:00:00+08:00')

class AlipayTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,10,26,12,tzinfo=ZoneInfo('Asia/Shanghai'))
        self.record={'code':'017641','scope':'alipay','status':'limited','daily_limit':10,'checked_at':self.now.isoformat(),'expires_at':(self.now+timedelta(hours=12)).isoformat(),'evidence_url':'https://example.org/masked-evidence/017641','note':'Synthetic test only'}
    def test_valid(self):self.assertEqual(validate_alipay_record(self.record,self.now,{'017641'})['daily_limit'],10)
    def test_wrong_channel(self):
        self.record['scope']='eastmoney'
        with self.assertRaises(ValueError):validate_alipay_record(self.record,self.now,{'017641'})
    def test_missing_evidence(self):
        del self.record['evidence_url']
        with self.assertRaises(ValueError):validate_alipay_record(self.record,self.now,{'017641'})
    def test_expired(self):
        self.record['checked_at']=(self.now-timedelta(days=2)).isoformat();self.record['expires_at']=(self.now-timedelta(days=1)).isoformat()
        with self.assertRaises(ValueError):validate_alipay_record(self.record,self.now,{'017641'})
    def test_future(self):
        self.record['checked_at']=(self.now+timedelta(days=1)).isoformat()
        with self.assertRaises(ValueError):validate_alipay_record(self.record,self.now,{'017641'})
    def test_bool_limit_rejected(self):
        self.record['daily_limit']=True
        with self.assertRaises(ValueError):validate_alipay_record(self.record,self.now,{'017641'})
    def test_no_zero_for_limited(self):
        self.record['daily_limit']=0
        with self.assertRaises(ValueError):validate_alipay_record(self.record,self.now,{'017641'})
    def test_expiry_cannot_extend_indefinitely(self):
        self.record['expires_at']=(self.now+timedelta(days=10)).isoformat()
        with self.assertRaises(ValueError):validate_alipay_record(self.record,self.now,{'017641'})

class WhitelistTests(unittest.TestCase):
    def test_allowed(self):validate_catalog([FUND])
    def test_duplicate(self):
        with self.assertRaises(ValueError):validate_catalog([FUND,FUND])
    def test_nonstandard(self):
        f=copy.deepcopy(FUND);f['name']='大成标普500等权重 A'
        with self.assertRaises(ValueError):validate_catalog([f])

if __name__=='__main__':unittest.main()

class FailureHandlingTests(unittest.TestCase):
    def test_total_failure_preserves_all_observation_dates(self):
        import json, tempfile, shutil
        from unittest.mock import patch
        import update
        original_root=update.ROOT
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            shutil.copytree(original_root/'config',root/'config')
            shutil.copytree(original_root/'site/data',root/'site/data')
            (root/'empty-fixtures').mkdir()
            old=json.loads((root/'site/data/funds.json').read_text())
            with patch.object(update,'ROOT',root),patch.dict('os.environ',{'ALIPAY_FEED_URL':''}):
                health=update.update(fixture_dir=root/'empty-fixtures')
            new=json.loads((root/'site/data/funds.json').read_text())
            self.assertEqual(health['status'],'failed')
            self.assertEqual(old['meta']['snapshot_date'],new['meta']['snapshot_date'])
            for a,b in zip(old['funds'],new['funds']):
                self.assertEqual(a['reference']['observed_at'],b['reference']['observed_at'])
                self.assertEqual(a['fees']['checked_at'],b['fees']['checked_at'])
                self.assertEqual(a['alipay'],b['alipay'])
