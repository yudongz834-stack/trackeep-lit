<#
  import.ps1 — PubMed → Zotero 自动导入器（v1）

  一条命令完成一本刊一个检索窗（-Month 月 / -Year 整年 / -ReldateDays 近 N 天，三选一）：
    1) 检索——清洗查询跑 PubMed esearch：默认只要 article/review 且有摘要(hasabstract)；
       JTO 特例额外保留 editorial（含 Controversy 辩论文，实测被标为 editorial[PT]）。
    2) 取元数据——efetch 拿每篇 DOI / 摘要 / 题录。
    3) 去重——按 DOI（PMID 兜底；无 DOI 者补归一标题）比对【导入台账 + 当前 Zotero 库】，重复跳过。
    4) 台账——每批只记 POST 确认成功的条目写入 .trackeep/zotero-import-ledger.json，后续每批都与它核对
              （根治 Online-Ahead ↔ 正式版的长期重复累积；POST 失败条目不记账、下轮自动重试）。
    5) 导入——新文献 POST 进 Zotero、归入该期刊 collection（仅 -Execute）。

  纪律
    · 默认 dry-run（只读预览，不写 Zotero、不动台账）；加 -Execute 才真导入 + 写台账。
    · 去重锚 = DOI（永久标识，Online-Ahead 与正式版一致），PMID 兜底；不靠摘要。
    · PubMed E-utilities 免 key；Zotero API key 仅用于请求头、不回显。

  用法
    pwsh -NoProfile -File zotero\import.ps1 -Journal "Ann Thorac Surg" -Month "2025-10"           # 预览
    pwsh -NoProfile -File zotero\import.ps1 -Journal "Ann Thorac Surg" -Month "2025-10" -Execute   # 真导入
    pwsh -NoProfile -File zotero\import.ps1 -Journal "J Thorac Oncol" -Year 2024                    # 整年（按刊期 DP）
    pwsh -NoProfile -File zotero\import.ps1 -Journal "J Thorac Oncol" -ReldateDays 30               # 近30天增量（按收录 edat）
    # -Month / -Year / -ReldateDays 三选一，恰好指定一个检索窗
    -TopicFilter "lung[tiab] OR esophag*[tiab] ..."   # 综合/AI/基础刊用胸部主题过滤；胸外/公卫刊留空=全收
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory)][string]$Journal,
  [string]$Month = '',
  [int]$Year = 0,
  [int]$ReldateDays = 0,
  [string]$TopicFilter,
  [switch]$IncludeEditorial,
  [switch]$IncludeLetter,
  [switch]$EmitJson,
  [switch]$Execute,
  [string]$ExcludePmids = '',
  [string]$ArticlePmids = '',
  [string]$CollectionKey = '',
  [string]$ExpectedRecordsPath = '',
  [string]$StateDir = $env:TRACKEEP_STATE
)
$ErrorActionPreference = 'Stop'
# 同用户的 GUI 与 Agent 共享写锁，查重到写入之间不可并发。
$writeMutex = $null
if ($Execute) {
  $writeMutex = [Threading.Mutex]::new($false, 'Local\TrackeepLiteratureImport')
  try { $locked = $writeMutex.WaitOne(0) } catch [Threading.AbandonedMutexException] { $locked = $true }
  if (-not $locked) { throw '另一个导入正在执行，请稍后重试' }
}
try {
try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 } catch {}
# 模式校验：-Month / -Year / -ReldateDays 三者须且只须指定一个
$modeCount = 0
if ($Month) { $modeCount++ }
if ($Year -gt 0) { $modeCount++ }
if ($ReldateDays -gt 0) { $modeCount++ }
if ($ArticlePmids) { $modeCount++ }; if ($modeCount -ne 1) { throw '须且只须指定 -Month / -Year / -ReldateDays 之一' }
if ($Month) {
  if ($Month -notmatch '^(\d{4})-(\d{2})$') { throw '-Month 须 YYYY-MM，如 2025-10' }
  $mY = [int]$Matches[1]; $mM = [int]$Matches[2]; $lastDay = [DateTime]::DaysInMonth($mY, $mM)
}

