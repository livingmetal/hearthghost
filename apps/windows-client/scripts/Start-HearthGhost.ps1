[CmdletBinding()]
param(
    [string]$InstallRoot = "",
    [string]$SourceRoot = [Environment]::GetEnvironmentVariable(
        "HEARTHGHOST_WINDOWS_UPDATE_SOURCE",
        "User"
    ),
    [string]$UpdateBranch = [Environment]::GetEnvironmentVariable(
        "HEARTHGHOST_WINDOWS_UPDATE_BRANCH",
        "User"
    ),
    [string]$CodeSigningThumbprint = [Environment]::GetEnvironmentVariable(
        "HEARTHGHOST_WINDOWS_CODE_SIGNING_THUMBPRINT",
        "User"
    ),
    [ValidateRange(1024, 65535)]
    [int]$WebPort = 51873,
    [switch]$SkipUpdate,
    [switch]$UpdateOnly
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

if ([string]::IsNullOrWhiteSpace($InstallRoot)) {
    # Windows PowerShell 5.1 does not reliably populate PSScriptRoot while
    # evaluating parameter default expressions. Resolve it from the script
    # body so installed launchers can omit -InstallRoot.
    $InstallRoot = $PSScriptRoot
}
if ([string]::IsNullOrWhiteSpace($InstallRoot)) {
    throw "HearthGhost installation root could not be resolved"
}

$installRootPath = [IO.Path]::GetFullPath($InstallRoot).TrimEnd('\')
$webRoot = Join-Path $installRootPath "web"
$nativeRoot = Join-Path $installRootPath "native"
$nativeExecutable = Join-Path $nativeRoot "HearthGhost.WindowsClient.exe"
$versionPath = Join-Path $installRootPath "UPDATE_VERSION.json"
$statusPath = Join-Path $installRootPath "UPDATE_STATUS.json"
$updateLogPath = Join-Path $installRootPath "UPDATE_LOG.txt"
$webPort = $WebPort
$webUrl = "http://127.0.0.1:$webPort/windows.html"

function Assert-InstallChildPath {
    param([Parameter(Mandatory)][string]$Path)

    $candidate = [IO.Path]::GetFullPath($Path)
    if (-not $candidate.StartsWith(
        $installRootPath + '\',
        [StringComparison]::OrdinalIgnoreCase
    )) {
        throw "Update path resolved outside the HearthGhost installation"
    }
}

function Write-UpdateStatus {
    param(
        [Parameter(Mandatory)][string]$State,
        [Parameter(Mandatory)][string]$Message,
        [string]$Commit = ""
    )

    [ordered]@{
        state = $State
        message = $Message
        branch = $UpdateBranch
        commit = $Commit
        checked_at = [DateTimeOffset]::Now.ToString("o")
    } | ConvertTo-Json | Set-Content -LiteralPath $statusPath -Encoding utf8
}

function Invoke-CheckedCommand {
    param(
        [Parameter(Mandatory)][string]$FilePath,
        [Parameter(Mandatory)][string[]]$Arguments,
        [Parameter(Mandatory)][string]$WorkingDirectory
    )

    Push-Location $WorkingDirectory
    try {
        $priorErrorAction = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        try {
            $commandOutput = & $FilePath @Arguments 2>&1
            $commandExitCode = $LASTEXITCODE
        } finally {
            $ErrorActionPreference = $priorErrorAction
        }
        $commandLines = @($commandOutput | ForEach-Object { "$_" })
        $commandLines | Out-Host
        $commandLines | Out-File -LiteralPath $updateLogPath -Encoding utf8 -Append
        if ($commandExitCode -ne 0) {
            throw "$FilePath exited with code $commandExitCode"
        }
    } finally {
        Pop-Location
    }
}

function Stop-OwnedWebServer {
    $listener = Get-NetTCPConnection -State Listen -LocalPort $webPort -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($null -eq $listener) {
        return
    }

    $process = Get-CimInstance Win32_Process -Filter "ProcessId=$($listener.OwningProcess)"
    if ($null -eq $process -or $process.CommandLine -notlike "*$webRoot*") {
        throw "HearthGhost loopback port $webPort is owned by another process"
    }
    $listenerProcessId = [int]$listener.OwningProcess
    Stop-Process -Id $listenerProcessId -Force
    for ($attempt = 0; $attempt -lt 50; $attempt++) {
        if ($null -eq (Get-Process -Id $listenerProcessId -ErrorAction SilentlyContinue)) {
            return
        }
        Start-Sleep -Milliseconds 100
    }
    throw "HearthGhost loopback server did not stop before update"
}

function Restore-PreviousInstall {
    $previousWeb = Join-Path $installRootPath "web.previous"
    $previousNative = Join-Path $installRootPath "native.previous"
    if (-not (Test-Path -LiteralPath $previousWeb -PathType Container) -or
        -not (Test-Path -LiteralPath $previousNative -PathType Container)) {
        return $false
    }

    foreach ($path in @($previousWeb, $previousNative, $webRoot, $nativeRoot)) {
        Assert-InstallChildPath -Path $path
    }
    Stop-OwnedWebServer
    if (Test-Path -LiteralPath $webRoot) {
        Remove-Item -LiteralPath $webRoot -Recurse -Force
    }
    if (Test-Path -LiteralPath $nativeRoot) {
        Remove-Item -LiteralPath $nativeRoot -Recurse -Force
    }
    Move-Item -LiteralPath $previousWeb -Destination $webRoot
    Move-Item -LiteralPath $previousNative -Destination $nativeRoot
    if (Test-Path -LiteralPath $versionPath) {
        Remove-Item -LiteralPath $versionPath -Force
    }
    Write-UpdateStatus -State "rolled_back" -Message (
        "The updated build did not start; the prior installed build was restored."
    )
    return $true
}

function Get-InstalledVersion {
    if (-not (Test-Path -LiteralPath $versionPath -PathType Leaf)) {
        return $null
    }
    try {
        return Get-Content -LiteralPath $versionPath -Raw | ConvertFrom-Json
    } catch {
        return $null
    }
}

function Remove-BuildSecrets {
    Get-ChildItem Env: | Where-Object {
        $_.Name -match "(_API_KEY|_ACCESS_TOKEN|_PRIVATE_KEY|_SECRET|_PASSWORD)$" -or
        $_.Name -in @("GH_TOKEN", "GITHUB_TOKEN", "NPM_TOKEN")
    } | ForEach-Object {
        Remove-Item -LiteralPath ("Env:" + $_.Name)
    }
}

function Protect-NativeSignature {
    param([Parameter(Mandatory)][string]$Executable)

    $requiredThumbprint = $CodeSigningThumbprint
    if ([string]::IsNullOrWhiteSpace($requiredThumbprint) -and
        (Test-Path -LiteralPath $nativeExecutable -PathType Leaf)) {
        $currentSignature = Get-AuthenticodeSignature -LiteralPath $nativeExecutable
        if ($currentSignature.Status -eq "Valid") {
            $requiredThumbprint = $currentSignature.SignerCertificate.Thumbprint
        }
    }
    if ([string]::IsNullOrWhiteSpace($requiredThumbprint)) {
        return
    }

    $normalizedThumbprint = $requiredThumbprint.Replace(" ", "").ToUpperInvariant()
    if ($normalizedThumbprint -notmatch "\A[0-9A-F]{40}\z") {
        throw "The configured code-signing certificate thumbprint is invalid"
    }
    $certificatePath = "Cert:\CurrentUser\My\$normalizedThumbprint"
    $certificate = Get-Item -LiteralPath $certificatePath -ErrorAction Stop
    if (-not $certificate.HasPrivateKey) {
        throw "The configured code-signing certificate has no private key"
    }

    Set-AuthenticodeSignature -LiteralPath $Executable -Certificate $certificate `
        -HashAlgorithm SHA256 | Out-Null
    $signature = Get-AuthenticodeSignature -LiteralPath $Executable
    if ($signature.Status -ne "Valid" -or
        $signature.SignerCertificate.Thumbprint -ne $normalizedThumbprint) {
        throw "The updated Windows executable did not pass signature verification"
    }
}

function Install-ValidatedUpdate {
    if ([string]::IsNullOrWhiteSpace($SourceRoot) -or
        [string]::IsNullOrWhiteSpace($UpdateBranch)) {
        Write-UpdateStatus -State "disabled" -Message (
            "Set HEARTHGHOST_WINDOWS_UPDATE_SOURCE and " +
            "HEARTHGHOST_WINDOWS_UPDATE_BRANCH to enable updates."
        )
        return
    }
    if ($UpdateBranch -notmatch '\A[A-Za-z0-9][A-Za-z0-9._/-]*\z' -or
        $UpdateBranch.Contains("..") -or $UpdateBranch.Contains("//")) {
        throw "The configured update branch is invalid"
    }

    $sourceRootPath = (Resolve-Path -LiteralPath $SourceRoot).Path
    $gitMetadata = Join-Path $sourceRootPath ".git"
    if (-not (Test-Path -LiteralPath $gitMetadata)) {
        throw "The configured update source is not a Git worktree"
    }

    $git = (Get-Command git.exe -ErrorAction Stop).Source
    $npm = (Get-Command npm.cmd -ErrorAction Stop).Source
    $dotnet = (Get-Command dotnet.exe -ErrorAction Stop).Source
    $remoteRef = "refs/remotes/origin/$UpdateBranch"
    $fetchRefspec = "refs/heads/${UpdateBranch}:$remoteRef"

    $originUrl = (& $git -C $sourceRootPath remote get-url origin).Trim()
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($originUrl)) {
        throw "The update source has no origin remote"
    }
    if ($originUrl -match "\Ahttps?://[^/@]+:[^/@]+@") {
        throw "The origin URL must not contain embedded credentials"
    }

    Set-Content -LiteralPath $updateLogPath -Value (
        "HearthGhost update check started at $([DateTimeOffset]::Now.ToString('o'))"
    ) -Encoding utf8
    Invoke-CheckedCommand -FilePath $git -Arguments @(
        "-C", $sourceRootPath, "fetch", "--quiet", "--no-tags", "origin", $fetchRefspec
    ) -WorkingDirectory $sourceRootPath

    $remoteCommit = (& $git -C $sourceRootPath rev-parse --verify "${remoteRef}^{commit}").Trim()
    if ($LASTEXITCODE -ne 0 -or $remoteCommit -notmatch '\A[0-9a-f]{40}\z') {
        throw "The configured remote branch did not resolve to a commit"
    }

    $installed = Get-InstalledVersion
    if ($null -ne $installed -and
        $installed.branch -eq $UpdateBranch -and
        $installed.commit -eq $remoteCommit) {
        Write-UpdateStatus -State "current" -Message "Installed build is current." -Commit $remoteCommit
        return
    }

    Remove-BuildSecrets

    $updateRoot = Join-Path $installRootPath ".update"
    $temporaryRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\')
    $stageSource = Join-Path $temporaryRoot (
        "hearthghost-update-" + $remoteCommit.Substring(0, 12) + "-" + [Guid]::NewGuid().ToString("N")
    )
    $stageWeb = Join-Path $updateRoot "web"
    $stageNative = Join-Path $updateRoot "native"
    foreach ($path in @($updateRoot, $stageWeb, $stageNative)) {
        Assert-InstallChildPath -Path $path
    }
    if (-not $stageSource.StartsWith(
        $temporaryRoot + '\hearthghost-update-',
        [StringComparison]::OrdinalIgnoreCase
    )) {
        throw "Temporary worktree path resolved outside the expected directory"
    }

    & $git -C $sourceRootPath worktree prune | Out-Null
    if (Test-Path -LiteralPath $updateRoot) {
        Remove-Item -LiteralPath $updateRoot -Recurse -Force
    }
    New-Item -ItemType Directory -Path $updateRoot | Out-Null

    try {
        Invoke-CheckedCommand -FilePath $git -Arguments @(
            "-C", $sourceRootPath, "worktree", "add", "--detach", $stageSource, $remoteCommit
        ) -WorkingDirectory $sourceRootPath

        $stageWebSource = Join-Path $stageSource "apps\web-client"
        Invoke-CheckedCommand -FilePath $npm -Arguments @("ci") -WorkingDirectory $stageWebSource
        Invoke-CheckedCommand -FilePath $npm -Arguments @("test") -WorkingDirectory $stageWebSource
        Invoke-CheckedCommand -FilePath $npm -Arguments @("run", "windows:assets") -WorkingDirectory $stageWebSource
        Invoke-CheckedCommand -FilePath $npm -Arguments @("run", "build") -WorkingDirectory $stageWebSource

        New-Item -ItemType Directory -Path $stageWeb | Out-Null
        $copyOutput = & robocopy.exe $stageWebSource $stageWeb /E `
            /XD android .test-dist dist node_modules /NFL /NDL /NJH /NJS /NP
        $copyExitCode = $LASTEXITCODE
        @($copyOutput | ForEach-Object { "$_" }) |
            Out-File -LiteralPath $updateLogPath -Encoding utf8 -Append
        if ($copyExitCode -ge 8) {
            throw "Copying the validated web client failed with code $copyExitCode"
        }
        Invoke-CheckedCommand -FilePath $npm -Arguments @(
            "ci", "--ignore-scripts"
        ) -WorkingDirectory $stageWeb

        $project = Join-Path $stageSource "apps\windows-client\HearthGhost.WindowsClient.csproj"
        Invoke-CheckedCommand -FilePath $dotnet -Arguments @(
            "publish", $project, "--configuration", "Release", "--output", $stageNative
        ) -WorkingDirectory $stageSource
        Protect-NativeSignature -Executable (
            Join-Path $stageNative "HearthGhost.WindowsClient.exe"
        )

        foreach ($requiredFile in @(
            (Join-Path $stageWeb "package.json"),
            (Join-Path $stageWeb "public\models\AvatarSample_A.vrm"),
            (Join-Path $stageWeb "public\animations\airi-idle-loop.vrma"),
            (Join-Path $stageNative "HearthGhost.WindowsClient.exe")
        )) {
            if (-not (Test-Path -LiteralPath $requiredFile -PathType Leaf)) {
                throw "Validated update is missing a required runtime file"
            }
        }

        & $git -C $sourceRootPath worktree remove --force $stageSource | Out-Null
        if ($LASTEXITCODE -ne 0) {
            throw "The temporary update worktree could not be detached"
        }

        Stop-OwnedWebServer
        $previousWeb = Join-Path $installRootPath "web.previous"
        $previousNative = Join-Path $installRootPath "native.previous"
        foreach ($path in @($previousWeb, $previousNative)) {
            Assert-InstallChildPath -Path $path
            if (Test-Path -LiteralPath $path) {
                Remove-Item -LiteralPath $path -Recurse -Force
            }
        }

        $webMoved = $false
        $nativeMoved = $false
        $newWebInstalled = $false
        $newNativeInstalled = $false
        try {
            if (Test-Path -LiteralPath $webRoot) {
                Move-Item -LiteralPath $webRoot -Destination $previousWeb
                $webMoved = $true
            }
            if (Test-Path -LiteralPath $nativeRoot) {
                Move-Item -LiteralPath $nativeRoot -Destination $previousNative
                $nativeMoved = $true
            }
            Move-Item -LiteralPath $stageWeb -Destination $webRoot
            $newWebInstalled = $true
            Move-Item -LiteralPath $stageNative -Destination $nativeRoot
            $newNativeInstalled = $true
        } catch {
            if ($newWebInstalled -and (Test-Path -LiteralPath $webRoot)) {
                Remove-Item -LiteralPath $webRoot -Recurse -Force
            }
            if ($newNativeInstalled -and (Test-Path -LiteralPath $nativeRoot)) {
                Remove-Item -LiteralPath $nativeRoot -Recurse -Force
            }
            if ($webMoved -and (Test-Path -LiteralPath $previousWeb)) {
                Move-Item -LiteralPath $previousWeb -Destination $webRoot
            }
            if ($nativeMoved -and (Test-Path -LiteralPath $previousNative)) {
                Move-Item -LiteralPath $previousNative -Destination $nativeRoot
            }
            throw
        }

        [ordered]@{
            branch = $UpdateBranch
            commit = $remoteCommit
            installed_at = [DateTimeOffset]::Now.ToString("o")
        } | ConvertTo-Json | Set-Content -LiteralPath $versionPath -Encoding utf8
        Write-UpdateStatus -State "updated" -Message "Validated update installed." -Commit $remoteCommit
    } finally {
        if (Test-Path -LiteralPath $stageSource) {
            $priorErrorAction = $ErrorActionPreference
            $ErrorActionPreference = "Continue"
            try {
                & $git -C $sourceRootPath worktree remove --force $stageSource 2>$null | Out-Null
            } finally {
                $ErrorActionPreference = $priorErrorAction
            }
        }
        if (Test-Path -LiteralPath $stageSource) {
            Remove-Item -LiteralPath $stageSource -Recurse -Force
        }
        if (Test-Path -LiteralPath $updateRoot) {
            Remove-Item -LiteralPath $updateRoot -Recurse -Force
        }
        & $git -C $sourceRootPath worktree prune | Out-Null
    }
}

New-Item -ItemType Directory -Path $installRootPath -Force | Out-Null

if (-not $UpdateOnly) {
    $runningNative = @(Get-CimInstance Win32_Process | Where-Object {
        $_.ExecutablePath -eq $nativeExecutable
    })
    if ($runningNative.Count -gt 0) {
        Write-UpdateStatus -State "deferred" -Message (
            "HearthGhost is already running; update deferred until the next launch."
        )
        exit 0
    }
}

$autoUpdate = [Environment]::GetEnvironmentVariable(
    "HEARTHGHOST_WINDOWS_AUTO_UPDATE",
    "User"
)
$updateFailed = $false
if (-not $SkipUpdate -and ($autoUpdate -eq "1" -or $UpdateOnly)) {
    try {
        Install-ValidatedUpdate
    } catch {
        $updateFailed = $true
        Write-UpdateStatus -State "failed" -Message (
            "Update failed; the previous installed build was preserved. " + $_.Exception.Message
        )
    }
} elseif (-not $SkipUpdate) {
    Write-UpdateStatus -State "disabled" -Message (
        "Set HEARTHGHOST_WINDOWS_AUTO_UPDATE=1 to enable startup updates."
    )
}

if ($UpdateOnly) {
    if ($updateFailed) {
        exit 1
    }
    exit 0
}

$requiredUserVariables = @(
    "HEARTHGHOST_WINDOWS_CERT_THUMBPRINT",
    "HEARTHGHOST_WINDOWS_CA_THUMBPRINT",
    "HEARTHGHOST_WINDOWS_CORE_HOST",
    "HEARTHGHOST_WINDOWS_CORE_PORT",
    "HEARTHGHOST_WINDOWS_NODE_ID"
)
foreach ($name in $requiredUserVariables) {
    $value = [Environment]::GetEnvironmentVariable($name, "User")
    if ([string]::IsNullOrWhiteSpace($value)) {
        throw "Required HearthGhost user configuration is missing: $name"
    }
    Set-Item -LiteralPath "Env:$name" -Value $value
}
$env:HEARTHGHOST_WEB_DEV_URL = $webUrl

function Start-WebServerAndWait {
    $listener = Get-NetTCPConnection -State Listen -LocalPort $webPort -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($null -ne $listener) {
        $listenerProcess = Get-CimInstance Win32_Process -Filter "ProcessId=$($listener.OwningProcess)"
        if ($null -eq $listenerProcess -or $listenerProcess.CommandLine -notlike "*$webRoot*") {
            throw "HearthGhost loopback port $webPort is already owned by another process"
        }
    } else {
        Start-Process -FilePath "npm.cmd" `
            -ArgumentList @("run", "dev", "--", "--port", "$webPort", "--strictPort") `
            -WorkingDirectory $webRoot `
            -WindowStyle Hidden | Out-Null
    }

    for ($attempt = 0; $attempt -lt 40; $attempt++) {
        try {
            $response = Invoke-WebRequest -UseBasicParsing -Uri $webUrl -TimeoutSec 1
            if ($response.StatusCode -eq 200 -and $response.Content -like "*HearthGhost Windows*") {
                return
            }
        } catch {
            Start-Sleep -Milliseconds 250
        }
    }
    throw "HearthGhost loopback UI did not become ready"
}

if (-not (Test-Path -LiteralPath $nativeExecutable -PathType Leaf)) {
    throw "HearthGhost Windows executable is missing"
}

try {
    Start-WebServerAndWait
    $nativeProcess = Start-Process -FilePath $nativeExecutable `
        -WorkingDirectory $nativeRoot -PassThru
    Start-Sleep -Milliseconds 750
    if ($nativeProcess.HasExited) {
        throw "HearthGhost Windows executable exited during startup"
    }
} catch {
    $startupFailure = $_.Exception.Message
    if (-not (Restore-PreviousInstall)) {
        throw
    }
    Start-WebServerAndWait
    Start-Process -FilePath $nativeExecutable -WorkingDirectory $nativeRoot | Out-Null
    Write-Warning "$startupFailure; restored and started the prior installed build."
}
