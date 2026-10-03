<#
  trash.ps1 — 把指定 Zotero 条目移入回收站（可恢复，非永久删除）。

  用途：导入后筛查的「清理候选」，由 Trackeep 经此脚本批量移入 Zotero 回收站，
        PI 不再逐条手点。

  纪律
    · 只做「移入回收站」一个写操作：PATCH data.deleted=1，**可逆**——条目仍在
      Zotero 回收站、可随时恢复。
    · 绝不发 DELETE（永久删除）；不动 collections / tags / notes；不碰 zotero.sqlite。
    · 永久清空回收站（不可逆）仍由 PI 在 Zotero 手动 Empty Trash。
    · 只移入脚本被显式点名的 key——不做分类判断；删谁由调用方（审计脚本/skill）定。
    · API key 仅用于 HTTP 头、不回显。

  用法：pwsh -NoProfile -File zotero\trash.ps1 <key1> <key2> ...
  输出：逐条 ✓/跳过/✗ + 汇总。
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory = $true, ValueFromRemainingArguments = $true)]
  [string[]]$Keys
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
$base   = "https://api.zotero.org/users/$userId"
$hRead  = @{ 'Zotero-API-Version' = '3'; 'Zotero-API-Key' = $apiKey }

function Get-Utf8($resp) { [System.Text.Encoding]::UTF8.GetString($resp.RawContentStream.ToArray()) }

$keysClean = @($Keys | ForEach-Object { "$_".Trim().ToUpper() } | Where-Object { $_ } | Select-Object -Unique)
Write-Host ("=== 移入 Zotero 回收站：{0} 项（可恢复，非永久删除）===" -f $keysClean.Count) -ForegroundColor Cyan

$ok = 0; $skip = 0; $fail = 0
foreach ($key in $keysClean) {
  if ($key -notmatch '^[A-Z0-9]{8}$') {
    Write-Host ("  跳过 {0}：不是合法 Zotero key" -f $key) -ForegroundColor Yellow; $skip++; continue
  }
  try {
    $rGet = Invoke-WebRequest -Uri "$base/items/$key" -Headers $hRead -UseBasicParsing -TimeoutSec 60
    $item = ConvertFrom-Json -InputObject (Get-Utf8 $rGet)
  } catch {
    Write-Host ("  跳过 {0}：条目未找到" -f $key) -ForegroundColor Yellow; $skip++; continue
  }
  $ver   = [int]$item.version
  $title = "$($item.data.title)"
  if ($item.data.deleted -eq 1) {
    Write-Host ("  - 已在回收站 {0}  {1}" -f $key, $title); $skip++; continue
  }
  try {
    $hWrite = @{
      'Zotero-API-Version'          = '3'
      'Zotero-API-Key'              = $apiKey
      'If-Unmodified-Since-Version' = "$ver"
    }
    Invoke-WebRequest -Uri "$base/items/$key" -Method Patch -Headers $hWrite `
      -ContentType 'application/json' -Body '{"deleted":1}' -UseBasicParsing -TimeoutSec 60 | Out-Null
    Write-Host ("  OK 移入回收站 {0}  {1}" -f $key, $title) -ForegroundColor Green
    $ok++
  } catch {
    Write-Host ("  X  失败 {0}：{1}" -f $key, $_.Exception.Message) -ForegroundColor Red
    $fail++
  }
}
Write-Host ('-' * 56)
Write-Host ("完成：移入回收站 {0} · 跳过 {1} · 失败 {2}" -f $ok, $skip, $fail)
Write-Host '条目在 Zotero 回收站可随时恢复；永久清空请在 Zotero 手动 Empty Trash。'
