"""记录本批全文结果，保留历史证据及交付清单。"""
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[1]
stage = '''## 当前活跃状态（2026-10-03 · 两篇官方全文续接完成）

具名授权与边界见 [.project/fulltext-task.md](.project/fulltext-task.md)。端到端计数：PubMed 命中2、题录新建2、入库后保留2／排除0／待核0、官方全文2、附件新建2；同批再运行复用2、新建0、失败0。PMID42420446 → WD9F8D8E → XT8K8X34；PMID42816625 → IU8CWQD2 → JBKB7SJZ。均为37页原始主文PDF，第一篇来自现行PMC官方云主文地址，第二篇来自Nature官方PDF地址。服务器文件实际读回与本地原件SHA256一致，父项内容、标签和目录保持原样。

创建证据：日志/fulltext-batches/20261003-151747-7ee932e7/report.json；实际重跑：20261003-152244-de96ea4a/report.json。官方下载及身份：日志/fulltext-validation/official-downloads.json。独立离线40探针和现有6测试通过，关闭DOI前缀误认、首页参考文献误认、锁竞争无回执三缺陷；实际独立验收见 independent-live-acceptance.json。最终本地全文6＋题录15＋检索38＋smoke88＋GUI29＋对抗70及地图检查通过，见该目录 final-verification.json。仅本地提交，未运行远端CI或发布。

失败与边界：初次静态出版社请求返回200但为HTML，已拒绝；后从官方PMC云和正常浏览器同源请求取得真PDF，不绕访问控制、不调用退休oa.fcgi、不把XML充PDF。原件未修改，临时浏览器tab已关闭。排除/待核不能下载或挂接已用独立离线反例验证；本批没有真实排除项及旧附件/笔记，不能声称实库清理或旧资料保护已验证。独立实际验收复算执行回执及本地原件，云端读回由执行路径完成；没有确认桌面同步。通用自动来源发现、存量元数据更新、持续增量、插件封装和旧GUI接线仍未完成。

复用Zotero既有授权及官方附件上传接口，题录仍由原PowerShell引擎负责；此轮未改外部引擎。工作区下载脚本包含本次已关闭tab，保留作证据，不能原样作为通用下载器重跑。全文原件和运行日志留在项目，受Git忽略；不是代码提交中的附件副本。

'''
p = root/'阶段日志.md'
old = p.read_text(encoding='utf-8-sig')
old = old.replace('## 当前活跃状态（2026-10-03 · 少量题录导入与入库后复核完成）', '## 本日上一阶段记录（少量题录导入与入库后复核；全文未启动为当时状态）', 1)
if '## 当前活跃状态（2026-10-03 · 两篇官方全文续接完成）' not in old:
    p.write_text(old.replace('# Trackeep Lit · 阶段日志\n\n', '# Trackeep Lit · 阶段日志\n\n'+stage, 1), encoding='utf-8')

p = root/'HANDOFF.md'
old = p.read_text(encoding='utf-8-sig')
paths = {line[2:] for line in old.splitlines() if line.startswith('- D:\\')}
for args in (['diff','--name-only','a96d8f6'], ['ls-files','--others','--exclude-standard']):
    raw = subprocess.check_output(['git','-c','core.quotepath=false',*args],cwd=root).decode('utf-8')
    paths.update(str(root/name) for name in raw.splitlines() if (root/name).is_file())
for folder in ('日志/fulltext-validation','日志/fulltext-batches','全文'):
    paths.update(str(f) for f in (root/folder).rglob('*') if f.is_file())
head = '''# Trackeep Literature 当前接手状态

2026-10-03：本批两篇已完成核验检索、题录导入、入库后复核及官方全文挂接。检索2 → 题录新增2 → 保留2／排除0／待核0 → 官方PDF2 → 附件新增2；题录和附件分别真实重跑，均新增0。

PMID42420446：父项WD9F8D8E，附件XT8K8X34；PMID42816625：父项IU8CWQD2，附件JBKB7SJZ。两份均37页，云端文件读回SHA256等于原件，父项内容/标签/目录保持不变。官方下载路径：第一篇PMC现行云主文、第二篇Nature官网。原件在全文目录。

正式路径 D:\\trackeep-lit，分支 codex/pubmed-rules；原题录引擎唯一正身 D:\\dev\\trackeep-scripts\\zotero-import.ps1，本全文阶段未改动。唯一筛选规范为 规则/PubMed检索规范_v1.0_20261003.md；具名授权为 .project/metadata-trial.md 与 .project/fulltext-task.md。旧GUI未接新护栏，通用自动下载、存量更新、增量追踪及插件未完成。

全文创建：日志/fulltext-batches/20261003-151747-7ee932e7/report.json；重跑：20261003-152244-de96ea4a/report.json。独立40探针及实际验收见 日志/fulltext-validation/independent-review.json、independent-live-acceptance.json。本地6＋15＋38＋88＋29＋70项和地图检查通过，见 final-verification.json；未运行远端CI、未发布。完整前序证据与失败史见阶段日志。

本批无真实排除项及原有附件笔记，相关拦截/旧资料保护仅合成验证。独立实际复核依执行回执核云端读回并独立解析本地PDF，没有确认桌面同步。初次静态下载HTML被拒，旧oa.fcgi未调用。既往PMID4误建仍在回收站，本轮未处理；题录阶段首次只读预演失败根因仍未知。旧隔离全管道原型仍保留，不是交付入口。下载脚本引用已关闭的临时tab，仅作此次运行记录。

## 本轮及前序产出清单

'''
p.write_text(head+'\n'.join('- '+s for s in sorted(paths))+'\n',encoding='utf-8')