# --- secret ---
$EnvFile = Join-Path $env:USERPROFILE '.config\trackeep\secrets\zotero.env'
if (-not (Test-Path -LiteralPath $EnvFile)) { throw "缺 secret 文件：$EnvFile" }
$cfg = @{}
foreach ($l in (Get-Content -LiteralPath $EnvFile)) {
  $t = $l.Trim(); if (-not $t -or $t.StartsWith('#')) { continue }
  $i = $t.IndexOf('='); if ($i -lt 1) { continue }
  $cfg[$t.Substring(0, $i).Trim()] = $t.Substring($i + 1).Trim().Trim(' ', '<', '>', '"', "'")
}
$uid = $cfg['ZOTERO_USER_ID']; $key = $cfg['ZOTERO_API_KEY']
if (-not $uid -or -not $key) { throw 'zotero.env 缺 ZOTERO_USER_ID / ZOTERO_API_KEY' }
$zBase = "https://api.zotero.org/users/$uid"
$zH = @{ 'Zotero-API-Version' = '3'; 'Zotero-API-Key' = $key }

if (-not $StateDir) { $StateDir = Join-Path $PSScriptRoot '..\..' }; $McDir = Join-Path $StateDir '.trackeep'
if ($Execute -and -not (Test-Path $McDir)) { New-Item -ItemType Directory -Path $McDir -Force | Out-Null }
$LedgerPath = Join-Path $McDir 'zotero-import-ledger.json'
$OverridesPath = Join-Path $McDir 'journal-overrides.json'
$ov = $null
if (Test-Path $OverridesPath) { try { $ov = (Get-Content $OverridesPath -Raw -Encoding UTF8).TrimStart([char]0xFEFF) | ConvertFrom-Json } catch { $ov = $null } }
$jov = if ($ov -and ($ov.PSObject.Properties.Name -contains $Journal)) { $ov.$Journal } else { $null }
$wantEditorial = [bool]$IncludeEditorial -or [bool]($jov -and $jov.includeEditorial)
$wantLetter = [bool]$IncludeLetter -or [bool]($jov -and $jov.includeLetter)
if ($jov -and $jov.topicFilter -and -not $TopicFilter) { $TopicFilter = "$($jov.topicFilter)" }

