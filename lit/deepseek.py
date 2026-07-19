# -*- coding: utf-8 -*-
"""DeepSeek V4 Flash 语义复筛（6b）：对检索出的 new 候选，按分类判据逐篇判"主体是否相关"。

两步：① efetch 抓 new 的标题+摘要（引擎只吐 hasAbstract 布尔、不吐正文；180 PMID/块）
      ② 喂 DeepSeek Flash 分批判 keep/drop + ≤20 字理由（20 篇/批，逐批合并）。
6b-1 只出判决供 PI 预览（advisory），**不拦截导入**；6b-2 才门控真写。
6b-3 分批：单批输出装不下（一年几百篇 → ~80 篇后 JSON 截断 → 整体崩）的根因治掉——
      切小批逐批判、单批失败保守保留不崩、全批皆失败才报错（见 classify）。

安全：`DEEPSEEK_TOKEN` 从进程环境读（Windows 用户环境变量登录时已注入进程）；
只进请求头，**绝不打印 / 记录 token 值**。走 Anthropic 兼容端点（与验证脚本同范式）。
"""
import json
import os
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

_EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
_DS_URL = "https://api.deepseek.com/anthropic/v1/messages"
_DS_MODEL = "deepseek-v4-flash"
_ABSTRACT_CAP = 1200          # 每篇摘要截断长度（控 token）
_EFETCH_CHUNK = 180           # efetch 分块：每块 PMID 数（对齐引擎 180/块，控 URL 长度）
_BATCH_SIZE = 20              # DeepSeek 判决分批：每批篇数（~20 判决远小于 max_tokens=4096，不截断）


def classify(items, criteria, *, timeout=180, progress=None):
    """对 items（含 pmid/title 的 new 候选）按 criteria 判相关性。

    返回 {pmid: {"keep": bool, "reason": str}}。items 空 / 无 pmid → 空 dict。

    分批判决（6b-3）：efetch 抓全部摘要后，按 _BATCH_SIZE 篇/批逐批调 DeepSeek，
    合并各批 {pmid: {keep,reason}}。单批失败（网络 / 解析 / RuntimeError）重试 1 次，
    仍失败 → 该批 pmid 标 keep=True + 透明理由「本批复筛失败·默认保留」（保守：不误滤）
    + 继续下一批，**不让整体崩**。全批皆失败（每一批都失败）才抛 RuntimeError，避免
    「全部默认保留」却无声、误导 PI 以为都判过了。顺序执行（不并发，尊重限流 + 确定性）。

    progress：可选回调，每判完一批（含失败兜底）调 progress(done_batches, total_batches)。
    """
    items = [it for it in (items or []) if it.get("pmid")]
    if not items:
        return {}
    abstracts = _fetch_abstracts([str(it["pmid"]) for it in items], timeout=timeout)
    total = (len(items) + _BATCH_SIZE - 1) // _BATCH_SIZE
    verdicts = {}
    failed_batches = 0
    last_err = None
    for i in range(total):
        batch = items[i * _BATCH_SIZE:(i + 1) * _BATCH_SIZE]
        done = False
        for _attempt in range(2):            # 初试 + 重试 1 次（规格缺陷类最多一次重试）
            try:
                verdicts.update(_deepseek_judge(batch, abstracts, criteria, timeout=timeout))
                done = True
                break
            except Exception as e:           # 网络 / 解析 / RuntimeError 统一兜（不吞 BaseException）
                last_err = e
        if not done:
            # 单批两次都失败：保守保留（宁多看不错杀）+ 透明理由，继续下一批
            for it in batch:
                pmid = str(it.get("pmid") or "")
                if pmid:
                    verdicts[pmid] = {"keep": True, "reason": "本批复筛失败·默认保留"}
            failed_batches += 1
        if progress is not None:
            progress(i + 1, total)
    if total > 0 and failed_batches == total:
        # 全批皆失败：不无声默认保留，让人话报错冒泡到 UI（末次原因不含 token：见 _deepseek_judge）
        raise RuntimeError("AI 复筛全部失败：%s" % last_err)
    return verdicts


