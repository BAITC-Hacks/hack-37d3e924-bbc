$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
Set-Location -LiteralPath $PSScriptRoot
$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$sharedModels = Join-Path $repoRoot '.local\models'
if (-not $env:MEETING_MODEL_DIR -and (Test-Path -LiteralPath (Join-Path $sharedModels '.meeting-models-verified.json'))) {
    $env:MEETING_MODEL_DIR = $sharedModels
}
if (-not $env:MEETING_LLM_RUNTIME) { $env:MEETING_LLM_RUNTIME = 'mlx_torch' }
if (-not $env:MEETING_DEVICE) { $env:MEETING_DEVICE = 'cpu' }
$env:PYTHONPATH = (@($repoRoot, $env:PYTHONPATH) | Where-Object { $_ }) -join [IO.Path]::PathSeparator

$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    throw 'Run .\setup.ps1 from PowerShell first.'
}

$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
$env:HF_HUB_DISABLE_TELEMETRY = '1'
$env:DO_NOT_TRACK = '1'

& $python -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501 --browser.gatherUsageStats false
exit $LASTEXITCODE
