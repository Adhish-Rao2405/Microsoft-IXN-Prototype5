param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("Mocked", "Real")]
    [string]$Suite
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ReadinessTimeout = [TimeSpan]::FromSeconds(20)
$PlaywrightTimeoutMilliseconds = 120000
$ShutdownTimeout = [TimeSpan]::FromSeconds(5)

$FrontendRoot = Split-Path -Parent $PSScriptRoot
$RepositoryRoot = Split-Path -Parent $FrontendRoot

$NodeExecutable = (Get-Command node -ErrorAction Stop).Source
$PythonExecutable = (Get-Command python -ErrorAction Stop).Source

$ViteScript = Join-Path $FrontendRoot "node_modules/vite/bin/vite.js"
$PlaywrightScript = Join-Path $FrontendRoot "node_modules/@playwright/test/cli.js"

$ownedProcesses = [System.Collections.Generic.List[object]]::new()
$ownedPorts = [System.Collections.Generic.List[int]]::new()

$exitCode = 1
$failureMessage = $null


function Assert-PortAvailable {
    param(
        [Parameter(Mandatory = $true)]
        [int]$Port
    )

    $listeners = @(
        Get-NetTCPConnection `
            -State Listen `
            -LocalPort $Port `
            -ErrorAction SilentlyContinue
    )

    if ($listeners.Count -gt 0) {
        throw "Required loopback port $Port already has a listener."
    }
}


function Start-OwnedProcess {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,

        [Parameter(Mandatory = $true)]
        [string]$FilePath,

        [Parameter(Mandatory = $true)]
        [string[]]$ArgumentList,

        [Parameter(Mandatory = $true)]
        [string]$WorkingDirectory,

        [hashtable]$Environment = @{}
    )

    if (-not (Test-Path -LiteralPath $FilePath -PathType Leaf)) {
        throw "Executable or script for $Name is unavailable: $FilePath"
    }

    if (-not (Test-Path -LiteralPath $WorkingDirectory -PathType Container)) {
        throw "Working directory for $Name is unavailable: $WorkingDirectory"
    }

    $startParameters = @{
        FilePath         = $FilePath
        ArgumentList     = $ArgumentList
        WorkingDirectory = $WorkingDirectory
        PassThru         = $true
        NoNewWindow      = $true
    }

    if ($Environment.Count -gt 0) {
        $startParameters.Environment = $Environment
    }

    $process = Start-Process @startParameters

    if ($null -eq $process) {
        throw "Failed to create owned process: $Name"
    }

    $owner = [pscustomobject]@{
        Name    = $Name
        Process = $process
    }

    $ownedProcesses.Add($owner)

    [Console]::Out.WriteLine(
        "owned_process_started name=$Name pid=$($process.Id)"
    )

    return $owner
}


function Wait-OwnedHttpReady {
    param(
        [Parameter(Mandatory = $true)]
        [object]$Owner,

        [Parameter(Mandatory = $true)]
        [string]$Url
    )

    $deadline = [DateTimeOffset]::UtcNow.Add($ReadinessTimeout)
    $client = [System.Net.Http.HttpClient]::new()
    $client.Timeout = [TimeSpan]::FromSeconds(2)

    try {
        while ([DateTimeOffset]::UtcNow -lt $deadline) {
            $Owner.Process.Refresh()

            if ($Owner.Process.HasExited) {
                throw "$($Owner.Name) exited before readiness with code $($Owner.Process.ExitCode)."
            }

            try {
                $response = $client.GetAsync($Url).GetAwaiter().GetResult()

                try {
                    if ($response.IsSuccessStatusCode) {
                        [Console]::Out.WriteLine(
                            "owned_process_ready name=$($Owner.Name) pid=$($Owner.Process.Id) url=$Url"
                        )
                        return
                    }
                }
                finally {
                    $response.Dispose()
                }
            }
            catch [System.Net.Http.HttpRequestException] {
                # Process is still starting. The global readiness deadline remains authoritative.
            }
            catch [System.Threading.Tasks.TaskCanceledException] {
                # Individual probe timed out. The global readiness deadline remains authoritative.
            }

            Start-Sleep -Milliseconds 250
        }
    }
    finally {
        $client.Dispose()
    }

    throw "$($Owner.Name) did not become ready within $($ReadinessTimeout.TotalSeconds) seconds."
}


function Stop-OwnedProcess {
    param(
        [Parameter(Mandatory = $true)]
        [object]$Owner
    )

    $process = $Owner.Process

    try {
        $process.Refresh()
    }
    catch [System.InvalidOperationException] {
        [Console]::Out.WriteLine(
            "owned_process_already_stopped name=$($Owner.Name) pid=$($process.Id)"
        )
        return
    }

    if ($process.HasExited) {
        [Console]::Out.WriteLine(
            "owned_process_already_stopped name=$($Owner.Name) pid=$($process.Id)"
        )
        return
    }

    try {
        # Operate only on the exact Process object returned by Start-Process.
        # Do not rediscover ownership through PID snapshots or process names.
        $process.Kill($true)
    }
    catch [System.InvalidOperationException] {
        $process.Refresh()

        if (-not $process.HasExited) {
            throw
        }
    }

    if (-not $process.WaitForExit(
        [int]$ShutdownTimeout.TotalMilliseconds
    )) {
        throw "$($Owner.Name) did not terminate within $($ShutdownTimeout.TotalSeconds) seconds."
    }

    $process.Refresh()

    if (-not $process.HasExited) {
        throw "$($Owner.Name) remained alive after bounded shutdown."
    }

    [Console]::Out.WriteLine(
        "owned_process_stopped name=$($Owner.Name) pid=$($process.Id)"
    )
}


function Assert-OwnedPortsReleased {
    if ($ownedPorts.Count -eq 0) {
        return
    }

    $deadline = [DateTimeOffset]::UtcNow.Add($ShutdownTimeout)

    do {
        $retainedPorts = [System.Collections.Generic.List[int]]::new()

        foreach ($port in $ownedPorts) {
            $listeners = @(
                Get-NetTCPConnection `
                    -State Listen `
                    -LocalPort $port `
                    -ErrorAction SilentlyContinue
            )

            if ($listeners.Count -gt 0) {
                $retainedPorts.Add($port)
            }
        }

        if ($retainedPorts.Count -eq 0) {
            [Console]::Out.WriteLine("owned_ports_released=PASS")
            return
        }

        Start-Sleep -Milliseconds 100
    }
    while ([DateTimeOffset]::UtcNow -lt $deadline)

    throw "Owned server ports remain bound after shutdown: $($retainedPorts -join ', ')."
}


