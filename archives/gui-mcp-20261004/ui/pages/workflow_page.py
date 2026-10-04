"""现役采集台：界面只编排共享流程，不另写检索、判重和入库逻辑。"""
import calendar
import copy
from datetime import date, timedelta
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QComboBox, QLineEdit, QPushButton, QPlainTextEdit, QTableWidget,
    QTableWidgetItem, QHeaderView, QMessageBox, QProgressBar, QSplitter, QDialog)
from lit import pubmed, journals
from ui.workers import run_async


class WorkflowPage(QWidget):
    def __init__(self, workflow=None):
        super().__init__()
        if workflow is None:
            from lit.workflow import Workflow
            workflow = Workflow()
        self.workflow = workflow
        self.run_id = None
        self.snapshot = {}
        self._workers = []
        self._busy = False
        self._buttons = []
        self._articles = []
        self._collection_names = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 16)
        title = QLabel('文献采集台')
        title.setObjectName('pageTitle')
        layout.addWidget(title)
        layout.addWidget(QLabel('明确计划并核验检索；确认导入后自动复核，保留项继续本机全文。'))
        form = QFormLayout()
        self.mode = QComboBox()
        self.mode.addItem('按期刊和年月采集', 'journal')
        self.mode.addItem('按主题检索', 'topic')
        self.mode.addItem('指定文章（PMID）', 'articles')
        self.journal = QComboBox()
        self.journal.setEditable(True)
        for j in pubmed.journals():
            self.journal.addItem(j['name'], j['ta'])
        self._journal_groups = journals.load()
        self.category = QComboBox()
        self.category.addItem('全部期刊')
        self.category.addItems(list(self._journal_groups))
        self.category.currentTextChanged.connect(self._journal_category)
        self._journal_category('全部期刊')
        self.year = QComboBox()
        for year in range(date.today().year, 1899, -1):
            self.year.addItem(str(year), year)
        self.month = QComboBox()
        self.month.addItem('最近60天', -1)
        self.month.addItem('全年', None)
        for month in range(1, 13):
            self.month.addItem(f'{month:02d}月', month)
        period = QHBoxLayout()
        period.addWidget(self.year)
        period.addWidget(self.month)
        self.query = QLineEdit()
        self.query.setPlaceholderText('用中文描述要找的研究；系统先生成可确认的检索计划')
        self.pmids = QLineEdit()
        self.pmids.setPlaceholderText('多个 PMID 用空格或逗号分隔')
        self.criteria = QLineEdit()
        self.criteria.setPlaceholderText('可填写收集标准；留空按已确认范围，按刊不额外缩窄主题')
        form.addRow('采集方式', self.mode)
        journal_row = QHBoxLayout()
        journal_row.addWidget(self.category)
        journal_row.addWidget(self.journal, 1)
        form.addRow('期刊（检索前核验）', journal_row)
        form.addRow('出版日期范围', period)
        form.addRow('主题检索', self.query)
        form.addRow('文章编号', self.pmids)
        form.addRow('复核要求', self.criteria)
        layout.addLayout(form)
        self.plan_context = QLabel('上方填写新计划；操作按钮使用下方已生成或恢复的批次。')
        self.plan_context.setWordWrap(True)
        layout.addWidget(self.plan_context)
        row = QHBoxLayout()
        self.plan_button = self._button(row, '1 生成计划', self.create_plan)
        self.search_button = self._button(row, '2 核验并检索', lambda: self.call('search'))
        self.preview_button = self._button(row, '3 导入前核重', lambda: self.import_batch(False))
        self.import_button = self._button(row, '确认存入 Zotero', lambda: self.import_batch(True))
        layout.addLayout(row)
        collections = QHBoxLayout()
        collections.addWidget(QLabel('存入集合'))
        self.collection = QComboBox()
        self.collection.addItem('按期刊匹配已有集合', '')
        collections.addWidget(self.collection, 1)
        self._button(collections, '读取已有集合', self.load_collections)
        self.resume = QComboBox()
        self.resume.setMinimumWidth(160)
        collections.addWidget(self.resume)
        self._button(collections, '恢复批次', self.restore_run)
        layout.addLayout(collections)
        split = QSplitter(Qt.Vertical)
        self.report = QPlainTextEdit()
        self.report.setReadOnly(True)
        self.report.setMaximumHeight(110)
        split.addWidget(self.report)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(['PMID', '标题', '题录 / 全文状态', '摘要', '复核决定', '理由'])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        for column, width in ((0, 85), (2, 180), (3, 65), (4, 100)):
            self.table.setColumnWidth(column, width)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.cellDoubleClicked.connect(self._read_doubleclicked)
        split.addWidget(self.table)
        layout.addWidget(split, 1)
        attention = QHBoxLayout()
        attention.addWidget(QLabel('查看'))
        self.view_filter = QComboBox()
        for label, key in [('全部题录', 'all'), ('集中待核 / 未完成', 'attention'), ('保留', 'keep'), ('排除', 'exclude')]:
            self.view_filter.addItem(label, key)
        self.view_filter.currentIndexChanged.connect(self.filter_rows)
        attention.addWidget(self.view_filter)
        self.queue_summary = QLabel('待核项会在这里集中显示。')
        attention.addWidget(self.queue_summary, 1)
        self.continue_button = self._button(attention, '继续未完成步骤', self.continue_batch)
        layout.addLayout(attention)
        reviews = QHBoxLayout()
        self.review_button = self._button(reviews, '保存人工复核并继续', self.save_review)
        self._button(reviews, '阅读题录', self.read_article)
        self.ai_button = self._button(reviews, 'AI 相关性复核', self.ai_review)
        self.fulltext_button = self._button(reviews, '5 获取并核验全文', self.fulltext)
        self._button(reviews, '刷新状态', lambda: self.call('status'))
        layout.addLayout(reviews)
        self.progress = QProgressBar()
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        layout.addWidget(self.progress)
        self.status = QLabel('先生成计划；检索不会写入 Zotero。')
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.mode.currentIndexChanged.connect(self._mode_changed)
        self.month.currentIndexChanged.connect(self._mode_changed)
        self._mode_changed()
        self._set_busy(False)
        self.refresh_runs()

    def _button(self, row, text, callback):
        button = QPushButton(text)
        button.clicked.connect(callback)
        row.addWidget(button)
        self._buttons.append(button)
        return button

    def _mode_changed(self):
        kind = self.mode.currentData()
        self.journal.setEnabled(kind == 'journal')
        self.category.setEnabled(kind == 'journal')
        self.year.setEnabled(kind != 'articles' and isinstance(self.month.currentData(), (int, type(None)))
                             and self.month.currentData() != -1)
        self.month.setEnabled(kind != 'articles')
        self.query.setEnabled(kind != 'articles')
        self.pmids.setEnabled(kind == 'articles')

    def _journal_category(self, name):
        self.journal.clear()
        names = ([j['ta'] for j in pubmed.journals()] +
                 [j for values in self._journal_groups.values() for j in values]
                 if name == '全部期刊' else self._journal_groups.get(name, []))
        for value in dict.fromkeys(names):
            self.journal.addItem(value, value)

    def build_plan(self):
        kind = self.mode.currentData()
        if kind == 'articles':
            import re
            values = re.split(r'[\s,，;；]+', self.pmids.text().strip())
            return {'kind': 'articles', 'pmids': values}
        year, month = self.year.currentData(), self.month.currentData()
        if isinstance(month, dict):
            date_part = copy.deepcopy(month)
        elif month == -1:
            start, end = date.today() - timedelta(days=60), date.today()
        else:
            start = date(year, month or 1, 1)
            end = date(year, month or 12, calendar.monthrange(year, month or 12)[1])
        if not isinstance(month, dict):
            if start > date.today():
                raise ValueError('所选月份尚未开始，请选择已开始的日期范围。')
            end = min(end, date.today())
            date_part = {'date': {'field': 'dp', 'start': start.isoformat(), 'end': end.isoformat()}}
        plan = {'kind': kind, **date_part, 'screening_location': 'after-import'}
        query = self.query.text().strip()
        if kind == 'journal':
            plan.update(journal=self.journal.currentText().strip(), selection_mode='broad')
            if query:
                plan.update(selection_mode='query-filtered', filter_query=query, filter_reason='用户在采集台明确指定主题过滤')
        else:
            plan.update(query=query, concepts=[{'name': query}])
        return plan

    def create_plan(self):
        if self._busy:
            return
        # 新计划失败也不能让旧批次继续充当当前输入的写入目标。
        self.run_id = None
        self.snapshot = {}
        self._articles = []
        self.table.setRowCount(0)
        self.report.clear()
        self.plan_context.setText('上方填写新计划；操作按钮使用下方已生成或恢复的批次。')
        self._set_busy(False)
        try:
            plan = self.build_plan()
        except ValueError as e:
            self.failed(str(e))
            return
        if self.query.text().strip() and plan['kind'] != 'articles':
            payload = {'text': self.query.text().strip(), 'criteria': self.criteria.text().strip()}
            payload.update({'date': plan['date']} if plan.get('date') else {'all_time': True})
            if plan.get('journal'):
                payload['journal'] = plan['journal']
            self.call('plan_natural', payload)
        else:
            self.call('plan', {'plan': plan, 'criteria': self.criteria.text().strip()})

    def _set_busy(self, busy):
        self._busy = busy
        for button in self._buttons:
            button.setEnabled(not busy)
        for button in (self.search_button, self.preview_button, self.import_button,
                       self.review_button, self.ai_button, self.fulltext_button, self.continue_button):
            button.setEnabled(not busy and bool(self.run_id))
        self.table.setEnabled(not busy)
        self.view_filter.setEnabled(not busy)
        self.criteria.setReadOnly(bool(self.snapshot.get('data', {}).get('continuation', {}).get('authorized')))
        if self.snapshot.get('data', {}).get('continuation', {}).get('authorized'):
            self.preview_button.setEnabled(False)
            if self.snapshot.get('data', {}).get('metadata', {}).get('status') in ('metadata_verified','review_required'):
                self.search_button.setEnabled(False)
        self.progress.setRange(0, 0 if busy else 1)
        if not busy:
            self.progress.setValue(1)

    def call(self, action, payload=None):
        if self._busy:
            return
        body = copy.deepcopy(payload or {})
        if action not in ('plan', 'plan_natural', 'collections', 'list_runs'):
            if not self.run_id:
                self.failed('请先生成或恢复一个批次。')
                return
            body['run_id'] = self.run_id
        self._set_busy(True)
        self.status.setText({'plan': '正在生成计划…', 'search': '正在核验 PubMed、获取全部匹配题录…',
                             'import': '正在核重并处理题录…', 'review': '正在复核身份、重复和撤稿信息…',
                             'continue': '正在接续导入、AI复核及保留项全文；待核和失败会保存，可恢复继续…',
                             'fulltext': '正在获取并核验本机全文…'}.get(action, '正在读取状态…'))
        run_async(self, lambda: self.workflow.dispatch(action, body), done=self.received, failed=self.failed)

    def import_batch(self, apply):
        if self._busy or not self.run_id:
            return
        if apply and self.import_confirmation().exec() != QMessageBox.Yes:
            return
        payload = {'apply': apply}
        data = self.snapshot.get('data', {})
        key = data.get('target_collection') if data.get('metadata') else self.collection.currentData()
        if key:
            payload['collection_key'] = key
        if apply:
            if not data.get('continuation', {}).get('authorized'):
                payload['criteria'] = self.criteria.text().strip()
            self.call('continue', payload)
        else:
            self.call('import', payload)

    def continue_batch(self):
        if self._busy or not self.run_id:
            return
        if not self.snapshot.get('data', {}).get('continuation', {}).get('authorized'):
            self.import_batch(True)
            return
        self.call('continue', {'apply': True})

    def collection_description(self, key):
        data = self.snapshot.get('data', {})
        name = self._collection_names.get(key) or data.get('target_collection_name')
        if not name:
            index = self.collection.findData(key)
            if index >= 0:
                text = self.collection.itemText(index)
                if text not in ('本批次已锁定集合', f'集合（{key}）'):
                    name = text
        return f'{name}（{key}）' if name and key not in name else (name or f'集合（{key}）')

    def import_confirmation(self):
        data = self.snapshot.get('data', {})
        search = data.get('search') or {}
        total = len(search['articles']) if 'articles' in search else '未取得核验数量'
        metadata = data.get('metadata') or {}
        counts = metadata.get('counts') or {}
        new = counts.get('new_candidate', 0) if counts else '尚未核重'
        existing = sum(counts.get(k, 0) for k in ('existing_verified', 'created_verified', 'existing_outside_target')) if counts else '尚未核重'
        target = data.get('target_collection') or self.collection.currentData()
        keys = {item.get('collection_key') for item in metadata.get('items', []) if item.get('collection_key')}
        destination = (self.collection_description(target) if target else
                       '、'.join(self.collection_description(k) for k in sorted(keys)) if keys else
                       '按期刊匹配已有集合（请先核重预览确认目标）')
        text = (f'批次：{self.run_id}\n范围：{data.get("readable_plan", "以该批次已核验计划为准")}\n'
                f'检索题录：{total}\n目标集合：{destination}\n拟新增：{new}；已存在：{existing}\n\n'
                f'收集标准：{self.criteria.text().strip() or (data.get("collection_policy") or {}).get("criteria", "依已确认范围保留，不额外缩窄主题")}\n'
                '确认后自动完成题录导入、AI复核和保留项全文。缺摘要、模型无结论及身份异常集中待核；'
                '排除项保留题录与理由。实际新增以再次核重及读回为准。')
        box = QMessageBox(QMessageBox.Question, '确认写入 Zotero', text,
                          QMessageBox.Yes | QMessageBox.No, self)
        box.button(QMessageBox.Yes).setText('确认导入')
        box.button(QMessageBox.No).setText('取消')
        box.setDefaultButton(QMessageBox.No)
        return box

    def restore_plan_fields(self, data):
        plan = data.get('plan') or {}
        kind = plan.get('kind')
        index = self.mode.findData(kind)
        if index < 0:
            return
        self.mode.setCurrentIndex(index)
        self.category.setCurrentIndex(0)
        self.journal.setEditText(plan.get('journal', ''))
        self.pmids.setText(' '.join(plan.get('pmids', [])))
        self.query.setText(plan.get('query', plan.get('filter_query', '')))
        self.criteria.setText((data.get('continuation') or {}).get('criteria') or
                              (data.get('collection_policy') or {}).get('criteria') or
                              (data.get('review') or {}).get('criteria', ''))
        # 自定义时间范围原样回显，不伪装成默认“最近60天”。
        while self.month.count() > 14:
            self.month.removeItem(self.month.count() - 1)
        period = plan.get('date')
        if period:
            start, end = date.fromisoformat(period['start']), date.fromisoformat(period['end'])
            year_index = self.year.findData(start.year)
            if year_index < 0:
                self.year.addItem(str(start.year), start.year)
                year_index = self.year.count() - 1
            self.year.setCurrentIndex(year_index)
            if period.get('field') == 'dp' and start == date(start.year, 1, 1) and end == date(start.year, 12, 31):
                self.month.setCurrentIndex(self.month.findData(None))
            elif period.get('field') == 'dp' and start.day == 1 and start.year == end.year and start.month == end.month and end.day == calendar.monthrange(end.year, end.month)[1]:
                self.month.setCurrentIndex(self.month.findData(start.month))
            else:
                self.month.addItem(f'{start} 至 {end}（{period.get("field", "dp")}）', {'date': period})
                self.month.setCurrentIndex(self.month.count() - 1)
        else:
            self.month.addItem('不限定日期' if kind != 'articles' else '按指定文章，不限定日期', {'all_time': True})
            self.month.setCurrentIndex(self.month.count() - 1)
        self._mode_changed()
        self.plan_context.setText('已恢复批次范围；修改上方字段后须点“生成计划”另建批次，原批次不会被改写。')

    def save_review(self):
        decisions = []
        for row, article in enumerate(self._articles):
            decision = self.table.cellWidget(row, 4).currentData()
            reason = self.table.item(row, 5).text().strip()
            if not reason:
                reason = '尚未复核' if decision == 'pending' else ''
            if not reason or (decision != 'pending' and reason in ('尚未复核', '尚无逐篇复核结论')):
                self.failed('保留或排除时请填写理由。')
                return
            decisions.append({'pmid': str(article['pmid']), 'decision': decision, 'reason': reason})
        self.call('review', {'decisions': decisions})

    def ai_review(self):
        # 模型调用与缺摘要策略也属于共同服务，GUI 不自行改变判决。
        criteria = self.criteria.text().strip()
        if not criteria:
            self.failed('请填写中文复核要求后运行 AI 复核；也可直接逐条人工复核。')
            return
        self.call('review_ai', {'criteria': criteria})

    def read_article(self):
        row = self.table.currentRow()
        if row < 0 or row >= len(self._articles):
            self.status.setText('请先选中一篇题录，双击也可打开。')
            return
        article = self._articles[row]
        dialog = QDialog(self)
        dialog.setWindowTitle('题录与复核依据')
        dialog.resize(760, 560)
        lay = QVBoxLayout(dialog)
        text = QPlainTextEdit()
        text.setReadOnly(True)
        lines = [article.get('title', ''), f'PMID：{article.get("pmid", "")}',
                 f'DOI：{article.get("doi", "")}', f'期刊：{article.get("journal", "")}',
                 '摘要：' + (article.get('abstract') or '缺摘要，不能据此自动排除'),
                 '日期来源：' + str(article.get('date_sources', article.get('dates', '未提供'))),
                 '撤稿及关联记录：' + str(article.get('retraction_links', article.get('links', [])))]
        text.setPlainText('\n\n'.join(lines))
        lay.addWidget(text)
        close = QPushButton('关闭')
        close.clicked.connect(dialog.accept)
        lay.addWidget(close)
        dialog.exec()

    def _read_doubleclicked(self, row, column):
        # 理由列保持原生双击编辑；仅标题、摘要列打开阅读窗。
        if column in (1, 3):
            self.read_article()

    def fulltext(self):
        self.call('fulltext', {'apply': True})

    def failed(self, message):
        self._set_busy(False)
        self.status.setText('操作未完成：' + message)
        self.report.appendPlainText('操作未完成：' + message)

    def received(self, result):
        self._set_busy(False)
        if result.get('action') == 'collections':
            if not result.get('ok'):
                self.failed('；'.join(result.get('errors', ['集合读取失败'])))
                return
            self._collections_received(result.get('data', {}).get('collections', []))
            return
        self.snapshot = result
        self.run_id = result.get('run_id') or self.run_id
        if (result.get('action') == 'status' and result.get('run_id')
                and isinstance(result.get('data', {}).get('plan'), dict)):
            self.restore_plan_fields(result.get('data', {}))
            if not result.get('data', {}).get('target_collection'):
                self.collection.setCurrentIndex(0)
        target = result.get('data', {}).get('target_collection')
        if target:
            index = self.collection.findData(target)
            if index < 0:
                self.collection.addItem(self.collection_description(target), target)
                index = self.collection.count() - 1
            self.collection.setCurrentIndex(index)
        self.render(result)
        if result.get('action') == 'continue':
            self.criteria.setText((result.get('data', {}).get('collection_policy') or {}).get('criteria', ''))
            if result.get('data', {}).get('pending_queue'):
                self.view_filter.setCurrentIndex(self.view_filter.findData('attention'))
        self._set_busy(False)
        self.refresh_runs()

    def render(self, result):
        """仅展示服务返回的事实；不凭按钮完成推断业务完成。"""
        data = result.get('data', result)
        states = {'planned':'计划待确认，请检查下方范围后点击核验检索', 'search_verified':'检索已核验',
                  'retrieval_verified':'检索已核验', 'search_blocked':'检索需核查', 'import_preview_only':'核重预览完成',
                  'import_metadata_verified':'题录入库已核验', 'import_review_required':'题录待核',
                  'import_blocked':'导入未完成', 'review_pending':'存在待核项', 'review_complete':'复核完成',
                  'fulltext_complete':'本机全文已核验', 'fulltext_partial_failure':'部分全文未完成',
                  'fulltext_review_pending':'尚有题录待复核，全文仅处理已保留项',
                  'fulltext_not_required':'没有需要获取全文的保留项',
                  'review_cleanup_pending':'复核已保存，部分可恢复清理待核'}
        states['continuation_blocked'] = '连续流程未完成，已保存检查点；可继续未完成步骤'
        self.status.setText(f'批次：{self.run_id or "—"} · {states.get(result.get("state"), "已返回回执，请核对下方结果")}')
        lines = []
        plan = data.get('readable_plan', '')
        if isinstance(plan, dict):
            lines.extend(f'{key}：{value}' for key, value in plan.items())
        elif isinstance(plan, list):
            lines.extend(str(x) for x in plan)
        elif plan:
            lines.append(str(plan))
        labels = {'keep': '保留', 'exclude': '排除', 'pending': '待核', 'needs_attention':'集中待核 / 未完成', 'new': '新题录',
                  'existing': '已存在', 'failed': '失败', 'created_verified': '全文已核验',
                  'existing_verified': '现有全文已核验', 'pending_review': '全文待核',
                  'review_pending': '仍待复核', 'excluded': '已排除', 'scope': '本次范围',
                  'cleanup_pending': '清理待核', 'cleanup_verified': '清理已核验',
                  'cleanup_protected': '已保护存量资料'}
        metadata_labels = {'existing_verified':'已有题录已核验', 'created_verified':'新题录已核验',
                           'new_candidate':'拟新增', 'identity_or_duplicate_pending':'身份或重复待核',
                           'already_trashed':'已在回收站', 'existing_outside_target':'已有文献位于其他集合',
                           'failed':'失败'}
        for key, value in result.get('counts', {}).items():
            if key == 'retrieved':
                name = '取得题录'
            elif key.startswith('metadata_'):
                name = '题录 / ' + metadata_labels.get(key[9:], key[9:])
            elif key.startswith('fulltext_'):
                name = '全文 / ' + labels.get(key[9:], key[9:])
            else:
                name = labels.get(key, key)
            lines.append(f'{name}：{value}')
        for error in result.get('errors', []):
            lines.append('未完成：' + str(error))
        search = data.get('search') or {}
        for reason in search.get('review_reasons', []):
            lines.append('需核查：' + str(reason))
        for event in search.get('searches', []):
            translation = event.get('response', {}).get('esearchresult', {}).get('querytranslation')
            if translation:
                lines.append('PubMed 实际解释：' + translation)
        self.report.setPlainText('\n'.join(lines) or '已取得回执。')
        articles = search.get('articles', data.get('articles', []))
        if isinstance(articles, dict):
            articles = list(articles.values())
        self._articles = articles
        self.table.setRowCount(len(articles))
        decisions = (data.get('review') or {}).get('items', data.get('decisions', {}))
        if isinstance(decisions, list):
            decisions = {str(x['pmid']): x for x in decisions}
        metadata = {str(x.get('pmid')): x for x in (data.get('metadata') or {}).get('items', [])}
        fulltext = {str(x.get('pmid')): x for x in (data.get('fulltext') or {}).get('items', [])}
        for row, article in enumerate(articles):
            pmid = str(article['pmid'])
            raw_status = metadata.get(pmid, {}).get('metadata_status', '已取题录')
            status = metadata_labels.get(raw_status, raw_status)
            ft = fulltext.get(pmid, {}).get('status')
            if ft:
                status += ' / ' + labels.get(ft, ft)
            for col, value in enumerate((article.get('pmid', ''), article.get('title', ''),
                                        status, '有' if article.get('abstract') else '缺摘要')):
                item = QTableWidgetItem(str(value))
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(row, col, item)
            choice = QComboBox()
            for label, key in [('待核', 'pending'), ('保留', 'keep'), ('排除', 'exclude')]:
                choice.addItem(label, key)
            decision = decisions.get(str(article['pmid']), {})
            choice.setCurrentIndex(max(0, choice.findData(decision.get('decision', 'pending'))))
            self.table.setCellWidget(row, 4, choice)
            self.table.setItem(row, 5, QTableWidgetItem(decision.get('reason', '尚未复核')))
            self.table.item(row, 2).setToolTip(str(fulltext.get(pmid, {}).get('reason', '')))
        policy = (data.get('collection_policy') or {}).get('criteria')
        if policy:
            self.report.appendPlainText('本批收集标准：' + policy)
        stage = (data.get('continuation') or {}).get('stage')
        if stage:
            stage_names = {'import':'题录导入', 'review':'AI复核', 'fulltext':'本机全文',
                           'needs_attention':'等待核查或重试', 'complete':'连续流程完成'}
            self.report.appendPlainText('连续流程检查点：' + stage_names.get(stage, stage))
        self.queue_summary.setText(f'本批待核 / 未完成：{len(data.get("pending_queue", []))}；人工保留后自动继续全文。')
        self.filter_rows()

    def filter_rows(self):
        """仅隐藏显示行；保存人工复核仍携带全部题录，不能丢掉隐藏行的判决。"""
        kind = self.view_filter.currentData()
        pending = {str(i['pmid']) for i in self.snapshot.get('data', {}).get('pending_queue', [])}
        for row, article in enumerate(self._articles):
            choice = self.table.cellWidget(row, 4)
            decision = choice.currentData() if choice else 'pending'
            show = (kind == 'all' or (kind == 'attention' and (decision == 'pending' or str(article['pmid']) in pending))
                    or kind == decision)
            self.table.setRowHidden(row, not show)

    def load_collections(self):
        self.call('collections')

    def _collections_received(self, rows):
        self.collection.clear()
        self.collection.addItem('按期刊匹配已有集合', '')
        names = {r['key']: r.get('data', r).get('name', '') for r in rows}
        self._collection_names.update(names)
        for row in rows:
            data = row.get('data', row)
            parent = names.get(data.get('parentCollection'), '')
            self.collection.addItem((parent + ' / ' if parent else '') + data.get('name', ''), row['key'])
        target = self.snapshot.get('data', {}).get('target_collection')
        if target:
            self.collection.setCurrentIndex(self.collection.findData(target))
        self._set_busy(False)
        self.status.setText(f'已读取 {len(rows)} 个已有集合。')

    def refresh_runs(self):
        # 只枚举共享服务自己的本地批次，不读取 Zotero 或账号资料。
        store = getattr(self.workflow, 'store', None)
        if store is None:
            return
        from pathlib import Path
        current = self.run_id
        self.resume.clear()
        for path in sorted(Path(store).glob('*/run.json'), reverse=True):
            self.resume.addItem(path.parent.name, path.parent.name)
        if current:
            self.resume.setCurrentIndex(self.resume.findData(current))

    def restore_run(self):
        if self.resume.currentData():
            self.run_id = self.resume.currentData()
            self.call('status')
