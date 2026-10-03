# 历史档案：原文保留（含旧品牌与历史路径，勿改史实）；批B 2026-10-03 归档注记
# ⚠️ 已过时（2026-07-24 去枢纽战役）：所属机制已废除，勿运行；留档待删由 PI 裁决
<#
  zotero-harvest.ps1 — 全自动月度文献采集：PubMed 查某刊新文献 → DOI/PMID 去重 → 直灌 Zotero。
  对应 Mecha-Memex 文献管线「步 1+2」。唯一性靠 DOI/PMID 去重 + 增量游标，不靠文件夹。

  纪律：PubMed 只读；Zotero 只「新建条目 + 归入该刊 collection」，不改 / 不删已有条目。
        API key 仅入 HTTP 头、不回显。默认「干跑预览」，加 -Apply 才真写。

  用法：
    powershell -File zotero-harvest.ps1 -Journal "J Thorac Oncol"                      # 干跑，近 60 天
    powershell -File zotero-harvest.ps1 -Journal "J Thorac Oncol" -ReldateDays 30 -Apply
#>
[CmdletBinding()]
param(
  [string]$Journal = 'J Thorac Oncol',
  [int]$Year = 0,            # >0 = 拉该整年（按刊期 pdat）；0 = 本月增量（按收录 edat）
  [int]$ReldateDays = 60,
  [int]$MaxImport = 500,
  [switch]$Apply
)
$ErrorActionPreference = 'Stop'
try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 } catch {}
$UA = 'mecha-memex/1.0 (mailto:yudongz834@gmail.com)'

# --- env（脚本是唯一接触 key 的边界）---
$EnvFile = Join-Path $env:USERPROFILE '.config\mecha\secrets\zotero.env'
if (-not (Test-Path -LiteralPath $EnvFile)) { throw "secret 不存在：$EnvFile" }
$cfg = @{}
foreach ($line in (Get-Content -LiteralPath $EnvFile)) {
  $t = $line.Trim(); if (-not $t -or $t.StartsWith('#')) { continue }
  $i = $t.IndexOf('='); if ($i -lt 1) { continue }
  $cfg[$t.Substring(0, $i).Trim()] = $t.Substring($i + 1).Trim().Trim(' ', '<', '>', '"', "'")
}
$apiKey = $cfg['ZOTERO_API_KEY']; $userId = $cfg['ZOTERO_USER_ID']
if (-not $apiKey -or -not $userId) { throw 'zotero.env 缺 ZOTERO_API_KEY / ZOTERO_USER_ID' }
$zBase = "https://api.zotero.org/users/$userId"
$hZ = @{ 'Zotero-API-Version' = '3'; 'Zotero-API-Key' = $apiKey }
function ZGet($path) {
  $r = Invoke-WebRequest -Uri "$zBase$path" -Headers $hZ -UseBasicParsing -TimeoutSec 60
  ConvertFrom-Json ([Text.Encoding]::UTF8.GetString($r.RawContentStream.ToArray()))
}

# --- 1. 刊名 → collection key ---
$cols = ZGet "/collections?limit=100"
$col = $cols | Where-Object { $_.data.name -eq $Journal } | Select-Object -First 1
if (-not $col) { throw "Zotero 里找不到名为「$Journal」的 collection（核对期刊来源表 / 缩写）" }
$colKey = $col.key
Write-Host "期刊：$Journal  → collection $colKey"

