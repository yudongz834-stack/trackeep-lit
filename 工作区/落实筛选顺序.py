"""更新唯一规范和示例，保留此前实测的历史边界。"""
import json
from pathlib import Path
root = Path(__file__).resolve().parents[1]
p = root / '规则/PubMed检索规范_v1.0_20261003.md'
s = p.read_text(encoding='utf-8')
s = s.replace('**没有统一的“宽检索后入库精筛”默认策略**。先声明范围和筛选位置，再执行只读预览；', '**PI 已定顺序：自然语言范围 → 核验 PubMed 检索及题录 → Zotero 题录导入 → Agent 入库后相关性与重复复核 → 可逆清理 → 仅为保留项获取全文**。明确、无歧义的范围先写进检索式，不确定判断留到入库后；')
s = s.replace('用户没选筛选位置时记录 `undecided`，只做预览。', '省略筛选位置时采用 `after-import`；显式 `undecided` 仍表示该计划待定，只做预览，不能自动批准导入。缺摘要或模型未作判断保留待核，不自动排除。')
s = s.replace('旧引擎修复保留在隔离分支，导入/PDF/插件工作暂停。', '题录导入正通过原 PowerShell 引擎补齐精确身份护栏；少量实测走 `lit.metadata_batch`，仍须独立复核。全文和插件封装不在本阶段。')
s = s.replace('筛选位置仍为 `undecided`。', '筛选位置采用已定的 `after-import`。')
s = s.replace('仍待定的是筛选位置：采用宽检索后筛、前端过滤后筛，还是分工模式；继续记录 `undecided`，不因日期默认已定而暗中决定筛选策略。', '筛选顺序已按本轮 PI 决定落实：前端表达明确范围，入库后 Agent 判断剩余相关性与重复，清理可逆且不永久删除。已有条目的附件、笔记、标签、目录不覆盖；身份或相关性不确定保留待核。撤稿原文与通知分别留出处，从有效候选中剔除。检索、题录导入、复核、全文分别计数和报告，不能将题录成功称为全文完成。')
p.write_text(s, encoding='utf-8')
for name in ('nature-month.json', 'stem-cell-topic.json'):
    p = root / '规则/示例' / name
    obj = json.loads(p.read_text(encoding='utf-8-sig'))
    obj['screening_location'] = 'after-import'
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