# --- helpers ---
function Get-Utf8($r) { [System.Text.Encoding]::UTF8.GetString($r.RawContentStream.ToArray()) }
function Write-ResultJson($obj) { if ($EmitJson) { Write-Host ('TRACKEEP_JSON ' + (ConvertTo-Json -InputObject $obj -Depth 8 -Compress)) } }
function Cand-Items($lst) { @($lst | ForEach-Object { [ordered]@{ pmid = "$($_.Pmid)"; doi = "$($_.Doi)"; title = "$($_.Title)"; type = "$($_.Type)"; hasAbstract = [bool]$_.HasAbs; status = "$($_.Status)"; dedupBy = "$($_.DedupBy)"; dupSrc = "$($_.DupSrc)"; zoteroKey = "$($_.ZoteroKey)" } }) }
function Eutils($fn, $q) { $u = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/$fn`?$q&tool=trackeep-lit"; Invoke-WebRequest -Uri $u -UseBasicParsing -TimeoutSec 120 }
function Zot-GetAll($path) {
  $rows = New-Object System.Collections.Generic.List[object]; $s = 0
  while ($true) {
    $u = "$zBase$path"; $u += $(if ($u -match '\?') { '&' } else { '?' }) + "limit=100&start=$s"
    $r = Invoke-WebRequest -Uri $u -Headers $zH -UseBasicParsing -TimeoutSec 90
    $d = ConvertFrom-Json (Get-Utf8 $r)
    $pg = @(if ($null -eq $d) { } elseif ($d -is [array]) { $d } else { $d })
    foreach ($x in $pg) { $rows.Add($x) }
    if ($pg.Count -lt 100) { break }; $s += 100
  }
  $rows
}
function Txt($node, $xpath) { if ($null -eq $node) { return '' }; $n = $node.SelectSingleNode($xpath); if ($n) { "$($n.InnerText)".Trim() } else { '' } }
function Norm-Doi($s) { (([string]$s).Trim() -replace '^(?i)(https?://(dx\.)?doi\.org/|doi:\s*)', '').ToLowerInvariant() }
function Norm-Title($s) { ("$s" -replace '[^\p{L}\p{Nd}]', '').ToLower() }

# --- 1) 查询 ---
# 检索日期子句 + 周期标签：按 -Month / -Year / -ReldateDays 三模式分支
if ($Month) {
  $dp = '("{0}/{1:00}/01"[DP] : "{0}/{1:00}/{2:00}"[DP])' -f $mY, $mM, $lastDay
  $periodLabel = $Month
}
elseif ($Year -gt 0) {
  $dp = '("{0}/01/01"[DP] : "{0}/12/31"[DP])' -f $Year
  $periodLabel = "$Year"
}
else {
  $dp = ''
  $periodLabel = "reldate-$ReldateDays"
}
# pubtype 策略由配置/开关驱动：默认只要 article/review 且有摘要；editorial/letter 按需附加（原 JTO 硬编码已迁进 journal-overrides.json）
$dropTypes = @('comment[PT]')
if (-not $wantLetter) { $dropTypes += 'letter[PT]' }
$dropTypes += @('published erratum[PT]', 'retraction of publication[PT]', 'retracted publication[PT]')
$ptDrop = '(' + ($dropTypes -join ' OR ') + ')'
$incParts = @('((journal article[PT] OR review[PT]) AND hasabstract)')
if ($wantEditorial) { $incParts += 'editorial[PT]' }
if ($wantLetter) { $incParts += 'letter[PT]' }
$ptClause = if ($incParts.Count -gt 1) { '(' + ($incParts -join ' OR ') + ')' } else { $incParts[0] }
if ($dp) {
  $term = '"{0}"[TA] AND {1} AND {2} NOT {3}' -f $Journal, $dp, $ptClause, $ptDrop
} else {
  $term = '"{0}"[TA] AND {1} NOT {2}' -f $Journal, $ptClause, $ptDrop
}
if ($TopicFilter) { $term += ' AND (' + $TopicFilter + ')' }
Write-Host ("模式: {0} · 周期: {1}" -f $(if ($Execute) { '真导入 (-Execute)' } else { '预览 (dry-run)' }), $periodLabel) -ForegroundColor $(if ($Execute) { 'Red' } else { 'Cyan' })
Write-Host "查询: $term" -ForegroundColor DarkGray
if ($ArticlePmids) {
  if ($ArticlePmids -notmatch '^\d+(,\d+)*$') { throw 'PMID 格式错误' }
  $pmids = @($ArticlePmids -split ',' | Select-Object -Unique); $periodLabel = 'pmids'; $term = 'PMID: ' + $ArticlePmids
} else {
$esQuery = "db=pubmed&retmode=json&retmax=10000&term=" + [uri]::EscapeDataString($term)
if ($ReldateDays -gt 0) { $esQuery += "&datetype=edat&reldate=$ReldateDays" }
$es = ConvertFrom-Json (Get-Utf8 (Eutils 'esearch.fcgi' $esQuery))
$pmids = @($es.esearchresult.idlist)
if ([int]$es.esearchresult.count -ne $pmids.Count) { throw 'PubMed 返回不完整，请缩小时间窗；禁止继续导入' }
}
Write-Host ("PubMed 命中: {0} 篇" -f $pmids.Count) -ForegroundColor Cyan
if ($pmids.Count -eq 0) {
  # 命中 0：补一发宽检索（仅 [TA] 单条件、无日期/pubtype/reldate）区分"本期真无新文"vs"刊名错配"
  $broadQuery = "db=pubmed&retmode=json&retmax=0&term=" + [uri]::EscapeDataString('"' + $Journal + '"[TA]')
  $broadEs = ConvertFrom-Json (Get-Utf8 (Eutils 'esearch.fcgi' $broadQuery))
  $broadCount = [int]"$($broadEs.esearchresult.count)"
  if ($broadCount -eq 0) {
    Write-Host "⚠ [$Journal] 命中0，且宽检索 [TA] 也为0 —— 刊名可能与 PubMed [TA] 不匹配，核对期刊表缩写" -ForegroundColor Yellow
  } else {
    Write-Host "[$Journal] 本期无新文献（该刊 [TA] 宽检索共 $broadCount 篇存在）"
  }
  Write-ResultJson ([ordered]@{ schema = 'trackeep-lit/import-result@1'; journal = $Journal; mode = $periodLabel; query = $term; executed = [bool]$Execute; found = 0; counts = [ordered]@{ new = 0; dup = 0; suspect = 0; imported = 0; failed = 0 }; collection = [ordered]@{ key = ''; exists = $false }; broadCount = $broadCount; taMismatch = ($broadCount -eq 0); items = @() })
  return
}

# --- 2) efetch 元数据 ---
$expectedPmids = @($pmids | ForEach-Object { [string]$_ })
$cands = @()
for ($i = 0; $i -lt $pmids.Count; $i += 180) {
  $chunk = @($pmids[$i..([Math]::Min($i + 179, $pmids.Count - 1))])
  [xml]$xml = Get-Utf8 (Eutils 'efetch.fcgi' ("db=pubmed&retmode=xml&id=" + ($chunk -join ',')))
  foreach ($pa in $xml.PubmedArticleSet.PubmedArticle) {
    $pmid = Txt $pa 'MedlineCitation/PMID'
    $title = Txt $pa 'MedlineCitation/Article/ArticleTitle'
    $doiN = $pa.SelectSingleNode("PubmedData/ArticleIdList/ArticleId[@IdType='doi']")
    $doi = if ($doiN) { "$($doiN.InnerText)".ToLower().Trim() } else { '' }
    $absParts = @()
    foreach ($an in $pa.SelectNodes('MedlineCitation/Article/Abstract/AbstractText')) {
      $lbl = $an.GetAttribute('Label'); $txt = "$($an.InnerText)".Trim()
      if ($txt) { $absParts += $(if ($lbl) { "${lbl}: $txt" } else { $txt }) }
    }
    $abstract = ($absParts -join "`n")
    $creators = @()
    foreach ($au in $pa.SelectNodes('MedlineCitation/Article/AuthorList/Author')) {
      $coll = $au.SelectSingleNode('CollectiveName')
      if ($coll) { $creators += @{ creatorType = 'author'; name = "$($coll.InnerText)".Trim() } }
      else {
        $ln = "$($au.SelectSingleNode('LastName').InnerText)".Trim()
        $fn = "$($au.SelectSingleNode('ForeName').InnerText)".Trim()
        if ($ln) { $creators += @{ creatorType = 'author'; lastName = $ln; firstName = $fn } }
      }
    }
    $yr = Txt $pa 'MedlineCitation/Article/Journal/JournalIssue/PubDate/Year'
    if (-not $yr) { $yr = Txt $pa 'MedlineCitation/Article/Journal/JournalIssue/PubDate/MedlineDate' }
    $mo = Txt $pa 'MedlineCitation/Article/Journal/JournalIssue/PubDate/Month'
    $pts = @(); foreach ($pt in $pa.SelectNodes('MedlineCitation/Article/PublicationTypeList/PublicationType')) { $pts += "$($pt.InnerText)".Trim() }
    $bucket = if ($pts -match '(?i)review') { 'Review' } elseif ($pts -match '(?i)editorial') { 'Editorial' } else { 'Article' }
    $cands += [pscustomobject]@{
      Pmid = $pmid; Doi = $doi; Title = $title; NlmId = (Txt $pa 'MedlineCitation/MedlineJournalInfo/NlmUniqueID'); ZoteroKey = '';
      DateEvidence = (@($pa.SelectNodes('MedlineCitation/Article/ArticleDate | MedlineCitation/Article/Journal/JournalIssue/PubDate') | ForEach-Object { $_.OuterXml }) -join "`n"); Abstract = $abstract; HasAbs = [bool]$abstract
      Creators = $creators; JFull = (Txt $pa 'MedlineCitation/Article/Journal/Title'); JAbbr = (Txt $pa 'MedlineCitation/Article/Journal/ISOAbbreviation')
      Vol = (Txt $pa 'MedlineCitation/Article/Journal/JournalIssue/Volume'); Iss = (Txt $pa 'MedlineCitation/Article/Journal/JournalIssue/Issue')
      Date = ("{0} {1}" -f $yr, $mo).Trim(); Pages = (Txt $pa 'MedlineCitation/Article/Pagination/MedlinePgn'); Issn = (Txt $pa 'MedlineCitation/Article/Journal/ISSN'); Type = $bucket
    }
  }
  Start-Sleep -Milliseconds 350
}

