# -*- coding: utf-8 -*-
"""后端桥：spawn zotero-import.ps1，从 stdout 取 `MECHA_JSON ` 前缀行并 json.loads。

Slice 1 只用 dry-run（绝不加 -Execute）——只读 PubMed + 遍历 Zotero 去重预览，
不写 Zotero、不动台账。引擎实测一次 -ReldateDays 60 约 30–60 秒（拉 PubMed + 全库去重）。
"""
import json
import subprocess

from lit import config

_PREFIX = "MECHA_JSON "


def run_search(journal, *, reldate_days=None, month=None, year=None,
               include_editorial=False, include_letter=False,
               topic_filter=None, timeout=180) -> dict:
    """spawn 引擎 dry-run，返回 MECHA_JSON 解析出的 dict。

    检索窗三选一：reldate_days(int) / month("YYYY-MM") / year(int)。引擎自身会校验
    「须且只须指定一个」；这里先在 Python 侧挡一道，给出更清晰的错误。

    末尾固定加 `-EmitJson`，**绝不加 `-Execute`**（Slice 1 禁真写）。
    """
    argv = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
            "-File", str(config.ENGINE_PATH), "-Journal", str(journal)]

    modes = [reldate_days is not None, bool(month), year is not None]
    if sum(modes) != 1:
        raise ValueError("检索窗须且只须指定 reldate_days / month / year 之一")
    if reldate_days is not None:
        argv += ["-ReldateDays", str(int(reldate_days))]
    elif month:
        argv += ["-Month", str(month)]
    else:
        argv += ["-Year", str(int(year))]

    if include_editorial:
        argv.append("-IncludeEditorial")
    if include_letter:
        argv.append("-IncludeLetter")
    if topic_filter:
        argv += ["-TopicFilter", str(topic_filter)]
    argv.append("-EmitJson")   # 固定加；绝不加 -Execute

    cp = subprocess.run(argv, capture_output=True, text=True,
                        encoding="utf-8", errors="replace", timeout=timeout)
    if cp.returncode != 0:
        raise RuntimeError(
            f"引擎退出码 {cp.returncode}\n--- stderr ---\n{cp.stderr.strip()[-2000:]}")

    # 解析：取以 `MECHA_JSON ` 开头的那行（PowerShell stdout 可能有 BOM / 混合换行，
    # 逐行 strip + 去 BOM 再判前缀）。
    line = None
    for ln in cp.stdout.splitlines():
        s = ln.strip().lstrip("﻿")
        if s.startswith(_PREFIX):
            line = s
            break
    if line is None:
        tail = cp.stdout.strip()[-500:]
        raise RuntimeError(f"stdout 未找到 MECHA_JSON 行。\n--- stdout 末尾 ---\n{tail}")
    return json.loads(line[len(_PREFIX):])