try {
    if (-not (Test-Path -LiteralPath $PlaywrightScript -PathType Leaf)) {
        throw "Playwright executable is unavailable: $PlaywrightScript"
    }

    if ($Suite -eq "Mocked") {
        Assert-PortAvailable -Port 5173

        $builtFrontend = Join-Path $FrontendRoot "dist/index.html"

        if (-not (Test-Path -LiteralPath $builtFrontend -PathType Leaf)) {
            throw "Built frontend is unavailable. Run npm run build before mocked E2E."
        }

        if (-not (Test-Path -LiteralPath $ViteScript -PathType Leaf)) {
            throw "Vite executable is unavailable: $ViteScript"
        }

        $viteOwner = Start-OwnedProcess `
            -Name "vite-preview" `
            -FilePath $NodeExecutable `
            -ArgumentList @(
                $ViteScript,
                "preview",
                "--host", "127.0.0.1",
                "--port", "5173",
                "--strictPort"
            ) `
            -WorkingDirectory $FrontendRoot

        $ownedPorts.Add(5173)

        Wait-OwnedHttpReady `
            -Owner $viteOwner `
            -Url "http://127.0.0.1:5173/"

        $playwrightConfig = "playwright.config.ts"
    }
    else {
        Assert-PortAvailable -Port 8000
        Assert-PortAvailable -Port 8001

        $builtFrontend = Join-Path $RepositoryRoot "frontend/dist/index.html"

        if (-not (Test-Path -LiteralPath $builtFrontend -PathType Leaf)) {
            throw "Built frontend is unavailable. Run npm run build before real-stack E2E."
        }

        $productionOwner = Start-OwnedProcess `
            -Name "production-demo" `
            -FilePath $PythonExecutable `
            -ArgumentList @(
                "scripts/prototype5/run_integrated_demo.py",
                "--port", "8000"
            ) `
            -WorkingDirectory $RepositoryRoot `
            -Environment @{
                PYTHONPATH                              = $RepositoryRoot
                OPENAI_API_KEY                          = ""
                FOUNDRY_LOCAL_BASE_URL                  = "http://127.0.0.1:9"
                PROTOTYPE5_SPEECH_ALLOW_MODEL_DOWNLOAD = "0"
            }

        $ownedPorts.Add(8000)

        Wait-OwnedHttpReady `
            -Owner $productionOwner `
            -Url "http://127.0.0.1:8000/api/v1/demo/manifest"

        $deterministicOwner = Start-OwnedProcess `
            -Name "deterministic-demo" `
            -FilePath $PythonExecutable `
            -ArgumentList @(
                "tests/prototype5/d2_3_e2e_server.py",
                "--port", "8001"
            ) `
            -WorkingDirectory $RepositoryRoot

        $ownedPorts.Add(8001)

        Wait-OwnedHttpReady `
            -Owner $deterministicOwner `
            -Url "http://127.0.0.1:8001/api/v1/demo/manifest"

        $playwrightConfig = "playwright.real.config.ts"
    }

    $playwrightOwner = Start-OwnedProcess `
        -Name "playwright-$($Suite.ToLowerInvariant())" `
        -FilePath $NodeExecutable `
        -ArgumentList @(
            $PlaywrightScript,
            "test",
            "--config", $playwrightConfig
        ) `
        -WorkingDirectory $FrontendRoot

    if (-not $playwrightOwner.Process.WaitForExit(
        $PlaywrightTimeoutMilliseconds
    )) {
        throw "Playwright exceeded the bounded 120-second execution deadline."
    }

    $exitCode = $playwrightOwner.Process.ExitCode

    if ($exitCode -ne 0) {
        $failureMessage = "Playwright exited with code $exitCode."
    }
}
catch {
    $failureMessage = $_.Exception.Message
    $exitCode = 1
}
finally {
    $cleanupFailures = [System.Collections.Generic.List[string]]::new()

    for (
        $index = $ownedProcesses.Count - 1;
        $index -ge 0;
        $index--
    ) {
        try {
            Stop-OwnedProcess -Owner $ownedProcesses[$index]
        }
        catch {
            $cleanupFailures.Add($_.Exception.Message)
        }
    }

    try {
        Assert-OwnedPortsReleased
    }
    catch {
        $cleanupFailures.Add($_.Exception.Message)
    }

    if ($cleanupFailures.Count -gt 0) {
        $failureMessage =
            "Owned-process cleanup failed: $($cleanupFailures -join ' | ')"
        $exitCode = 1
    }
}

if ($null -ne $failureMessage) {
    [Console]::Error.WriteLine($failureMessage)
}

exit $exitCode
