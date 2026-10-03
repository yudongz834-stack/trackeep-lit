// zotero-findpdf-sweep.js —— 由 Actions&Tags「启动」规则加载执行（Zotero 桌面内 JS）。
// 作用：全库扫一遍，给「缺 PDF 且未标记过」的条目自动找可用 PDF（= 批量 Find Available PDF）。
//   找到的挂上；找不到的打 `_no-oa-pdf-YYYY-MM` 标记 → 3 个月内跳过、过期自动重试（避免每次开机卡，又不漏掉 embargo 转 OA 的）。
//   结果写 .trackeep/zotero-findpdf-log.json 供 Trackeep 读取回报。
// 仅找 OA（本机无机构账号）；纯 Zotero API，不碰外部。运行上下文：Zotero、window 在作用域内。

const lib = Zotero.Libraries.userLibraryID;

// 1. 取全库非附件条目
const search = new Zotero.Search();
search.libraryID = lib;
search.addCondition('itemType', 'isNot', 'attachment');
const ids = await search.search();
const items = Zotero.Items.get(ids).filter(function (i) { return i.isRegularItem(); });

// 2. 挑「没 PDF」的；_no-oa-pdf* 标记带 TTL（3 个月），过期或裸标记先清掉再纳入重试
const now = new Date();
const ym = now.getFullYear() + '-' + String(now.getMonth() + 1).padStart(2, '0');
const nowYear = now.getFullYear();
const nowMonth = now.getMonth() + 1;

// 读条目上的 _no-oa-pdf* 标记：返回 { bare:true, name }（裸标记）/ { year, month, name }（带年月）/ null
function noOaInfo(it) {
  for (const t of it.getTags()) {
    const name = t.tag;
    if (name === '_no-oa-pdf') return { bare: true, name: name };
    const m = name && name.match(/^_no-oa-pdf-(\d{4})-(\d{2})$/);
    if (m) return { year: +m[1], month: +m[2], name: name };
  }
  return null;
}
// 裸标记（历史遗留）一律当过期；带年月的距今 ≥ 3 个月即过期
function isExpired(info) {
  if (!info) return false;
  if (info.bare) return true;
  return (nowYear - info.year) * 12 + (nowMonth - info.month) >= 3;
}

const need = [];
for (const it of items) {
  const atts = Zotero.Items.get(it.getAttachments());
  if (atts.some(function (a) { return a.attachmentContentType === 'application/pdf'; })) continue;  // 已有 PDF
  const info = noOaInfo(it);
  if (!info || isExpired(info)) {                 // 新条目，或标记过期 → 纳入重试
    if (info) {                                    // 过期 / 裸标记先清掉，避免重试后又被旧标记跳过
      it.removeTag(info.name);
      await it.saveTx();
    }
    need.push(it);
  }
  // 有未过期标记 → 跳过（TTL 内不重试）
}

const checked = need.length;

// 3. 批量找 PDF
if (checked > 0) {
  await Zotero.Attachments.addAvailablePDFs(need);
}

// 4. 统计 + 给找不到的打标记（带年月，TTL 后重试）
let found = 0;
const missing = [];
for (const it of need) {
  const atts = Zotero.Items.get(it.getAttachments());
  if (atts.some(function (a) { return a.attachmentContentType === 'application/pdf'; })) {
    found++;
  } else {
    it.addTag('_no-oa-pdf-' + ym);
    await it.saveTx();
    missing.push({ key: it.key, title: it.getField('title') });
  }
}

// 5. 写结果日志（best-effort）
try {
  const log = {
    time: (new Date()).toISOString(),
    checked: checked,
    found: found,
    stillMissing: checked - found,
    missing: missing
  };
  await Zotero.File.putContentsAsync(String.raw`D:\dev\.trackeep\zotero-findpdf-log.json`, JSON.stringify(log));
} catch (e) { /* 日志写失败不影响找 PDF */ }
