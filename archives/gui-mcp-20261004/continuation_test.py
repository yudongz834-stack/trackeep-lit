"""连续流程增量反例；真实引擎、模型及原生写入均替身，磁盘检查点真保存。"""
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lit import workflow as w
from lit.mcp_server import Server
from workflow_test import A, ROW, preview
REAL_CLASSIFY = w.deepseek.classify


class ContinuationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.flow = w.Workflow(self.tmp.name)
        result = self.flow.dispatch('plan', {'plan':{'kind':'articles','pmids':['12345']}, 'criteria':'合成主体'})
        self.run_id = result['run_id']
        self.articles = [copy.deepcopy(A)]
        self.rows = [copy.deepcopy(ROW)]
        self.search()
        self.lib = Mock()
        self.lib.all.side_effect = lambda path: copy.deepcopy(self.rows) if path.startswith('/items?') else []
        self.importer = Mock(side_effect=self.import_result)
        self.model = Mock(return_value={'12345':{'evaluated':True,'keep':True,'reason':'主体符合要求'}})
        self.fulltext = Mock(side_effect=lambda jobs, **kw: {'status':'complete','counts':{'existing_verified':len(jobs)},
            'items':[{'pmid':j['pmid'],'status':'existing_verified','parent_key':j['parent_key']} for j in jobs]})
        for obj, name, value in [(w,'Library',Mock(return_value=self.lib)), (w.metadata_batch,'run',self.importer),
                                  (w.deepseek,'classify',self.model)]:
            p = patch.object(obj,name,value); p.start(); self.addCleanup(p.stop)
        p = patch('lit.native_fulltext.execute_jobs',self.fulltext);p.start();self.addCleanup(p.stop)
        p = patch.dict(os.environ, {'DEEPSEEK_TOKEN':'synthetic-test-only'});p.start();self.addCleanup(p.stop)

    def search(self):
        with patch.object(w.pubmed, 'preview', return_value=preview(self.articles)):
            self.flow.dispatch('search', {'run_id':self.run_id})

    def import_result(self, args, folder):
        return {'status':'metadata_verified','articles':copy.deepcopy(self.articles), 'collection':{'key':'COLL1234'},
            'items':[{'pmid':a['pmid'],'keys':[r['key']],'created_key':r['key'],
                      'metadata_status':'created_verified'} for a,r in zip(self.articles,self.rows)]}

    def call(self, **kw):
        return self.flow.dispatch('continue', {'run_id':self.run_id,'apply':True,'collection_key':'COLL1234',**kw})

    def test_one_operation_runs_all_and_second_does_not_reimport_or_rejudge(self):
        result = self.call()
        self.assertEqual(result['state'],'fulltext_complete')
        self.assertEqual(result['data']['continuation']['stage'],'complete')
        self.call()
        self.importer.assert_called_once();self.model.assert_called_once()
        self.assertEqual(self.fulltext.call_count,2)  # 已有附件仍经原生层重新读回，不能直接信旧回执
        self.lib.trash_created.assert_not_called()

    def test_preview_cannot_authorize_import_model_or_fulltext(self):
        result = self.call(apply=False)
        self.assertTrue(result['data']['continuation_preview']['read_only'])
        self.assertNotIn('continuation',result['data'])
        self.importer.assert_not_called();self.model.assert_not_called();self.fulltext.assert_not_called()

    def test_collection_and_criteria_cannot_change_after_confirmation(self):
        self.call()
        for payload in ({'criteria':'不同标准'},{'collection_key':'OTHER123'}):
            self.assertFalse(self.call(**payload)['ok'])
        self.importer.assert_called_once();self.model.assert_called_once()

    def test_model_unavailable_then_recovery_reuses_import(self):
        with patch.dict(os.environ, {}, clear=True):
            result = self.call()
        self.assertEqual(result['counts']['pending'],1)
        self.assertIn('模型未配置',result['data']['pending_queue'][0]['reasons'][0])
        self.fulltext.assert_not_called()
        result = self.call()
        self.assertEqual(result['counts']['keep'],1)
        self.importer.assert_called_once()

    def test_malformed_and_failed_verdicts_never_become_keep_or_exclude(self):
        for verdict in (None,[],{'12345':None},{'12345':{'keep':'false','reason':5,'evaluated':True}}):
            self.model.return_value=verdict
            result=self.call()
            self.assertEqual(result['counts']['pending'],1)
            self.assertEqual(result['counts']['keep'],0)
            self.assertEqual(result['counts']['exclude'],0)
        self.fulltext.assert_not_called();self.importer.assert_called_once()

    def test_mixed_decisions_only_keep_goes_to_fulltext(self):
        self.articles += [{**A,'pmid':'23456','doi':'10.1/b','title':'缺摘要','abstract':''},
                          {**A,'pmid':'34567','doi':'10.1/c','title':'主体不符'}]
        self.rows += [{**ROW,'key':'BBBB1234','data':{**ROW['data'],'DOI':'10.1/b','title':'缺摘要','extra':'PMID: 23456\nNLM ID: 0410462'}},
                      {**ROW,'key':'CCCC1234','data':{**ROW['data'],'DOI':'10.1/c','title':'主体不符','extra':'PMID: 34567\nNLM ID: 0410462'}}]
        self.search()
        self.model.return_value['34567']={'evaluated':True,'keep':False,'reason':'主体不符合明确标准'}
        result=self.call()
        self.assertEqual([j['pmid'] for j in self.fulltext.call_args.args[0]],['12345'])
        self.assertEqual(result['counts']['pending'],1);self.assertEqual(result['counts']['exclude'],1)
        self.assertEqual(result['state'],'fulltext_review_pending')
        self.lib.trash_created.assert_not_called()

    def test_wide_journal_model_cannot_add_topic_exclusion(self):
        run=self.flow.dispatch('status',{'run_id':self.run_id})['data']
        run['plan']={'kind':'journal','journal':'Nature','selection_mode':'broad'}
        run['collection_policy']=w.collection_policy(run['plan']);self.flow._save(run)
        self.model.return_value={'12345':{'evaluated':True,'keep':False,'reason':'不是肿瘤研究'}}
        result=self.call()
        self.assertEqual(result['counts']['pending'],1);self.assertEqual(result['counts']['exclude'],0)
        self.assertIn('全部文章',self.model.call_args.args[1])
        self.fulltext.assert_not_called()

    def test_identity_change_stays_pending_no_fulltext(self):
        self.rows[0]['data']['DOI']='10.1/wrong'
        result=self.call()
        self.assertEqual(result['counts']['pending'],1)
        self.assertIn('身份',result['data']['pending_queue'][0]['reasons'][0])
        self.fulltext.assert_not_called()

    def test_fulltext_exception_saved_and_new_instance_resumes(self):
        self.fulltext.side_effect=RuntimeError('合成原生界面暂不可用')
        result=self.call()
        self.assertEqual(result['state'],'continuation_blocked')
        persisted=json.loads((self.flow._folder(self.run_id)/'run.json').read_text(encoding='utf-8'))
        self.assertEqual(persisted['continuation']['stage'],'fulltext')
        self.assertEqual(persisted['review']['counts']['keep'],1)
        self.flow=w.Workflow(self.tmp.name)
        self.fulltext.side_effect=None
        self.fulltext.return_value={'status':'complete','counts':{},'items':[]}
        self.assertTrue(self.call()['ok'])
        self.importer.assert_called_once();self.model.assert_called_once()

    def test_manual_pending_resolution_automatically_continues_without_model(self):
        self.model.return_value={};self.call()
        count=self.model.call_count
        result=self.flow.dispatch('review',{'run_id':self.run_id,
            'decisions':[{'pmid':'12345','decision':'keep','reason':'人工核过全文依据'}]})
        self.assertEqual(result['state'],'fulltext_complete')
        self.assertEqual(self.model.call_count,count)
        self.fulltext.assert_called_once()
        self.call();self.assertEqual(self.model.call_count,count)

    def test_mcp_continue_passes_same_authorization_and_result(self):
        server=Server(self.flow);server.handle({'jsonrpc':'2.0','id':1,'method':'initialize'})
        response=server.handle({'jsonrpc':'2.0','id':2,'method':'tools/call','params':{'name':'literature_dispatch',
            'arguments':{'action':'continue','payload':{'run_id':self.run_id,'apply':True,'collection_key':'COLL1234'}}}})
        result=json.loads(response['result']['content'][0]['text'])
        self.assertEqual(result['state'],'fulltext_complete')
        self.importer.assert_called_once();self.model.assert_called_once();self.fulltext.assert_called_once()

    def test_without_apply_or_with_nonboolean_never_writes(self):
        self.call(apply=False)
        self.assertFalse(self.call(apply='true')['ok'])
        self.importer.assert_not_called();self.model.assert_not_called();self.fulltext.assert_not_called()

    def test_old_import_action_cannot_erase_confirmed_manual_review(self):
        self.model.return_value={};self.call()
        self.flow.dispatch('review',{'run_id':self.run_id,
            'decisions':[{'pmid':'12345','decision':'keep','reason':'人工已确认'}]})
        for apply in (False,True):
            result=self.flow.dispatch('import',{'run_id':self.run_id,'apply':apply,'collection_key':'COLL1234'})
            self.assertFalse(result['ok'])
            self.assertEqual(result['data']['review']['items'][0]['reason'],'人工已确认')
            self.assertEqual(result['data']['fulltext']['status'],'complete')
        self.importer.assert_called_once()

    def test_old_ai_action_obeys_scope_lock_and_preserves_manual_keep(self):
        self.call()
        before=self.model.call_count
        result=self.flow.dispatch('review_ai',{'run_id':self.run_id,'criteria':'换一个标准'})
        self.assertFalse(result['ok'])
        self.model.return_value={'12345':{'evaluated':True,'keep':False,'reason':'改成排除'}}
        result=self.flow.dispatch('review_ai',{'run_id':self.run_id,'criteria':'合成主体'})
        self.assertTrue(result['ok'])
        self.assertEqual(result['counts']['keep'],1)
        self.assertEqual(self.model.call_count,before)

    def test_refetched_abstract_missing_does_not_accept_model_exclusion(self):
        import io
        xml = b'<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>12345</PMID></MedlineCitation></PubmedArticle></PubmedArticleSet>'
        with patch.object(w.deepseek,'classify',REAL_CLASSIFY), patch.object(w.deepseek.urllib.request,'urlopen',
                side_effect=lambda *a, **kw: io.BytesIO(xml)) as http:
            result=self.call()
        self.assertEqual(result['counts']['pending'],1)
        self.assertEqual(result['counts']['exclude'],0)
        self.assertIn('未取得摘要',result['data']['pending_queue'][0]['reasons'][0])
        self.fulltext.assert_not_called()
        self.assertEqual(http.call_count,1)  # 仅取摘要，不向模型请求

    def test_missing_abstract_number_cannot_be_forged_in_mixed_model_reply(self):
        import io
        raw=json.dumps({'content':[{'type':'text','text':json.dumps([
            {'n':1,'keep':False,'reason':'伪造缺摘要排除'},
            {'n':2,'keep':True,'reason':'主体相符'}])}]}).encode()
        with patch.object(w.deepseek.urllib.request,'urlopen',return_value=io.BytesIO(raw)) as http:
            result=w.deepseek._deepseek_judge([{'pmid':'1'},{'pmid':'2'}],{'2':'有摘要'},'主体',timeout=1)
        self.assertFalse(result['1']['evaluated'])
        self.assertTrue(result['2']['evaluated'])
        sent=json.loads(http.call_args.args[0].data)['messages'][0]['content']
        self.assertNotIn('[1]',sent)

    def test_import_blocked_before_metadata_preserves_target_on_resume(self):
        run=self.flow.dispatch('status',{'run_id':self.run_id})['data']
        run['search']['status']='review_required';self.flow._save(run)
        self.assertFalse(self.call()['ok'])
        self.assertFalse(self.call(collection_key='OTHER123')['ok'])
        self.assertFalse(self.flow.dispatch('import',{'run_id':self.run_id,'apply':False,'collection_key':'OTHER123'})['ok'])
        self.search()
        result=self.flow.dispatch('continue',{'run_id':self.run_id,'apply':True})
        self.assertTrue(result['ok'])
        self.assertEqual(self.importer.call_args.args[0].collection_key,'COLL1234')
        self.assertEqual(result['data']['target_collection'],'COLL1234')

    def test_legacy_pending_review_keeps_its_saved_criteria(self):
        self.model.return_value={};self.call()
        run=self.flow.dispatch('status',{'run_id':self.run_id})['data']
        run.pop('continuation');run.pop('collection_policy')
        run['review']['criteria']='旧批次已确认主体标准';self.flow._save(run)
        self.call()
        self.assertEqual(self.model.call_args.args[1],'旧批次已确认主体标准')
        result=self.flow.dispatch('status',{'run_id':self.run_id})
        self.assertEqual(result['data']['collection_policy']['criteria'],'旧批次已确认主体标准')


if __name__=='__main__':unittest.main()
