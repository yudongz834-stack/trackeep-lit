<#
  shelve-by-date.ps1 — 把某期刊 collection 下的条目，按各自 date 字段归入 年/月 子集。
  对应 Trackeep-Memex 元宪法 §5「期刊/年/月」层级在 Zotero 侧的镜像（靠条目自身日期分桶）。

  纪律：只新增 collection；只往条目的 collections 数组「追加」年月子集 —— 不移除原期刊归属、
        不改任何其它字段、不删条目。API key 仅入 HTTP 头、不回显。
        默认「干跑预览」，加 -Apply 才真写。

  用法：
    pwsh -NoProfile -File zotero\shelve-by-date.ps1                          # 干跑预览（默认 J Thorac Oncol）
    pwsh -NoProfile -File zotero\shelve-by-date.ps1 -Apply                   # 真写
    pwsh -NoProfile -File zotero\shelve-by-date.ps1 -CollectionKey <KEY> -Apply
#>
[CmdletBinding()]
param(
  [string]$CollectionKey = '2HID2MQK',   # 默认 J Thorac Oncol
  [switch]$Apply
)
$ErrorActionPreference = 'Stop'
try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 } catch {}

# --- env（脚本是唯一接触 key 的边界）---
$EnvFile = Join-Path $env:USERPROFILE '.config\trackeep\secrets\zotero.env'
if (-not (Test-Path -LiteralPath $EnvFile)) { throw "secret 不存在：$EnvFile" }
$cfg = @{}
foreach ($line in (Get-Content -LiteralPath $EnvFile)) {
  $t = $line.Trim(); if (-not $t -or $t.StartsWith('#')) { continue }
  $i = $t.IndexOf('='); if ($i -lt 1) { continue }
  $cfg[$t.Substring(0, $i).Trim()] = $t.Substring($i + 1).Trim().Trim(' ', '<', '>', '"', "'")
}
$apiKey = $cfg['ZOTERO_API_KEY']; $userId = $cfg['ZOTERO_USER_ID']
if (-not $apiKey -or -not $userId) { throw 'zotero.env 缺 ZOTERO_API_KEY / ZOTERO_USER_ID' }
$base  = "https://api.zotero.org/users/$userId"
$hRead = @{ 'Zotero-API-Version' = '3'; 'Zotero-API-Key' = $apiKey }

function Get-Utf8($resp) { [Text.Encoding]::UTF8.GetString($resp.RawContentStream.ToArray()) }
function Zot-Get($path) {
  $r = Invoke-WebRequest -Uri "$base$path" -Headers $hRead -UseBasicParsing -TimeoutSec 60
  ConvertFrom-Json -InputObject (Get-Utf8 $r)
}
function New-ZotCollection($name, $parentKey) {
  # 手拼 JSON 数组，规避 PS5.1 单元素数组被展开成对象的坑
  $body = '[{"name":' + (ConvertTo-Json -InputObject $name) + ',"parentCollection":"' + $parentKey + '"}]'
  $h = $hRead.Clone(); $h['Zotero-Write-Token'] = ([guid]::NewGuid().ToString('N')); $h['Content-Type'] = 'application/json'
  $r = Invoke-WebRequest -Uri "$base/collections" -Headers $h -Method Post -Body $body -UseBasicParsing -TimeoutSec 60
  $j = ConvertFrom-Json -InputObject (Get-Utf8 $r)
  if ($j.failed -and $j.failed.PSObject.Properties.Count -gt 0) { throw "建 collection 失败：$($j | ConvertTo-Json -Compress)" }
  $k = $j.successful.'0'.key; if (-not $k) { $k = $j.success.'0' }
  if (-not $k) { throw "建 collection 未返回 key：$($j | ConvertTo-Json -Compress)" }
  return $k
}
function Add-ItemColl($itemKey, $version, $colls) {
  $collsJson = '[' + (($colls | ForEach-Object { '"' + $_ + '"' }) -join ',') + ']'
  $body = '{"collections":' + $collsJson + '}'
  $h = $hRead.Clone(); $h['If-Unmodified-Since-Version'] = "$version"; $h['Content-Type'] = 'application/json'
  Invoke-WebRequest -Uri "$base/items/$itemKey" -Headers $h -Method Patch -Body $body -UseBasicParsing -TimeoutSec 60 | Out-Null
}

