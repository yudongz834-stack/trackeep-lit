<#
  status.ps1 — 只读核查 Zotero 服务器端库状态
  计数：顶层条目 / 全部条目 / 回收站 / collection。只 GET，不写。
#>
$ErrorActionPreference = 'Stop'
try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 } catch {}

$EnvFile = Join-Path $env:USERPROFILE '.config\trackeep\secrets\zotero.env'
$cfg = @{}
foreach ($line in (Get-Content -LiteralPath $EnvFile)) {
  $t = $line.Trim()
  if (-not $t -or $t.StartsWith('#')) { continue }
  $i = $t.IndexOf('='); if ($i -lt 1) { continue }
  $cfg[$t.Substring(0, $i).Trim()] = $t.Substring($i + 1).Trim().Trim(' ', '<', '>', '"', "'")
}
$base = "https://api.zotero.org/users/$($cfg['ZOTERO_USER_ID'])"
$h = @{ 'Zotero-API-Version' = '3'; 'Zotero-API-Key' = $cfg['ZOTERO_API_KEY'] }

function Get-Count($path) {
  $r = Invoke-WebRequest -Uri ($base + $path + '?limit=1') -Headers $h -UseBasicParsing -TimeoutSec 60
  foreach ($k in $r.Headers.Keys) { if ($k -ieq 'Total-Results') { return [int]$r.Headers[$k] } }
  return -1
}

Write-Host '=== Zotero 服务器端状态 ==='
Write-Host ("  顶层条目 /items/top  : {0}" -f (Get-Count '/items/top'))
Write-Host ("  全部条目 /items      : {0}" -f (Get-Count '/items'))
Write-Host ("  回收站   /items/trash: {0}" -f (Get-Count '/items/trash'))
Write-Host ("  collection           : {0}" -f (Get-Count '/collections'))