if ($cands.Count -ne $expectedPmids.Count -or @(Compare-Object $expectedPmids @($cands | ForEach-Object { [string]$_.Pmid })).Count -gt 0) { throw '取回 PMID 与请求不一致，禁止写入' }

# 指定 PMID 的真实写入必须与调用方已验证题录逐字段一致。
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

# --- 3) 去重锚：台账 + 当前库（DOI 主、PMID 兜底）---
$ledger = $null; $ledgerMissing = $false
if (Test-Path $LedgerPath) { try { $ledger = (Get-Content $LedgerPath -Raw -Encoding UTF8).TrimStart([char]0xFEFF) | ConvertFrom-Json } catch { $ledger = $null } }
else { $ledgerMissing = $true; Write-Warning "去重已降级为现库单锚（台账缺失）：$LedgerPath 不存在——本次仅与当前 Zotero 库比对" }
$sumLedger = if ($ledgerMissing) { ' ledger=missing(dedup=live-lib-only)' } else { '' }
$ldDoi = @{}; $ldPmid = @{}; $ldTitle = @{}
if ($ledger -and $ledger.items) { foreach ($it in $ledger.items) { if ($it.doi) { $ldDoi[("$($it.doi)").ToLower()] = $true }; if ($it.pmid) { $ldPmid["$($it.pmid)"] = $true }; $nt = Norm-Title $it.title; if ($nt) { $ldTitle[$nt] = $true } } }
$live = @(Zot-GetAll '/items?includeTrashed=1')
foreach ($c in $cands) {
  foreach ($it in $live) {
    $d = Norm-Doi $it.data.DOI; $p = ''
    if ("$($it.data.extra)" -match '(?im)^PMID:\s*(\d+)') { $p = $Matches[1] }
    if (($d -and $c.Doi -and $d -eq (Norm-Doi $c.Doi)) -or ($p -and $p -eq $c.Pmid)) {
      if (($d -and $c.Doi -and $d -ne (Norm-Doi $c.Doi)) -or ($p -and $p -ne $c.Pmid)) { throw '已有条目标识冲突，禁止导入或自动合并' }
    }
  }
}
$libDoi = @{}; $libPmid = @{}; $libTitle = @{}
foreach ($it in $live) { $d = Norm-Doi $it.data.DOI; if ($d) { $libDoi[$d] = $true }; if ("$($it.data.extra)" -match '(?im)PMID:\s*(\d+)') { $libPmid[$Matches[1]] = $true }; $nt = Norm-Title $it.data.title; if ($nt) { $libTitle[$nt] = $true } }
foreach ($c in $cands) {
  $inLed = ($c.Doi -and $ldDoi[$c.Doi]) -or ($c.Pmid -and $ldPmid[$c.Pmid])
  $inLib = ($c.Doi -and $libDoi[$c.Doi]) -or ($c.Pmid -and $libPmid[$c.Pmid])
  # DOI/PMID 命中＝确定重复(跳过)；仅无 DOI 且未按 PMID 命中时，标题归一命中只作「疑似」，不自动跳过/合并/导入
  $inTitle = $false
  if (-not $c.Doi -and -not $inLib -and -not $inLed) { $nt = Norm-Title $c.Title; $inTitle = [bool]($nt -and ($libTitle[$nt] -or $ldTitle[$nt])) }
  if ($inLed -or $inLib) {
    $status = 'dup'
    $src = if ($inLed -and $inLib) { '台账+库' } elseif ($inLed) { '台账' } else { '库' }
    $by = if ($c.Doi -and ($ldDoi[$c.Doi] -or $libDoi[$c.Doi])) { 'doi' } else { 'pmid' }
  }
  elseif ($inTitle) { $status = 'suspect'; $src = '疑似标题'; $by = 'title' }
  else { $status = 'new'; $src = ''; $by = '' }
  $c | Add-Member NoteProperty Status $status -Force
  $c | Add-Member NoteProperty DedupBy $by -Force
  $c | Add-Member NoteProperty Dup ([bool]($status -eq 'dup')) -Force
  $c | Add-Member NoteProperty DupSrc $src -Force
}
$new = @($cands | Where-Object { $_.Status -eq 'new' })
$dup = @($cands | Where-Object { $_.Status -eq 'dup' })
$suspect = @($cands | Where-Object { $_.Status -eq 'suspect' })

