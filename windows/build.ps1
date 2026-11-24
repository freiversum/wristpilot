# Builds the ZWindoor Bridge for Windows as a single .exe (Nuitka, onefile).
# Run on Windows (or in GitHub Actions, see .github/workflows/release.yml), in the folder windows\:
#   powershell -ExecutionPolicy Bypass -File build.ps1
# Result: windows\dist\ZWindoorBridge.exe

$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $true   # a failing pip/nuitka call stops the build
Set-Location $PSScriptRoot

# Prefer "python" (the interpreter set up by CI or on PATH), fall back to the py launcher
$py = "python"
if (-not (Get-Command $py -ErrorAction SilentlyContinue)) { $py = "py" }

& $py -m venv .venv-build
$venvPy = ".venv-build\Scripts\python.exe"
& $venvPy -m pip install --upgrade pip
& $venvPy -m pip install "..\bridge[tray]" nuitka ordered-set zstandard

& $venvPy make_ico.py
& $venvPy ..\bridge\tools\fetch_rtk_firmware.py   # Realtek firmware for Bumble (UB500 and similar)

$version = (& $venvPy -c "import zwindoor_bridge; print(zwindoor_bridge.__version__)").Trim()

& $venvPy -m nuitka `
  --onefile `
  --assume-yes-for-downloads `
  --windows-console-mode=disable `
  --windows-icon-from-ico=zwindoor.ico `
  --company-name="linuxundich" `
  --product-name="ZWindoor Bridge" `
  --file-version=$version `
  --product-version=$version `
  --file-description="Garmin watch remote for Zwift" `
  --include-package=zwindoor_bridge `
  --include-package=winrt `
  --include-package-data=winrt `
  --include-package=zeroconf `
  --include-package=bumble `
  --include-package-data=bumble `
  --include-module=usb1 `
  --include-package=libusb_package `
  --include-package-data=libusb_package `
  --include-data-dir=..\bridge\zwindoor_bridge\firmware=zwindoor_bridge\firmware `
  --include-package=pystray `
  --include-module=zwiftlogin `
  --enable-plugin=tk-inter `
  --output-dir=dist `
  --output-filename=ZWindoorBridge.exe `
  zwindoor_tray.py

Get-Item dist\ZWindoorBridge.exe | Select-Object Name, Length
