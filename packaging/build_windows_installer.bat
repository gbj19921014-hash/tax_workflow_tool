@echo off
setlocal
chcp 65001 >nul

cd /d "%~dp0\.."

echo 正在制作 Windows 安装包，请不要关闭这个窗口。
echo.
echo 当前目录：%cd%
echo 日志文件：%cd%\build_windows_installer.log
echo.

echo 第一步：调用 PowerShell 打包脚本...
echo 如果这里停留较久，是在下载依赖或打包程序，属于正常情况。
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "packaging\build_windows_installer.ps1" > "build_windows_installer.log" 2>&1

if errorlevel 1 (
  echo.
  echo 打包失败。请打开下面这个日志文件，把里面最后几行发给我：
  echo %cd%\build_windows_installer.log
  echo.
  echo ===== 日志内容开始 =====
  type "build_windows_installer.log"
  echo ===== 日志内容结束 =====
) else (
  echo.
  echo 打包命令执行完成。
  echo.
  echo 请检查是否生成：
  echo %cd%\dist\installer\A1-A3税务工作流安装包.exe
)

echo.
echo 如果看到 dist\installer\A1-A3税务工作流安装包.exe，说明安装包已经生成。
pause