# --- 4) collection key（按期刊名匹配）---
$collKey = ''; $cols = @(Zot-GetAll '/collections')
$cm = @($cols | Where-Object { $_.data.name -eq $Journal }); if ($cm.Count -eq 1) { $collKey = $cm[0].key }; if ($CollectionKey) { if (@($cols | Where-Object { $_.key -ceq $CollectionKey }).Count -ne 1) { throw '指定目录不存在或编号不唯一' }; $collKey = $CollectionKey }
$collMsg = if ($collKey) { "collection「$Journal」key=$collKey" } else { "⚠ 未找到 collection「$Journal」(先跑 zotero\journals.ps1)；导入将不归集" }

# --- 5) 报告 ---
Write-Host ''
$cands | Sort-Object Status, Type | Format-Table `
  @{ n = '状态'; e = { switch ($_.Status) { 'dup' { "DUP($($_.DupSrc))" } 'suspect' { 'SUSPECT(疑似标题)' } default { 'NEW' } } } }, Type, `
  @{ n = '摘要'; e = { if ($_.HasAbs) { '有' } else { '无' } } }, `
  @{ n = 'Title'; e = { if ($_.Title.Length -gt 62) { $_.Title.Substring(0, 60) + '..' } else { $_.Title } } } -AutoSize
Write-Host '=== 汇总 ===' -ForegroundColor Green
Write-Host ("  命中 {0} · 新增 {1} · 重复跳过 {2} · 疑似 {3}" -f $cands.Count, $new.Count, $dup.Count, $suspect.Count)
Write-Host ('  类型: ' + (($cands | Group-Object Type | ForEach-Object { '{0} {1}' -f $_.Name, $_.Count }) -join ' / '))
Write-Host ("  新增中 有摘要(≈真研究) {0} / 无摘要(≈评论社论) {1}" -f @($new | Where-Object { $_.HasAbs }).Count, @($new | Where-Object { -not $_.HasAbs }).Count)
Write-Host ("  $collMsg")

if (-not $Execute) {
  Write-Host ("SUMMARY journal=[$Journal] found={0} dup={1} new={2} imported=0 failed=0$sumLedger" -f $cands.Count, $dup.Count, $new.Count)
  Write-ResultJson ([ordered]@{ schema = 'trackeep-lit/import-result@1'; journal = $Journal; mode = $periodLabel; query = $term; executed = $false; found = $cands.Count; counts = [ordered]@{ new = $new.Count; dup = $dup.Count; suspect = $suspect.Count; imported = 0; failed = 0 }; collection = [ordered]@{ key = $collKey; exists = [bool]$collKey }; broadCount = $null; taMismatch = $false; items = @(Cand-Items $cands) })
  Write-Host "`n[dry-run] 未写 Zotero、未动台账。确认无误后加 -Execute 真导入。" -ForegroundColor Yellow; return
}
if ($new.Count -eq 0) {
  Write-Host ("SUMMARY journal=[$Journal] found={0} dup={1} new=0 imported=0 failed=0$sumLedger" -f $cands.Count, $dup.Count)
  Write-ResultJson ([ordered]@{ schema = 'trackeep-lit/import-result@1'; journal = $Journal; mode = $periodLabel; query = $term; executed = [bool]$Execute; found = $cands.Count; counts = [ordered]@{ new = 0; dup = $dup.Count; suspect = $suspect.Count; imported = 0; failed = 0 }; collection = [ordered]@{ key = $collKey; exists = [bool]$collKey }; broadCount = $null; taMismatch = $false; items = @(Cand-Items $cands) })
  Write-Host "`n无新增，结束。"; return
}

