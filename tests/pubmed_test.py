"""检索护栏的离线边界测试：不访问网络或 Zotero。"""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lit import pubmed as p


PLAN = {'kind':'journal', 'journal':'Nature', 'date':{'field':'dp','start':'2026-09-01','end':'2026-09-30'},
        'selection_mode':'broad','screening_location':'undecided'}

def response(ids=('1',), count=None, **extra):
    return json.dumps({'esearchresult': {'count':str(len(ids) if count is None else count), 'idlist':list(ids),
                     'querytranslation':'"Nature"[Journal]', **extra}}).encode(), {}

def xml(ids=('1',), nlm='0410462', pt='Journal Article'):
    return ('<PubmedArticleSet>'+''.join(f'''<PubmedArticle><MedlineCitation><PMID>{i}</PMID><Article>
    <ArticleTitle>题名</ArticleTitle><Journal><Title>Nature</Title><ISOAbbreviation>Nature</ISOAbbreviation></Journal>
    <PublicationTypeList><PublicationType>{pt}</PublicationType></PublicationTypeList></Article>
    <MedlineJournalInfo><NlmUniqueID>{nlm}</NlmUniqueID></MedlineJournalInfo></MedlineCitation>
    <PubmedData><ArticleIdList><ArticleId IdType="doi">10.1/test</ArticleId></ArticleIdList></PubmedData>
    </PubmedArticle>''' for i in ids)+'</PubmedArticleSet>').encode(), {}

