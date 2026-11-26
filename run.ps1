param([ValidateSet('all','technical','pipeline','benchmark','sql-benchmark','load-test','test','dashboard','report','package')][string]$Task = 'dashboard')

& (Join-Path $PSScriptRoot 'run.cmd') $Task
exit $LASTEXITCODE
