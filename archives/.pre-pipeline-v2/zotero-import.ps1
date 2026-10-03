# 历史档案：原文保留（含旧品牌与历史路径，勿改史实）；批B 2026-10-03 归档注记
<#
  zotero-import.ps1 — PubMed → Zotero 自动导入器（v1）

  一条命令完成一本刊一个月：
    1) 检索——清洗查询跑 PubMed esearch：默认只要 article/review 且有摘要(hasabstract)；
       JTO 特例额外保留 editorial（含 Controversy 辩论文，实测被标为 editorial[PT]）。
    2) 取元数据——efetch 拿每篇 DOI / 摘要 / 题录。
    3) 去重——按 DOI（PMID 兜底）比对【导入台账 + 当前 Zotero 库】，重复跳过。
    4) 台账——每批写入 .mecha/zotero-import-ledger.json，后续每批都与它核对
              （根治 Online-Ahead ↔ 正式版的长期重复累积）。
    5) 导入——新文献 POST 进 Zotero、归入该期刊 collection（仅 -Execute）。

  纪律
    · 默认 dry-run（只读预览，不写 Zotero、不动台账）；加 -Execute 才真导入 + 写台账。
    · 去重锚 = DOI（永久标识，Online-Ahead 与正式版一致），PMID 兜底；不靠摘要。
    · PubMed E-utilities 免 key；Zotero API key 仅用于请求头、不回显。

  用法
    powershell -File zotero-import.ps1 -Journal "Ann Thorac Surg" -Month "2025-10"           # 预览
    powershell -File zotero-import.ps1 -Journal "Ann Thorac Surg" -Month "2025-10" -Execute   # 真导入
    -TopicFilter "lung[tiab] OR esophag*[tiab] ..."   # 综合/AI/基础刊用胸部主题过滤；胸外/公卫刊留空=全收
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory)][string]$Journal,
  [Parameter(Mandatory)][string]$Month,
  [string]$TopicFilter,
  [switch]$Execute
)
$ErrorActionPreference = 'Stop'
try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 } catch {}
if ($Month -notmatch '^(\d{4})-(\d{2})$') { throw '-Month 须 YYYY-MM，如 2025-10' }
$mY = [int]$Matches[1]; $mM = [int]$Matches[2]; $lastDay = [DateTime]::DaysInMonth($mY, $mM)

# --- secret ---
$EnvFile = Join-Path $env:USERPROFILE '.config\mecha\secrets\zotero.env'
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

$McDir = Join-Path $PSScriptRoot '..\.mecha'
if (-not (Test-Path $McDir)) { New-Item -ItemType Directory -Path $McDir -Force | Out-Null }
$LedgerPath = Join-Path $McDir 'zotero-import-ledger.json'

