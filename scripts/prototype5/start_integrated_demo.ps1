param(
    [int]$ApiPort = 8000,
    [int]$UiPort = 5173
)

$ErrorActionPreference = "Stop"
$RepositoryRoot = (
    Resolve-Path (Join-Path $PSScriptRoot "..\..")
).Path
$FrontendRoot = Join-Path $RepositoryRoot "frontend"

if (-not (Test-Path -LiteralPath (Join-Path $FrontendRoot "node_modules"))) {
    throw "Frontend dependencies are missing. Run npm ci in frontend first."
}

$Api = Start-Process `
    -FilePath "python" `
    -ArgumentList @(
        "-m",
        "uvicorn",
        "src.prototype5.demo_api:create_runtime_app",
        "--factory",
        "--host",
        "127.0.0.1",
        "--port",
        $ApiPort
    ) `
    -WorkingDirectory $RepositoryRoot `
    -WindowStyle Hidden `
    -PassThru

try {
    Set-Location $FrontendRoot
    npm run dev -- --port $UiPort
}
finally {
    if (-not $Api.HasExited) {
        Stop-Process -Id $Api.Id
    }
}
