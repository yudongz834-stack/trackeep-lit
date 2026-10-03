// 历史档案：原文保留（含旧品牌与历史路径，勿改史实）；批B 2026-10-03 归档注记
// ⚠️ 已过时（2026-07-24 去枢纽战役）：所属机制已废除，勿运行；留档待删由 PI 裁决
// zotero-findpdf-sweep.js —— 由 Actions&Tags「启动」规则加载执行（Zotero 桌面内 JS）。
// 作用：全库扫一遍，给「缺 PDF 且未标记过」的条目自动找可用 PDF（= 批量 Find Available PDF）。
//   找到的挂上；找不到的打 `_no-oa-pdf` 标记 → 下次启动跳过、不重复试（避免每次开机卡）。
//   结果写 .mecha/zotero-findpdf-log.json 供 Mecha 读取回报。
// 仅找 OA（本机无机构账号）；纯 Zotero API，不碰外部。运行上下文：Zotero、window 在作用域内。

const lib = Zotero.Libraries.userLibraryID;

// 1. 取全库非附件条目
const search = new Zotero.Search();
search.libraryID = lib;
search.addCondition('itemType', 'isNot', 'attachment');
const ids = await search.search();
const items = Zotero.Items.get(ids).filter(function (i) { return i.isRegularItem(); });

// 2. 挑「没 PDF 且没被标记过」的
const need = items.filter(function (it) {
  if (it.hasTag('_no-oa-pdf')) return false;
  const atts = Zotero.Items.get(it.getAttachments());
  return !atts.some(function (a) { return a.attachmentContentType === 'application/pdf'; });
});

const checked = need.length;

// 3. 批量找 PDF
if (checked > 0) {
  await Zotero.Attachments.addAvailablePDFs(need);
}

// 4. 统计 + 给找不到的打标记（下次跳过）
let found = 0;
for (const it of need) {
  const atts = Zotero.Items.get(it.getAttachments());
  if (atts.some(function (a) { return a.attachmentContentType === 'application/pdf'; })) {
    found++;
  } else {
    it.addTag('_no-oa-pdf');
    await it.saveTx();
  }
}

// 5. 写结果日志（best-effort）
try {
  const log = {
    time: (new Date()).toISOString(),
    checked: checked,
    found: found,
    stillMissing: checked - found
  };
  await Zotero.File.putContentsAsync(String.raw`D:\BaiduSyncdisk\Mecha-Core\.mecha\zotero-findpdf-log.json`, JSON.stringify(log));
} catch (e) { /* 日志写失败不影响找 PDF */ }
