<#
.SYNOPSIS
  Wrapper for the embroidery toolkit. Runs the CLI inside the repo venv.

.EXAMPLE
  .\stitch.ps1 machine
  .\stitch.ps1 validate designs\out\*.pes
  .\stitch.ps1 stage designs\out\heart.pes --to E:\
#>

$ErrorActionPreference = 'Stop'
$repo = $PSScriptRoot
$python = Join-Path $repo '.venv\Scripts\python.exe'

if (-not (Test-Path $python)) {
    Write-Host "Virtual environment not found. Creating it..." -ForegroundColor Yellow
    py -m venv (Join-Path $repo '.venv')
    & $python -m pip install --quiet --upgrade pip
    & $python -m pip install --quiet -r (Join-Path $repo 'tools\requirements.txt')
    Write-Host "Environment ready." -ForegroundColor Green
}

# Prepend rather than assign, so an existing PYTHONPATH survives.
$toolsPath = Join-Path $repo 'tools'
if ($env:PYTHONPATH -and $env:PYTHONPATH -notlike "*$toolsPath*") {
    $env:PYTHONPATH = "$toolsPath;$env:PYTHONPATH"
} elseif (-not $env:PYTHONPATH) {
    $env:PYTHONPATH = $toolsPath
}

& $python -m embroidery_tools.cli @args
exit $LASTEXITCODE
