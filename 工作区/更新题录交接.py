"""按本阶段实际文件生成最终交接清单，不复制规则正文。"""
from pathlib import Path
import subprocess
root=Path(__file__).resolve().parents[1]
paths=set()
for args in (['diff','--name-only'], ['ls-files','--others','--exclude-standard']):
    out=subprocess.check_output(['git','-c','core.quotepath=false',*args],cwd=root).decode('utf-8')
    paths.update(root/p for p in out.splitlines() if p)
for folder in ('日志/metadata-validation','日志/metadata-batches','日志/metadata-reviews'):
    paths.update(p for p in (root/folder).rglob('*') if p.is_file())
paths.update([root/'日志/pubmed-preview/20261003-144356-a9213f2b.json',root/'.trackeep/zotero-import-ledger.json',
              root/'HANDOFF.md',Path(r'D:\dev\trackeep-scripts\zotero-import.ps1')])
text='''# Trackeep Literature 当前接手状态

2026-10-03：本轮少量题录导入与入库后复核完成。通过原 PowerShell 引擎真实新建2篇，读回核对 PMID/DOI/标题/NLM/目录；同批重跑已有2、新增0。复核保留2、排除0、待核0，本次无需清理。全文未启动，获取数0；不做插件封装或全刊批量。

最终路径为 D:\\trackeep-lit，分支 codex/pubmed-rules。原引擎唯一正身 D:\\dev\\trackeep-scripts\\zotero-import.ps1，分支 codex/metadata-import，原版本由 Git 保存；没有另造 Python 题录导入器。当前写台账由原引擎维护在本项目 .trackeep 下，不改旧台账。旧 GUI 尚未接新护栏。旧隔离全管道原型仍保留，包含未解决的全文身份问题，不是本轮交付入口。

本轮授权与样本边界见 .project/metadata-trial.md；筛选顺序和日期口径只有 规则/PubMed检索规范_v1.0_20261003.md 一份正文。过程与失败史见 阶段日志.md。首次 apply 在只读预演失败，未进入 Execute；失败保留，根因未复现仍未知，后续经只读重查才重试。既往 PMID4 误建仍在回收站，本轮未处理。

证据：日志/metadata-batches/20261003-145432-2b6d0965/report.json（创建），20261003-145542-09f4f670/report.json（同批重跑）；日志/metadata-reviews/review-1141862b.json（复核）。独立离线49例及实际验收分别见 日志/metadata-validation/independent-review.json、independent-live-acceptance.json。最终本地15＋38＋88＋29＋70项及地图检查通过，见 final-verification.json；未运行远端CI、未发布。

真实样本没有旧附件或笔记，因此不能声称已实库验证含附件旧条目保护；这一面目前仅有合成测试。存量元数据更新、持续增量、全文及插件仍是后续阶段。

## 本轮产出清单

'''
missing=[str(p) for p in paths if not p.is_file()]
if missing: raise SystemExit('清单文件缺失：'+str(missing))
(root/'HANDOFF.md').write_text(text+''.join('- '+str(p)+'\n' for p in sorted(paths,key=str)),encoding='utf-8')
print(f'交接清单 {len(paths)} 个实际文件')
