<#
  wipe.ps1 — Zotero 库彻底清空（破坏性 · 不可逆）
  Zotero ⇄ Trackeep-Memex 整合 · PI 显式指令下的总清空

  做什么
    删除 Zotero 个人库的全部条目与全部 collection。
    GET 一批 → DELETE 一批 → 循环到空；自纠错、可重跑。

  纪律
    · 破坏性、不可逆。默认 dry-run（只统计、不删）；加 -Execute 才真删。
    · API key 仅用于 HTTP 请求头，绝不写入输出 / 日志。
    · PI（yudongz）2026-05-17 多次显式确认：彻底清空 Zotero、不留备份。
      原因：库内 25355 条目为批量导入，非人工精选，PI 决定全部舍弃。

  用法
    pwsh -NoProfile -ExecutionPolicy Bypass -File zotero\wipe.ps1            # dry-run
    pwsh -NoProfile -ExecutionPolicy Bypass -File zotero\wipe.ps1 -Execute   # 真删
#>
param([switch]$Execute)

$ErrorActionPreference = 'Stop'
try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 } catch {}

$EnvFile = Join-Path $env:USERPROFILE '.config\trackeep\secrets\zotero.env'

# --- 加载 secret ---
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
if (-not $apiKey -or -not $userId) { throw 'zotero.env 缺 ZOTERO_API_KEY / ZOTERO_USER_ID' }

$base = "https://api.zotero.org/users/$userId"

function Get-Header($resp, $name) {
  foreach ($k in $resp.Headers.Keys) { if ($k -ieq $name) { return [string]$resp.Headers[$k] } }
  return $null
}

# 取一批对象的 key + 当前库版本 + 总数
function Get-Batch($path) {
  $h = @{ 'Zotero-API-Version' = '3'; 'Zotero-API-Key' = $apiKey }
  $resp = Invoke-WebRequest -Uri ($base + $path + '?limit=50') -Headers $h -UseBasicParsing -TimeoutSec 90
  $txt  = [Text.Encoding]::UTF8.GetString($resp.RawContentStream.ToArray())
  $rows = ConvertFrom-Json -InputObject $txt
  if ($null -eq $rows)       { $arr = @() }
  elseif ($rows -is [array]) { $arr = $rows }
  else                       { $arr = @($rows) }
  [pscustomobject]@{
    keys    = @($arr | ForEach-Object { $_.key })
    total   = [int](Get-Header $resp 'Total-Results')
    version = [int](Get-Header $resp 'Last-Modified-Version')
    backoff = [int](Get-Header $resp 'Backoff')
  }
}

# 删一批（多对象删除需 If-Unmodified-Since-Version）
function Remove-Batch($kind, $param, $keys, $libVer) {
  $u = $base + '/' + $kind + '?' + $param + '=' + ($keys -join ',')
  $h = @{ 'Zotero-API-Version' = '3'; 'Zotero-API-Key' = $apiKey; 'If-Unmodified-Since-Version' = "$libVer" }
  Invoke-WebRequest -Uri $u -Method Delete -Headers $h -UseBasicParsing -TimeoutSec 90 | Out-Null
}

function Invoke-Wipe($kind, $path, $param, $label) {
  $b0 = Get-Batch $path
  Write-Host ("{0}：当前 {1}" -f $label, $b0.total)
  if (-not $Execute) { Write-Host '  (dry-run，未删)'; return }
  $done = 0
  while ($true) {
    $b = Get-Batch $path
    if ($b.keys.Count -eq 0) { break }
    $ok = $false; $tries = 0
    while (-not $ok -and $tries -lt 5) {
      $tries++
      try { Remove-Batch $kind $param $b.keys $b.version; $ok = $true }
      catch {
        Write-Host ("  批次重试 {0}：{1}" -f $tries, $_.Exception.Message)
        Start-Sleep -Seconds 2
        $b = Get-Batch $path
        if ($b.keys.Count -eq 0) { $ok = $true }
      }
    }
    if (-not $ok) { throw "$label 批次连续失败，已停。可重跑续删。" }
    $done += $b.keys.Count
    Write-Host ("  已删约 {0}" -f $done)
    if ($b.backoff -gt 0) { Start-Sleep -Seconds $b.backoff }
  }
  $bf = Get-Batch $path
  Write-Host ("{0}：删后剩 {1}" -f $label, $bf.total)
}

Write-Host '=== Zotero 彻底清空 ==='
if (-not $Execute) { Write-Host '*** DRY-RUN：只统计、不删除。加 -Execute 才真删。***' }
Write-Host ''
Invoke-Wipe 'items'       '/items'       'itemKey'       '条目'
Invoke-Wipe 'collections' '/collections' 'collectionKey' 'collection'
Write-Host ''
Write-Host '完成。'