def _fetch_abstracts(pmids, *, timeout):
    """efetch 抓每个 PMID 的摘要正文 → {pmid: abstract}。按 _EFETCH_CHUNK 个 PMID 一块
    分次请求（对齐引擎 180/块、控 URL 长度），合并结果。任一块网络失败抛 URLError。
    """
    out = {}
    for start in range(0, len(pmids), _EFETCH_CHUNK):
        chunk = pmids[start:start + _EFETCH_CHUNK]
        q = urllib.parse.urlencode({"db": "pubmed", "retmode": "xml",
                                    "id": ",".join(chunk), "tool": "trackeep-lit"})
        req = urllib.request.Request(_EUTILS + "/efetch.fcgi?" + q)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            xml = resp.read()
        root = ET.fromstring(xml)
        for art in root.findall(".//PubmedArticle"):
            pmid = art.findtext(".//PMID") or ""
            parts = [("".join(a.itertext())).strip()
                     for a in art.findall(".//Abstract/AbstractText")]
            out[pmid] = " ".join(p for p in parts if p)[:_ABSTRACT_CAP]
    return out


def _deepseek_judge(items, abstracts, criteria, *, timeout):
    """构 DeepSeek Flash 请求，逐篇判 keep/drop，映射回 pmid。"""
    token = os.environ.get("DEEPSEEK_TOKEN")
    if not token:
        raise RuntimeError(
            "未找到 DEEPSEEK_TOKEN 环境变量（Windows 用户环境变量）——无法调 DeepSeek。")
    blocks, idx2pmid = [], {}
    for i, it in enumerate(items, 1):
        pmid = str(it["pmid"])
        idx2pmid[i] = pmid
        ab = abstracts.get(pmid) or "（无摘要）"
        blocks.append("[%d] 标题: %s\n摘要: %s" % (i, it.get("title", ""), ab))
    prompt = (
        "你是文献相关性筛选器。下面 %d 篇文献已用关键词粗筛命中，逐篇判断："
        "研究**主体**是否满足以下判据 —— %s。"
        "只看研究主体，不看是否顺带提及。返回**纯 JSON 数组**，每篇一个对象 "
        "{\"n\":序号(int),\"keep\":true或false,\"reason\":\"≤20字中文理由\"}，"
        "数组之外不要输出任何文字。\n\n%s"
        % (len(items), criteria, "\n\n".join(blocks)))
    body = json.dumps({"model": _DS_MODEL, "max_tokens": 4096,
                       "messages": [{"role": "user", "content": prompt}]},
                      ensure_ascii=True).encode("utf-8")
    req = urllib.request.Request(
        _DS_URL, data=body, method="POST",
        headers={"Content-Type": "application/json", "x-api-key": token,
                 "anthropic-version": "2023-06-01"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", "replace")
    # 顶层非 JSON（如网关 HTML 错误页）→ 转人话 RuntimeError，不抛原始 JSONDecodeError
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        raise RuntimeError("DeepSeek 返回无法解析（顶层非 JSON，疑似网关错误页）。") from None
    text = "".join(b.get("text", "") for b in data.get("content", [])
                   if b.get("type") == "text")
    m = re.search(r"\[.*\]", text, re.S)
    if not m:
        raise RuntimeError("DeepSeek 返回无法解析（未见 JSON 数组）。")
    # 正则命中的 [...] 内部非法 JSON → 同上转人话 RuntimeError
    try:
        parsed = json.loads(m.group(0))
    except json.JSONDecodeError:
        raise RuntimeError("DeepSeek 返回无法解析（JSON 数组内部格式非法）。") from None
    verdicts = {}
    for v in parsed:
        pmid = idx2pmid.get(v.get("n"))
        if pmid:
            # keep 类型归一：bool 照原值；其它（字符串等）仅显式 "false" 才滤，
            # 歧义值保守留——advisory 语义下宁多看不错杀（旧 bool("false")=True 误留）
            k = v.get("keep")
            keep = k if isinstance(k, bool) else str(k).strip().lower() != "false"
            verdicts[pmid] = {"keep": keep,
                              "reason": (v.get("reason") or "")[:40]}
    return verdicts
