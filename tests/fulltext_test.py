"""全文准入及文件类型护栏，无真实请求或写库。"""
import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from lit.fulltext_batch import eligible
from lit.fulltext import verify_pdf

class FulltextTests(unittest.TestCase):
    def setUp(self):
        self.a={'pmid':'123','doi':'10.1/a','title':'合成研究'}
        self.batch={'status':'metadata_verified','articles':[self.a],'items':[{'pmid':'123','keys':['ABCD1234']}]}
        self.review={'schema':'trackeep-literature/batch-review@1','status':'review_complete','items':[{'pmid':'123','keys':['ABCD1234'],'decision':'keep'}]}

    def test_keep_only(self):
        self.assertEqual(eligible(self.review,self.batch),[(self.a,'ABCD1234')])
        for decision in ('exclude','pending'):
            self.review['items'][0]['decision']=decision
            self.assertEqual(eligible(self.review,self.batch),[])

    def test_retraction_blocks(self):
        for key in ('retracted','retraction_notice'):
            a=copy.deepcopy(self.batch);a['articles'][0][key]=True
            with self.assertRaises(ValueError):eligible(self.review,a)

    def test_key_drift_blocks(self):
        self.review['items'][0]['keys']=['OTHER123']
        with self.assertRaises(ValueError):eligible(self.review,self.batch)

    def test_duplicate_decisions_block(self):
        self.review['items']*=2
        with self.assertRaises(ValueError):eligible(self.review,self.batch)

    def test_failed_metadata_blocks(self):
        self.batch['status']='blocked'
        with self.assertRaises(ValueError):eligible(self.review,self.batch)

    def test_html_and_xml_not_pdf(self):
        for blob in (b'<html>Access denied</html>',b'<article><body>Full XML</body></article>',b''):
            with self.assertRaises(ValueError):verify_pdf(blob,self.a)

if __name__=='__main__':unittest.main()