# --- helpers ---
function Get-Utf8($r) { [System.Text.Encoding]::UTF8.GetString($r.RawContentStream.ToArray()) }
function Eutils($fn, $q) { $u = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/$fn`?$q&tool=mecha-zotero-import"; Invoke-WebRequest -Uri $u -UseBasicParsing -TimeoutSec 120 }
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

# --- 1) 查询 ---
$dp = '("{0}/{1:00}/01"[DP] : "{0}/{1:00}/{2:00}"[DP])' -f $mY, $mM, $lastDay
$ptDrop = '(comment[PT] OR letter[PT] OR published erratum[PT] OR retraction of publication[PT] OR retracted publication[PT])'
if ($Journal -eq 'J Thorac Oncol') {
  # JTO 特例：article/review（须有摘要）外，额外保留 editorial —— 实测 JTO 的 Controversy 辩论文被 PubMed 标为 editorial[PT]
  $ptClause = '(((journal article[PT] OR review[PT]) AND hasabstract) OR editorial[PT])'
}
else {
  # 其余刊：只要 article/review，且必须有摘要（hasabstract）
  $ptClause = '((journal article[PT] OR review[PT]) AND hasabstract)'
}
$term = '"{0}"[TA] AND {1} AND {2} NOT {3}' -f $Journal, $dp, $ptClause, $ptDrop
if ($TopicFilter) { $term += ' AND (' + $TopicFilter + ')' }
Write-Host ("模式: {0}" -f $(if ($Execute) { '真导入 (-Execute)' } else { '预览 (dry-run)' })) -ForegroundColor $(if ($Execute) { 'Red' } else { 'Cyan' })
Write-Host "查询: $term" -ForegroundColor DarkGray
$es = ConvertFrom-Json (Get-Utf8 (Eutils 'esearch.fcgi' ("db=pubmed&retmode=json&retmax=1000&term=" + [uri]::EscapeDataString($term))))
$pmids = @($es.esearchresult.idlist)
Write-Host ("PubMed 命中: {0} 篇" -f $pmids.Count) -ForegroundColor Cyan
if ($pmids.Count -eq 0) { return }

# --- 2) efetch 元数据 ---
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
      Pmid = $pmid; Doi = $doi; Title = $title; Abstract = $abstract; HasAbs = [bool]$abstract
      Creators = $creators; JFull = (Txt $pa 'MedlineCitation/Article/Journal/Title'); JAbbr = (Txt $pa 'MedlineCitation/Article/Journal/ISOAbbreviation')
      Vol = (Txt $pa 'MedlineCitation/Article/Journal/JournalIssue/Volume'); Iss = (Txt $pa 'MedlineCitation/Article/Journal/JournalIssue/Issue')
      Date = ("{0} {1}" -f $yr, $mo).Trim(); Pages = (Txt $pa 'MedlineCitation/Article/Pagination/MedlinePgn'); Issn = (Txt $pa 'MedlineCitation/Article/Journal/ISSN'); Type = $bucket
    }
  }
  Start-Sleep -Milliseconds 350
}

# --- 3) 去重锚：台账 + 当前库（DOI 主、PMID 兜底）---
$ledger = $null
if (Test-Path $LedgerPath) { try { $ledger = (Get-Content $LedgerPath -Raw -Encoding UTF8).TrimStart([char]0xFEFF) | ConvertFrom-Json } catch { $ledger = $null } }
$ldDoi = @{}; $ldPmid = @{}
if ($ledger -and $ledger.items) { foreach ($it in $ledger.items) { if ($it.doi) { $ldDoi[("$($it.doi)").ToLower()] = $true }; if ($it.pmid) { $ldPmid["$($it.pmid)"] = $true } } }
$live = @(Zot-GetAll '/items')
$libDoi = @{}; $libPmid = @{}
foreach ($it in $live) { $d = "$($it.data.DOI)".ToLower().Trim(); if ($d) { $libDoi[$d] = $true }; if ("$($it.data.extra)" -match '(?im)PMID:\s*(\d+)') { $libPmid[$Matches[1]] = $true } }
foreach ($c in $cands) {
  $inLed = ($c.Doi -and $ldDoi[$c.Doi]) -or ($c.Pmid -and $ldPmid[$c.Pmid])
  $inLib = ($c.Doi -and $libDoi[$c.Doi]) -or ($c.Pmid -and $libPmid[$c.Pmid])
  $c | Add-Member NoteProperty Dup ([bool]($inLed -or $inLib)) -Force
  $c | Add-Member NoteProperty DupSrc $(if ($inLed -and $inLib) { '台账+库' } elseif ($inLed) { '台账' } elseif ($inLib) { '库' } else { '' }) -Force
}
$new = @($cands | Where-Object { -not $_.Dup }); $dup = @($cands | Where-Object { $_.Dup })

# --- 4) collection key（按期刊名匹配）---
$collKey = ''; $cols = @(Zot-GetAll '/collections')
$cm = @($cols | Where-Object { $_.data.name -eq $Journal }); if ($cm.Count -ge 1) { $collKey = $cm[0].key }
$collMsg = if ($collKey) { "collection「$Journal」key=$collKey" } else { "⚠ 未找到 collection「$Journal」(先跑 zotero-journals.ps1)；导入将不归集" }

# --- 5) 报告 ---
Write-Host ''
$cands | Sort-Object Dup, Type | Format-Table `
  @{ n = '状态'; e = { if ($_.Dup) { "DUP($($_.DupSrc))" } else { 'NEW' } } }, Type, `
  @{ n = '摘要'; e = { if ($_.HasAbs) { '有' } else { '无' } } }, `
  @{ n = 'Title'; e = { if ($_.Title.Length -gt 62) { $_.Title.Substring(0, 60) + '..' } else { $_.Title } } } -AutoSize
Write-Host '=== 汇总 ===' -ForegroundColor Green
Write-Host ("  命中 {0} · 新增 {1} · 重复跳过 {2}" -f $cands.Count, $new.Count, $dup.Count)
Write-Host ('  类型: ' + (($cands | Group-Object Type | ForEach-Object { '{0} {1}' -f $_.Name, $_.Count }) -join ' / '))
Write-Host ("  新增中 有摘要(≈真研究) {0} / 无摘要(≈评论社论) {1}" -f @($new | Where-Object { $_.HasAbs }).Count, @($new | Where-Object { -not $_.HasAbs }).Count)
Write-Host ("  $collMsg")

if (-not $Execute) { Write-Host "`n[dry-run] 未写 Zotero、未动台账。确认无误后加 -Execute 真导入。" -ForegroundColor Yellow; return }
if ($new.Count -eq 0) { Write-Host "`n无新增，结束。"; return }

# --- 6) 导入（-Execute）---
$batchId = (Get-Date).ToString('yyyyMMdd-HHmmss') + '-' + ($Journal -replace '\s', '') + "-$Month"
$imported = 0; $failed = 0
for ($i = 0; $i -lt $new.Count; $i += 50) {
  $slice = @($new[$i..([Math]::Min($i + 49, $new.Count - 1))])
  $items = @()
  foreach ($c in $slice) {
    $items += [ordered]@{
      itemType = 'journalArticle'; title = $c.Title; creators = $c.Creators; abstractNote = $c.Abstract
      publicationTitle = $c.JFull; journalAbbreviation = $c.JAbbr; volume = $c.Vol; issue = $c.Iss; pages = $c.Pages
      date = $c.Date; DOI = $c.Doi; ISSN = $c.Issn; extra = ("PMID: {0}" -f $c.Pmid)
      tags = @(@{ tag = 'mecha-import' }); collections = @($collKey | Where-Object { $_ })
    }
  }
  $body = [System.Text.Encoding]::UTF8.GetBytes((ConvertTo-Json -InputObject $items -Depth 8))
  $hW = @{ 'Zotero-API-Version' = '3'; 'Zotero-API-Key' = $key; 'Zotero-Write-Token' = ([guid]::NewGuid().ToString('N')) }
  $resp = Invoke-WebRequest -Uri "$zBase/items" -Method Post -Headers $hW -ContentType 'application/json' -Body $body -UseBasicParsing -TimeoutSec 120
  $rj = ConvertFrom-Json (Get-Utf8 $resp)
  $okN = @($rj.successful.PSObject.Properties).Count; $failN = @($rj.failed.PSObject.Properties).Count
  $imported += $okN; $failed += $failN
  Write-Host ("  批 {0}-{1}: 成功 {2} 失败 {3}" -f ($i + 1), ($i + $slice.Count), $okN, $failN)
  if ($failN -gt 0) { foreach ($f in $rj.failed.PSObject.Properties) { Write-Host ("    失败: {0}" -f $f.Value.message) -ForegroundColor Red } }
}

# --- 7) 写台账 ---
if (-not $ledger) { $ledger = [pscustomobject]@{ version = 1; items = @(); batches = @() } }
$newRecs = @(); foreach ($c in $new) { $newRecs += [pscustomobject]@{ doi = $c.Doi; pmid = $c.Pmid; title = $c.Title; journal = $Journal; month = $Month; batch = $batchId } }
$ledger.items = @($ledger.items) + $newRecs
$ledger.batches = @($ledger.batches) + , ([pscustomobject]@{ id = $batchId; journal = $Journal; month = $Month; time = (Get-Date).ToString('s'); hits = $cands.Count; new = $new.Count; dup = $dup.Count; imported = $imported; failed = $failed })
($ledger | ConvertTo-Json -Depth 8) | Out-File -LiteralPath $LedgerPath -Encoding utf8
Write-Host ("`n导入完成: {0} 成功 / {1} 失败。台账已更新: {2}" -f $imported, $failed, $LedgerPath) -ForegroundColor Green
