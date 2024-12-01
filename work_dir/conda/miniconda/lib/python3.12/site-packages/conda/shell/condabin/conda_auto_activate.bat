:: Copyright (C) 2012 Anaconda, Inc
:: SPDX-License-Identifier: BSD-3-Clause
:: Helper script to conda_hook.bat.  This is a separate script so that the Anaconda Prompt
:: can enable this option while only conda_hook.bat can be used in AutoRun.

@FOR /F "delims=" %%i IN ('@CALL "%CONDA_EXE%" config --show auto_activate_base') DO @SET "__conda_auto_activate_base=%%i"
@IF NOT "x%__conda_auto_activate_base:True=%"=="x%__conda_auto_activate_base%" @CALL "%CONDA_BAT%" activate base
@SET __conda_auto_activate_base=
