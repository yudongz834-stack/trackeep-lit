"""少量题录桥接的离线行为测试；引擎与网络均替换为合成对象。"""
import argparse
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lit import metadata_batch as batch
from lit.library import matching, exact
from lit.batch_review import review

A = {'pmid':'12345','doi':'10.1/a','title':'合成研究','nlm_id':'0410462','abstract':'合成摘要'}
ROW = {'key':'ABCD1234','version':1,'data':{'itemType':'journalArticle','title':A['title'], 'DOI':A['doi'],
       'extra':'PMID: 12345\nNLM ID: 0410462','collections':['COLL1234'],'tags':[{'tag':'保留标签'}]}}


class TestMetadata(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='trackeep-test-')
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.source = self.folder/'source.json'
        self.report = {'schema':'trackeep-literature/pubmed-preview@1','read_only':True,'status':'retrieval_verified',
            'retrieval_complete':True,'counts':{'unique_pmids':1,'metadata':1},'pmids':[A['pmid']], 'articles':[A],
            'plan':{'journal':'Nature','screening_location':'after-import'}}
        self.write()

    def write(self):
        self.source.write_text(json.dumps(self.report), encoding='utf-8')

    def test_valid_scope(self):
        self.assertEqual(batch.load_scope(self.source,['12345'])[0], [A])

    def test_scope_not_in_preview(self):
        with self.assertRaises(ValueError): batch.load_scope(self.source,['999'])

    def test_scope_bounded(self):
        for ids in ([], ['1','2','3','4'], ['12345','12345']):
            with self.assertRaises(ValueError): batch.load_scope(self.source,ids)

    def test_warning_blocked(self):
        self.report['status']='review_required'; self.write()
        with self.assertRaises(ValueError): batch.load_scope(self.source,['12345'])

    def test_undecided_blocked(self):
        self.report['plan']['screening_location']='undecided'; self.write()
        with self.assertRaises(ValueError): batch.load_scope(self.source,['12345'])

    def test_count_mismatch(self):
        self.report['counts']['metadata']=2; self.write()
        with self.assertRaises(ValueError): batch.load_scope(self.source,['12345'])

    def test_conflict_not_exact(self):
        row=copy.deepcopy(ROW); row['data']['extra']='PMID: 999'
        self.assertEqual(len(matching([row], A)),1)
        self.assertFalse(exact(row,A))

    def test_multiple_pmids_not_exact(self):
        row=copy.deepcopy(ROW); row['data']['extra']+='\nPMID: 999'
        self.assertFalse(exact(row,A))

    def test_doi_normalized(self):
        row=copy.deepcopy(ROW); row['data']['DOI']='https://doi.org/10.1/A'
        self.assertTrue(exact(row,A))

    def execute(self, row, apply=True):
        lib=unittest.mock.Mock()
        lib.all.side_effect=[[{'key':'COLL1234','data':{'name':'Nature'}}], [row]]
        args=argparse.Namespace(preview=self.source,pmids='12345',apply=apply)
        with patch.object(batch.pubmed,'metadata',return_value=[A]), patch.object(batch,'Library',return_value=lib), patch.object(batch,'engine_call') as engine:
            out=batch.run(args,self.folder)
            engine.assert_not_called()
        return out

    def test_existing_preserved(self):
        row=copy.deepcopy(ROW)
        out=self.execute(row)
        self.assertEqual(out['status'],'metadata_verified')
        self.assertEqual(out['items'][0]['before'],[ROW])
        self.assertEqual(row,ROW)
        self.assertEqual(out['fulltext_status'],'not_started')

    def test_trash_not_resurrected(self):
        row=copy.deepcopy(ROW); row['data']['deleted']=1
        self.assertEqual(self.execute(row)['items'][0]['metadata_status'],'already_trashed')

    def test_other_collection_not_changed(self):
        row=copy.deepcopy(ROW); row['data']['collections']=['OTHER123']
        self.assertEqual(self.execute(row)['items'][0]['metadata_status'],'existing_outside_target')

    def review_fixture(self, article, decision):
        lib=unittest.mock.Mock()
        lib.all.side_effect=[[copy.deepcopy(ROW)], []]
        b={'schema':'trackeep-literature/metadata-batch@1','status':'metadata_verified','articles':[article],
           'items':[{'pmid':A['pmid'],'keys':[ROW['key']]}], 'collection':{'key':'COLL1234'}}
        return review(b,[{'pmid':A['pmid'],'decision':decision,'reason':'合成判断'}],lib)

    def test_missing_abstract_not_auto_excluded(self):
        a={**A,'source':'https://pubmed.ncbi.nlm.nih.gov/12345/','abstract':''}
        self.assertEqual(self.review_fixture(a,'exclude')['counts']['pending'],1)

    def test_retraction_excluded_with_source(self):
        a={**A,'source':'https://pubmed.ncbi.nlm.nih.gov/12345/','retracted':True}
        result=self.review_fixture(a,'keep')
        self.assertEqual(result['counts']['exclude'],1)
        self.assertEqual(result['zotero_mutations'],0)
        self.assertEqual(result['items'][0]['source'],a['source'])

    def test_undecided_review_stays_pending(self):
        a={**A,'source':'https://pubmed.ncbi.nlm.nih.gov/12345/'}
        self.assertEqual(self.review_fixture(a,'pending')['status'],'review_pending')


if __name__=='__main__':
    unittest.main()
