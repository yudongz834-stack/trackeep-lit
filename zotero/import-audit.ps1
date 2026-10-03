<#
  import-audit.ps1 — 导入后筛查 v2（PubMed publication type 权威分类）

  做什么
    PI 全量导入 Zotero 后跑此脚本，全程只读，做两件事：
      ① 三类分流——用 PubMed publication type 把本批文献分成
         保留候选 / 短文候选 / 清理候选（权威分类，不靠标题猜）。
      ② 重复检测——跨整个 Zotero 库（含回收站）按 DOI / PMID / 标题找同一篇。

  参数（两者必给）
    -Journal  期刊 [ta] 缩写，如 "J Thorac Oncol"。
    -Month    YYYY-MM，如 "2025-01"。
    脚本用这两项跑一次 PubMed esearch 定位「本期刊本月」这一批（批次靠检索结果定义，
    不靠 Zotero 文件夹 / date 字段——勘误的 date 常是旧年份）。三类分流只输出这批；
    重复检测恒定扫全库 + 回收站。

  连接键 = DOI
    Zotero 经网页插件导入的条目 extra 字段常为空、无 PMID，但 DOI 齐全。
    故批次匹配与查重以 DOI 为主键，PMID / 归一标题为辅。

  纪律：只 GET——Zotero 与 PubMed E-utilities 都只读；不写 Zotero、不动条目、不碰
        zotero.sqlite。Zotero API key 仅用于 HTTP 头、不回显；PubMed E-utilities 免 key。

  用法
    pwsh -NoProfile -File zotero\import-audit.ps1 -Journal "J Thorac Oncol" -Month "2025-01"
#>
[CmdletBinding()]
param(
  [string]$Journal,
  [string]$Month
)
$ErrorActionPreference = 'Stop'
try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 } catch {}

if (-not ($Journal -and $Month)) {
  throw '必须同时给 -Journal 与 -Month，如：-Journal "J Thorac Oncol" -Month "2025-01"'
}
if ($Month -notmatch '^(\d{4})-(\d{2})$') { throw "-Month 格式须为 YYYY-MM，如 2025-01" }
$mYear = [int]$Matches[1]; $mMon = [int]$Matches[2]

# ---------- Zotero secret（脚本是唯一接触 key 的边界）----------
$EnvFile = Join-Path $env:USERPROFILE '.config\trackeep\secrets\zotero.env'
if (-not (Test-Path -LiteralPath $EnvFile)) { throw "secret 文件不存在：$EnvFile" }
$cfg = @{}
foreach ($line in (Get-Content -LiteralPath $EnvFile)) {
  $t = $line.Trim()
  if (-not $t -or $t.StartsWith('#')) { continue }
  $i = $t.IndexOf('='); if ($i -lt 1) { continue }
  $cfg[$t.Substring(0, $i).Trim()] = $t.Substring($i + 1).Trim().Trim(' ', '<', '>', '"', "'")
}
$apiKey = $cfg['ZOTERO_API_KEY']
$userId = $cfg['ZOTERO_USER_ID']
if (-not $apiKey -or -not $userId) { throw 'zotero.env 缺 ZOTERO_API_KEY / ZOTERO_USER_ID' }
$zBase = "https://api.zotero.org/users/$userId"
$zHead = @{ 'Zotero-API-Version' = '3'; 'Zotero-API-Key' = $apiKey }

# ---------- HTTP 工具 ----------
function Get-Utf8($resp) { [System.Text.Encoding]::UTF8.GetString($resp.RawContentStream.ToArray()) }

function Zot-GetAll([string]$path) {
  $rows = New-Object System.Collections.Generic.List[object]
  $start = 0
  while ($true) {
    $u = "$zBase$path"; $u += $(if ($u -match '\?') { '&' } else { '?' }) + "limit=100&start=$start"
    $r = Invoke-WebRequest -Uri $u -Headers $zHead -UseBasicParsing -TimeoutSec 90
    $d = ConvertFrom-Json -InputObject (Get-Utf8 $r)
    $page = @(if ($null -eq $d) { } elseif ($d -is [array]) { $d } else { $d })
    foreach ($x in $page) { $rows.Add($x) }
    if ($page.Count -lt 100) { break }
    $start += 100
  }
  $rows
}

