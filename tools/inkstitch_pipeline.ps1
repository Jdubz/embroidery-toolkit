<#
.SYNOPSIS
  Line art -> centreline strokes -> continuous running stitch -> PES, via Ink/Stitch.

.DESCRIPTION
  For outline artwork this beats the built-in `stitch trace`, which scanline-FILLS
  every shape. Ink/Stitch says it plainly in its own Fill-to-Stroke dialog:
  "Fill outlines never look nice when embroidered."

  Pipeline:
    1. vtracer      raster -> SVG filled shapes
    2. fill_to_stroke   filled linework -> centrelines
    3. redwork      centrelines -> ONE continuous running stitch path
    4. output       -> PES
    5. stitch fix-pes   correct the hoop code Ink/Stitch leaves at 130x180

  IMPORTANT: inkstitch.exe is a GUI-subsystem binary. Shell `>` redirection
  silently yields an empty file â€” the usage shown in Ink/Stitch's own CLI docs
  does not work in PowerShell. Everything here goes through Start-Process with
  -RedirectStandardOutput.

.EXAMPLE
  .\tools\inkstitch_pipeline.ps1 -Image images\LemonCat_outline_transparent.png `
      -Out designs\out\LemonY_rw.pes -WidthMm 91
#>
param(
    [Parameter(Mandatory)][string]$Image,
    [Parameter(Mandatory)][string]$Out,
    [ValidateSet('redwork', 'layered')][string]$Mode = 'redwork',
    [double]$WidthMm = 91,
    [double]$StitchLenMm = 2.0,
    # layered mode: one 'RRGGBB:fill' or 'RRGGBB:line' per thread layer, bottom
    # layer first. Quote them -- PowerShell reads an unquoted 000000 as 0.
    # -Skip colours take part in pixel assignment but are never stitched, so
    # the fabric shows through.
    [string[]]$Layer = @(),
    [string[]]$Skip = @(),
    [double]$SpacingMm = 0.4,
    # Line layers are stitched as a single running stitch, which is one 40 wt
    # thread â€” about 0.4 mm, against a documented minimum linework width of
    # 1.0 mm. Bean stitch re-runs each stitch to build weight: 2 repeats is
    # ~2.5x the thread on the same path, for no extra jumps. 0 = plain run.
    [int]$BeanRepeats = 2,
    # Strokes at least this wide are filled rather than centrelined. Lower it
    # to make more of the artwork solid.
    [double]$SplitMm = 1.5,
    [int]$TimeoutSec = 1800,
    [string]$WorkDir = ""
)

$ErrorActionPreference = 'Stop'
$repo = Split-Path $PSScriptRoot -Parent
$inkstitch = Join-Path $env:APPDATA 'inkscape\extensions\inkstitch\inkstitch\bin\inkstitch.exe'
if (-not (Test-Path $inkstitch)) { throw "Ink/Stitch not found at $inkstitch" }
if (-not $WorkDir) { $WorkDir = Join-Path $env:TEMP ("inkstitch_" + [System.IO.Path]::GetRandomFileName()) }
New-Item -ItemType Directory -Force -Path $WorkDir | Out-Null

# Inkscape extensions act on a selection. Headless, that selection is supplied
# as one --id=<id> argument per object; with none, Ink/Stitch prints "Please
# select one or more strokes" and exits 0 having produced nothing.
function Get-SvgIds {
    param([string]$Svg, [switch]$StrokedOnly)
    $text = Get-Content $Svg -Raw
    $ids = @()
    foreach ($m in [regex]::Matches($text, '<path\b[^>]*>')) {
        $tag = $m.Value
        $id = [regex]::Match($tag, 'id="([^"]+)"')
        if (-not $id.Success) { continue }
        if ($StrokedOnly) {
            $hasStroke = $tag -match 'stroke\s*[:=]\s*"?#?[0-9a-zA-Z]' -and $tag -notmatch 'stroke\s*[:=]\s*"?none'
            if (-not $hasStroke) { continue }
        }
        $ids += $id.Groups[1].Value
    }
    return $ids
}

# Ink/Stitch is a GUI application wearing a CLI. On anything it considers
# irregular it raises a modal wx dialog, which headless nobody can answer -- the
# process then sits at ~0% CPU forever. Rather than hang, wait a bounded time,
# scrape the dialog's text so the cause is visible, and fail.
Add-Type @'
using System;
using System.Text;
using System.Collections.Generic;
using System.Runtime.InteropServices;
public class InkStitchDlg {
  delegate bool EnumProc(IntPtr h, IntPtr l);
  [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc cb, IntPtr l);
  [DllImport("user32.dll")] static extern bool EnumChildWindows(IntPtr h, EnumProc cb, IntPtr l);
  [DllImport("user32.dll")] static extern int GetWindowThreadProcessId(IntPtr h, out int pid);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] static extern int GetWindowTextW(IntPtr h, StringBuilder s, int n);
  static int target; static List<string> res;
  static string Txt(IntPtr h){ var sb=new StringBuilder(2048); GetWindowTextW(h,sb,2048); return sb.ToString(); }
  static bool Child(IntPtr h, IntPtr d){ string t=Txt(h); if(t.Length>0) res.Add(t); return true; }
  static bool Top(IntPtr h, IntPtr d){
    int pid; GetWindowThreadProcessId(h, out pid);
    if(pid==target) EnumChildWindows(h, Child, IntPtr.Zero);
    return true;
  }
  public static string[] Read(int pid){ target=pid; res=new List<string>(); EnumWindows(Top, IntPtr.Zero); return res.ToArray(); }
}
'@ -ErrorAction SilentlyContinue

function Invoke-InkStitch {
    param([string]$Extension, [string]$InSvg, [string]$OutFile, [string[]]$Extra = @(),
          [int]$TimeoutSec = 1800)
    $args = @("--extension=$Extension") + $Extra + @($InSvg)
    # Keep stderr in the work dir. Writing it beside $OutFile litters
    # designs\out with a stray .err on the final export step.
    $err = Join-Path $WorkDir "$Extension.err"
    $p = Start-Process $inkstitch -ArgumentList $args -NoNewWindow -PassThru `
         -RedirectStandardOutput $OutFile -RedirectStandardError $err

    # Touching .Handle forces the process handle to be cached. Without it
    # $p.ExitCode reads back empty once the process has exited, and every run
    # fails its own success check.
    $null = $p.Handle

    if (-not $p.WaitForExit($TimeoutSec * 1000)) {
        $dlg = @()
        try { $dlg = [InkStitchDlg]::Read($p.Id) | Where-Object { $_ -notmatch '^(panel|OK|Cancel|Update)$' } } catch {}
        Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
        $what = if ($dlg) { "It is showing a dialog:`n      " + ($dlg -join "`n      ") }
                else { "No dialog text could be read; it may simply be slow -- raise -TimeoutSec." }
        throw "inkstitch --extension=$Extension did not finish in ${TimeoutSec}s. $what"
    }

    $p.WaitForExit()   # the timed overload can return before output is flushed
    $size = if (Test-Path $OutFile) { (Get-Item $OutFile).Length } else { 0 }
    if ($p.ExitCode -ne 0 -or $size -eq 0) {
        $msg = if (Test-Path $err) { (Get-Content $err -Raw) } else { "(no stderr)" }
        throw "inkstitch --extension=$Extension failed (exit $($p.ExitCode), $size bytes): $msg"
    }
    Write-Host ("    {0,-16} -> {1,9:N0} bytes" -f $Extension, $size)
}

