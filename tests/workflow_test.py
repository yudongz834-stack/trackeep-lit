"""双入口共用流程反例；网络、模型与 Zotero 写入一律使用合成对象。"""
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from lit import workflow as w, pubmed, metadata_batch as mb

A = {'pmid':'12345','doi':'10.1/a','title':'合成研究','journal':'Nature','nlm_id':'0410462',
     'abstract':'合成摘要','source':'https://pubmed.ncbi.nlm.nih.gov/12345/','retracted':False,'retraction_notice':False}
ROW = {'key':'ABCD1234','version':1,'data':{'itemType':'journalArticle','title':A['title'],'DOI':A['doi'],
       'extra':'PMID: 12345\nNLM ID: 0410462','collections':['COLL1234']}}


def preview(articles=None):
    articles = articles or [copy.deepcopy(A)]
    return {'schema':'trackeep-literature/pubmed-preview@1','read_only':True,'status':'retrieval_verified',
            'created_at':'2026-10-03T00:00:00+00:00','retrieval_complete':True,'review_reasons':[],
            'counts':{'unique_pmids':len(articles),'metadata':len(articles)},'articles':articles,
            'pmids':[a['pmid'] for a in articles], 'plan':{'kind':'articles','pmids':[a['pmid'] for a in articles],
            'screening_location':'after-import'}}


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.flow = w.Workflow(self.tmp.name)
        self.id = self.flow.dispatch('plan',{'pmids':['12345']})['run_id']

    def search(self, report=None):
        with patch.object(pubmed,'preview',return_value=report or preview()):
            return self.flow.dispatch('search',{'run_id':self.id})

    def batch(self, items=None):
        self.search()
        run = self.flow.dispatch('status',{'run_id':self.id})['data']
        run['metadata'] = {'schema':'trackeep-literature/metadata-batch@1','status':'metadata_verified',
            'articles':[copy.deepcopy(A)],'items':items or [{'pmid':'12345','keys':['ABCD1234'],
            'collection_key':'COLL1234','metadata_status':'existing_verified'}]}
        self.flow._save(run)

    def test_plan_defaults_and_readable(self):
        result = self.flow.dispatch('plan',{'journal':'Nature','year':2026,'month':9})
        self.assertTrue(result['ok'])
        self.assertEqual(result['data']['plan']['date']['field'],'dp')
        self.assertIn('2026-09-30',result['data']['readable_plan'])

    def test_invalid_plan_does_not_create_run(self):
        result = self.flow.dispatch('plan',{'journal':'Nature','year':2026,'month':13})
        self.assertFalse(result['ok'])
        self.assertIsNone(result['run_id'])

    def test_path_escape_rejected(self):
        for value in ('../../x','D:/x','20261003-120000-abc'):
            self.assertFalse(self.flow.dispatch('status',{'run_id':value})['ok'])

    def test_import_requires_search(self):
        with patch.object(mb,'run') as call:
            result = self.flow.dispatch('import',{'run_id':self.id,'apply':True})
            self.assertFalse(result['ok'])
            call.assert_not_called()

    def test_nonboolean_apply_rejected(self):
        self.assertFalse(self.flow.dispatch('import',{'run_id':self.id,'apply':'false'})['ok'])

    def test_search_failure_saved_and_no_import(self):
        self.search({**preview(),'status':'blocked','retrieval_complete':False,'failure':'NCBI 连接失败'})
        restored = w.Workflow(self.tmp.name).dispatch('status',{'run_id':self.id})
        self.assertEqual(restored['state'],'search_blocked')
        self.assertFalse(restored['ok'])
        self.assertIn('NCBI 连接失败',restored['errors'])
        self.assertFalse(self.flow.dispatch('import',{'run_id':self.id})['ok'])

    def test_warning_does_not_open_write_gate(self):
        self.search({**preview(),'status':'review_required','review_reasons':['PubMed 检索警告']})
        self.assertFalse(self.flow.dispatch('import',{'run_id':self.id})['ok'])

    def test_seed_absence_is_separate_from_retrieval(self):
        result=self.search({**preview(),'status':'review_required','review_reasons':['尚无已知文献召回验证；不能声称主题检索已验证']})
        self.assertEqual(result['data']['search']['status'],'retrieval_verified')
        self.assertTrue(result['data']['search']['review_reasons'])

    def test_same_pmid_across_month_is_seen(self):
        self.search()
        second=self.flow.dispatch('plan',{'pmids':['12345']})['run_id']
        with patch.object(pubmed,'preview',return_value=preview()):
            result=self.flow.dispatch('search',{'run_id':second})
        self.assertEqual(result['data']['search']['cross_batch']['seen_count'],1)
        self.assertEqual(result['data']['search']['cross_batch']['new_count'],0)

    def test_cross_batch_identity_conflict_blocks_import(self):
        self.search()
        second=self.flow.dispatch('plan',{'pmids':['12345']})['run_id']
        with patch.object(pubmed,'preview',return_value=preview([{**A,'doi':'10.1/other'}])):
            result=self.flow.dispatch('search',{'run_id':second})
        self.assertEqual(result['data']['search']['status'],'review_required')
        self.assertFalse(self.flow.dispatch('import',{'run_id':second,'apply':True})['ok'])

    def test_preview_never_requests_apply(self):
        self.search()
        with patch.object(mb,'run',return_value={'status':'preview_only','items':[], 'collection':{'key':'COLL1234'}}) as execute:
            self.flow.dispatch('import',{'run_id':self.id,'collection_key':'COLL1234'})
        self.assertIs(execute.call_args.args[0].apply,False)

    def test_target_locked_after_preview(self):
        self.search()
        with patch.object(mb,'run',return_value={'status':'preview_only','items':[]}) as execute:
            self.flow.dispatch('import',{'run_id':self.id,'collection_key':'COLL1234'})
            result=self.flow.dispatch('import',{'run_id':self.id,'collection_key':'OTHER123','apply':True})
        self.assertFalse(result['ok'])
        self.assertEqual(execute.call_count,1)

    def test_multi_journal_is_sequential_groups(self):
        self.search(preview([A,{**A,'pmid':'67890','doi':'10.1/b','journal':'Science','nlm_id':'0404511'}]))
        with patch.object(mb,'run',return_value={'status':'preview_only','items':[]}) as execute:
            self.flow.dispatch('import',{'run_id':self.id})
        self.assertEqual(execute.call_count,2)
        self.assertEqual([c.args[0].pmids for c in execute.call_args_list],['12345','67890'])

    def test_no_decision_remains_pending_and_no_jobs(self):
        self.batch()
        lib=Mock();lib.all.side_effect=[[ROW],[]]
        with patch.object(w,'Library',return_value=lib):
            result=self.flow.dispatch('review',{'run_id':self.id})
        self.assertEqual(result['counts']['pending'],1)
        self.assertEqual(self.flow.dispatch('fulltext_jobs',{'run_id':self.id})['data']['jobs'],[])

    def test_missing_model_stays_pending(self):
        self.batch();lib=Mock();lib.all.side_effect=[[ROW],[]]
        with patch.dict(os.environ,{},clear=True),patch.object(w,'Library',return_value=lib),patch.object(w.deepseek,'classify') as model:
            result=self.flow.dispatch('review_ai',{'run_id':self.id,'criteria':'研究主体'})
        self.assertEqual(result['counts']['pending'],1);model.assert_not_called()

    def test_model_failure_fallback_not_keep(self):
        self.batch();lib=Mock();lib.all.side_effect=[[ROW],[]]
        with patch.dict(os.environ,{'DEEPSEEK_TOKEN':'synthetic'}),patch.object(w,'Library',return_value=lib),patch.object(w.deepseek,'classify',return_value={'12345':{'keep':True,'reason':'本批复筛失败·默认保留'}}):
            result=self.flow.dispatch('review_ai',{'run_id':self.id,'criteria':'研究主体'})
        self.assertEqual(result['counts']['pending'],1)

    def test_existing_item_cannot_be_cleaned(self):
        self.batch();lib=Mock();lib.all.side_effect=[[ROW],[]]
        with patch.object(w,'Library',return_value=lib):
            result=self.flow.dispatch('review',{'run_id':self.id,'apply_cleanup':True,
                'decisions':[{'pmid':'12345','decision':'exclude','reason':'主体不符'}]})
        self.assertEqual(result['data']['review']['items'][0]['cleanup'],'protected_existing_or_children')
        lib.trash_created.assert_not_called()

    def test_created_with_note_protected(self):
        self.batch([{'pmid':'12345','keys':['ABCD1234'],'created_key':'ABCD1234','collection_key':'COLL1234'}])
        lib=Mock();lib.all.side_effect=[[ROW],[{'key':'NOTE1234','data':{'itemType':'note'}}]]
        with patch.object(w,'Library',return_value=lib):
            self.flow.dispatch('review',{'run_id':self.id,'apply_cleanup':True,
                'decisions':[{'pmid':'12345','decision':'exclude','reason':'主体不符'}]})
        lib.trash_created.assert_not_called()

    def test_created_empty_item_reversible_cleanup(self):
        self.batch([{'pmid':'12345','keys':['ABCD1234'],'created_key':'ABCD1234','collection_key':'COLL1234'}])
        lib=Mock();lib.all.side_effect=[[ROW],[]];lib.trash_created.return_value={**ROW,'data':{**ROW['data'],'deleted':1}}
        with patch.object(w,'Library',return_value=lib):
            result=self.flow.dispatch('review',{'run_id':self.id,'apply_cleanup':True,
                'decisions':[{'pmid':'12345','decision':'exclude','reason':'主体不符'}]})
        self.assertEqual(result['data']['review']['zotero_mutations'],1)
        lib.trash_created.assert_called_once()

    def test_live_match_not_blocked_by_trash_copy(self):
        from lit.batch_review import review
        batch={'schema':'trackeep-literature/metadata-batch@1','status':'metadata_verified','articles':[A],
               'items':[{'pmid':'12345','keys':['ABCD1234']}],'collection':{'key':'COLL1234'}}
        lib=Mock();lib.all.side_effect=[[ROW,{**ROW,'key':'TRASH123','data':{**ROW['data'],'deleted':1}}],[]]
        result=review(batch,[{'pmid':'12345','decision':'keep','reason':'主体吻合'}],lib)
        self.assertEqual(result['counts']['keep'],1)

    def test_list_runs_recovers_saved_batch(self):
        result=w.Workflow(self.tmp.name).dispatch('list_runs')
        self.assertEqual(result['data']['runs'][0]['run_id'],self.id)

    def test_os_lock_excludes_other_instance(self):
        with w.process_lock(self.flow.store/'workflow.lock'):
            result=self.flow.dispatch('plan',{'pmids':['67890']})
        self.assertFalse(result['ok'])

    def test_natural_no_key_never_networks(self):
        with patch.dict(os.environ,{},clear=True),patch.object(w.urllib.request,'urlopen') as request:
            result=self.flow.dispatch('plan_natural',{'text':'糖与菌群'})
        self.assertFalse(result['ok']);request.assert_not_called()

    def test_same_batch_identity_conflict_blocks_import(self):
        result=self.search(preview([A,{**A,'pmid':'67890'}]))
        self.assertEqual(result['data']['search']['status'],'review_required')
        self.assertFalse(self.flow.dispatch('import',{'run_id':self.id,'apply':True})['ok'])

    def test_fulltext_goes_through_native_and_persists(self):
        self.batch();lib=Mock();lib.all.side_effect=[[ROW],[]]
        with patch.object(w,'Library',return_value=lib):
            self.flow.dispatch('review',{'run_id':self.id,'decisions':[{'pmid':'12345','decision':'keep','reason':'相关'}]})
        with patch('lit.native_fulltext.execute_jobs',return_value={'status':'complete','items':[], 'counts':{'existing_verified':1}}) as native:
            result=self.flow.dispatch('fulltext',{'run_id':self.id,'apply':True})
        self.assertEqual(native.call_args.args[0][0]['parent_key'],'ABCD1234')
        self.assertTrue(native.call_args.kwargs['apply'])
        self.assertEqual(result['counts']['fulltext_existing_verified'],1)
        self.assertEqual(w.Workflow(self.tmp.name).dispatch('status',{'run_id':self.id})['state'],'fulltext_complete')

    def test_no_three_item_ceiling_and_fifty_item_chunks(self):
        articles=[{**A,'pmid':str(1000+i),'doi':f'10.1/{i}'} for i in range(51)]
        source=self.flow.root/'source.json';mb.save(source,preview(articles))
        lib=Mock();lib.all.side_effect=[[{'key':'COLL1234','data':{'name':'Nature'}}],[]]
        def engine(chunk,journal,collection,pin,apply):
            self.assertFalse(apply)
            return {'items':[{'pmid':a['pmid'],'status':'new'} for a in chunk]}
        with patch.object(mb.pubmed,'metadata',return_value=articles),patch.object(mb,'Library',return_value=lib),patch.object(mb,'engine_call',side_effect=engine) as execute:
            result=mb.run(w.SimpleNamespace(preview=source,pmids=','.join(a['pmid'] for a in articles),apply=False),self.flow.root)
        self.assertEqual(result['status'],'preview_only')
        self.assertEqual([len(c.args[0]) for c in execute.call_args_list],[50,1])

    def test_ambiguous_catalog_stops_without_guess(self):
        reply=json.dumps({'esearchresult':{'count':'2','idlist':['1','2']}}).encode()
        with patch.object(pubmed,'request',return_value=(reply,{})) as request:
            with self.assertRaises(ValueError): pubmed.resolve_journal('合成刊名')
        self.assertEqual(request.call_count,1)

    def test_all_pending_never_claims_fulltext_complete(self):
        self.batch();lib=Mock();lib.all.side_effect=[[ROW],[]]
        with patch.object(w,'Library',return_value=lib):
            self.flow.dispatch('review',{'run_id':self.id})
        with patch('lit.native_fulltext.execute_jobs') as native:
            result=self.flow.dispatch('fulltext',{'run_id':self.id,'apply':True})
        native.assert_not_called()
        self.assertFalse(result['ok'])
        self.assertEqual(result['state'],'fulltext_review_pending')
        self.assertEqual(result['counts']['fulltext_review_pending'],1)
        self.assertTrue(result['errors'])
        restored=self.flow.dispatch('status',{'run_id':self.id})
        self.assertFalse(restored['ok'])

    def test_all_excluded_fulltext_is_not_required(self):
        self.batch();lib=Mock();lib.all.side_effect=[[ROW],[]]
        with patch.object(w,'Library',return_value=lib):
            self.flow.dispatch('review',{'run_id':self.id,'decisions':[{'pmid':'12345','decision':'exclude','reason':'无关'}]})
        with patch('lit.native_fulltext.execute_jobs') as native:
            result=self.flow.dispatch('fulltext',{'run_id':self.id,'apply':True})
        native.assert_not_called()
        self.assertTrue(result['ok'])
        self.assertEqual(result['state'],'fulltext_not_required')

    def test_cleanup_failure_visible_in_envelope_and_recovery(self):
        self.batch([{'pmid':'12345','keys':['ABCD1234'],'created_key':'ABCD1234','collection_key':'COLL1234'}])
        lib=Mock();lib.all.side_effect=[[ROW],[]];lib.trash_created.side_effect=RuntimeError('模拟网络中断')
        with patch.object(w,'Library',return_value=lib):
            result=self.flow.dispatch('review',{'run_id':self.id,'apply_cleanup':True,
                'decisions':[{'pmid':'12345','decision':'exclude','reason':'无关'}]})
        self.assertFalse(result['ok'])
        self.assertEqual(result['state'],'review_cleanup_pending')
        self.assertEqual(result['counts']['cleanup_pending'],1)
        self.assertEqual(result['counts']['cleanup_verified'],0)
        self.assertTrue(result['errors'])
        self.assertFalse(self.flow.dispatch('status',{'run_id':self.id})['ok'])

    def test_kept_done_but_other_pending_not_batch_complete(self):
        self.batch()
        run=self.flow.dispatch('status',{'run_id':self.id})['data']
        run['review']={'status':'review_pending','items':[
            {'pmid':'12345','decision':'keep','keys':['ABCD1234']},
            {'pmid':'67890','decision':'pending','keys':[]}], 'counts':{'keep':1,'pending':1,'exclude':0}}
        self.flow._save(run)
        with patch('lit.native_fulltext.execute_jobs',return_value={'status':'complete','items':[], 'counts':{'existing_verified':1}}):
            result=self.flow.dispatch('fulltext',{'run_id':self.id,'apply':True})
        self.assertFalse(result['ok'])
        self.assertEqual(result['state'],'fulltext_review_pending')
        self.assertEqual(result['data']['fulltext']['eligible_status'],'complete')

    def test_status_preserves_import_failure(self):
        run=self.flow.dispatch('status',{'run_id':self.id})['data']
        run.update(state='import_blocked',metadata={'groups':[{'status':'blocked','failure':'目标集合不符合约束'}]})
        self.flow._save(run)
        result=self.flow.dispatch('status',{'run_id':self.id})
        self.assertFalse(result['ok'])
        self.assertIn('目标集合不符合约束',result['errors'])

    def test_engine_error_is_classified_without_raw_output(self):
        result=Mock(returncode=1,stderr='指定目录不存在 synthetic-secret'.encode('gb18030'),stdout=b'')
        with patch.object(mb.subprocess,'run',return_value=result):
            with self.assertRaisesRegex(RuntimeError,'目标集合不存在') as caught:
                mb.engine_call([A],'Nature','COLL1234',self.flow.root/'expected.json',False)
        self.assertNotIn('synthetic-secret',str(caught.exception))


if __name__=='__main__':
    unittest.main()
