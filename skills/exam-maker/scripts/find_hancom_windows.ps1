# Read-only native discovery, including machines without Python/Node/Git.
function Find-ExamNativeHancom {
    [CmdletBinding()]
    param()
    $candidates = @()
    $roots = @()
    function Read-ExamRegistryDefault([string]$Path) {
        try { (Get-Item -LiteralPath $Path -ErrorAction Stop).GetValue('') } catch { $null }
    }
    Get-Process -Name Hwp -ErrorAction SilentlyContinue | ForEach-Object {
        try { $candidates += $_.Path } catch { }
    }
    foreach ($hive in @('HKLM:', 'HKCU:')) {
        foreach ($prefix in @('SOFTWARE', 'SOFTWARE\WOW6432Node')) {
            $appKey = "$hive\$prefix\Microsoft\Windows\CurrentVersion\App Paths\Hwp.exe"
            $candidates += Read-ExamRegistryDefault $appKey
            $comKey = "$hive\$prefix\Classes\HWPFrame.HwpObject\CLSID"
            $clsid = Read-ExamRegistryDefault $comKey
            if ($clsid) {
                $server = "$hive\$prefix\Classes\CLSID\$clsid\LocalServer32"
                $candidates += Read-ExamRegistryDefault $server
            }
            Get-ItemProperty -Path "$hive\$prefix\Microsoft\Windows\CurrentVersion\Uninstall\*" -ErrorAction SilentlyContinue |
                Where-Object { $_.DisplayName -match 'hancom|hanword|hangeul|한글|한컴' } | ForEach-Object {
                    $candidates += $_.DisplayIcon
                    if ($_.InstallLocation -and (Test-Path -LiteralPath $_.InstallLocation -PathType Container)) {
                        $resolved = (Resolve-Path -LiteralPath $_.InstallLocation).Path
                        if ($resolved.TrimEnd('\') -ne [IO.Path]::GetPathRoot($resolved).TrimEnd('\')) { $roots += $resolved }
                    }
                }
        }
    }
    foreach ($base in @($env:ProgramFiles, ${env:ProgramFiles(x86)}, "$env:LOCALAPPDATA\Programs")) {
        if ($base -and (Test-Path -LiteralPath $base -PathType Container)) {
            $roots += Get-ChildItem -LiteralPath $base -Directory -ErrorAction SilentlyContinue |
                Where-Object { $_.Name -match 'hnc|hancom|hanword|hangeul|한컴|한글' } | ForEach-Object FullName
        }
    }
    foreach ($root in ($roots | Select-Object -Unique)) {
        $candidates += Get-ChildItem -LiteralPath $root -Filter Hwp.exe -File -Recurse -Depth 7 -ErrorAction SilentlyContinue | ForEach-Object FullName
    }
    $paths = foreach ($candidate in $candidates) {
        if (-not ($candidate -is [string])) { continue }
        $exe = $null
        if ($candidate -match '^\s*"([^\"]+\.exe)"') { $exe = $Matches[1] }
        elseif ($candidate -match '^\s*(.*?\.exe)(?=\s|,|$)') { $exe = $Matches[1] }
        if (-not $exe) { continue }
        $exe = [Environment]::ExpandEnvironmentVariables($exe)
        if ([IO.Path]::GetFileName($exe) -ine 'Hwp.exe' -or $exe -match 'viewer|뷰어') { continue }
        if (Test-Path -LiteralPath $exe -PathType Leaf) { (Resolve-Path -LiteralPath $exe).Path }
    }
    foreach ($path in ($paths | Select-Object -Unique)) {
        @{ path=$path; app="process:$path"; sources=@('Windows native discovery') }
    }
}
