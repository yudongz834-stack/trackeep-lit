"""记录两份附件经 Zotero 原生定位流程恢复后的交付状态。"""
import datetime as dt
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
folder=ROOT/'日志/fulltext-validation'
(folder/'desktop-relink-actions.json').write_text(json.dumps({
 'at':dt.datetime.now(dt.timezone.utc).isoformat(),'method':'Zotero 原生缺失附件对话框→检索/定位文件→选择已校验PDF',
 'items':[
 {'pmid':'42420446','parent':'WD9F8D8E','attachment':'XT8K8X34','source':str(ROOT/'全文/42420446.pdf'),'reader_opened':True,'reader_pages':37},
 {'pmid':'42816625','parent':'IU8CWQD2','attachment':'JBKB7SJZ','source':str(ROOT/'全文/42816625.pdf'),'reader_opened':True,'reader_pages':37}],
 'scope':'只操作本批两个原附件，程序自行接收文件；未直接写数据库或storage，未改WebDAV或账户配置',
 'webdav_remote_file_readback':'not_verified','sync_ui':'恢复后原有红色同步错误标志消失，但不据此声称WebDAV两份远端文件读回通过',
 'prior_routes_checked':['Trackeep zotero-pdf.ps1仅定位只读','zotero-findpdf-sweep.js为全库流程，不运行','当前本机9.0.6 API只读','现有Zotero GUI定位文件可保留原附件key'],
 'limitations':'桌面修复是Agent执行现有原生UI流程，不是新增通用命令；网络远端WebDAV未另取凭证或核验'
},ensure_ascii=False,indent=2),encoding='utf-8')
note='''## 最新交付：两篇本机全文已可用（2026-10-03）

桌面缺文件问题已通过 Zotero 自带“找不到文件→检索/定位文件”流程解决。Agent 逐一选择已校验官方PDF，由 Zotero 自己补回原附件存储：PMID42420446／XT8K8X34、PMID42816625／JBKB7SJZ。两份均在本机阅读器实际打开、显示37页；本地API给出的文件真实存在，SHA256与官方原件一致。没有新建附件、直接写storage/数据库、升级软件或改变现有WebDAV设置，用户无需手动搬文件。证据：日志/fulltext-validation/desktop-verification.json、desktop-relink-actions.json；独立本机验收见 independent-desktop-acceptance.json。

此前错误是只验了Zotero Storage云端而未核用户WebDAV桌面交付，失败记录保留。现已完成本批本机可读交付；WebDAV远端文件没有另行下载核验，不能将UI同步错误标志消失称为远端验收。旧GUI仍未接新Agent护栏，命令复用范围与需Agent编排的环节见下方历史核对中的入口说明；桌面定位操作也是本次Agent执行原生UI，尚非一个通用自动管道。

'''
for name in ('HANDOFF.md','阶段日志.md'):
 p=ROOT/name;s=p.read_text(encoding='utf-8-sig')
 s=s.replace('## 桌面交付核对追加（2026-10-03，覆盖前文“未确认同步”）','## 桌面交付核对历史（当时文件未到本机；已由上方定位修复关闭）')
 first,rest=s.split('\n',1);p.write_text(first+'\n\n'+note+rest.lstrip('\n'),encoding='utf-8')
p=ROOT/'HANDOFF.md';s=p.read_text(encoding='utf-8')
for f in [ROOT/'工作区/收口本机交付.py',ROOT/'工作区/独立复核/fulltext_desktop_acceptance.py',*folder.glob('desktop*.json'),folder/'independent-desktop-acceptance.json']:
 line='- '+str(f)
 if f.exists() and line not in s:s+=line+'\n'
p.write_text(s,encoding='utf-8')
