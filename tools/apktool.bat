@echo off
if "%PATH_TO_FX%" == "" (
    set PATH_TO_FX=
)
java -jar "%~dp0\apktool.jar" %*