# --- 2. PubMed esearch（年份=按刊期拉整年；否则按收录日增量）---
$term = [uri]::EscapeDataString("`"$Journal`"[ta]")
if ($Year -gt 0) {
  $esUrl = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term=$term&datetype=pdat&mindate=$Year/01/01&maxdate=$Year/12/31&retmax=1000&retmode=json"
  $scope = "$Year 全年（按刊期）"
} else {
  $esUrl = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term=$term&datetype=edat&reldate=$ReldateDays&retmax=1000&retmode=json"
  $scope = "近 $ReldateDays 天（按收录）"
}
$es = Invoke-RestMethod -Uri $esUrl -Headers @{ 'User-Agent' = $UA } -TimeoutSec 60
$pmids = @($es.esearchresult.idlist)
Write-Host "PubMed [$Journal] $scope 命中：$($pmids.Count) 篇"
if ($pmids.Count -eq 0) { Write-Host "无新文献，结束。"; return }

# --- 3. efetch + 解析 ---
$monMap = @{ January='01';February='02';March='03';April='04';May='05';June='06';July='07';August='08';September='09';October='10';November='11';December='12';Jan='01';Feb='02';Mar='03';Apr='04';Jun='06';Jul='07';Aug='08';Sep='09';Oct='10';Nov='11';Dec='12' }
function Norm-Date($pd) {
  if ($pd.Year) {
    $y = "$($pd.Year)"; $m = $null
    if ($pd.Month) { $mm = "$($pd.Month)"; if ($monMap.ContainsKey($mm)) { $m = $monMap[$mm] } elseif ($mm -match '^\d+$') { $m = '{0:D2}' -f [int]$mm } }
    if ($m) { return "$y-$m" } else { return "$y" }
  } elseif ($pd.MedlineDate) {
    $md = "$($pd.MedlineDate)"
    if ($md -match '(\d{4})') { $y = $matches[1]; foreach ($k in $monMap.Keys) { if ($md -match "\b$k\b") { return "$y-$($monMap[$k])" } }; return "$y" }
  }
  return ''
}
$fetched = @()
for ($i = 0; $i -lt $pmids.Count; $i += 100) {
  $chunk = $pmids[$i..([Math]::Min($i + 99, $pmids.Count - 1))] -join ','
  $efUrl = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id=$chunk&retmode=xml"
  $r = Invoke-WebRequest -Uri $efUrl -Headers @{ 'User-Agent' = $UA } -UseBasicParsing -TimeoutSec 120
  [xml]$xml = [Text.Encoding]::UTF8.GetString($r.RawContentStream.ToArray())
  foreach ($art in $xml.PubmedArticleSet.PubmedArticle) {
    if (-not $art) { continue }
    $pmid = $art.MedlineCitation.PMID.'#text'; if (-not $pmid) { $pmid = "$($art.MedlineCitation.PMID)" }
    $doi = ($art.PubmedData.ArticleIdList.ArticleId | Where-Object { $_.IdType -eq 'doi' }).'#text'
    if (-not $doi) { $doi = ($art.MedlineCitation.Article.ELocationID | Where-Object { $_.EIdType -eq 'doi' }).'#text' }
    $titleNode = $art.MedlineCitation.Article.ArticleTitle
    $title = if ($titleNode -is [System.Xml.XmlElement]) { $titleNode.InnerText } else { "$titleNode" }
    $jr = $art.MedlineCitation.Article.Journal.ISOAbbreviation
    $ji = $art.MedlineCitation.Article.Journal.JournalIssue
    $date = Norm-Date $ji.PubDate
    $creators = @()
    foreach ($a in @($art.MedlineCitation.Article.AuthorList.Author)) {
      if (-not $a) { continue }
      if ($a.CollectiveName) { $creators += @{ creatorType = 'author'; name = "$($a.CollectiveName)" } }
      elseif ($a.LastName) { $creators += @{ creatorType = 'author'; lastName = "$($a.LastName)"; firstName = "$($a.ForeName)" } }
    }
    $absNodes = @($art.MedlineCitation.Article.Abstract.AbstractText)
    $abs = ($absNodes | ForEach-Object {
        if (-not $_) { return }
        $lbl = $_.Label; $txt = if ($_ -is [System.Xml.XmlElement]) { $_.InnerText } else { "$_" }
        if ($lbl) { "${lbl}: $txt" } else { $txt }
      }) -join "`n"
    $fetched += [pscustomobject]@{ PMID = "$pmid"; DOI = "$doi"; Title = $title; Journal = $jr; Date = $date
      Vol = "$($ji.Volume)"; Issue = "$($ji.Issue)"; Pages = "$($art.MedlineCitation.Article.Pagination.MedlinePgn)"; Creators = $creators; Abstract = $abs }
  }
  Start-Sleep -Milliseconds 350
}
Write-Host "解析成功：$($fetched.Count) 篇"

# --- 4. 去重（against 该刊 collection 现有 DOI / PMID）---
$existDoi = @{}; $existPmid = @{}; $start = 0
do {
  $page = ZGet "/collections/$colKey/items/top?itemType=-attachment&limit=100&start=$start"
  foreach ($it in $page) {
    if ($it.data.DOI) { $existDoi[$it.data.DOI.ToLower()] = $true }
    if ($it.data.extra -and $it.data.extra -match 'PMID:\s*(\d+)') { $existPmid[$matches[1]] = $true }
  }
  $start += 100
} while ($page.Count -eq 100)
Write-Host "现有库内该刊：DOI $($existDoi.Count) 个、PMID $($existPmid.Count) 个"

