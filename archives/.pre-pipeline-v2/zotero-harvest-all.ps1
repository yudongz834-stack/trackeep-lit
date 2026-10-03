# 历史档案：原文保留（含旧品牌与历史路径，勿改史实）；批B 2026-10-03 归档注记
<#
  zotero-harvest-all.ps1 — 批量编排：对「一批期刊」循环跑采集(zotero-harvest) + 年月归档(zotero-shelve-by-date)。
  一条指令完成多刊。唯一性/去重由子脚本各自保证；本脚本只负责选刊、循环、汇总。

  选刊优先级：-Journals（显式刊名列表）> -Category（某来源分类下全部刊）> 默认（全部刊）。
  纪律：默认干跑预览；-Apply 才真写。子脚本只新建不改旧。

  用法：
    powershell -File zotero-harvest-all.ps1 -Category "胸部肿瘤与胸外科"               # 干跑：胸外全部刊，本月增量
    powershell -File zotero-harvest-all.ps1 -Category "胸部肿瘤与胸外科" -Apply        # 真跑
    powershell -File zotero-harvest-all.ps1 -Journals "J Thorac Oncol","Lung Cancer" -Year 2024 -Apply   # 指定刊、拉 2024 整年
    powershell -File zotero-harvest-all.ps1 -Apply                                     # 全部 79 刊（慎用）
#>
[CmdletBinding()]
param(
  [string]$Category,
  [string[]]$Journals,
  [int]$Year = 0,
  [int]$ReldateDays = 45,
  [int]$MaxImport = 500,
  [switch]$Apply,
  [switch]$NoShelve
)
$ErrorActionPreference = 'Stop'
try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 } catch {}
$harvest = Join-Path $PSScriptRoot 'zotero-harvest.ps1'
$shelve  = Join-Path $PSScriptRoot 'zotero-shelve-by-date.ps1'

# --- env + 取全部 collection ---
$EnvFile = Join-Path $env:USERPROFILE '.config\mecha\secrets\zotero.env'
$cfg = @{}; foreach ($l in (Get-Content $EnvFile)) { $t = $l.Trim(); if (-not $t -or $t.StartsWith('#')) { continue }; $i = $t.IndexOf('='); if ($i -lt 1) { continue }; $cfg[$t.Substring(0, $i).Trim()] = $t.Substring($i + 1).Trim().Trim(' ', '<', '>', '"', "'") }
$hR = @{ 'Zotero-API-Version' = '3'; 'Zotero-API-Key' = $cfg['ZOTERO_API_KEY'] }; $uid = $cfg['ZOTERO_USER_ID']
$col = (Invoke-WebRequest -Uri "https://api.zotero.org/users/$uid/collections?limit=100" -Headers $hR -UseBasicParsing -TimeoutSec 60)
$cols = ConvertFrom-Json ([Text.Encoding]::UTF8.GetString($col.RawContentStream.ToArray()))

# 顶层 = 来源分类；其子 = 期刊；期刊之子(年/月)排除在采集目标外
$catKeys = @{}; foreach ($c in $cols) { if (-not $c.data.parentCollection) { $catKeys[$c.key] = $c.data.name } }
$journalsAll = @($cols | Where-Object { $catKeys.ContainsKey("$($_.data.parentCollection)") })
$name2key = @{}; foreach ($j in $journalsAll) { $name2key[$j.data.name] = $j.key }

# --- 选刊 ---
if ($Journals) {
  # 容错：-File 调用会把 "A","B" 压成 "A,B" 单串 → 统一按逗号拆开
  $targets = @($Journals | ForEach-Object { $_ -split ',' } | ForEach-Object { $_.Trim() } | Where-Object { $_ })
} elseif ($Category) {
  $catKey = ($catKeys.GetEnumerator() | Where-Object { $_.Value -eq $Category }).Key
  if (-not $catKey) { throw "找不到来源分类「$Category」" }
  $targets = @($journalsAll | Where-Object { $_.data.parentCollection -eq $catKey } | ForEach-Object { $_.data.name } | Sort-Object)
} else {
  $targets = @($journalsAll | ForEach-Object { $_.data.name } | Sort-Object)
}
$scope = if ($Year -gt 0) { "$Year 整年" } else { "近 $ReldateDays 天增量" }
$mode = if ($Apply) { 'APPLY（真写）' } else { 'DRY-RUN（仅预览）' }
Write-Host "==== 批量采集 · $mode · $scope · 共 $($targets.Count) 本刊 ====`n"

# --- 循环 ---
$rows = @()
foreach ($j in $targets) {
  Write-Host "--- $j ---"
  $a = @('-ExecutionPolicy', 'Bypass', '-File', $harvest, '-Journal', $j, '-ReldateDays', "$ReldateDays", '-MaxImport', "$MaxImport")
  if ($Year -gt 0) { $a += @('-Year', "$Year") }
  if ($Apply) { $a += '-Apply' }
  $out = & powershell @a 2>&1 | ForEach-Object { "$_" }
  $found = 0; $dup = 0; $new = 0; $imp = 0
  ($out | Where-Object { $_ -match 'found=(\d+) dup=(\d+) new=(\d+)' } | Select-Object -First 1) | Out-Null
  foreach ($ln in $out) {
    if ($ln -match 'found=(\d+) dup=(\d+) new=(\d+)') { $found = [int]$matches[1]; $dup = [int]$matches[2]; $new = [int]$matches[3] }
    if ($ln -match '导入完成：(\d+)') { $imp = [int]$matches[1] }
    if ($ln -match '命中：(\d+)') { } # 已含在 found
  }
  # 归档（真写 + 有导入 + 未禁用）
  if ($Apply -and -not $NoShelve -and $imp -gt 0 -and $name2key.ContainsKey($j)) {
    & powershell -ExecutionPolicy Bypass -File $shelve -CollectionKey $name2key[$j] -Apply 2>&1 | Out-Null
  }
  $rows += [pscustomobject]@{ 刊 = $j; PubMed命中 = $found; 撞库去重 = $dup; 新增 = $new; 已导入 = $imp }
  Start-Sleep -Milliseconds 300
}

# --- 汇总 ---
Write-Host "`n==== 汇总 ===="
$rows | Format-Table -AutoSize | Out-String | Write-Host
$tNew = ($rows | Measure-Object 新增 -Sum).Sum
$tImp = ($rows | Measure-Object 已导入 -Sum).Sum
Write-Host ("合计：命中 {0}、去重 {1}、新增 {2}、导入 {3}" -f ($rows | Measure-Object PubMed命中 -Sum).Sum, ($rows | Measure-Object 撞库去重 -Sum).Sum, $tNew, $tImp)
if (-not $Apply) { Write-Host "`n（预览，未写。确认范围无误后加 -Apply 真跑。）" }