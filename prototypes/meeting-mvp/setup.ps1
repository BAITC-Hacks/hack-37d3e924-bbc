param(
    [switch]$DownloadModels
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
Set-Location -LiteralPath $PSScriptRoot

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

if ($DownloadModels) {
    & $python download_models.py
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    Write-Host 'Original model files were downloaded and verified. Native Windows MLX analysis is not available.'
} else {
    Write-Host 'Model files were not downloaded. To try original model download, run: .\setup.ps1 -DownloadModels'
}

Write-Host 'Done. Start the interface with: .\start.cmd'
