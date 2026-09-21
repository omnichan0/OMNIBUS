\
    $ErrorActionPreference = "Stop"
    $Root = Split-Path -Parent $MyInvocation.MyCommand.Path

    Write-Host "============================================================"
    Write-Host " SOVEREIGN AI FACTORY - Windows bootstrap"
    Write-Host "============================================================"

    # The core runtime is Linux-first because llama.cpp, Open WebUI,
    # Cline and the service supervisor are designed around POSIX tooling.
    # Windows is supported through WSL2 so the same repository is used.
    $wsl = Get-Command wsl.exe -ErrorAction SilentlyContinue
    if (-not $wsl) {
        Write-Host "WSL2 is required for the supported Windows runtime."
        Write-Host "Install WSL2, reboot if requested, then run this script again."
        Write-Host "Microsoft command: wsl --install"
        exit 1
    }

    $linuxPath = (wsl.exe wslpath -a "$Root").Trim()
    if (-not $linuxPath) {
        throw "Could not convert repository path for WSL."
    }

    Write-Host "[platform] Windows + WSL2"
    Write-Host "[repo] $linuxPath"
    wsl.exe bash -lc "cd '$linuxPath' && chmod +x install.sh && ./install.sh"
