:: Copyright (C) 2012 Anaconda, Inc
:: SPDX-License-Identifier: BSD-3-Clause
:: Helper routine for activation, deactivation, and reactivation.

@IF "%CONDA_PS1_BACKUP%"=="" GOTO :FIXUP43
    :: Handle transition from shell activated with conda 4.3 to a subsequent activation
    :: after conda updated to 4.4. See issue #6173.
    @SET "PROMPT=%CONDA_PS1_BACKUP%"
    @SET CONDA_PS1_BACKUP=
:FIXUP43

@SETLOCAL EnableDelayedExpansion
@FOR %%A IN ("%TMP%") DO @SET TMP=%%~sA
:: It seems that it is not possible to have "CONDA_EXE=Something With Spaces"
:: and %* to contain: activate "Something With Spaces does not exist".
:: MSDOS associates the outer "'s and is unable to run very much at all.
:: @SET CONDA_EXES="%CONDA_EXE%" %_CE_M% %_CE_CONDA%
:: @FOR /F %%i IN ('%CONDA_EXES% shell.cmd.exe %*') DO @SET _TEMP_SCRIPT_PATH=%%i not return error
:: This method will not work if %TMP% contains any spaces.
@FOR /L %%I IN (1,1,100) DO @(
    @SET UNIQUE_DIR=%TMP%\conda-!RANDOM!
    @MKDIR !UNIQUE_DIR! > NUL 2> NUL
    @IF NOT ERRORLEVEL 1 @(
        @SET UNIQUE=!UNIQUE_DIR!\conda.tmp
        @TYPE NUL 1> !UNIQUE!
        @GOTO :TMP_FILE_CREATED
    )
)
@ECHO Failed to create temp directory "%TMP%\conda-<RANDOM>\" & EXIT /B 1
:TMP_FILE_CREATED
@"%CONDA_EXE%" %_CE_M% %_CE_CONDA% shell.cmd.exe %* 1>%UNIQUE%
@IF %ERRORLEVEL% NEQ 0 @EXIT /B %ERRORLEVEL%
@FOR /F %%i IN (%UNIQUE%) DO @SET _TEMP_SCRIPT_PATH=%%i
@RMDIR /S /Q %UNIQUE_DIR%
@FOR /F "delims=" %%A IN (""!_TEMP_SCRIPT_PATH!"") DO @ENDLOCAL & @SET _TEMP_SCRIPT_PATH=%%~A
@IF "%_TEMP_SCRIPT_PATH%" == "" @EXIT /B 1
@IF NOT "%CONDA_PROMPT_MODIFIER%" == "" @CALL SET "PROMPT=%%PROMPT:%CONDA_PROMPT_MODIFIER%=%_empty_not_set_%%%"
@CALL "%_TEMP_SCRIPT_PATH%"
@IF NOT "%CONDA_TEST_SAVE_TEMPS%x"=="x" @ECHO CONDA_TEST_SAVE_TEMPS :: retaining activate_batch %_TEMP_SCRIPT_PATH% 1>&2
@IF "%CONDA_TEST_SAVE_TEMPS%x"=="x" @DEL /F /Q "%_TEMP_SCRIPT_PATH%"
@SET _TEMP_SCRIPT_PATH=
@SET "PROMPT=%CONDA_PROMPT_MODIFIER%%PROMPT%"
