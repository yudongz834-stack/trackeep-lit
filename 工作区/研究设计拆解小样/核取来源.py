"""只读取公开官方来源，保存本轮拆解的可复核原件；不访问文献库。"""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import io
import json
import urllib.request
import zipfile

root = Path(__file__).resolve().parent
sources = root / "来源"
sources.mkdir(exist_ok=True)
receipts = []

def get(url, name, kind="file"):
    target = sources / name
    try:
        with urllib.request.urlopen(url, timeout=35) as response:
            data = response.read()
            mime = response.headers.get("Content-Type", "")
        if kind == "zip":
            archive = zipfile.ZipFile(io.BytesIO(data))
            selected = [n for n in archive.namelist() if n.lower().endswith("_appendix.pdf")]
            if len(selected) != 1:
                raise ValueError("附件文件不能唯一识别")
            data = archive.read(selected[0])
        if target.suffix == ".pdf" and not data.startswith(b"%PDF"):
            raise ValueError("响应不是PDF")
        if target.suffix == ".xml" and b"<body>" not in data:
            raise ValueError("响应缺少全文正文")
        target.write_bytes(data)
        receipts.append({"url": url, "file": str(target), "status": "saved",
                         "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                         "response_content_type": mime})
    except Exception as exc:
        receipts.append({"url": url, "file": str(target), "status": "unavailable",
                         "reason": type(exc).__name__ + ": " + str(exc)})
    print(name, receipts[-1]["status"], flush=True)

get("https://www.ebi.ac.uk/europepmc/webservices/rest/PMC9006787/fullTextXML", "Moreira2022全文.xml")
get("https://www.ebi.ac.uk/europepmc/webservices/rest/PMC9006787/supplementaryFiles", "Moreira2022补充.pdf", "zip")
get("https://mediacenteratypon.nejmgroup-production.org/NEJMoa2201688.pdf", "Magen2022全文.pdf")
get("https://mediacenteratypon.nejmgroup-production.org/NEJMoa2201570.pdf", "BarOn2022全文.pdf")
get("https://www.ebi.ac.uk/europepmc/webservices/rest/PMC9020581/supplementaryFiles", "Magen2022补充.pdf", "zip")
(root / "来源回执.json").write_text(json.dumps({"checked_at": datetime.now(timezone.utc).isoformat(),
    "purpose": "官方全文拆解小样；不作临床决策", "sources": receipts}, ensure_ascii=False, indent=2), encoding="utf-8")
