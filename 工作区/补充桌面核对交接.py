"""补充真实桌面边界及现有 Agent 入口；不改变任何同步设置。"""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
folder=ROOT/'日志/fulltext-validation'
(folder/'desktop-sync-boundary.json').write_text(json.dumps({
    'local_version':'9.0.6','metadata_synced':2,'attachment_records_synced':2,'local_files_available':0,
    'desktop_file_sync_protocol':'webdav','cloud_upload_backend':'Zotero Storage',
    'configuration_read':'仅读取 sync.storage.protocol，未读取服务器地址、账户或密码',
    'attempts':['系统 zotero://open-pdf URI 调用失败：未注册处理程序',
                '现有 zotero.exe -url 仅打开两份指定附件；进程调用返回成功，但后续本地文件仍不存在'],
    'boundary':'不能宣称桌面全文完成；不同存储后端与实测缺文件相符，未取得桌面内部下载错误，具体下载失败原因未完全诊断',
    'changes':'未改配置、账户、凭证、注册表；未复制文件到Zotero存储或改数据库；未启动全库同步',
    'references':['https://www.zotero.org/support/preferences/sync','https://www.zotero.org/support/sync',
                  'https://forums.zotero.org/discussion/98234/is-there-anyway-i-can-open-pdfs-in-zotero-pdf-viewer-via-the-command-line']
},ensure_ascii=False,indent=2),encoding='utf-8')
note='''## 桌面交付核对追加（2026-10-03，覆盖前文“未确认同步”）

本机 Zotero9.0.6 API 已读到两篇正确父项与两份附件，PMID/DOI/标题/关联一致；但 API 返回的两个 storage 文件路径均不存在。现有桌面附件同步配置为 WebDAV，本批上传后端为 Zotero Storage，不能把云端附件成功等同于桌面文件可用。尝试系统 open-pdf URI 因未注册失败；改用已有 Zotero 可执行文件 -url 打开指定两份附件后复查仍无文件。没有修改账户/凭证/全局同步配置或注册表，也没有向 storage 目录自行塞文件或改库。尚缺“本机全文文件可用”这一环，具体桌面下载错误未取得，不能声称完全诊断。证据：日志/fulltext-validation/desktop-verification.json、desktop-sync-boundary.json。最初标题句末点差异导致的严格字符串误报亦保留为 desktop-verification-before-normalization.json，改用既有规范化比较并核PMID后确认题录无误。

后续需要确定如何沿用户既有 WebDAV 路径完成这两份文件的交付，或明确授权其他受支持的本地附件写入方式；本次仅核对，不开新功能。用户无需自行执行下面命令，它们用于后续 Agent 接手。

现成 Agent 命令从 D:\\trackeep-lit 运行：`E:\\Python\\python.exe -m lit.pubmed --plan <计划JSON>`；`-m lit.metadata_batch --preview <检索回执> --pmids <明确PMID列表>`（只预演，具名授权后才加 --apply）；`-m lit.batch_review --batch <题录回执> --decisions <决定JSON>`；`-m lit.fulltext_batch --review <复核回执> --downloads <官方下载凭据>`（只预演，具名授权后才加 --apply）。检索计划编写、相关性判断/决定JSON、官方来源定位和下载仍由 Agent 编排。全文入口依赖已有PDF、下载证据及当前既有PyMuPDF；此次下载脚本含已关闭tab，不是通用下载器。工作区/核对本机全文.py 仅只读核对本批两篇。

旧GUI仍走原有桌面流程，未接这些新校验与入库后复核；本批没有做插件或一个自然语言命令包办全部的产品。当前交付是可复用的分段命令和两篇云端实测，桌面文件闭环仍未完成。

'''
for name in ('HANDOFF.md','阶段日志.md'):
    p=ROOT/name;s=p.read_text(encoding='utf-8-sig');first,rest=s.split('\n',1)
    p.write_text(first+'\n\n'+note+rest.lstrip('\n'),encoding='utf-8')
p=ROOT/'HANDOFF.md';s=p.read_text(encoding='utf-8')
for f in [ROOT/'工作区/核对本机全文.py',ROOT/'工作区/补充桌面核对交接.py',*folder.glob('desktop*.json')]:
    line='- '+str(f)
    if line not in s:s+=line+'\n'
p.write_text(s,encoding='utf-8')
