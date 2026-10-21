# Removes agent-voice (keeps pyenv and its Python, which other projects may use).
$ErrorActionPreference = "Continue"
$AppHome = if ($env:AGENT_VOICE_HOME) { $env:AGENT_VOICE_HOME } else { Join-Path $HOME ".agent-voice" }
$Cli = Join-Path $AppHome "venv\Scripts\agent-voice.exe"
if (Test-Path $Cli) {
    & $Cli stop
    & $Cli autostart off
}
$BinDir = Join-Path $AppHome "bin"
$userPath = (Get-ItemProperty -Path HKCU:\Environment -Name Path -ErrorAction SilentlyContinue).Path
if ($userPath -and (($userPath -split ";") -contains $BinDir)) {
    $kept = ($userPath -split ";") | Where-Object { $_ -and $_ -ne $BinDir }
    # Registry write instead of [Environment]::SetEnvironmentVariable, which can hang.
    New-ItemProperty -Path HKCU:\Environment -Name Path -Value ($kept -join ";") -PropertyType ExpandString -Force | Out-Null
}
Start-Sleep -Milliseconds 500
Remove-Item -Recurse -Force $AppHome -ErrorAction SilentlyContinue
Write-Host "agent-voice removed."