# --- 6) 导入（-Execute）---
if (-not $collKey) { throw '目标期刊目录不存在或重名，拒绝无归属导入' }
if ($cands.Count -ne $pmids.Count) { throw '元数据数量不齐，拒绝导入' }
# ExcludePmids（6b-2 真门控）：App 侧 AI 复筛判滤且未捞回的 PMID，导入时跳过——打
# Status='excluded'（≠ failed：未导入 ≠ 导入失败），不 POST、不进台账。空参数 = 无排除，
# 完全等于旧行为（向后兼容）；dry-run 路径不参与（门控数由 App 侧从判决算）。
$exclSet = @{}; foreach ($p in ($ExcludePmids -split ',')) { $t = "$p".Trim(); if ($t) { $exclSet[$t] = $true } }
foreach ($c in $new) { if ($exclSet["$($c.Pmid)"]) { $c.Status = 'excluded' } }
$toImport = @($new | Where-Object { $_.Status -eq 'new' })
$batchId = (Get-Date).ToString('yyyyMMdd-HHmmss') + '-' + ($Journal -replace '\s', '') + "-$periodLabel"
$imported = 0; $failed = 0; $confirmed = @()
for ($i = 0; $i -lt $toImport.Count; $i += 50) {
  $slice = @($toImport[$i..([Math]::Min($i + 49, $toImport.Count - 1))])
  $items = @()
  foreach ($c in $slice) {
    $items += [ordered]@{
      itemType = 'journalArticle'; title = $c.Title; creators = $c.Creators; abstractNote = $c.Abstract
      publicationTitle = $c.JFull; journalAbbreviation = $c.JAbbr; volume = $c.Vol; issue = $c.Iss; pages = $c.Pages
      date = $c.Date; DOI = $c.Doi; ISSN = $c.Issn; extra = ("PMID: {0}`nNLM ID: {1}`nPubMed date sources: {2}" -f $c.Pmid, $c.NlmId, $c.DateEvidence); url = ("https://pubmed.ncbi.nlm.nih.gov/{0}/" -f $c.Pmid)
      tags = @(@{ tag = 'mecha-import' }); collections = @($collKey | Where-Object { $_ })
    }
  }
  $body = [System.Text.Encoding]::UTF8.GetBytes((ConvertTo-Json -InputObject $items -Depth 8))
  $hW = @{ 'Zotero-API-Version' = '3'; 'Zotero-API-Key' = $key; 'Zotero-Write-Token' = ([guid]::NewGuid().ToString('N')) }
  $resp = Invoke-WebRequest -Uri "$zBase/items" -Method Post -Headers $hW -ContentType 'application/json' -Body $body -UseBasicParsing -TimeoutSec 120
  $rj = ConvertFrom-Json (Get-Utf8 $resp)
  foreach ($k in $rj.successful.PSObject.Properties.Name) {
    if ($k -notmatch '^\d+$' -or [int]$k -ge $slice.Count -or $rj.successful.$k.key -notmatch '^[A-Z0-9]{8}$') { throw '写入回执异常，须重新读库，不可盲重试' }
    $got = $rj.successful.$k.data; $want = $slice[[int]$k]; $gotPmid = ''; $gotNlm = ''
    if ("$($got.extra)" -match '(?im)^PMID:\s*(\d+)\s*$') { $gotPmid = $Matches[1] }
    if ("$($got.extra)" -match '(?im)^NLM ID:\s*(\S+)\s*$') { $gotNlm = $Matches[1] }
    if ($gotPmid -cne $want.Pmid -or $got.title -cne $want.Title -or (Norm-Doi $got.DOI) -cne (Norm-Doi $want.Doi) -or
        $got.itemType -cne 'journalArticle' -or $gotNlm -cne $want.NlmId -or $collKey -notin @($got.collections)) { throw '写入回执身份或目录错误，须重新读库，不可盲重试' }
    if (@($confirmed | Where-Object { $_.ZoteroKey -eq $rj.successful.$k.key }).Count) { throw '不同文章返回同一 Zotero 编号，须重新读库' }
    $slice[[int]$k].ZoteroKey = $rj.successful.$k.key; $confirmed += $slice[[int]$k]
  }
  if (@($rj.successful.PSObject.Properties).Count + @($rj.failed.PSObject.Properties).Count -ne $slice.Count) { throw '写入回执数量不齐，须重新读库' }
  $okN = @($rj.successful.PSObject.Properties).Count; $failN = @($rj.failed.PSObject.Properties).Count
  $imported += $okN; $failed += $failN
  Write-Host ("  批 {0}-{1}: 成功 {2} 失败 {3}" -f ($i + 1), ($i + $slice.Count), $okN, $failN)
  if ($failN -gt 0) { foreach ($f in $rj.failed.PSObject.Properties) { Write-Host ("    失败: {0}" -f $f.Value.message) -ForegroundColor Red } }
}

