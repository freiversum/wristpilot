# Builds the Wristpilot Bridge for Windows as a single .exe (Nuitka, onefile).
# Run on Windows (or in GitHub Actions, see .github/workflows/release.yml), in the folder windows\:
#   powershell -ExecutionPolicy Bypass -File build.ps1
# Result: windows\dist\WristpilotBridge.exe

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

$version = (& $venvPy -c "import wristpilot_bridge; print(wristpilot_bridge.__version__)").Trim()

& $venvPy -m nuitka `
  --onefile `
  --assume-yes-for-downloads `
  --windows-console-mode=disable `
  --windows-icon-from-ico=wristpilot.ico `
  --company-name="linuxundich" `
  --product-name="Wristpilot Bridge" `
  --file-version=$version `
  --product-version=$version `
  --file-description="Garmin watch remote for Zwift" `
  --include-package=wristpilot_bridge `
  --include-package=winrt `
  --include-package-data=winrt `
  --include-package=zeroconf `
  --noinclude-custom-mode=bumble:bytecode `
  --noinclude-custom-mode=cryptography:bytecode `
  --include-module=bumble.transport.usb `
  --include-module=bumble.drivers.rtk `
  --include-module=bumble.drivers.intel `
  --nofollow-import-to=bumble.apps `
  --nofollow-import-to=bumble.tools `
  --nofollow-import-to=bumble.testing `
  --nofollow-import-to=bumble.transport.android_emulator `
  --nofollow-import-to=bumble.transport.android_netsim `
  --nofollow-import-to=bumble.transport.grpc_protobuf `
  --nofollow-import-to=grpc `
  --include-module=usb1 `
  --include-package=libusb_package `
  --include-package-data=libusb_package `
  --include-data-dir=..\bridge\wristpilot_bridge\firmware=wristpilot_bridge\firmware `
  --include-package=pystray `
  --include-module=zwiftlogin `
  --enable-plugin=tk-inter `
  --output-dir=dist `
  --output-filename=WristpilotBridge.exe `
  wristpilot_tray.py

Get-Item dist\WristpilotBridge.exe | Select-Object Name, Length
