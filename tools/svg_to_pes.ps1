<#
.SYNOPSIS
  Vector SVG -> PES, using real satin columns.

.DESCRIPTION
  The whole pipeline for artwork that already exists as vector:

    1. svg_prep.py       size in mm, resolve inherited paint, split fill/stroke,
                         group by colour, knock out skipped colours as holes.
                         Writes exactly FOUR parameter overrides, plus the
                         per-stroke widths step 3 needs.
    2. stroke_to_satin   convert every stroke into a real two-rail satin column.
    3. satin_params.py   add underlay, banded by column width. stroke_to_satin
                         emits none, and a satin with nothing under it shows
                         bobbin thread along the rails.
    4. output            -> PES
    5. stitch fix-pes    correct the hoop code Ink/Stitch leaves at 130x180

  Step 2 is the one that matters and the one an earlier version got wrong. It
  used stroke_method="zigzag_stitch" instead, which Ink/Stitch's own docs warn
  against for exactly this job:

    "It is not recommended to use the zigzag stitch mode to create a satin
     border, use Satin Column instead."
    "Sharper curves and corners will result in sparse stitching around the
     outside of the curve."

  A cat outline is nearly all curves.

.EXAMPLE
  .\tools\svg_to_pes.ps1 -Svg images\lemon-cat\LemonCat_embroidery_outline.svg `
      -Out designs\out\LemonY.pes -ArtworkMm 91
#>
param(
    [Parameter(Mandatory)][string]$Svg,
    [Parameter(Mandatory)][string]$Out,
    [double]$ArtworkMm = 91,
    [string[]]$Skip = @(),
    [string[]]$ColourOrder = @(),
    # Reliability levers. Defaults match svg_prep's, so omitting them changes
    # nothing; reach for them when the machine is bending or breaking needles.
    [double]$Spacing = 0,
    [double]$Expand = -1,
    # What the design is stitched ON. 'dark' tightens the default row spacing to
    # design_limits.fill_density_mm_dark, because the validated 0.4 mm covers on
    # white and speckles on black. Explicit -Spacing still wins.
    [ValidateSet('light', 'dark', 'knits')][string]$Cloth = 'light',
    [switch]$NoFillUnderlay,
    [double]$CollapseMm = -1,
    # Tack style at the start and end of every run. Defaults to svg_prep's;
    # -LockStyle default restores Ink/Stitch's half_stitch behaviour.
    [string]$LockStyle = "",
    # Underlay is chosen per column by width (see satin_params.py). This forces
    # contour onto every column including the narrow ones; it is an escape
    # hatch, not the normal path.
    [switch]$ContourUnderlay,
    [int]$TimeoutSec = 1800,
    [string]$WorkDir = ""
)

$ErrorActionPreference = 'Stop'
$repo = Split-Path $PSScriptRoot -Parent
$py = Join-Path $repo '.venv\Scripts\python.exe'
$inkstitch = Join-Path $env:APPDATA 'inkscape\extensions\inkstitch\inkstitch\bin\inkstitch.exe'
if (-not (Test-Path $inkstitch)) { throw "Ink/Stitch not found at $inkstitch" }
if (-not $WorkDir) { $WorkDir = Join-Path $env:TEMP ("svg2pes_" + [System.IO.Path]::GetRandomFileName()) }
New-Item -ItemType Directory -Force -Path $WorkDir | Out-Null

function Invoke-InkStitch {
    param([string]$Extension, [string]$InFile, [string]$OutFile, [string[]]$Extra = @())
    $err = Join-Path $WorkDir "$Extension.err"
    # inkstitch.exe is a GUI-subsystem binary: shell redirection yields an empty
    # file, so stdout has to be captured through Start-Process.
    $p = Start-Process $inkstitch -ArgumentList (@("--extension=$Extension") + $Extra + @($InFile)) `
         -NoNewWindow -PassThru -RedirectStandardOutput $OutFile -RedirectStandardError $err
    $null = $p.Handle          # cache the handle or ExitCode reads back empty
    if (-not $p.WaitForExit($TimeoutSec * 1000)) {
        Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
        throw "inkstitch --extension=$Extension did not finish in ${TimeoutSec}s (modal dialog?)"
    }
    $p.WaitForExit()
    $size = if (Test-Path $OutFile) { (Get-Item $OutFile).Length } else { 0 }
    if ($p.ExitCode -ne 0 -or $size -eq 0) {
        $msg = if (Test-Path $err) { Get-Content $err -Raw } else { "(no stderr)" }
        throw "inkstitch --extension=$Extension failed (exit $($p.ExitCode), $size bytes): $msg"
    }
    Write-Host ("    {0,-16} -> {1,9:N0} bytes" -f $Extension, $size)
}

