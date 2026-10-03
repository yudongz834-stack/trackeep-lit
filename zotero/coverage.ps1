<#
  coverage.ps1 — 核心期刊覆盖率自检（只读）

  核对 74 本核心期刊的「期刊表「推荐目录名」 ↔ Zotero collection ↔ PubMed [TA] 可检索性」三者一致，
  抓出漏配（缺 collection）与错配（刊名与 PubMed [TA] 不符）。

  纯只读：只 GET Zotero + PubMed，不写任何文件、不 POST/PATCH/DELETE。

  用法
    pwsh -NoProfile -File zotero\coverage.ps1
#>
$ErrorActionPreference = 'Stop'
try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 } catch {}

# --- secret ---（照抄 import.ps1）
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

# --- helpers ---（照抄 import.ps1）
function Get-Utf8($r) { [System.Text.Encoding]::UTF8.GetString($r.RawContentStream.ToArray()) }
function Eutils($fn, $q) { $u = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/$fn`?$q&tool=trackeep-zotero-import"; Invoke-WebRequest -Uri $u -UseBasicParsing -TimeoutSec 120 }
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

# --- 解析期刊表 →「推荐目录名」列表 ---
# 表格式：| 来源分类 | 期刊全名 | PubMed 缩写 | 推荐目录名 | 备注 |
# 「推荐目录名」= PubMed [TA] 检索名 = Zotero collection 名 —— 三者核对的键。
$TablePath = 'E:\Trackeep-Obsidian\00-系统\期刊来源表.md'
if (-not (Test-Path -LiteralPath $TablePath)) { throw "缺期刊表：$TablePath" }
$journals = New-Object System.Collections.Generic.List[string]
$inTable = $false
foreach ($l in (Get-Content -LiteralPath $TablePath -Encoding UTF8)) {
  if ($l -match '^##\s') {
    if ($inTable) { break }                       # 进入表区后遇到下一个 ## 标题（## 收录统计）即结束
    if ($l -match '期刊登记表') { $inTable = $true }
    continue
  }
  if (-not $inTable) { continue }
  $line = $l.Trim()
  if (-not $line.StartsWith('|')) { continue }     # 只处理表格行
  $cells = $line -split '\|'                        # 切分后首尾为空串；数据列从 cells[1] 起
  if ($cells.Count -lt 5) { continue }              # 不足 4 数据列 → 跳过
  if ($cells[1] -match '来源分类') { continue }     # 表头行
  if ($cells[1].Trim() -match '^-+$') { continue }  # 分隔行（---）
  $name = $cells[4].Trim()                          # 第 4 数据列 = 推荐目录名
  if ($name) { $journals.Add($name) }
}
Write-Host ("期刊表解析: {0} 本（预期 74）" -f $journals.Count) -ForegroundColor Cyan

# --- Zotero collection 名集合 ---
$cols = @(Zot-GetAll '/collections')
$colSet = @{}
foreach ($c in $cols) { $n = "$($c.data.name)".Trim(); if ($n) { $colSet[$n] = $true } }
Write-Host ("Zotero collection: {0} 个" -f $colSet.Count) -ForegroundColor Cyan

# --- 逐刊核对：collection 命中 + PubMed [TA] 宽检索 ---
$missing = @(); $mismatch = @(); $normal = 0
foreach ($name in $journals) {
  $hasCollection = $colSet.ContainsKey($name)
  $broadQuery = "db=pubmed&retmode=json&retmax=0&term=" + [uri]::EscapeDataString('"' + $name + '"[TA]')
  $es = ConvertFrom-Json (Get-Utf8 (Eutils 'esearch.fcgi' $broadQuery))
  $count = [int]"$($es.esearchresult.count)"
  Start-Sleep -Milliseconds 350                     # NCBI 礼貌限速
  if (-not $hasCollection) {
    $missing += [pscustomobject]@{ Name = $name; Count = $count }
  } elseif ($count -eq 0) {
    $mismatch += [pscustomobject]@{ Name = $name; Count = $count }
  } else {
    $normal++
  }
}

# --- 输出（两张问题清单逐条列刊名 + count；正常只报数）---
Write-Host ''
Write-Host ("=== 缺 collection ({0}) ===" -f $missing.Count) -ForegroundColor Yellow
foreach ($m in $missing) { Write-Host ("  {0,-42} [TA]={1}" -f $m.Name, $m.Count) }
Write-Host ("=== 疑似刊名错配 ({0}) ===" -f $mismatch.Count) -ForegroundColor Yellow
foreach ($m in $mismatch) { Write-Host ("  {0,-42} [TA]=0" -f $m.Name) }
Write-Host ''
Write-Host ("{0} = 正常 {1} / 缺collection {2} / 疑似错配 {3}" -f $journals.Count, $normal, $missing.Count, $mismatch.Count) -ForegroundColor Green
