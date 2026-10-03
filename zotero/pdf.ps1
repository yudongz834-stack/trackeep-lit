<#
  pdf.ps1 — 由文献标识符解析出其 PDF 在 Zotero 本地 storage 的绝对路径。

  用途：PI 不手动搬 PDF。给 Zotero item key / DOI / PMID / 标题 之一，本脚本只读
        Zotero Web API 定位条目 → 找 PDF 附件 → 拼出本地路径，供 forge-docling 原地读取。

  纪律：只 GET；不写 Zotero、不动条目、不碰 zotero.sqlite。API key 仅用于 HTTP 头、不回显。

  用法：
    pwsh -NoProfile -File zotero\pdf.ps1 "<Zotero key / DOI / PMID / 标题>"
  输出：`PDF=<绝对路径>` + `EXISTS=<True|False>`；多命中时列候选、不猜。
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory = $true, Position = 0)]
  [string]$Query,
  [string]$ZoteroDataDir
)
$ErrorActionPreference = 'Stop'
try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 } catch {}

# --- env（脚本是唯一接触 key 的边界）---
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
function Get-ZoteroDataDir {
  # 读 Zotero 自己的 profile 配置，返回本机真实数据目录；解析不出返回 $null。
  # 不写死盘符 —— 同一脚本同步到不同盘符的机器（如家用机 E 盘 / 工作机 C 盘）各读各的、自动对上。
  try {
    $root = Join-Path $env:APPDATA 'Zotero\Zotero'
    $profilesIni = Join-Path $root 'profiles.ini'
    if (-not (Test-Path -LiteralPath $profilesIni)) { return $null }
    $blocks = (Get-Content -LiteralPath $profilesIni -Raw) -split '(?m)^\['
    $chosen = $null; $first = $null
    foreach ($b in $blocks) {
      if ($b -notmatch '^Profile') { continue }
      $isRel = if ($b -match '(?m)^IsRelative=(\d)') { $matches[1] } else { '1' }
      $path  = if ($b -match '(?m)^Path=(.+?)\s*$') { $matches[1] } else { $null }
      if (-not $path) { continue }
      $full  = if ($isRel -eq '1') { Join-Path $root ($path -replace '/', '\') } else { $path }
      if (-not $first) { $first = $full }
      if ($b -match '(?m)^Default=1') { $chosen = $full }
    }
    $prof = if ($chosen) { $chosen } else { $first }
    if (-not $prof) { return $null }
    $prefs = Join-Path $prof 'prefs.js'
    if (-not (Test-Path -LiteralPath $prefs)) { return $null }
    $useCustom = $true; $dataDir = $null
    foreach ($ln in (Get-Content -LiteralPath $prefs)) {
      if ($ln -match 'extensions\.zotero\.useDataDir"\s*,\s*(true|false)') { $useCustom = ($matches[1] -eq 'true') }
      if ($ln -match 'extensions\.zotero\.dataDir"\s*,\s*"(.+?)"\s*\)')     { $dataDir   = $matches[1] -replace '\\\\', '\' }
    }
    if ($useCustom -and $dataDir) { return $dataDir }
    return $null   # 未用自定义目录 → 交给默认 %USERPROFILE%\Zotero
  } catch { return $null }
}

if (-not $ZoteroDataDir) {
  # 优先级：命令行参数 > 自动解析(prefs.js) > env 覆写 > Zotero 默认目录
  $ZoteroDataDir = Get-ZoteroDataDir
  if (-not $ZoteroDataDir) { $ZoteroDataDir = $cfg['ZOTERO_DATA_DIR'] }
  if (-not $ZoteroDataDir) { $ZoteroDataDir = Join-Path $env:USERPROFILE 'Zotero' }
}
$storage = Join-Path $ZoteroDataDir 'storage'
$base    = "https://api.zotero.org/users/$userId"
$hRead   = @{ 'Zotero-API-Version' = '3'; 'Zotero-API-Key' = $apiKey }

function Get-Utf8($resp) { [System.Text.Encoding]::UTF8.GetString($resp.RawContentStream.ToArray()) }
function Zot-Get($path) {
  $r = Invoke-WebRequest -Uri "$base$path" -Headers $hRead -UseBasicParsing -TimeoutSec 60
  ConvertFrom-Json -InputObject (Get-Utf8 $r)
}

# --- 1. 定位顶层条目 ---
$q = $Query.Trim()
$item = $null
if ($q -cmatch '^[A-Z0-9]{8}$') {
  try { $item = Zot-Get "/items/$q" }
  catch { throw "未找到 Zotero key=$q 的条目。" }
} else {
  $enc  = [uri]::EscapeDataString($q)
  $hitsRaw = Zot-Get "/items?q=$enc&qmode=everything&itemType=-attachment&limit=50"
  $hits = @(); foreach ($h in $hitsRaw) { $hits += $h }
  $hits = @($hits | Where-Object { $_.data.itemType -ne 'note' })
  if ($hits.Count -eq 0) { throw "未找到匹配「$q」的条目。" }
  $exact = @($hits | Where-Object {
      ($_.data.DOI -and $_.data.DOI.ToLower() -eq $q.ToLower()) -or
      ($_.data.extra -and $_.data.extra -match "(?im)PMID:\s*$([regex]::Escape($q))\b")
    })
  if     ($exact.Count -eq 1) { $item = $exact[0] }
  elseif ($hits.Count  -eq 1) { $item = $hits[0] }
  else {
    Write-Host ("命中 {0} 条，未能唯一确定 —— 从下列取 Zotero key 重跑：" -f $hits.Count)
    foreach ($h in $hits) { Write-Host ("  {0}  {1} ({2})" -f $h.key, $h.data.title, $h.data.date) }
    return
  }
}
$itemKey = $item.key
Write-Host ("条目：{0}  [{1}]" -f $item.data.title, $itemKey)

# --- 2. 找 PDF 附件 ---
# ConvertFrom-Json 的数组经函数返回后 @() 不会展开 → 用 foreach 强制摊平
$childrenRaw = Zot-Get "/items/$itemKey/children"
$children = @(); foreach ($c in $childrenRaw) { $children += $c }
$pdfs = @($children | Where-Object {
    $_.data.itemType -eq 'attachment' -and
    ($_.data.contentType -eq 'application/pdf' -or $_.data.filename -match '\.pdf$')
  })
if ($pdfs.Count -eq 0) { throw "条目无 PDF 附件 —— 先在 Zotero 里确认该文献已抓到 PDF。" }
if ($pdfs.Count -gt 1) { Write-Host ("注意：{0} 个 PDF 附件，取第 1 个。" -f $pdfs.Count) }
$pdf = $pdfs[0]

# --- 3. 拼本地路径 ---
if ($pdf.data.linkMode -eq 'linked_file' -and $pdf.data.path) {
  $path = $pdf.data.path
} else {
  $path = Join-Path (Join-Path $storage $pdf.key) $pdf.data.filename
}
$exists = Test-Path -LiteralPath $path
Write-Host ("PDF={0}" -f $path)
Write-Host ("EXISTS={0}" -f $exists)
if (-not $exists) {
  Write-Host "文件不在本地 —— 该附件可能仅云端、未下载（查 Zotero 同步 / 下载设置）。"
}
