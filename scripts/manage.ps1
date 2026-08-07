[CmdletBinding()]
param(
    [ValidateSet("start", "stop", "restart", "status", "watch")]
    [string]$Action = "status"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$RuntimeDir = Join-Path $ProjectRoot ".runtime"
$StateFile = Join-Path $RuntimeDir "services.json"
$LogDir = Join-Path $RuntimeDir "logs"
$ThisScript = $MyInvocation.MyCommand.Path
$PublicUrl = "https://syllabus.xiaominapps.com"
$PublicHostname = ([uri]$PublicUrl).Host
$CloudflareServiceName = "cloudflared"

function Initialize-Runtime {
    New-Item -ItemType Directory -Force -Path $RuntimeDir, $LogDir | Out-Null
}

function Read-State {
    if (-not (Test-Path $StateFile)) { return [ordered]@{} }
    try {
        $saved = Get-Content $StateFile -Raw | ConvertFrom-Json
        if ($null -eq $saved) { return [ordered]@{} }
        $state = [ordered]@{}
        foreach ($property in $saved.PSObject.Properties) {
            $state[$property.Name] = $property.Value
        }
        return $state
    } catch {
        return [ordered]@{}
    }
}

function Write-State([System.Collections.IDictionary]$State) {
    Initialize-Runtime
    $State | ConvertTo-Json -Depth 5 | Set-Content -Path $StateFile
}

function Test-ProcessId($ProcessId) {
    if (-not $ProcessId) { return $false }
    return $null -ne (Get-Process -Id ([int]$ProcessId) -ErrorAction SilentlyContinue)
}

function Stop-ProcessTree($ProcessId) {
    if (-not (Test-ProcessId $ProcessId)) { return }
    # npm.cmd and uv can launch child processes; taskkill /T stops the complete,
    # explicitly managed tree instead of leaving Vite or Uvicorn orphaned.
    & taskkill.exe /PID ([int]$ProcessId) /T /F 2>$null | Out-Null
}

function Require-Command([string]$Name) {
    $command = Get-Command $Name -ErrorAction SilentlyContinue
    if (-not $command) { throw "Required command '$Name' was not found in PATH." }
    return $command.Source
}

function Start-LoggedProcess {
    param(
        [string]$Name,
        [string]$FilePath,
        [string[]]$Arguments,
        [string]$WorkingDirectory,
        [hashtable]$Environment = @{}
    )

    $stdout = Join-Path $LogDir "$Name.out.log"
    $stderr = Join-Path $LogDir "$Name.err.log"
    Remove-Item $stdout, $stderr -Force -ErrorAction SilentlyContinue

    $previous = @{}
    foreach ($key in $Environment.Keys) {
        $previous[$key] = [Environment]::GetEnvironmentVariable($key, "Process")
        [Environment]::SetEnvironmentVariable($key, $Environment[$key], "Process")
    }
    try {
        $process = Start-Process -FilePath $FilePath -ArgumentList $Arguments `
            -WorkingDirectory $WorkingDirectory -WindowStyle Hidden -PassThru `
            -RedirectStandardOutput $stdout -RedirectStandardError $stderr
    } finally {
        foreach ($key in $Environment.Keys) {
            [Environment]::SetEnvironmentVariable($key, $previous[$key], "Process")
        }
    }
    return $process.Id
}

function Start-Backend([System.Collections.IDictionary]$State) {
    $uv = Require-Command "uv"
    $pidValue = Start-LoggedProcess -Name "backend" -FilePath $uv `
        -Arguments @("run", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8010") `
        -WorkingDirectory (Join-Path $ProjectRoot "backend")
    $State.backendPid = $pidValue
    Write-Host "Backend started (PID $pidValue)."
}

function Start-Frontend([System.Collections.IDictionary]$State) {
    $npm = Require-Command "npm.cmd"
    $pidValue = Start-LoggedProcess -Name "frontend" -FilePath $npm -Arguments @("run", "dev") `
        -WorkingDirectory (Join-Path $ProjectRoot "frontend") `
        -Environment @{ "__VITE_ADDITIONAL_SERVER_ALLOWED_HOSTS" = $PublicHostname }
    $State.frontendPid = $pidValue
    Write-Host "Frontend started (PID $pidValue)."
}

function Stop-ManagedServices {
    $state = Read-State
    # Stop the watchdog first so it cannot relaunch a service during shutdown.
    foreach ($name in @("watchdogPid", "frontendPid", "backendPid")) {
        $pidValue = $state[$name]
        if (Test-ProcessId $pidValue) {
            Stop-ProcessTree $pidValue
            Write-Host "Stopped $name (PID $pidValue)."
        }
    }
    Remove-Item $StateFile -Force -ErrorAction SilentlyContinue
}

function Start-Watchdog {
    Initialize-Runtime
    $powershell = (Get-Process -Id $PID).Path
    $process = Start-Process -FilePath $powershell `
        -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "`"$ThisScript`"", "watch") `
        -WorkingDirectory $ProjectRoot -WindowStyle Hidden -PassThru
    $state = Read-State
    $state.watchdogPid = $process.Id
    $state.publicUrl = $PublicUrl
    Write-State $state
    Write-Host "Supervisor started (PID $($process.Id))."
    Write-Host "Public URL: $PublicUrl"
}

function Run-Watchdog {
    Initialize-Runtime
    $state = Read-State
    $state.watchdogPid = $PID
    $state.publicUrl = $PublicUrl
    Write-State $state
    Set-Content -Path (Join-Path $ProjectRoot "PUBLIC-URL.txt") -Value $PublicUrl

    while ($true) {
        try {
            if (-not (Test-ProcessId $state.backendPid)) {
                Start-Backend $state
                Write-State $state
            }

            if (-not (Test-ProcessId $state.frontendPid)) {
                Start-Frontend $state
                Write-State $state
            }
        } catch {
            $_ | Out-String | Add-Content (Join-Path $LogDir "watchdog.err.log")
        }
        Start-Sleep -Seconds 5
        $state = Read-State
        $state.watchdogPid = $PID
    }
}

function Show-Status {
    $state = Read-State
    foreach ($service in @(
        @{ Name = "Backend"; Key = "backendPid" },
        @{ Name = "Frontend"; Key = "frontendPid" },
        @{ Name = "Supervisor"; Key = "watchdogPid" }
    )) {
        $pidValue = $state[$service.Key]
        $status = if (Test-ProcessId $pidValue) { "running (PID $pidValue)" } else { "stopped" }
        Write-Host "$($service.Name): $status"
    }
    $cloudflare = Get-Service -Name $CloudflareServiceName -ErrorAction SilentlyContinue
    $cloudflareStatus = if ($cloudflare) { $cloudflare.Status.ToString().ToLowerInvariant() } else { "not installed" }
    Write-Host "Cloudflare Windows service: $cloudflareStatus"
    Set-Content -Path (Join-Path $ProjectRoot "PUBLIC-URL.txt") -Value $PublicUrl
    Write-Host "Public URL: $PublicUrl"
    Write-Host "Logs: $LogDir"
}

switch ($Action) {
    "start" {
        $state = Read-State
        if (Test-ProcessId $state.watchdogPid) {
            Write-Host "The supervisor is already running."
            Show-Status
        } else {
            Start-Watchdog
        }
    }
    "stop" { Stop-ManagedServices }
    "restart" {
        Stop-ManagedServices
        Start-Sleep -Seconds 1
        Start-Watchdog
    }
    "status" { Show-Status }
    "watch" { Run-Watchdog }
}
