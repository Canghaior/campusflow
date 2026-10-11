$ErrorActionPreference = 'Stop'
$dashboardDirectory = $PSScriptRoot
$projectDirectory = Split-Path -Parent $dashboardDirectory
$dashboardScript = Join-Path $dashboardDirectory 'server.py'
$pythonLauncher = Get-Command py -ErrorAction SilentlyContinue
if ($pythonLauncher) {
    $launcherArguments = @('-3', ('"' + $dashboardScript + '"'), '--open-browser')
} else {
    $pythonLauncher = Get-Command python -ErrorAction Stop
    $launcherArguments = @(('"' + $dashboardScript + '"'), '--open-browser')
}
Start-Process -FilePath $pythonLauncher.Source -ArgumentList $launcherArguments -WorkingDirectory $projectDirectory -WindowStyle Hidden