function Eutils-Get([string]$fn, [string]$query) {
  $u = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/$fn`?$query&tool=trackeep-zotero-audit"
  $r = Invoke-WebRequest -Uri $u -UseBasicParsing -TimeoutSec 90
  ConvertFrom-Json -InputObject (Get-Utf8 $r)
}

# ---------- 元数据工具 ----------
function Get-Pmid($extra) {
  if ($extra -and "$extra" -match '(?im)PMID:\s*(\d+)') { return $Matches[1] }
  return ''
}
function Get-NormTitle($s) { ("$s" -replace '[^\p{L}\p{Nd}]', '').ToLower() }

# publication type → 三类（itemType 非文献优先判清理）
$articleTypes = @('journalArticle', 'conferencePaper', 'preprint')
function Get-Bucket([string[]]$pubtypes, [string]$itemType) {
  if ($itemType -and $articleTypes -notcontains $itemType) { return '清理候选' }
  $pt = (@($pubtypes) -join '|')
  if (-not $pt) { return '保留候选' }   # 未匹配到 PubMed —— 默认保留，列摘要提醒
  if ($pt -match '(?i)(published erratum|retraction of publication|retraction notice|retracted publication|expression of concern)') { return '清理候选' }
  if ($pt -match '(?i)\bletter\b')  { return '清理候选' }
  if ($pt -match '(?i)editorial')   { return '短文候选' }
  if ($pt -match '(?i)\bcomment\b') { return '清理候选' }   # Editorial 先判，故 Editorial+Comment 的真编者按仍归短文
  return '保留候选'
}

Write-Host '=== 导入后筛查 v2（PubMed publication type）===' -ForegroundColor Cyan

# ---------- 1. 拉 Zotero（全库 + 回收站，只读）----------
$liveAll  = @(Zot-GetAll '/items')
$trashAll = @(Zot-GetAll '/items/trash')
$liveTop  = @($liveAll  | Where-Object { -not $_.data.parentItem -and $_.data.itemType -ne 'attachment' -and $_.data.itemType -ne 'note' })
$trashTop = @($trashAll | Where-Object { -not $_.data.parentItem -and $_.data.itemType -ne 'attachment' -and $_.data.itemType -ne 'note' })

# PDF 计数：按 parentItem 聚合附件
$pdfByParent = @{}
foreach ($a in ((@($liveAll) + @($trashAll)) | Where-Object { $_.data.itemType -eq 'attachment' })) {
  if (-not $a.data.parentItem) { continue }
  if ($a.data.contentType -eq 'application/pdf' -or "$($a.data.filename)" -match '\.pdf$') {
    $pdfByParent[$a.data.parentItem] = [int]$pdfByParent[$a.data.parentItem] + 1
  }
}

function New-Row($it) {
  [pscustomobject]@{
    Key = $it.key; Type = $it.data.itemType; Title = "$($it.data.title)"
    Doi = "$($it.data.DOI)".ToLower().Trim(); Pmid = (Get-Pmid $it.data.extra)
    PdfN = [int]$pdfByParent[$it.key]; Pub = @(); 分流 = ''; 批次 = $false
  }
}
$live  = @(foreach ($it in $liveTop)  { New-Row $it })
$trash = @(foreach ($it in $trashTop) { New-Row $it })

# ---------- 2. 批次 = PubMed esearch（期刊 + 月份）----------
$lastDay = [DateTime]::DaysInMonth($mYear, $mMon)
$term = '"{0}"[ta] AND ("{1}/{2:00}/01"[dp] : "{1}/{2:00}/{3:00}"[dp])' -f $Journal, $mYear, $mMon, $lastDay
$es = Eutils-Get 'esearch.fcgi' ("db=pubmed&retmode=json&retmax=500&term=" + [uri]::EscapeDataString($term))
$batchPmids = @($es.esearchresult.idlist)

# ---------- 3. esummary → 每篇 publication type + DOI（连接键 = DOI）----------
$batchByDoi   = @{}   # doi(小写) -> pubtype[]
$batchByTitle = @{}   # 归一标题  -> pubtype[]
for ($i = 0; $i -lt $batchPmids.Count; $i += 180) {
  $chunk = @($batchPmids[$i..([Math]::Min($i + 179, $batchPmids.Count - 1))])
  if (-not $chunk) { continue }
  $sum = Eutils-Get 'esummary.fcgi' ("db=pubmed&retmode=json&id=" + ($chunk -join ','))
  foreach ($pmid in $chunk) {
    $rec = $sum.result.$pmid
    if (-not $rec) { continue }
    $pt = @($rec.pubtype)
    $doi = ''
    foreach ($aid in @($rec.articleids)) { if ($aid.idtype -eq 'doi') { $doi = "$($aid.value)".ToLower().Trim(); break } }
    if ($doi) { $batchByDoi[$doi] = $pt }
    $nt = Get-NormTitle $rec.title
    if ($nt) { $batchByTitle[$nt] = $pt }
  }
  Start-Sleep -Milliseconds 350   # NCBI 礼貌限速
}

# ---------- 4. 匹配 Zotero 条目到批次 + 分流 ----------
foreach ($r in $live) {
  $pt = $null
  if ($r.Doi -and $batchByDoi.ContainsKey($r.Doi)) { $pt = $batchByDoi[$r.Doi] }
  else {
    $nt = Get-NormTitle $r.Title
    if ($nt -and $batchByTitle.ContainsKey($nt)) { $pt = $batchByTitle[$nt] }
  }
  if ($null -ne $pt) { $r.批次 = $true; $r.Pub = $pt }
  $r.分流 = Get-Bucket $r.Pub $r.Type
}
$matched   = @($live | Where-Object { $_.批次 }).Count
$batchInfo = "PubMed〔{0} {1}〕共 {2} 篇 · Zotero 匹配 {3} 篇" -f $Journal, $Month, $batchPmids.Count, $matched

# ---------- 5. 三类分流输出（批次条目 + 任何非文献垃圾项）----------
$scope = @($live | Where-Object { $_.批次 -or ($articleTypes -notcontains $_.Type) })
Write-Host ''
Write-Host "[批次] $batchInfo" -ForegroundColor Green

foreach ($bk in '保留候选', '短文候选', '清理候选') {
  $rows = @($scope | Where-Object { $_.分流 -eq $bk })
  Write-Host ''
  Write-Host ("-- {0} · {1} 篇 --" -f $bk, $rows.Count) -ForegroundColor Yellow
  if ($rows.Count -gt 0) {
    $rows | Select-Object `
      @{ n = 'Key'; e = { $_.Key } }, `
      @{ n = 'PDF'; e = { if ($_.PdfN -gt 0) { 'OK' } else { '-' } } }, `
      @{ n = 'PubType'; e = { if ($_.Pub.Count) { (@($_.Pub) | Where-Object { $_ -ne 'Journal Article' -and $_ -notmatch '^Research Support' }) -join ',' } else { '(未匹配)' } } }, `
      @{ n = 'Title'; e = { $_.Title } } |
      Sort-Object Title | Format-Table -AutoSize -Wrap
  }
}

# ---------- 6. 重复检测（跨全库 + 回收站，并查集）----------
$dedupSet = @($live) + @($trash)
$parent = @{}
foreach ($r in $dedupSet) { $parent[$r.Key] = $r.Key }
function Resolve-Root($k) { while ($parent[$k] -ne $k) { $k = $parent[$k] }; $k }
function Join-Keys($a, $b) { $ra = Resolve-Root $a; $rb = Resolve-Root $b; if ($ra -ne $rb) { $parent[$ra] = $rb } }
foreach ($field in 'Doi', 'Pmid') {
  foreach ($g in ($dedupSet | Where-Object { $_.$field } | Group-Object $field | Where-Object { $_.Count -gt 1 })) {
    $ks = @($g.Group.Key); for ($i = 1; $i -lt $ks.Count; $i++) { Join-Keys $ks[0] $ks[$i] }
  }
}
foreach ($g in ($dedupSet | Where-Object { Get-NormTitle $_.Title } |
      Group-Object { Get-NormTitle $_.Title } | Where-Object { $_.Count -gt 1 })) {
  $ks = @($g.Group.Key); for ($i = 1; $i -lt $ks.Count; $i++) { Join-Keys $ks[0] $ks[$i] }
}
$liveKeys = @{}; foreach ($r in $live) { $liveKeys[$r.Key] = $true }
$clusters = @($dedupSet | Group-Object { Resolve-Root $_.Key } | Where-Object { $_.Count -gt 1 })
Write-Host ''
Write-Host ("-- 重复条目 · {0} 簇（全库 + 回收站）--" -f $clusters.Count) -ForegroundColor Yellow
foreach ($c in $clusters) {
  $doivals  = @($c.Group | ForEach-Object Doi  | Where-Object { $_ } | Select-Object -Unique)
  $pmidvals = @($c.Group | ForEach-Object Pmid | Where-Object { $_ } | Select-Object -Unique)
  $basis = if ($doivals.Count -eq 1) { 'DOI 相同' }
           elseif ($doivals.Count -eq 0 -and $pmidvals.Count -eq 1) { 'PMID 相同' }
           else { '仅标题相同 · PI 确认' }
  Write-Host ("  [{0}]" -f $basis)
  foreach ($m in $c.Group) {
    $loc = if ($liveKeys.ContainsKey($m.Key)) { '库内' } else { '回收站' }
    Write-Host ("    {0}  ({1})  {2}" -f $m.Key, $loc, $m.Title)
  }
}

# ---------- 7. 摘要 ----------
Write-Host ''
Write-Host '=== 摘要 ===' -ForegroundColor Cyan
Write-Host "  $batchInfo"
$scriptN = @($liveTop | Where-Object { $_.data.tags.tag -contains 'mecha-import' }).Count
Write-Host ("  来源  脚本导入(mecha-import) {0} · 其它/Connector 补录 {1}" -f $scriptN, ($liveTop.Count - $scriptN))
$cKeep   = @($scope | Where-Object { $_.分流 -eq '保留候选' }).Count
$cShort  = @($scope | Where-Object { $_.分流 -eq '短文候选' }).Count
$cClean  = @($scope | Where-Object { $_.分流 -eq '清理候选' }).Count
$cPdf    = @($scope | Where-Object { $_.PdfN -gt 0 }).Count
$unmatch = @($scope | Where-Object { ($articleTypes -contains $_.Type) -and $_.Pub.Count -eq 0 }).Count
$offBatch = @($live | Where-Object { -not $_.批次 -and ($articleTypes -contains $_.Type) }).Count
Write-Host ("  分流范围条目  {0}" -f $scope.Count)
Write-Host ("  保留候选      {0}" -f $cKeep)
Write-Host ("  短文候选      {0}" -f $cShort)
Write-Host ("  清理候选      {0}" -f $cClean)
Write-Host ("  重复簇        {0}" -f $clusters.Count)
Write-Host ("  PDF 到位      {0} / {1}" -f $cPdf, $scope.Count)
if ($batchPmids.Count -gt $matched) {
  $inTrash = @($trash | Where-Object {
      ($_.Doi -and $batchByDoi.ContainsKey($_.Doi)) -or
      ((Get-NormTitle $_.Title) -and $batchByTitle.ContainsKey((Get-NormTitle $_.Title)))
    }).Count
  $missing = $batchPmids.Count - $matched - $inTrash
  if ($inTrash -gt 0) { Write-Host ("  本批另有 {0} 篇在回收站（清理候选已移入）" -f $inTrash) }
  if ($missing -gt 0) { Write-Host ("  本批 {0} 篇未在 Zotero（可能漏导）" -f $missing) -ForegroundColor Yellow }
}
if ($offBatch -gt 0) { Write-Host ("  库内另有 {0} 篇非本批文献" -f $offBatch) -ForegroundColor Yellow }
if ($unmatch -gt 0)  { Write-Host ("  未匹配 PubMed 未核 {0} 篇" -f $unmatch) -ForegroundColor Yellow }
