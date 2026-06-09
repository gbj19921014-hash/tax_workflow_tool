$ErrorActionPreference = "Stop"

Set-Location (Join-Path $PSScriptRoot "..\..")

python -m pip install -r tax_workflow_tool\requirements-build.txt
python -m PyInstaller --clean --noconfirm tax_workflow_tool\packaging\pyinstaller_windows.spec

$isccCandidates = @(
  "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
  "${env:ProgramFiles}\Inno Setup 6\ISCC.exe"
)
$iscc = $isccCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $iscc) {
  Write-Host "已生成 dist\A1-A3税务工作流。"
  Write-Host "如需安装程序，请先安装 Inno Setup 6，然后重新运行本脚本。"
  exit 0
}

& $iscc "tax_workflow_tool\packaging\windows_installer.iss"
Write-Host "已生成 Windows 安装包：dist\installer"