$new = @(); $dup = 0
foreach ($f in $fetched) {
  $isDup = ($f.DOI -and $existDoi.ContainsKey($f.DOI.ToLower())) -or ($f.PMID -and $existPmid.ContainsKey($f.PMID))
  if ($isDup) { $dup++ } else { $new += $f }
}
Write-Host "去重：撞库跳过 $dup 篇，新文献 $($new.Count) 篇"
if ($new.Count -gt $MaxImport) { Write-Host "[!] 新文献 $($new.Count) > 上限 $MaxImport，只取前 $MaxImport（防误灌）"; $new = $new[0..($MaxImport - 1)] }
Write-Host ("SUMMARY journal=[{0}] found={1} dup={2} new={3}" -f $Journal, $fetched.Count, $dup, $new.Count)

# --- 5. 构造 Zotero item ---
function To-ZItem($f) {
  [ordered]@{
    itemType = 'journalArticle'; title = $f.Title; creators = $f.Creators; abstractNote = $f.Abstract
    publicationTitle = $f.Journal; volume = $f.Vol; issue = $f.Issue; pages = $f.Pages; date = $f.Date
    DOI = $f.DOI; extra = $(if ($f.PMID) { "PMID: $($f.PMID)" } else { '' }); collections = @($colKey)
  }
}
$items = @($new | ForEach-Object { To-ZItem $_ })

$mode = if ($Apply) { 'APPLY（真写）' } else { 'DRY-RUN（仅预览）' }
Write-Host "`n==== 模式：$mode ===="
$new | Select-Object -First 8 | ForEach-Object { "  [新] $($_.Date)  $($_.Title.Substring(0,[Math]::Min(58,$_.Title.Length)))  (PMID $($_.PMID))" }
if ($new.Count -gt 8) { "  … 余 $($new.Count - 8) 篇" }

if (-not $Apply) {
  Write-Host "`n--- 首条 JSON 形状自检（确认 collections/creators 是数组）---"
  if ($items.Count -ge 1) { ConvertTo-Json -Depth 6 $items[0] }
  Write-Host "`n（预览，未写。确认无误后加 -Apply 真灌。）"
  return
}
if ($items.Count -eq 0) { Write-Host "无新文献可导，结束。"; return }

# --- 6. 批量 POST（≤50/批）---
$imported = 0
for ($i = 0; $i -lt $items.Count; $i += 50) {
  $batch = @($items[$i..([Math]::Min($i + 49, $items.Count - 1))])
  $body = if ($batch.Count -eq 1) { '[' + (ConvertTo-Json -Depth 6 $batch[0]) + ']' } else { ConvertTo-Json -Depth 6 $batch }
  $h = $hZ.Clone(); $h['Zotero-Write-Token'] = ([guid]::NewGuid().ToString('N')); $h['Content-Type'] = 'application/json'
  $resp = Invoke-WebRequest -Uri "$zBase/items" -Headers $h -Method Post -Body ([Text.Encoding]::UTF8.GetBytes($body)) -UseBasicParsing -TimeoutSec 120
  $j = ConvertFrom-Json ([Text.Encoding]::UTF8.GetString($resp.RawContentStream.ToArray()))
  $ok = @($j.successful.PSObject.Properties).Count; $fail = @($j.failed.PSObject.Properties).Count
  $imported += $ok
  if ($fail -gt 0) { Write-Host "  [!] 本批失败 $fail：$($j.failed | ConvertTo-Json -Compress)" }
  Start-Sleep -Milliseconds 300
}
Write-Host "导入完成：$imported 篇"

# --- 7. 增量游标（记住每刊扫到哪）---
$curFile = 'D:\BaiduSyncdisk\Mecha-Core\.mecha\zotero-harvest-cursor.json'
$cur = @{}
if (Test-Path $curFile) { try { $o = Get-Content $curFile -Raw | ConvertFrom-Json; foreach ($p in $o.PSObject.Properties) { $cur[$p.Name] = $p.Value } } catch {} }
$cur[$Journal] = [ordered]@{ lastRun = (Get-Date).ToString('o'); reldateDays = $ReldateDays; lastImported = $imported }
$dir = Split-Path $curFile; if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Force $dir | Out-Null }
($cur | ConvertTo-Json -Depth 5) | Set-Content -LiteralPath $curFile -Encoding UTF8
Write-Host "游标已更新 → $curFile"
Write-Host "下一步：年月归档  scripts\zotero-shelve-by-date.ps1 -CollectionKey $colKey -Apply"