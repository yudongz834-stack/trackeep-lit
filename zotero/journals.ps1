<#
  journals.ps1 — 在 Zotero 5 类 collection 下创建期刊子 collection
  数据源：Trackeep-Memex/00-系统/期刊来源表.md（74 期刊权威表）。

  纪律
    · 只 GET（核验）+ POST（创建期刊子 collection）；幂等——已存在的跳过；不删除、不改条目。
    · API key 仅用于 HTTP 请求头。
#>
$ErrorActionPreference = 'Stop'
try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 } catch {}

$EnvFile   = Join-Path $env:USERPROFILE '.config\trackeep\secrets\zotero.env'
$TablePath = 'E:\Trackeep-Obsidian\00-系统\期刊来源表.md'

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

function Get-Utf8($resp) { [System.Text.Encoding]::UTF8.GetString($resp.RawContentStream.ToArray()) }
function Get-AllCollections {
  $acc = @(); $start = 0
  while ($true) {
    $r  = Invoke-WebRequest -Uri "$base/collections?limit=100&start=$start" -Headers $hRead -UseBasicParsing -TimeoutSec 60
    $pg = @((ConvertFrom-Json -InputObject (Get-Utf8 $r)))
    $acc += $pg
    if ($pg.Count -lt 100) { break }
    $start += 100
  }
  $acc
}

$classNames = @('胸部肿瘤与胸外科', '流行病学与公共卫生', '临床医学综合', '医学AI与数字医学', '基础与转化医学')

# --- 1. 解析期刊来源表（取 来源分类 + 推荐目录名）---
$journals = @()
foreach ($line in (Get-Content -LiteralPath $TablePath -Encoding UTF8)) {
  if (-not $line.StartsWith('|')) { continue }
  $p = $line.Split('|')
  if ($p.Count -lt 6) { continue }
  $cls = $p[1].Trim(); $dir = $p[4].Trim()
  if ($classNames -notcontains $cls) { continue }
  if (-not $dir) { continue }
  $journals += [pscustomobject]@{ class = $cls; name = $dir }
}
Write-Host ("期刊来源表解析：{0} 本期刊" -f $journals.Count)
if ($journals.Count -eq 0) { throw '未解析到期刊行 —— 检查期刊来源表路径/格式。' }

# --- 2. 取现有 collections：建 5 类 name->key + 已存在 (parent|name) ---
$existing = Get-AllCollections
$classKey = @{}
foreach ($c in $existing) {
  if (-not $c.data.parentCollection -and $classNames -contains $c.data.name) { $classKey[$c.data.name] = $c.key }
}
foreach ($cn in $classNames) {
  if (-not $classKey.ContainsKey($cn)) { throw "5 类 collection 缺「$cn」—— 先跑归档件 .pre-zotero-cleanup-20261003\zotero-init.ps1。" }
}
$have = @{}
foreach ($c in $existing) { $have["$($c.data.parentCollection)|$($c.data.name)"] = $true }

# --- 3. 算出待建（幂等：已存在跳过）---
$toCreate = @()
foreach ($j in $journals) {
  $pk = $classKey[$j.class]
  if ($have.ContainsKey("$pk|$($j.name)")) { continue }
  $toCreate += @{ name = $j.name; parentCollection = $pk }
}
Write-Host ("待创建期刊 collection：{0}（已存在的已跳过）" -f $toCreate.Count)
if ($toCreate.Count -eq 0) { Write-Host '全部已存在，无需创建。'; return }

# --- 4. 分批 POST（≤50/批）---
for ($i = 0; $i -lt $toCreate.Count; $i += 50) {
  $batch = @($toCreate[$i..([Math]::Min($i + 49, $toCreate.Count - 1))])
  $body  = [System.Text.Encoding]::UTF8.GetBytes((ConvertTo-Json -InputObject $batch -Depth 4))
  $hW    = @{ 'Zotero-API-Version' = '3'; 'Zotero-API-Key' = $apiKey; 'Zotero-Write-Token' = ([guid]::NewGuid().ToString('N')) }
  $resp  = Invoke-WebRequest -Uri "$base/collections" -Method Post -Headers $hW `
           -ContentType 'application/json' -Body $body -UseBasicParsing -TimeoutSec 90
  Write-Host ("  批 {0}-{1}：HTTP {2}" -f ($i + 1), ($i + $batch.Count), [int]$resp.StatusCode)
}

# --- 5. 复核 ---
Start-Sleep -Milliseconds 800
$all = Get-AllCollections
Write-Host ''
Write-Host ("复核：collection 总数 {0}（目标 = 5 类 + 74 期刊 = 79）" -f $all.Count)
foreach ($cn in $classNames) {
  $ck = $classKey[$cn]
  $n  = @($all | Where-Object { $_.data.parentCollection -eq $ck }).Count
  Write-Host ("  {0,-18} 期刊子集 {1}" -f $cn, $n)
}