# --- 7) 写台账 ---
if (-not $ledger) { $ledger = [pscustomobject]@{ version = 1; items = @(); batches = @() } }
$newRecs = @(); foreach ($c in $confirmed) { $newRecs += [pscustomobject]@{ doi = $c.Doi; pmid = $c.Pmid; title = $c.Title; journal = $Journal; month = $periodLabel; batch = $batchId } }
$ledger.items = @($ledger.items) + $newRecs
$ledger.batches = @($ledger.batches) + , ([pscustomobject]@{ id = $batchId; journal = $Journal; month = $periodLabel; time = (Get-Date).ToString('s'); hits = $cands.Count; new = $new.Count; dup = $dup.Count; imported = $imported; failed = $failed })
$ledgerTmp = $LedgerPath + '.tmp'; [IO.File]::WriteAllText($ledgerTmp, ($ledger | ConvertTo-Json -Depth 8), [Text.UTF8Encoding]::new($false)); Move-Item -LiteralPath $ledgerTmp -Destination $LedgerPath -Force
Write-Host ("`n导入完成: {0} 成功 / {1} 失败。台账已更新: {2}" -f $imported, $failed, $LedgerPath) -ForegroundColor Green
Write-Host ("SUMMARY journal=[$Journal] found={0} dup={1} new={2} imported={3} failed={4}$sumLedger" -f $cands.Count, $dup.Count, $new.Count, $imported, $failed)
$confPmids = @{}; foreach ($c in $confirmed) { $confPmids["$($c.Pmid)"] = $true }
foreach ($c in $cands) { if ($c.Status -eq 'new') { $c.Status = $(if ($confPmids["$($c.Pmid)"]) { 'imported' } else { 'failed' }) } }
Write-ResultJson ([ordered]@{ schema = 'trackeep-lit/import-result@1'; journal = $Journal; mode = $periodLabel; query = $term; executed = $true; found = $cands.Count; counts = [ordered]@{ new = $new.Count; dup = $dup.Count; suspect = $suspect.Count; imported = $imported; failed = $failed; excluded = @($new | Where-Object { $_.Status -eq 'excluded' }).Count }; collection = [ordered]@{ key = $collKey; exists = [bool]$collKey }; broadCount = $null; taMismatch = $false; batchId = $batchId; items = @(Cand-Items $cands) })

} finally { if ($writeMutex) { if ($locked) { $writeMutex.ReleaseMutex() }; $writeMutex.Dispose() } }
