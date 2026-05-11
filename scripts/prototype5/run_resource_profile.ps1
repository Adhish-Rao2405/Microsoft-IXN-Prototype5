param(
    [switch]$CheckPsutil
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path (Join-Path $ScriptDir "..\..")
Set-Location $ProjectRoot

$VenvActivate = Join-Path $ProjectRoot ".venv\Scripts\Activate.ps1"
if (Test-Path $VenvActivate) {
    . $VenvActivate
}

if ($CheckPsutil) {
    python -c "import importlib.util; raise SystemExit(0 if importlib.util.find_spec('psutil') else 1)"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "psutil is not installed. Optional install: pip install psutil"
    } else {
        Write-Host "psutil: PRESENT"
    }
}

python -m src.prototype5.throughput_runner

Write-Host ""
Write-Host "Mode D outputs:"
Write-Host "  results/prototype5/mode_d/resource_profile_samples.csv"
Write-Host "  results/prototype5/mode_d/resource_profile_summary.csv"
Write-Host "  results/prototype5/mode_d/throughput_stability.csv"
Write-Host "  results/prototype5/mode_d/mode_d_summary.json"
Write-Host "  docs/prototype5/prototype5_resource_profile.md"