Write-Host "1. prepare the document" -ForegroundColor Cyan
$prepped = Join-Path $WorkDir 'prepped.svg'
# Split on commas as well as taking an array. PowerShell's own parser turns
# `-Skip A,B` into two elements, but only when it parses a command line string:
# a caller passing argv directly (build.py does) hands over the single element
# "A,B", which svg_prep then treats as one malformed colour and silently skips
# nothing. Accepting both forms removes the trap.
$SkipList = @($Skip | ForEach-Object { $_ -split '[,;]' } | Where-Object { $_.Trim() })
$args = @($Svg, $prepped, '--artwork-mm', $ArtworkMm) +
        ($SkipList | ForEach-Object { @('--skip', $_.Trim()) }) +
        $(if ($Spacing -gt 0) { @('--spacing', $Spacing) } else { @() }) +
        $(if ($Cloth -ne 'light') { @('--cloth', $Cloth) } else { @() }) +
        $(if ($Expand -ge 0) { @('--expand', $Expand) } else { @() }) +
        $(if ($NoFillUnderlay) { @('--no-fill-underlay') } else { @() }) +
        $(if ($CollapseMm -ge 0) { @('--collapse-mm', $CollapseMm) } else { @() }) +
        $(if ($LockStyle) { @('--lock-style', $LockStyle) } else { @() }) +
        $(if ($ColourOrder) { @('--colour-order') + $ColourOrder } else { @() })
& $py (Join-Path $PSScriptRoot 'svg_prep.py') @args
if ($LASTEXITCODE -ne 0) { throw "svg_prep failed" }

Write-Host "2. strokes -> real satin columns" -ForegroundColor Cyan
$idsFile = [IO.Path]::ChangeExtension($prepped, '.stroke-ids.txt')
$ids = @()
if (Test-Path $idsFile) { $ids = @(Get-Content $idsFile | Where-Object { $_.Trim() }) }
$satin = Join-Path $WorkDir 'satin.svg'
if ($ids.Count -gt 0) {
    Write-Host "    selecting $($ids.Count) stroke(s)"
    Invoke-InkStitch -Extension 'stroke_to_satin' -InFile $prepped -OutFile $satin `
        -Extra ($ids | ForEach-Object { "--id=$_" })
} else {
    Write-Host "    no strokes; nothing to convert"
    Copy-Item $prepped $satin -Force
}

Write-Host "3. satin underlay" -ForegroundColor Cyan
$final = Join-Path $WorkDir 'final.svg'
# Underlay is chosen per column by width, so satin_params needs the widths
# svg_prep measured — stroke_to_satin has thrown them away by this point.
$widthsFile = [IO.Path]::ChangeExtension($prepped, '.stroke-widths.txt')
$ulArgs = @($satin, $final) +
          $(if (Test-Path $widthsFile) { @('--widths', $widthsFile) } else { @() }) +
          $(if ($ContourUnderlay) { @('--contour') } else { @() })
& $py (Join-Path $PSScriptRoot 'satin_params.py') @ulArgs
if ($LASTEXITCODE -ne 0) { throw "satin_params failed" }

Write-Host "4. export PES" -ForegroundColor Cyan
Invoke-InkStitch -Extension 'output' -InFile $final -OutFile $Out -Extra @('--format=pes')

Write-Host "5. repair PES container for this machine" -ForegroundColor Cyan
& (Join-Path $repo 'stitch.ps1') fix-pes $Out

Write-Host "`nWork files: $WorkDir" -ForegroundColor DarkGray

