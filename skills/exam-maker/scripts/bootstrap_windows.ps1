[CmdletBinding()]
param(
    [switch]$Apply,
    [switch]$Editor,
    [string]$Report = 'exam-environment.json',
    [string]$SkillsDir,
    [string[]]$RuntimeBin = @()
)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'find_hancom_windows.ps1')
$examHancom = @(Find-ExamNativeHancom)
if ($examHancom.Count -gt 0 -and -not $Editor) {
    $nativeReport = @{
        status='READY'; workflow='hancom'; apply=[bool]$Apply; actions=@()
        hancom=$examHancom; editor_required=$false
        editor_smoke=@{status='SKIPPED_NATIVE'}
        native_layout_status='AVAILABLE_NOT_YET_VERIFIED'; computer_use_status='CHECK_IN_AGENT'
    }
    $reportPath = [IO.Path]::GetFullPath($Report)
    [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($reportPath)) | Out-Null
    $nativeReport | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $reportPath -Encoding UTF8
    $nativeReport | ConvertTo-Json -Depth 6
    exit 0
}
function Find-ExamPython {
    $candidates = @()
    $command = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($command) { $candidates += $command.Source }
    foreach ($bin in $RuntimeBin) { $candidates += Join-Path $bin 'python.exe' }
    $candidates += @(Get-ChildItem -Path "$env:LOCALAPPDATA\Programs\Python\Python*\python.exe" -ErrorAction SilentlyContinue | ForEach-Object FullName)
    foreach ($candidate in ($candidates | Select-Object -Unique)) {
        if ((Test-Path -LiteralPath $candidate) -and $candidate -notmatch '\\WindowsApps\\') {
            try {
                & $candidate -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)'
                if ($LASTEXITCODE -eq 0) { return $candidate }
            } catch { }
        }
    }
    return $null
}
$examPython = Find-ExamPython
if (-not $examPython -and $Apply) {
    Write-Host 'Python is required. Installing Python.Python.3.12 from winget.'
    $manager = Get-Command winget.exe -ErrorAction SilentlyContinue
    if (-not $manager) { throw 'Python and winget are unavailable. Supply the Codex bundled Python path using -RuntimeBin.' }
    & $manager.Source install --id Python.Python.3.12 -e --source winget --scope user --silent --accept-package-agreements --accept-source-agreements --disable-interactivity --no-upgrade
    if ($LASTEXITCODE -ne 0) { throw "Python installer failed: $LASTEXITCODE" }
    $examPython = Find-ExamPython
}
if (-not $examPython) { throw 'No verified Python 3.10+. Run with -Apply or provide a bundled runtime path.' }
$examArgs = @('-X','utf8',(Join-Path $PSScriptRoot 'bootstrap_exam.py'),'--report',$Report)
if ($Apply) { $examArgs += '--apply' }
if ($Editor) { $examArgs += '--editor' }
if ($SkillsDir) { $examArgs += @('--skills-dir',$SkillsDir) }
foreach ($bin in $RuntimeBin) { $examArgs += @('--runtime-bin',$bin) }
& $examPython @examArgs
exit $LASTEXITCODE
