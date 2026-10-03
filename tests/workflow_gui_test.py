"""现役采集台离屏测试；所有业务和网络调用替换为共享服务桩。"""
import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
os.environ['TRACKEEP_SELFTEST'] = '1'
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import unittest
from unittest.mock import patch
from PySide6.QtWidgets import QApplication, QMessageBox
from ui.pages.workflow_page import WorkflowPage

app = QApplication.instance() or QApplication([])


class FakeWorkflow:
    def __init__(self):
        self.calls = []

    def dispatch(self, action, payload):
        self.calls.append((action, payload))
        return {'ok': True, 'action': action, 'run_id': 'test-run', 'state': 'planned',
                'counts': {}, 'data': {'readable_plan': 'Nature；出版日期宽口径'}, 'errors': []}


def sync(owner, function, *args, done=None, failed=None, **kwargs):
    try:
        value = function(*args)
    except Exception as exc:
        failed(str(exc))
    else:
        if done:
            done(value)


class WorkflowGuiTests(unittest.TestCase):
    def setUp(self):
        self.service = FakeWorkflow()
        self.page = WorkflowPage(self.service)
        self.async_patch = patch('ui.pages.workflow_page.run_async', sync)
        self.async_patch.start()

    def tearDown(self):
        self.async_patch.stop()
        self.page.close()

    def test_production_window_uses_shared_page(self):
        with patch('lit.workflow.Workflow', return_value=self.service):
            from ui.main_window import MainWindow
            window = MainWindow()
            self.assertIsInstance(window.pages[0], WorkflowPage)
            window.close()

    def test_year_and_month_plan(self):
        self.page.year.setCurrentIndex(self.page.year.findData(2025))
        self.page.month.setCurrentIndex(self.page.month.findData(2))
        plan = self.page.build_plan()
        self.assertEqual(plan['date'], {'field':'dp', 'start':'2025-02-01', 'end':'2025-02-28'})
        self.assertEqual(plan['selection_mode'], 'broad')
        self.assertEqual(plan['screening_location'], 'after-import')

    def test_natural_request_delegated(self):
        self.page.mode.setCurrentIndex(1)
        self.page.query.setText('肺癌术后免疫治疗')
        self.page.create_plan()
        action, payload = self.service.calls[-1]
        self.assertEqual(action, 'plan_natural')
        self.assertEqual(payload['text'], '肺癌术后免疫治疗')
        self.assertNotIn('query', payload)

    def test_articles_require_no_model(self):
        self.page.mode.setCurrentIndex(2)
        self.page.pmids.setText('42420446，42816625')
        self.page.create_plan()
        action, payload = self.service.calls[-1]
        self.assertEqual(action, 'plan')
        self.assertEqual(payload['plan']['pmids'], ['42420446', '42816625'])

    def test_import_cancel_never_dispatches(self):
        self.page.run_id = 'locked'
        with patch.object(QMessageBox, 'exec', return_value=QMessageBox.No):
            self.page.import_batch(True)
        self.assertEqual(self.service.calls, [])

    def test_import_uses_locked_run_not_form(self):
        self.page.run_id = 'locked'
        self.page.journal.setEditText('另一刊')
        with patch.object(QMessageBox, 'exec', return_value=QMessageBox.Yes):
            self.page.import_batch(True)
        action, payload = self.service.calls[-1]
        self.assertEqual(action, 'import')
        self.assertEqual(payload, {'apply': True, 'run_id': 'locked'})

    def test_busy_prevents_duplicate_operation(self):
        self.page._set_busy(True)
        self.page.create_plan()
        self.assertEqual(self.service.calls, [])
        self.assertFalse(self.page.import_button.isEnabled())

    def test_pending_default_and_review_reason(self):
        self.page.run_id = 'locked'
        self.page.render({'data': {'search': {'articles': [{'pmid':'1', 'title':'a', 'abstract':''}]}}})
        self.assertEqual(self.page.table.cellWidget(0, 4).currentData(), 'pending')
        self.page.table.cellWidget(0, 4).setCurrentIndex(1)
        self.page.table.item(0, 5).setText('')
        self.page.save_review()
        self.assertEqual(self.service.calls, [])

    def test_fulltext_goes_through_shared_gate(self):
        self.page.run_id = 'locked'
        self.page.fulltext()
        self.assertEqual(self.service.calls[-1], ('fulltext', {'run_id':'locked', 'apply':True}))

    def test_service_failure_visible(self):
        self.page.received({'ok':False, 'state':'blocked', 'errors':['网络异常'], 'data':{}, 'counts':{}})
        self.assertIn('网络异常', self.page.report.toPlainText())
        self.assertFalse(self.page._busy)

    def test_failed_new_plan_cannot_write_previous_run(self):
        self.page.run_id = 'old-run'
        with patch.object(self.service, 'dispatch', return_value={'ok':False,'action':'plan',
                'errors':['异常计划'], 'data':{}, 'run_id':None}):
            self.page.create_plan()
        self.assertIsNone(self.page.run_id)
        self.assertFalse(self.page.import_button.isEnabled())

    def test_placeholder_is_not_keep_reason(self):
        self.page.run_id = 'locked'
        self.page.render({'data':{'search':{'articles':[{'pmid':'1','title':'a'}]}}})
        self.page.table.cellWidget(0,4).setCurrentIndex(1)
        self.page.save_review()
        self.assertEqual(self.service.calls, [])

    def test_collection_failure_is_not_zero_success(self):
        self.page.received({'ok':False,'action':'collections','data':{},'errors':['网络失败']})
        self.assertIn('网络失败', self.page.status.text())

    def test_restore_articles_replaces_default_journal_form(self):
        self.page.received({'ok':True,'action':'status','run_id':'restored','data':{
            'plan':{'kind':'articles','pmids':['34265844']}, 'target_collection':'75X3U7JU'}})
        self.assertEqual(self.page.mode.currentData(), 'articles')
        self.assertEqual(self.page.pmids.text(), '34265844')
        self.assertEqual(self.page.journal.currentText(), '')
        self.assertIn('75X3U7JU', self.page.collection.currentText())
        self.assertIn('已恢复', self.page.plan_context.text())

    def test_restore_journal_month_and_custom_date(self):
        plan = {'kind':'journal','journal':'Science','date':{'field':'dp','start':'2025-02-01','end':'2025-02-28'}}
        self.page.restore_plan_fields({'plan':plan})
        self.assertEqual(self.page.journal.currentText(), 'Science')
        self.assertEqual(self.page.year.currentData(), 2025)
        self.assertEqual(self.page.month.currentData(), 2)
        plan['date'] = {'field':'epdat','start':'2024-03-12','end':'2024-07-09'}
        self.page.restore_plan_fields({'plan':plan})
        self.assertIn('2024-03-12', self.page.month.currentText())
        self.assertEqual(self.page.build_plan()['date'], plan['date'])

    def test_restore_topic_all_time_and_saved_criteria(self):
        self.page.restore_plan_fields({'plan':{'kind':'topic','query':'lung cancer[tiab]','all_time':True},
                                       'review':{'criteria':'研究主体为肺癌'}})
        self.assertEqual(self.page.mode.currentData(), 'topic')
        self.assertEqual(self.page.query.text(), 'lung cancer[tiab]')
        self.assertTrue(self.page.build_plan()['all_time'])
        self.assertNotIn('date', self.page.build_plan())
        self.assertEqual(self.page.criteria.text(), '研究主体为肺癌')

    def test_import_dialog_shows_saved_scope_counts_target_and_chinese_buttons(self):
        self.page.run_id = 'locked-run'
        self.page._collection_names['ABCDEFGH'] = '隔离验收集合'
        self.page.snapshot = {'data':{'readable_plan':'指定3篇文献','target_collection':'ABCDEFGH',
            'search':{'articles':[{}, {}, {}]},'metadata':{'counts':{'new_candidate':1,'existing_verified':2}}}}
        self.page.collection.addItem('后来选择的集合', 'IJKLMNOP')
        self.page.collection.setCurrentIndex(1)
        box = self.page.import_confirmation()
        for value in ('locked-run', '指定3篇文献', '检索题录：3','隔离验收集合（ABCDEFGH）','拟新增：1；已存在：2'):
            self.assertIn(value, box.text())
        self.assertNotIn('IJKLMNOP', box.text())
        self.assertEqual(box.button(QMessageBox.Yes).text(), '确认导入')
        self.assertEqual(box.button(QMessageBox.No).text(), '取消')
        self.assertEqual(box.defaultButton(), box.button(QMessageBox.No))

    def test_no_preview_dialog_does_not_invent_zero_counts(self):
        box = self.page.import_confirmation()
        self.assertIn('尚未核重', box.text())
        self.assertIn('未取得核验数量', box.text())

    def test_failed_batch_restores_its_plan_and_chinese_counts(self):
        self.page.received({'action':'status','ok':False,'run_id':'failed-run',
            'data':{'plan':{'kind':'articles','pmids':['35357919']}},
            'counts':{'fulltext_review_pending':1,'fulltext_excluded':0},'errors':['官方来源不可用']})
        self.assertEqual(self.page.mode.currentData(), 'articles')
        self.assertIn('仍待复核', self.page.report.toPlainText())
        self.assertNotIn('review_pending', self.page.report.toPlainText())

    def test_double_click_reason_does_not_open_reader(self):
        with patch.object(self.page, 'read_article') as read:
            self.page.table.cellDoubleClicked.emit(0, 5)
            read.assert_not_called()
            self.page.table.cellDoubleClicked.emit(0, 1)
            read.assert_called_once()

    def test_confirmed_import_uses_same_locked_collection_as_dialog(self):
        self.page.run_id = 'locked'
        self.page.snapshot = {'data':{'target_collection':'ABCDEFGH','metadata':{'counts':{'new_candidate':1}}}}
        self.page.collection.addItem('另一集合', 'IJKLMNOP')
        self.page.collection.setCurrentIndex(1)
        with patch.object(QMessageBox, 'exec', return_value=QMessageBox.Yes):
            self.page.import_batch(True)
        self.assertEqual(self.service.calls[-1][1]['collection_key'], 'ABCDEFGH')

    def test_real_threads_single_flight_and_failure_recovery_50_rounds(self):
        import threading
        import time
        from ui.workers import run_async
        for number in range(50):
            gate = threading.Event()
            calls = []
            fail = number % 7 == 0
            def dispatch(action, payload):
                calls.append((action, payload))
                if not gate.wait(2):
                    raise RuntimeError('合成任务等待超时')
                if fail:
                    raise RuntimeError('合成网络失败')
                return {'ok':True, 'action':action, 'run_id':'locked', 'state':'planned',
                        'data':{}, 'counts':{}, 'errors':[]}
            self.page.run_id = 'locked'
            with patch('ui.pages.workflow_page.run_async', run_async), patch.object(self.service, 'dispatch', dispatch):
                self.page.call('search')
                for _ in range(10):
                    self.page.call('status')
                    self.page.create_plan()
                    self.page.import_batch(False)
                    self.page.fulltext()
                gate.set()
                deadline = time.monotonic() + 3
                while self.page._workers and time.monotonic() < deadline:
                    app.processEvents()
                    time.sleep(.001)
            self.assertFalse(self.page._workers, f'第{number}轮线程未清理')
            self.assertFalse(self.page._busy)
            self.assertEqual(calls, [('search', {'run_id':'locked'})])
            if fail:
                self.assertIn('合成网络失败', self.page.status.text())

    def test_large_title_stays_in_table(self):
        self.page.resize(1040, 760)
        self.page.render({'data': {'search': {'articles': [{'pmid':'1','title':'长标题'*300,'abstract':''}]}}})
        self.page.show()
        app.processEvents()
        self.assertLessEqual(self.page.table.width(), self.page.width())
        self.assertEqual(self.page.table.rowCount(), 1)


if __name__ == '__main__':
    unittest.main()