# --- 日期分桶（年 + 月；口径同 vault：刊期日期）---
$mon = @{ Jan='01';Feb='02';Mar='03';Apr='04';May='05';Jun='06';Jul='07';Aug='08';Sep='09';Oct='10';Nov='11';Dec='12' }
function Parse-YM($d) {
  if (-not $d) { return $null }
  if ($d -notmatch '(\d{4})') { return $null }
  $y = $matches[1]; $m = $null
  if ($d -match "$y[-/](\d{1,2})") { $m = '{0:D2}' -f [int]$matches[1] }
  elseif ($d -match '(?i)\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)') { $m = $mon[$matches[1].Substring(0,3)] }
  [pscustomobject]@{ Year = $y; Month = $m }
}

# --- 1. 期刊名 + 现有全部 collection（建「名@父→key」索引）---
$journal = Zot-Get "/collections/$CollectionKey"
Write-Host ("期刊 collection：{0}  [{1}]" -f $journal.data.name, $CollectionKey)
$allCols = Zot-Get "/collections?limit=100"
$index = @{}
foreach ($c in $allCols) { $index["$($c.data.name)@$($c.data.parentCollection)"] = $c.key }
function Find-Sub($name, $parentKey) { if ($parentKey) { $index["$name@$parentKey"] } else { $null } }

# --- 2. 顶层条目（带 version / collections / date；翻页拉全——limit=100 单页会静默漏尾巴，实测 2026-10-04 JTO 132 条坐实）---
$items = @(); $s = 0
while ($true) {
  $pg = @(Zot-Get "/collections/$CollectionKey/items/top?itemType=-attachment&limit=100&start=$s")
  $items += $pg
  if ($pg.Count -lt 100) { break }
  $s += 100
}
Write-Host ("条目数：{0}" -f $items.Count)
$mode = if ($Apply) { 'APPLY（真写）' } else { 'DRY-RUN（仅预览，未写）' }
Write-Host "==== 模式：$mode ====`n"

# --- 3. 规划 ---
$plan = @()
foreach ($it in $items) {
  $ym = Parse-YM $it.data.date
  $plan += [pscustomobject]@{
    Key = $it.key; Ver = $it.version; Colls = @($it.data.collections)
    Title = $it.data.title; Year = $(if ($ym) { $ym.Year }); Month = $(if ($ym) { $ym.Month }); Raw = $it.data.date
  }
}
$years = $plan | Where-Object Year | Select-Object -ExpandProperty Year -Unique | Sort-Object

# --- 4. 建 年 / 月 子集（缺才建）---
$createdCount = 0; $ymKey = @{}
foreach ($y in $years) {
  $yKey = Find-Sub $y $CollectionKey
  if (-not $yKey) {
    if ($Apply) { $yKey = New-ZotCollection $y $CollectionKey; $index["$y@$CollectionKey"] = $yKey }
    Write-Host ("  [+年] {0}" -f $y); $createdCount++
  }
  $ymKey[$y] = $yKey
  $months = $plan | Where-Object { $_.Year -eq $y -and $_.Month } | Select-Object -ExpandProperty Month -Unique | Sort-Object
  foreach ($m in $months) {
    $mKey = Find-Sub $m $yKey
    if (-not $mKey) {
      if ($Apply -and $yKey) { $mKey = New-ZotCollection $m $yKey; $index["$m@$yKey"] = $mKey }
      Write-Host ("  [+月] {0}/{1}" -f $y, $m); $createdCount++
    }
    $ymKey["$y-$m"] = $mKey
  }
}

# --- 5. 条目归位（追加，不移除原归属）---
$assign = 0; $skip = 0; $noDate = 0
foreach ($p in $plan) {
  if (-not $p.Year) { $noDate++; Write-Host ("  [无日期] {0}" -f $p.Title); continue }
  $target = if ($p.Month) { $ymKey["$($p.Year)-$($p.Month)"] } else { $ymKey[$p.Year] }
  if ($Apply) {
    if (-not $target) { Write-Host "  [!] 目标子集缺失，跳过：$($p.Title)"; continue }
    if ($p.Colls -contains $target) { $skip++; continue }
    Add-ItemColl $p.Key $p.Ver @($p.Colls + $target | Select-Object -Unique)
    $assign++
  } else {
    if ($target -and ($p.Colls -contains $target)) { $skip++ } else { $assign++ }
  }
}

Write-Host ""
Write-Host ("子集 需新建：{0}" -f $createdCount)
Write-Host ("条目 待归位：{0}   已在位(跳过)：{1}   无日期：{2}" -f $assign, $skip, $noDate)
if (-not $Apply) { Write-Host "`n（这是预览，未写任何东西。确认无误后加 -Apply 真写。）" }
