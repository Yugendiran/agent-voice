<#
.SYNOPSIS
  Installs agent-voice on Windows.

.DESCRIPTION
  1. Installs pyenv-win (if missing) and the Python version from .python-version
  2. Creates a private virtualenv in ~/.agent-voice/venv and installs agent-voice
  3. Downloads the Kokoro voice model (~115 MB)
  4. Puts the `agent-voice` command on your PATH
  5. Starts it now and at every login (skip with -NoAutostart)

  Run from a checkout:   powershell -ExecutionPolicy Bypass -File install.ps1
  Or just double-click install.cmd.
#>
param(
    [switch]$NoAutostart,
    # Where to install agent-voice from: this folder, or a pip-installable URL.
    [string]$Source = ""
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"   # makes Invoke-WebRequest much faster on PS 5.1

function Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Ok($msg)   { Write-Host "    $msg" -ForegroundColor Green }

$Repo = "Yugendiran/agent-voice"
$Here = $PSScriptRoot
if (-not $Source) {
    if ($Here -and (Test-Path (Join-Path $Here "pyproject.toml"))) { $Source = $Here }
    elseif ($env:AGENT_VOICE_SOURCE) { $Source = $env:AGENT_VOICE_SOURCE }
    else {
        # Not run from a checkout (e.g. `irm .../install.ps1 | iex`): fetch the
        # latest source from GitHub. No git needed.
        Step "Downloading agent-voice from github.com/$Repo"
        $zip = Join-Path $env:TEMP "agent-voice-main.zip"
        $unpacked = Join-Path $env:TEMP "agent-voice-src"
        Invoke-WebRequest -UseBasicParsing -Uri "https://github.com/$Repo/archive/refs/heads/main.zip" -OutFile $zip
        if (Test-Path $unpacked) { Remove-Item -Recurse -Force $unpacked }
        Expand-Archive -Path $zip -DestinationPath $unpacked -Force
        Remove-Item $zip -ErrorAction SilentlyContinue
        $Here = (Get-ChildItem $unpacked -Directory | Select-Object -First 1).FullName
        $Source = $Here
    }
}

$PyVersion = "3.12.10"
$VersionFile = Join-Path $Here ".python-version"
if ($Here -and (Test-Path $VersionFile)) { $PyVersion = (Get-Content $VersionFile -TotalCount 1).Trim() }

$AppHome = if ($env:AGENT_VOICE_HOME) { $env:AGENT_VOICE_HOME } else { Join-Path $HOME ".agent-voice" }
$Venv = Join-Path $AppHome "venv"
$BinDir = Join-Path $AppHome "bin"
New-Item -ItemType Directory -Force $AppHome, $BinDir | Out-Null

# Stop a running copy so its files can be replaced.
$running = Join-Path $Venv "Scripts\agent-voice.exe"
if (Test-Path $running) { & $running stop | Out-Null }

# ---------------------------------------------------------------- pyenv-win
Step "Checking pyenv"
$PyenvRoot = if ($env:PYENV_ROOT) { $env:PYENV_ROOT } else { Join-Path $HOME ".pyenv\pyenv-win" }
$PyenvBat = Join-Path $PyenvRoot "bin\pyenv.bat"
if (-not (Test-Path $PyenvBat)) {
    $found = Get-Command pyenv -ErrorAction SilentlyContinue
    if ($found) {
        $PyenvBat = $found.Source
        $PyenvRoot = Split-Path (Split-Path $PyenvBat)
    } else {
        Write-Host "    pyenv-win not found, installing it to $HOME\.pyenv ..."
        $installer = Join-Path $env:TEMP "install-pyenv-win.ps1"
        Invoke-WebRequest -UseBasicParsing -Uri "https://raw.githubusercontent.com/pyenv-win/pyenv-win/master/pyenv-win/install-pyenv-win.ps1" -OutFile $installer
        & $installer
        Remove-Item $installer -ErrorAction SilentlyContinue
        $PyenvRoot = Join-Path $HOME ".pyenv\pyenv-win"
        $PyenvBat = Join-Path $PyenvRoot "bin\pyenv.bat"
        if (-not (Test-Path $PyenvBat)) { throw "pyenv-win install failed; see https://github.com/pyenv-win/pyenv-win" }
    }
}
$env:PYENV = $PyenvRoot + "\"
$env:PYENV_ROOT = $env:PYENV
$env:PYENV_HOME = $env:PYENV
$env:Path = "$PyenvRoot\bin;$PyenvRoot\shims;$env:Path"
Ok "pyenv: $PyenvRoot"

# ---------------------------------------------------------------- Python
Step "Installing Python $PyVersion with pyenv"
$Python = Join-Path $PyenvRoot "versions\$PyVersion\python.exe"
if (-not (Test-Path $Python)) {
    & $PyenvBat update | Out-Null
    & $PyenvBat install $PyVersion
    if (-not (Test-Path $Python)) { throw "pyenv could not install Python $PyVersion" }
}
Ok (& $Python --version)

# ---------------------------------------------------------------- virtualenv + package
Step "Installing agent-voice into $Venv"
$VenvPython = Join-Path $Venv "Scripts\python.exe"
if (Test-Path $VenvPython) {
    # Recreate the venv if it was built from a different Python.
    $current = (& $VenvPython -c "import platform; print(platform.python_version())").Trim()
    if ($current -ne $PyVersion) { Remove-Item -Recurse -Force $Venv }
}
if (-not (Test-Path $VenvPython)) { & $Python -m venv $Venv }
& $VenvPython -m pip install --quiet --disable-pip-version-check --upgrade pip
& $VenvPython -m pip install --quiet --disable-pip-version-check --upgrade "$Source"
if ($LASTEXITCODE -ne 0) { throw "pip install failed" }
Ok "installed"

# ---------------------------------------------------------------- command on PATH
Step "Adding the agent-voice command to your PATH"
Set-Content -Encoding ascii -Path (Join-Path $BinDir "agent-voice.cmd") -Value "@`"$Venv\Scripts\agent-voice.exe`" %*"
$userPath = (Get-ItemProperty -Path HKCU:\Environment -Name Path -ErrorAction SilentlyContinue).Path
if (-not $userPath) { $userPath = "" }
if (($userPath -split ";") -notcontains $BinDir) {
    # Write the registry directly: [Environment]::SetEnvironmentVariable can hang
    # for minutes broadcasting the change to an unresponsive window.
    $newPath = ($userPath.TrimEnd(";") + ";" + $BinDir).TrimStart(";")
    New-ItemProperty -Path HKCU:\Environment -Name Path -Value $newPath -PropertyType ExpandString -Force | Out-Null
    Add-Type -Namespace AgentVoice -Name Win32 -MemberDefinition @'
[DllImport("user32.dll", CharSet = CharSet.Auto)]
public static extern IntPtr SendMessageTimeout(IntPtr hWnd, uint Msg, UIntPtr wParam, string lParam, uint fuFlags, uint uTimeout, out UIntPtr lpdwResult);
'@
    $result = [UIntPtr]::Zero
    # HWND_BROADCAST, WM_SETTINGCHANGE, SMTO_ABORTIFHUNG, 1s per window
    [AgentVoice.Win32]::SendMessageTimeout([IntPtr]0xffff, 0x1A, [UIntPtr]::Zero, "Environment", 2, 1000, [ref]$result) | Out-Null
    Ok "added $BinDir (open a new terminal to use it)"
} else {
    Ok "already on PATH"
}
$env:Path = "$BinDir;$env:Path"
$Cli = Join-Path $Venv "Scripts\agent-voice.exe"

# ---------------------------------------------------------------- voice model
Step "Downloading the voice model"
& $Cli download
if ($LASTEXITCODE -ne 0) { throw "model download failed" }
Ok "ready"

# ---------------------------------------------------------------- start
if ($NoAutostart) {
    & $Cli autostart off | Out-Null
} else {
    Step "Starting agent-voice (and at every login)"
    & $Cli autostart on
    & $Cli start
    & $Cli say "agent-voice is ready. I will read out what Claude Code and Codex say."
}

Write-Host ""
Write-Host "Done! Useful commands (in a new terminal):" -ForegroundColor Green
Write-Host "  agent-voice status        is it running?"
Write-Host "  agent-voice mute/unmute   silence it"
Write-Host "  agent-voice voices        list voices, then: agent-voice config voice am_michael"
Write-Host "  agent-voice config final_only true   only speak the end-of-turn summary"
Write-Host "  agent-voice help          everything else"
