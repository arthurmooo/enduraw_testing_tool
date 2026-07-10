#requires -Version 5.1
[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

if ([System.Environment]::OSVersion.Platform -ne [System.PlatformID]::Win32NT) {
    throw "Ce build doit etre execute sur Windows. Utilisez le workflow GitHub Actions depuis macOS."
}

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$UiRoot = Join-Path $RepoRoot "local_ui"
$VenvRoot = Join-Path $RepoRoot ".venv-build-windows"
$VenvPython = Join-Path $VenvRoot "Scripts\python.exe"
$SpecPath = Join-Path $RepoRoot "packaging\windows\EndurawTestingTool.spec"
$IssPath = Join-Path $RepoRoot "packaging\windows\EndurawTestingTool.iss"
$AppDist = Join-Path $RepoRoot "dist\EndurawTestingTool"
$SetupPath = Join-Path $RepoRoot "artifacts\EndurawTestingTool-Setup.exe"

function Assert-Command {
    param([Parameter(Mandatory = $true)][string]$Name)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Commande requise introuvable: $Name"
    }
}

function Find-InnoCompiler {
    if ($env:INNO_SETUP_COMPILER -and (Test-Path $env:INNO_SETUP_COMPILER)) {
        return (Resolve-Path $env:INNO_SETUP_COMPILER).Path
    }
    $command = Get-Command "ISCC.exe" -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }
    $candidates = @(
        (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"),
        (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe")
    )
    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path $candidate)) {
            return $candidate
        }
    }
    throw "Inno Setup 6 est requis. Installez-le puis relancez ce script."
}

Push-Location $RepoRoot
try {
    Assert-Command "node"
    Assert-Command "npm"
    Write-Host "[1/5] Build React" -ForegroundColor Cyan
    & npm --prefix $UiRoot ci
    if ($LASTEXITCODE -ne 0) { throw "npm ci a echoue." }
    & npm --prefix $UiRoot run build
    if ($LASTEXITCODE -ne 0) { throw "Le build React a echoue." }
    if (-not (Test-Path (Join-Path $UiRoot "dist\index.html"))) {
        throw "local_ui\dist\index.html n'a pas ete produit."
    }

    Write-Host "[2/5] Environnement Python de build" -ForegroundColor Cyan
    if (-not (Test-Path $VenvPython)) {
        Assert-Command "python"
        & python -m venv $VenvRoot
        if ($LASTEXITCODE -ne 0) { throw "Creation du venv Windows impossible." }
    }
    & $VenvPython -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) { throw "Mise a jour de pip impossible." }
    & $VenvPython -m pip install -r (Join-Path $RepoRoot "requirements.txt")
    if ($LASTEXITCODE -ne 0) { throw "Installation des dependances Python impossible." }

    Write-Host "[3/5] Bundle PyInstaller onedir" -ForegroundColor Cyan
    Remove-Item (Join-Path $RepoRoot "build\windows") -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item $AppDist -Recurse -Force -ErrorAction SilentlyContinue
    & $VenvPython -m PyInstaller `
        --noconfirm `
        --clean `
        --workpath (Join-Path $RepoRoot "build\windows") `
        --distpath (Join-Path $RepoRoot "dist") `
        $SpecPath
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller a echoue." }
    if (-not (Test-Path (Join-Path $AppDist "EndurawTestingTool.exe"))) {
        throw "L'executable PyInstaller attendu est absent."
    }

    Write-Host "[4/5] Installateur Inno Setup" -ForegroundColor Cyan
    $InnoCompiler = Find-InnoCompiler
    $ConfigText = Get-Content (Join-Path $RepoRoot "src\config.py") -Raw
    $VersionMatch = [regex]::Match($ConfigText, 'APP_VERSION\s*=\s*["'']([^"'']+)["'']')
    if (-not $VersionMatch.Success) { throw "APP_VERSION est introuvable dans src\config.py." }
    $AppVersion = $VersionMatch.Groups[1].Value
    New-Item (Join-Path $RepoRoot "artifacts") -ItemType Directory -Force | Out-Null
    Remove-Item $SetupPath -Force -ErrorAction SilentlyContinue
    $VersionDefine = "/DMyAppVersion=$AppVersion"
    $SourceDefine = "/DSourceRoot=$RepoRoot"
    & $InnoCompiler $VersionDefine $SourceDefine $IssPath
    if ($LASTEXITCODE -ne 0) { throw "Inno Setup a echoue." }
    if (-not (Test-Path $SetupPath)) { throw "Le setup final attendu est absent." }

    Write-Host "[5/5] Termine" -ForegroundColor Green
    Write-Host "Installateur: $SetupPath" -ForegroundColor Green
}
finally {
    Pop-Location
}
