<#
  zotero-init.ps1 — 清空后初始化 Zotero collection 骨架
  在 Zotero 个人库创建 5 个顶层 collection（元宪法 §5 的 5 类），
  使 Zotero 结构对齐 Trackeep-Memex 文献结构。

  纪律
    · 只 GET（核验）+ POST（创建 5 个 collection）；不删除、不改条目。
    · collection 未清空则停；条目残留 ≤50 仅警告不阻塞（建 collection 与条目无关）。
    · API key 仅用于 HTTP 请求头。
#>
$ErrorActionPreference = 'Stop'
try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 } catch {}

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

$base  = "https://api.zotero.org/users/$userId"
$hRead = @{ 'Zotero-API-Version' = '3'; 'Zotero-API-Key' = $apiKey }

function Get-Header($resp, $name) {
  foreach ($k in $resp.Headers.Keys) { if ($k -ieq $name) { return [string]$resp.Headers[$k] } }
  return $null
}
function Get-Utf8($resp) { [System.Text.Encoding]::UTF8.GetString($resp.RawContentStream.ToArray()) }

# --- 1. 核验库状态 ---
$ri = Invoke-WebRequest -Uri "$base/items?limit=50"      -Headers $hRead -UseBasicParsing -TimeoutSec 60
$rc = Invoke-WebRequest -Uri "$base/collections?limit=1" -Headers $hRead -UseBasicParsing -TimeoutSec 60
$nItems = [int](Get-Header $ri 'Total-Results')
$nCols  = [int](Get-Header $rc 'Total-Results')
Write-Host ("当前库：条目 {0} · collection {1}" -f $nItems, $nCols)

if ($nCols -gt 0)   { throw "还有 $nCols 个 collection 未清 —— 未创建。先清掉旧 collection。" }
if ($nItems -gt 50) { throw "还有 $nItems 个条目（同步可能没跑完）—— 未创建。等彻底清空再来。" }

if ($nItems -gt 0) {
  Write-Host ("[!] 仍有 {0} 个残留条目：" -f $nItems)
  foreach ($it in @((ConvertFrom-Json -InputObject (Get-Utf8 $ri)))) {
    Write-Host ("    [{0}] key={1}  {2}" -f $it.data.itemType, $it.key, $it.data.title)
  }
  Write-Host '    (不阻塞建 collection；建议在 Zotero 桌面端删掉它 + 清回收站 + 同步)'
}

# --- 2. 创建 5 类顶层 collection ---
$classes = @('胸部肿瘤与胸外科', '流行病学与公共卫生', '临床医学综合', '医学AI与数字医学', '基础与转化医学')
$payload = @($classes | ForEach-Object { @{ name = $_ } })
$json    = ConvertTo-Json -InputObject $payload -Depth 4
$body    = [System.Text.Encoding]::UTF8.GetBytes($json)
$hWrite  = @{
  'Zotero-API-Version' = '3'
  'Zotero-API-Key'     = $apiKey
  'Zotero-Write-Token' = ([guid]::NewGuid().ToString('N'))
}
$resp = Invoke-WebRequest -Uri "$base/collections" -Method Post -Headers $hWrite `
        -ContentType 'application/json' -Body $body -UseBasicParsing -TimeoutSec 90
Write-Host ("创建请求 HTTP {0}" -f [int]$resp.StatusCode)

# --- 3. 复核 ---
Start-Sleep -Milliseconds 800
$rc2  = Invoke-WebRequest -Uri "$base/collections?limit=50" -Headers $hRead -UseBasicParsing -TimeoutSec 60
$cols = @((ConvertFrom-Json -InputObject (Get-Utf8 $rc2)))
Write-Host ''
Write-Host ("复核：当前 collection {0} 个" -f $cols.Count)
foreach ($c in $cols) { Write-Host ("  - {0,-20} {1}" -f $c.data.name, $c.key) }
