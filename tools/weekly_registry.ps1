# weekly_registry.ps1 — 期刊雷达周闹钟包装（计划任务「\Trackeep\期刊雷达-每周」的执行体）
# 跑 journal-registry.py（本地 API 优先/云端自切）→ 登记表落 D:\workbench\期刊登记表-<日期>.md
# ＋ 警报面 D:\workbench\期刊雷达-警报.txt（全跟齐也留时间戳）；日志追加 .trackeep\weekly-registry.log
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8  # 审核整改：python UTF-8 输出别按 GBK 解码落档
$env:PYTHONIOENCODING = 'utf-8'
$root = Split-Path $PSScriptRoot -Parent
$log = Join-Path $root '.trackeep\weekly-registry.log'
try {
  $out = $null; $code = 1
  foreach ($attempt in 1..2) {
    $stamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    $out = & E:\Python\python.exe (Join-Path $root 'zotero\journal-registry.py') 2>&1
    $code = $LASTEXITCODE
    if ($code -eq 0) { break }
    if ($attempt -lt 2) {
      Add-Content -LiteralPath $log -Value "[$stamp] 第${attempt}次失败(exit=$code)，60秒后重试"
      Start-Sleep -Seconds 60
    }
  }
  Add-Content -LiteralPath $log -Value "[$stamp] exit=$code`r`n$($out -join "`r`n")`r`n---"
  if ($code -ne 0) { throw "journal-registry.py 重试后仍退出 $code" }
  Write-Output $out
} catch {
  Add-Content -LiteralPath $log -Value "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] FAILED: $($_.Exception.Message)"
  throw
}
