# One-time setup for automatic updates

This project is designed so the user does **not** need Python, PyInstaller, Inno Setup, or CMD after the first installation.

## 1. Create a GitHub repository

Create a repository named `embroidery-sorter-pro` under your GitHub account.

## 2. Upload this project

Upload the project files, including `.github/workflows/build-release.yml`.

## 3. Set the repository URL in the app

In `EmbroiderySorterPro.py`, replace:

`https://raw.githubusercontent.com/REPLACE_ME/embroidery-sorter-pro/main/update.json`

with:

`https://raw.githubusercontent.com/YOUR_USERNAME/embroidery-sorter-pro/main/update.json`

Also replace `REPLACE_ME` in `update.json` with your GitHub username.

## 4. Create a release

For example, create a tag/release named `v2.3.0`.
GitHub Actions will automatically build the Windows EXE and Inno Setup installer and attach the installer to the release.

## 5. Future versions

Change `APP_VERSION` in `EmbroiderySorterPro.py`, update `installer.iss`, and update `update.json`, then create a new tag such as `v2.4.0`.
GitHub Actions builds the installer automatically.

Installed users can use **Check for Updates**. The app also checks silently a few seconds after startup. When a newer version is found, it downloads the latest installer, launches it, and exits so the installer can update the installed application.