$py = Join-Path $repo '.venv\Scripts\python.exe'

if ($Mode -eq 'redwork') {
    Write-Host "1. vectorising" -ForegroundColor Cyan
    $svg0 = Join-Path $WorkDir 'traced.svg'
    & $py (Join-Path $PSScriptRoot 'vectorize.py') $Image $svg0 $WidthMm
    if (-not (Test-Path $svg0)) { throw "vectorise step produced nothing" }
    Write-Host ("    vtracer          -> {0,9:N0} bytes" -f (Get-Item $svg0).Length)

    Write-Host "2. fill -> centreline strokes" -ForegroundColor Cyan
    $svg1 = Join-Path $WorkDir 'stroked.svg'
    $ids0 = Get-SvgIds -Svg $svg0
    Write-Host "    selecting $($ids0.Count) filled path(s)"
    Invoke-InkStitch -Extension 'fill_to_stroke' -InSvg $svg0 -OutFile $svg1 -TimeoutSec $TimeoutSec `
        -Extra (@('--threshold_mm=0.3', '--line_width_mm=1.2', '--keep_original=false') +
                ($ids0 | ForEach-Object { "--id=$_" }))

    Write-Host "3. redwork (one continuous path)" -ForegroundColor Cyan
    $final = Join-Path $WorkDir 'redwork.svg'
    $ids1 = Get-SvgIds -Svg $svg1 -StrokedOnly
    if (-not $ids1) { $ids1 = Get-SvgIds -Svg $svg1 }
    Write-Host "    selecting $($ids1.Count) stroke(s)"
    Invoke-InkStitch -Extension 'redwork' -InSvg $svg1 -OutFile $final -TimeoutSec $TimeoutSec `
        -Extra (@("--redwork_running_stitch_length_mm=$StitchLenMm", "--redwork_bean_stitch_repeats=$BeanRepeats", '--keep_originals=false') +
                ($ids1 | ForEach-Object { "--id=$_" }))
}
else {
    if (-not $Layer) { throw "layered mode needs at least one -Layer, e.g. -Layer 'FFD600:fill','000000:line'" }

    Write-Host "1. colour separation" -ForegroundColor Cyan
    $layerDir = Join-Path $WorkDir 'layers'
    if (Test-Path $layerDir) { Remove-Item $layerDir -Recurse -Force }
    $sepArgs = @($Image, $layerDir, $WidthMm, '--spacing', $SpacingMm, '--split-mm', $SplitMm) +
               ($Layer | ForEach-Object { @('--layer', $_) }) +
               ($Skip  | ForEach-Object { @('--skip',  $_) })
    & $py (Join-Path $PSScriptRoot 'color_separate.py') @sepArgs
    if ($LASTEXITCODE -ne 0) { throw "colour separation failed" }

    # Sorting by filename restores stitch order: color_separate numbers layers
    # L00, L01, ... bottom first, and encodes the mode in the name.
    $files = Get-ChildItem $layerDir -Filter 'L*.svg' | Sort-Object Name
    if (-not $files) { throw "colour separation produced no layers" }

    Write-Host "2. per-layer treatment" -ForegroundColor Cyan
    $done = @()
    foreach ($f in $files) {
        if ($f.Name -match '^L\d+[a-z]?_line_') {
            Write-Host "   $($f.Name): line -> centreline -> running stitch"
            $st = Join-Path $WorkDir "$($f.BaseName)_stroked.svg"
            $ids = Get-SvgIds -Svg $f.FullName
            Write-Host "      selecting $($ids.Count) filled path(s)"
            Invoke-InkStitch -Extension 'fill_to_stroke' -InSvg $f.FullName -OutFile $st -TimeoutSec $TimeoutSec `
                -Extra (@('--threshold_mm=0.3', '--line_width_mm=1.2', '--keep_original=false') +
                        ($ids | ForEach-Object { "--id=$_" }))

            $rw = Join-Path $WorkDir "$($f.BaseName)_redwork.svg"
            $sids = Get-SvgIds -Svg $st -StrokedOnly
            if (-not $sids) { $sids = Get-SvgIds -Svg $st }
            Write-Host "      selecting $($sids.Count) stroke(s)"
            Invoke-InkStitch -Extension 'redwork' -InSvg $st -OutFile $rw -TimeoutSec $TimeoutSec `
                -Extra (@("--redwork_running_stitch_length_mm=$StitchLenMm", "--redwork_bean_stitch_repeats=$BeanRepeats", '--keep_originals=false') +
                        ($sids | ForEach-Object { "--id=$_" }))
            $done += $rw
        }
        else {
            Write-Host "   $($f.Name): fill (routed with underpath at export)"
            $done += $f.FullName
        }
    }

    Write-Host "3. merge layers" -ForegroundColor Cyan
    $final = Join-Path $WorkDir 'merged.svg'
    & $py (Join-Path $PSScriptRoot 'svg_merge.py') $final @done
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $final)) { throw "layer merge failed" }
}

$n = if ($Mode -eq 'redwork') { 4 } else { 4 }
Write-Host "$n. export PES  (fills route travel under the stitching - minutes, not seconds)" -ForegroundColor Cyan
Invoke-InkStitch -Extension 'output' -InSvg $final -OutFile $Out -TimeoutSec $TimeoutSec -Extra @('--format=pes')

Write-Host "$($n + 1). repair PES container for this machine" -ForegroundColor Cyan
& (Join-Path $repo 'stitch.ps1') fix-pes $Out

Write-Host "`nWork files: $WorkDir" -ForegroundColor DarkGray

