@echo off
pushd %~dp0
mkdir dist
del /q dist\*

echo Build with pyinstaller...

pyinstaller main.py --onefile -n arcin_conf_infinitas --noconsole

REM python setup.py py2exe

popd