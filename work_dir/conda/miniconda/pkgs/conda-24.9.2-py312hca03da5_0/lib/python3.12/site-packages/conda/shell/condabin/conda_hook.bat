:: Copyright (C) 2012 Anaconda, Inc
:: SPDX-License-Identifier: BSD-3-Clause
:: The file name is conda_hook.bat rather than conda-hook.bat because conda will see
:: the latter as a 'conda hook' command.

@IF DEFINED CONDA_SHLVL GOTO :EOF

@FOR %%F IN ("%~dp0") DO @SET "__condabin_dir=%%~dpF"
@SET "__condabin_dir=%__condabin_dir:~0,-1%"
@SET "PATH=%__condabin_dir%;%PATH%"
@SET "CONDA_BAT=%__condabin_dir%\conda.bat"
@FOR %%F IN ("%__condabin_dir%") DO @SET "__conda_root=%%~dpF"
@SET "CONDA_EXE=%__conda_root%Scripts\conda.exe"
@SET __condabin_dir=
@SET __conda_root=

@DOSKEY conda="%CONDA_BAT%" $*

@SET CONDA_SHLVL=0
