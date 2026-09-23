param(
    [switch]$DownloadModels
)

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

$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    foreach ($candidate in @('py -3.12', 'py', 'python')) {
        try {
            if ($candidate -eq 'py -3.12') { py -3.12 -m venv .venv }
            elseif ($candidate -eq 'py') { py -m venv .venv }
            else { python -m venv .venv }
            if (Test-Path -LiteralPath $python) { break }
        } catch {
            continue
        }
    }
}

if (-not (Test-Path -LiteralPath $python)) {
    throw 'Could not create .venv. Install Python 3.12+ and run setup again.'
}

& $python -c 'import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)'
if ($LASTEXITCODE -ne 0) {
    throw 'This dependency lock requires Python 3.12+. Existing .venv was preserved; use a supported Python environment.'
}

& $python -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& $python -m pip install -r requirements.windows.lock.txt
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

# The common torch==2.14.0 pin accepts an installed 2.14.0+cu* wheel.
# Do not use --upgrade or force a CPU package index for the inference dependencies.
& $python -m pip install -r (Join-Path $repoRoot 'ai\requirements-windows.lock.txt')
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if ($DownloadModels) {
    & $python download_models.py
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    Write-Host 'Original model files were downloaded and verified. Windows uses these same MLX 4-bit weights through PyTorch.'
} else {
    Write-Host 'Model files were not downloaded. Prepared models in the root .local\models directory are reused automatically.'
    Write-Host 'To download and verify original weights, run: .\setup.ps1 -DownloadModels'
}

Write-Host 'Done. Start the interface with: .\start.cmd'