class PubMedTests(unittest.TestCase):
    def run_plan(self, search=None, meta=None, plan=None):
        with patch.object(p, 'request', side_effect=[search or response(), meta or xml()]):
            return p.preview(plan or PLAN)

    def test_read_only_complete_and_missing_abstract_retained(self):
        r=self.run_plan()
        self.assertEqual(r['status'],'retrieval_verified')
        self.assertTrue(r['retrieval_complete'])
        self.assertFalse(r['relevance_validated'])
        self.assertEqual(r['counts']['missing_abstract'],1)
        self.assertTrue(r['read_only'])

    def test_error_is_saved_and_blocks_fetch(self):
        with patch.object(p,'request',return_value=response(errorlist={'phrasesnotfound':['publication']})) as req:
            r=p.preview(PLAN)
        self.assertEqual(r['status'],'blocked')
        self.assertEqual(req.call_count,1)
        self.assertIn('publication',str(r['searches']))

    def test_empty_errorlist_is_not_false_failure(self):
        self.assertEqual(self.run_plan(response(errorlist={'phrasesnotfound':[],'fieldsnotfound':[]}))['status'],'retrieval_verified')

    def test_warning_saved_never_silently_passed(self):
        r=self.run_plan(response(warninglist={'outputmessages':['changed query']}))
        self.assertEqual(r['status'],'review_required')
        self.assertTrue(r['review_reasons'])

    def test_no_translation_blocks(self):
        self.assertEqual(self.run_plan(response(querytranslation=''))['status'],'blocked')

    def test_truncated_count_blocks(self):
        self.assertEqual(self.run_plan(response(count=2))['status'],'blocked')

    def test_duplicate_search_ids_blocks(self):
        self.assertEqual(self.run_plan(response(('1','1')))['status'],'blocked')

    def test_wrong_metadata_identity_blocks(self):
        self.assertEqual(self.run_plan(meta=xml(('4',)))['status'],'blocked')

    def test_duplicate_metadata_blocks(self):
        self.assertEqual(self.run_plan(meta=xml(('1','1')))['status'],'blocked')

    def test_missing_metadata_blocks(self):
        self.assertEqual(self.run_plan(meta=xml(()))['status'],'blocked')

    def test_wrong_journal_blocks(self):
        self.assertEqual(self.run_plan(meta=xml(nlm='wrong'))['status'],'blocked')

    def test_no_default_date_or_mode(self):
        for field in ('date','selection_mode'):
            plan=copy.deepcopy(PLAN); del plan[field]
            with patch.object(p,'request') as req:
                self.assertEqual(p.preview(plan)['status'],'blocked')
                req.assert_not_called()

    def test_screening_default_preserves_explicit_undecided(self):
        plan=copy.deepcopy(PLAN); del plan['screening_location']
        result=self.run_plan(plan=plan)
        self.assertEqual(result['effective_plan']['screening_location'], 'after-import')
        self.assertNotIn('screening_location', plan)
        plan['screening_location']='undecided'
        self.assertEqual(self.run_plan(plan=plan)['effective_plan']['screening_location'], 'undecided')

    def test_bad_dates_and_journal_rejected(self):
        for date in ({'field':'bad','start':'2026-01-01','end':'2026-02-01'},
                     {'field':'dp','start':'2026-02-30','end':'2026-03-01'},
                     {'field':'dp','start':'2026-03-02','end':'2026-03-01'}):
            plan=copy.deepcopy(PLAN); plan['date']=date
            self.assertEqual(p.preview(plan)['status'],'blocked')
        with self.assertRaises(ValueError): p.resolve_journal('Nature Medicine')

    def test_seven_unique_identities_and_lancet_not_catalog_uid(self):
        rows=p.journals()
        self.assertEqual(len(rows),7)
        self.assertEqual(len({j['nlm_id'] for j in rows}),7)
        self.assertEqual(p.resolve_journal('NEJM')['ta'],'N Engl J Med')
        self.assertEqual(p.resolve_journal('Lancet')['nlm_id'],'2985213R')

    def test_filter_needs_reason_and_broad_cannot_hide_filter(self):
        plan=copy.deepcopy(PLAN); plan['filter_query']='hasabstract'
        self.assertEqual(p.preview(plan)['status'],'blocked')
        plan['selection_mode']='query-filtered'
        self.assertEqual(p.preview(plan)['status'],'blocked')

    def test_known_item_miss_needs_review(self):
        plan=copy.deepcopy(PLAN); plan['known_pmids']=['2']
        self.assertEqual(self.run_plan(plan=plan)['status'],'review_required')

    def test_current_and_historical_retraction_notice(self):
        for pt in ('Retraction Notice','Retraction of Publication'):
            r=self.run_plan(meta=xml(pt=pt))
            self.assertTrue(r['articles'][0]['retraction_notice'])
            self.assertFalse(r['articles'][0]['retracted'])
        r=self.run_plan(meta=xml(pt='Retracted Publication'))
        self.assertTrue(r['articles'][0]['retracted'])
        self.assertFalse(r['articles'][0]['retraction_notice'])

    def test_split_union_dedup_and_parent_count(self):
        with patch.object(p,'LIMIT',2), patch.object(p,'request',side_effect=[response(('1','2'),3),response(('1','2')),response(('2','3')),xml(('1','2','3'))]):
            r=p.preview(PLAN)
        self.assertEqual(r['status'],'retrieval_verified')
        self.assertEqual(r['partitions'][0]['overlap'],1)

    def test_split_parent_mismatch_blocks(self):
        with patch.object(p,'LIMIT',2), patch.object(p,'request',side_effect=[response(('1','2'),4),response(('1','2')),response(('2','3'))]):
            self.assertEqual(p.preview(PLAN)['status'],'blocked')

    def test_single_day_overflow_blocks(self):
        plan=copy.deepcopy(PLAN); plan['date']['end']=plan['date']['start']
        with patch.object(p,'LIMIT',2), patch.object(p,'request',return_value=response(('1','2'),3)) as req:
            self.assertEqual(p.preview(plan)['status'],'blocked')
            self.assertEqual(req.call_count,1)

    def test_topic_requires_concepts_and_explicit_time(self):
        plan={'kind':'topic','query':'cancer[tiab]','screening_location':'undecided'}
        self.assertEqual(p.preview(plan)['status'],'blocked')
        plan.update(all_time=True,concepts=[{'name':'cancer'}])
        self.assertEqual(self.run_plan(plan=plan)['status'],'review_required')

    def test_malformed_plan_always_produces_failure_report(self):
        for key,value in [('date',['dp']),('journal',17),('filter_query',17),('date',{}),('all_time','true')]:
            plan=copy.deepcopy(PLAN); plan[key]=value
            r=p.preview(plan)
            self.assertEqual(r['status'],'blocked')
            self.assertIn('failure',r)
        self.assertEqual(p.preview([])['status'],'blocked')

    def test_malformed_response_cannot_pass_or_escape(self):
        for values in ({'warninglist':[]},{'errorlist':[]},{'warninglist':'warning'},
                       {'querytranslation':17},{'count':True},{'idlist':[True]}):
            r=self.run_plan(response(**values))
            self.assertEqual(r['status'],'blocked')
        with patch.object(p,'request',return_value=(b'broken json',{})):
            r=p.preview(PLAN)
        self.assertEqual(r['status'],'blocked')
        self.assertEqual(r['searches'][0]['unparsed_response'],'broken json')

    def test_cli_invalid_plan_file_still_records_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            plan=root/'bad.json'; plan.write_text('{bad',encoding='utf-8')
            with patch.object(p,'ROOT',root),patch.object(sys,'argv',['pubmed','--plan',str(plan)]),patch('builtins.print'):
                self.assertEqual(p.main(),1)
            reports=list((root/'日志/pubmed-preview').glob('*.json'))
            self.assertEqual(len(reports),1)
            self.assertEqual(json.loads(reports[0].read_text(encoding='utf-8'))['status'],'blocked')

    def test_unknown_filter_not_silently_ignored(self):
        plan=copy.deepcopy(PLAN); plan['exclude_retracted']=True
        self.assertEqual(p.preview(plan)['status'],'blocked')

    def test_network_failure_preserves_attempted_query(self):
        with patch.object(p,'request',side_effect=RuntimeError('超时')):
            r=p.preview(PLAN)
        self.assertEqual(r['status'],'blocked')
        self.assertIn('Nature',r['searches'][0]['query'])

    def test_metadata_doi_not_taken_from_reference(self):
        raw,_=xml()
        raw=raw.replace(b'<PubmedData>',b'<References><ArticleId IdType="doi">10.wrong/ref</ArticleId></References><PubmedData>')
        self.assertEqual(self.run_plan(meta=(raw,{}))['articles'][0]['doi'],'10.1/test')

    def test_online_first_same_pmid_is_update_not_new(self):
        current=self.run_plan(); old=copy.deepcopy(current)
        old['articles'][0].update(publication_status='aheadofprint',volume='',issue='',pages='')
        current['articles'][0].update(publication_status='ppublish',volume='657',issue='8130',pages='1-10')
        p.compare_previous(current,[old])
        self.assertEqual(current['cross_batch']['new_count'],0)
        self.assertEqual(current['cross_batch']['seen_count'],1)
        self.assertEqual(current['counts']['unique_pmids'],1)
        self.assertIn('publication_status',current['cross_batch']['metadata_changes'][0]['fields'])
        self.assertEqual(old['articles'][0]['volume'],'')

    def test_same_title_distinct_pmids_never_auto_merged(self):
        current=self.run_plan(); old=copy.deepcopy(current)
        old['pmids']=['2']; old['articles'][0]['pmid']='2'; old['articles'][0]['doi']='10.2/other'
        p.compare_previous(current,[old])
        self.assertEqual(current['cross_batch']['new_count'],1)
        self.assertFalse(current['cross_batch']['identity_conflicts'])

    def test_doi_conflict_and_same_doi_distinct_pmid_review(self):
        for same_pmid in (True,False):
            current=self.run_plan(); old=copy.deepcopy(current)
            if same_pmid: old['articles'][0]['doi']='10.2/conflict'
            else: old['pmids']=['2']; old['articles'][0]['pmid']='2'
            p.compare_previous(current,[old])
            self.assertEqual(current['status'],'review_required')
            self.assertTrue(current['cross_batch']['identity_conflicts'])

    def test_preprint_and_notice_are_distinct_objects(self):
        # 先造旧快照再造新快照，时间顺序与真实跨批次使用相同。
        old=self.run_plan(meta=xml(pt='Preprint')); current=self.run_plan(meta=xml(pt='Retraction Notice'))
        old['pmids']=['2']; old['articles'][0]['pmid']='2'; old['articles'][0]['doi']='10.2/preprint'
        p.compare_previous(current,[old])
        self.assertEqual(current['cross_batch']['new_count'],1)
        self.assertTrue(current['articles'][0]['retraction_notice'])

    def test_missing_or_invalid_history_never_claims_global_new(self):
        r=self.run_plan(); p.compare_previous(r,[])
        self.assertEqual(r['cross_batch']['status'],'not_evaluated')
        r=self.run_plan(); p.compare_previous(r,[{}])
        self.assertEqual(r['status'],'blocked')

    def test_future_history_not_accepted_as_seen(self):
        r=self.run_plan(); old=copy.deepcopy(r); old['created_at']='2099-01-01T00:00:00+00:00'
        p.compare_previous(r,[old])
        self.assertEqual(r['status'],'blocked')

    def test_history_count_must_match_actual_set(self):
        r=self.run_plan(); old=copy.deepcopy(r); old['counts']['unique_pmids']=999
        p.compare_previous(r,[old])
        self.assertEqual(r['status'],'blocked')

    def test_journal_default_dp_recorded_without_mutating_input(self):
        plan=copy.deepcopy(PLAN); del plan['date']['field']
        r=self.run_plan(plan=plan)
        self.assertEqual(r['status'],'retrieval_verified')
        self.assertNotIn('field',plan['date'])
        self.assertEqual(r['effective_plan']['date']['field'],'dp')
        self.assertEqual(r['date_policy']['origin'],'default')
        self.assertIn('[dp]',r['searches'][0]['query'])
        self.assertEqual(r['effective_plan']['screening_location'],'undecided')

    def test_explicit_publication_date_overrides_default(self):
        for field in ('epdat','ppdat'):
            plan=copy.deepcopy(PLAN); plan['date']['field']=field
            r=self.run_plan(plan=plan)
            self.assertEqual(r['date_policy']['origin'],'explicit')
            self.assertIn('['+field+']',r['searches'][0]['query'])
            self.assertIn('漏收',r['date_policy']['limitation'])
        plan['date']['field']=''
        self.assertEqual(p.preview(plan)['status'],'blocked')

    def test_missing_dates_explicit_not_invented(self):
        r=self.run_plan()
        self.assertEqual(r['articles'][0]['date_sources'],{
          'electronic':{'status':'missing','xml':[]},'issue':{'status':'missing','xml':[]}})
        raw,_=xml()
        empty=raw.replace(b'<Journal>',b'<ArticleDate DateType="Electronic"/><Journal>')
        self.assertEqual(self.run_plan(meta=(empty,{}))['articles'][0]['date_sources']['electronic']['status'],'missing')
        raw,_=xml()
        raw=raw.replace(b'<Journal>',b'<ArticleDate DateType="Electronic"><Year>2026</Year><Month>07</Month><Day>08</Day></ArticleDate><Journal><JournalIssue><PubDate><Year>2026</Year><Month>Sep</Month></PubDate></JournalIssue>')
        r=self.run_plan(meta=(raw,{}))
        dates=r['articles'][0]['date_sources']
        self.assertIn('<Day>08</Day>',dates['electronic']['xml'][0])
        self.assertNotIn('<Day>',dates['issue']['xml'][0])

if __name__=='__main__':
    unittest.main(verbosity=2)
