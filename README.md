# Embroidery Sorter Pro

Offline Windows desktop utility for organizing embroidery design files.

## Build
1. Install Python 3.
2. Open Command Prompt in this folder.
3. Run `build_windows.bat`.
4. The script builds `dist\Embroidery Sorter Pro.exe`.
5. If Inno Setup 6 is installed, it also builds `installer\Embroidery_Sorter_Pro_Setup.exe`.

## Installer
The installer places the app in Program Files, creates Start Menu and Desktop shortcuts, and registers a normal Windows uninstaller.

Install Inno Setup 6 if the installer step says it was not found.

## Updating later
Keep the same source project. When features are added, update `EmbroiderySorterPro.py`, increase `MyAppVersion` in `installer.iss`, then run `build_windows.bat` again. Installing the newer setup updates the existing app. User settings/history are stored outside the install folder, so they are not tied to Program Files.
