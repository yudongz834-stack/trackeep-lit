"""本轮第一次迁移的历史记录；后续已在原仓修复，不可再次执行覆盖。"""
from pathlib import Path

raise SystemExit('迁移已完成；当前正本是 D:/dev/trackeep-scripts/zotero-import.ps1，禁止重放旧迁移')

source = Path(r'C:\Users\yudon\AppData\Local\Temp\trackeep-literature-engine\zotero-import.ps1')
target = Path(r'D:\dev\trackeep-scripts\zotero-import.ps1')
s = source.read_text(encoding='utf-8-sig')
s = s.replace("[string]$CollectionKey = '',", "[string]$CollectionKey = '',\n  [string]$ExpectedRecordsPath = '',")
s = s.replace("if (-not $StateDir) { $StateDir = Join-Path $env:LOCALAPPDATA 'Trackeep\\Literature' }; $McDir = Join-Path $StateDir '.trackeep'", "if (-not $StateDir) { $StateDir = Join-Path $PSScriptRoot '..' }; $McDir = Join-Path $StateDir '.trackeep'")
s = s.replace('dupSrc = "$($_.DupSrc)"', 'dupSrc = "$($_.DupSrc)"; zoteroKey = "$($_.ZoteroKey)"')
s = s.replace("function Norm-Title($s)", "function Norm-Doi($s) { (([string]$s).Trim() -replace '^(?i)(https?://(dx\\.)?doi\\.org/|doi:\\s*)', '').ToLowerInvariant() }\nfunction Norm-Title($s)")
s = s.replace("Pmid = $pmid; Doi = $doi; Title = $title;", "Pmid = $pmid; Doi = $doi; Title = $title; NlmId = (Txt $pa 'MedlineCitation/MedlineJournalInfo/NlmUniqueID'); ZoteroKey = '';\n      DateEvidence = (@($pa.SelectNodes('MedlineCitation/Article/ArticleDate | MedlineCitation/Article/Journal/JournalIssue/PubDate') | ForEach-Object { $_.OuterXml }) -join \"`n\");")
marker = '# --- 3) 去重锚'
guard = '''# 指定 PMID 的真实写入必须与调用方已验证题录逐字段一致。
if ($ArticlePmids -and $Execute -and -not $ExpectedRecordsPath) { throw '精确导入缺少已核题录，禁止写入' }
if ($ExpectedRecordsPath) {
  $expected = @(Get-Content -LiteralPath $ExpectedRecordsPath -Raw -Encoding UTF8 | ConvertFrom-Json)
  if ($expected.Count -ne $cands.Count -or @($expected.pmid | Select-Object -Unique).Count -ne $expected.Count) { throw '已核题录集合不一致' }
  foreach ($c in $cands) {
    $pin = @($expected | Where-Object { $_.pmid -ceq $c.Pmid })
    if ($pin.Count -ne 1 -or -not $pin[0].title -or -not $pin[0].nlm_id -or
        $pin[0].title -cne $c.Title -or (Norm-Doi $pin[0].doi) -cne (Norm-Doi $c.Doi) -or $pin[0].nlm_id -cne $c.NlmId) { throw 'PMID/DOI/标题/期刊身份与已核题录不一致，禁止写入' }
  }
}

'''
s = s.replace(marker, guard+marker)
s = s.replace("$live = @(Zot-GetAll '/items?includeTrashed=1')", """$live = @(Zot-GetAll '/items?includeTrashed=1')
foreach ($c in $cands) {
  foreach ($it in $live) {
    $d = Norm-Doi $it.data.DOI; $p = ''
    if ("$($it.data.extra)" -match '(?im)^PMID:\\s*(\\d+)') { $p = $Matches[1] }
    if (($d -and $c.Doi -and $d -eq (Norm-Doi $c.Doi)) -or ($p -and $p -eq $c.Pmid)) {
      if (($d -and $c.Doi -and $d -ne (Norm-Doi $c.Doi)) -or ($p -and $p -ne $c.Pmid)) { throw '已有条目标识冲突，禁止导入或自动合并' }
    }
  }
}""")
s = s.replace('$d = "$($it.data.DOI)".ToLower().Trim()', '$d = Norm-Doi $it.data.DOI')
s = s.replace("$_.key -eq $CollectionKey }).Count", "$_.key -eq $CollectionKey -and $_.data.name -ceq $Journal }).Count")
s = s.replace('extra = ("PMID: {0}" -f $c.Pmid)', 'extra = ("PMID: {0}`nNLM ID: {1}`nPubMed date sources: {2}" -f $c.Pmid, $c.NlmId, $c.DateEvidence); url = ("https://pubmed.ncbi.nlm.nih.gov/{0}/" -f $c.Pmid)')
s = s.replace('foreach ($k in $rj.successful.PSObject.Properties.Name) { $confirmed += $slice[[int]$k] }', '''foreach ($k in $rj.successful.PSObject.Properties.Name) {
    if ($k -notmatch '^\\d+$' -or [int]$k -ge $slice.Count -or $rj.successful.$k.key -notmatch '^[A-Z0-9]{8}$') { throw '写入回执异常，须重新读库，不可盲重试' }
    $slice[[int]$k].ZoteroKey = $rj.successful.$k.key; $confirmed += $slice[[int]$k]
  }
  if (@($rj.successful.PSObject.Properties).Count + @($rj.failed.PSObject.Properties).Count -ne $slice.Count) { throw '写入回执数量不齐，须重新读库' }''')
target.write_text(s, encoding='utf-8')
