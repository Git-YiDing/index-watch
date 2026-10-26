import unittest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from validate import collection_complete


class CollectionHealthTests(unittest.TestCase):
    def complete_returns(self):
        return {'meta':{'total_count':1,'success_count':1},'funds':{'017641':{'error':None}}}

    def test_complete_public_and_returns_succeed(self):
        self.assertTrue(collection_complete({'status':'ok'},self.complete_returns()))

    def test_successful_fees_do_not_hide_failed_returns(self):
        returns=self.complete_returns()
        returns['funds']['017641']['error']='source unavailable; dated value retained'
        returns['meta']['success_count']=0
        self.assertFalse(collection_complete({'status':'ok'},returns))

    def test_successful_returns_do_not_hide_failed_fees(self):
        self.assertFalse(collection_complete({'status':'partial'},self.complete_returns()))

    def test_missing_return_feed_is_not_success(self):
        self.assertFalse(collection_complete({'status':'ok'},{}))
