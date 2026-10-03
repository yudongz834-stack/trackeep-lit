<#
  zotero-pull.ps1 — Zotero Web API v3 只读拉取器
  Zotero ⇄ Trackeep-Memex 整合方案 v1 · 构建步骤 §9.3

  做什么
    加载本机 secret，连 Zotero 读取 collections 与顶层条目元数据，
    写出脱敏 JSON 缓存 .trackeep/zotero-pull.json，
    供后续生成 zotero-memex-map.json 与文献主卡使用。

  纪律
    · 只读：只发 GET 请求，不写 Zotero，不触碰 zotero.sqlite。
    · API key 仅用于 HTTP 请求头，绝不写入输出文件 / 日志 / 屏幕。
    · secret 唯一来源：%USERPROFILE%\.config\trackeep\secrets\zotero.env

  用法
    pwsh -NoProfile -ExecutionPolicy Bypass -File zotero-pull.ps1 -Probe   仅 collections + 计数（快）
    pwsh -NoProfile -ExecutionPolicy Bypass -File zotero-pull.ps1          含全部顶层条目（慢）
#>
param([switch]$Probe)

$ErrorActionPreference = 'Stop'
try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 } catch {}

$EnvFile = Join-Path $env:USERPROFILE '.config\trackeep\secrets\zotero.env'
$McDir   = Join-Path $PSScriptRoot '..\.trackeep'
$OutFile = Join-Path $McDir 'zotero-pull.json'

# --- 1. 加载 secret（容错：跳注释/空行；去值两端空白与误留的 <> 引号）---
if (-not (Test-Path -LiteralPath $EnvFile)) { throw "secret 文件不存在：$EnvFile" }
$cfg = @{}
foreach ($line in (Get-Content -LiteralPath $EnvFile)) {
  $t = $line.Trim()
  if (-not $t -or $t.StartsWith('#')) { continue }
  $i = $t.IndexOf('=')
  if ($i -lt 1) { continue }
  $cfg[$t.Substring(0, $i).Trim()] = $t.Substring($i + 1).Trim().Trim(' ', '<', '>', '"', "'")
}
$apiKey = $cfg['ZOTERO_API_KEY']
$userId = $cfg['ZOTERO_USER_ID']
if (-not $apiKey) { throw 'zotero.env 缺 ZOTERO_API_KEY' }
if (-not $userId) { throw 'zotero.env 缺 ZOTERO_USER_ID' }
if ($userId -notmatch '^\d+$') {
  throw "ZOTERO_USER_ID 须为纯数字 API userID（当前值不是数字）。见 zotero.org/settings/security 上 'Your user ID for use in API calls is ...'。"
}

# --- 2. API 基础 ---
$base    = "https://api.zotero.org/users/$userId"
$headers = @{ 'Zotero-API-Version' = '3'; 'Zotero-API-Key' = $apiKey }

function Get-Header($resp, $name) {
  foreach ($k in $resp.Headers.Keys) { if ($k -ieq $name) { return [string]$resp.Headers[$k] } }
  return $null
}

# 把响应体按 UTF-8 正确解码（PS 5.1 默认会按 Latin-1 误解码中文 → 乱码）
function ConvertTo-Utf8Text($resp) {
  try {
    return [System.Text.Encoding]::UTF8.GetString($resp.RawContentStream.ToArray())
  } catch {
    return [System.Text.Encoding]::UTF8.GetString([System.Text.Encoding]::GetEncoding(28591).GetBytes($resp.Content))
  }
}

# 取一页：UTF-8 解码 + 数组规整 + 头信息
function Get-ZoteroPage([string]$path, [string]$query) {
  $u = $base + $path
  if ($query) { $u = $u + '?' + $query }
  $resp = Invoke-WebRequest -Uri $u -Headers $headers -UseBasicParsing -TimeoutSec 90
  $data = ConvertFrom-Json -InputObject (ConvertTo-Utf8Text $resp)
  if ($null -eq $data)       { $rows = @() }
  elseif ($data -is [array]) { $rows = $data }
  else                       { $rows = @($data) }
  [pscustomobject]@{
    rows    = $rows
    total   = [int](Get-Header $resp 'Total-Results')
    version = [int](Get-Header $resp 'Last-Modified-Version')
    backoff = [int](Get-Header $resp 'Backoff')
  }
}

# --- 3. 验证凭证 + 读库版本/计数 ---
Write-Host '[1/4] 验证 Zotero 凭证 ...'
try { $p0 = Get-ZoteroPage '/items/top' 'limit=1' }
catch { throw "连接 Zotero 失败：$($_.Exception.Message)" }
$libVersion = $p0.version
$totalItems = $p0.total
Write-Host ("      OK · userID {0} · 库版本 {1} · 顶层条目 {2}" -f $userId, $libVersion, $totalItems)

# --- 4. collections（全量分页）---
Write-Host '[2/4] 拉取 collections ...'
$collections = New-Object System.Collections.Generic.List[object]
$start = 0
while ($true) {
  $pg = Get-ZoteroPage '/collections' ("limit=100&start={0}" -f $start)
  foreach ($c in $pg.rows) {
    $collections.Add([pscustomobject]@{
      key = $c.key; name = $c.data.name; parent = $c.data.parentCollection; items = $c.meta.numItems
    })
  }
  if ($pg.rows.Count -lt 100) { break }
  $start += 100
}
Write-Host ("      collections 共 {0}" -f $collections.Count)

# --- 5. 顶层条目（Probe 模式跳过）---
$items = New-Object System.Collections.Generic.List[object]
if ($Probe) {
  Write-Host '[3/4] Probe 模式：跳过全量条目拉取'
} else {
  Write-Host ("[3/4] 拉取顶层条目（{0}）..." -f $totalItems)
  $start = 0
  while ($items.Count -lt $totalItems) {
    $pg = Get-ZoteroPage '/items/top' ("limit=100&start={0}" -f $start)
    if ($pg.rows.Count -eq 0) { break }
    foreach ($it in $pg.rows) {
      $d = $it.data
      $items.Add([pscustomobject]@{
        key = $it.key; version = $d.version; itemType = $d.itemType; title = $d.title
        journal = $d.publicationTitle; journalAbbr = $d.journalAbbreviation
        date = $d.date; volume = $d.volume; issue = $d.issue; doi = $d.DOI; extra = $d.extra
        collections = @($d.collections)
      })
    }
    $start += 100
    Write-Host ("      ... {0}/{1}" -f $items.Count, $totalItems)
    if ($pg.backoff -gt 0) { Start-Sleep -Seconds $pg.backoff }
  }
}

# --- 6. 写脱敏缓存（绝不含 key）---
Write-Host '[4/4] 写出脱敏缓存 ...'
if (-not (Test-Path -LiteralPath $McDir)) { New-Item -ItemType Directory -Path $McDir -Force | Out-Null }
$mode = 'full'; if ($Probe) { $mode = 'probe' }
$out = [ordered]@{
  generated       = (Get-Date -Format 'yyyy-MM-ddTHH:mm:ss')
  zotero_user_id  = $userId
  library_version = $libVersion
  total_top_items = $totalItems
  mode            = $mode
  collections     = $collections
  items           = $items
}
($out | ConvertTo-Json -Depth 8) | Out-File -LiteralPath $OutFile -Encoding UTF8
Write-Host ("完成 → {0}" -f $OutFile)
Write-Host ('-' * 50)
Write-Host ("摘要：{0} 顶层条目 · {1} collections · 库版本 {2} · 模式 {3}" -f $totalItems, $collections.Count, $libVersion, $mode)
