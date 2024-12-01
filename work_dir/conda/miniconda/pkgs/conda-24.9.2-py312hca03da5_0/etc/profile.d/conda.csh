setenv CONDA_EXE "/var/folders/k1/30mswbxs7r1g6zwn8y4fyt500000gp/T/abs_f0q92r98ek/croot/conda_1729193891987/_h_env_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehol/bin/conda"
setenv _CONDA_ROOT "/var/folders/k1/30mswbxs7r1g6zwn8y4fyt500000gp/T/abs_f0q92r98ek/croot/conda_1729193891987/_h_env_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehol"
setenv _CONDA_EXE "/var/folders/k1/30mswbxs7r1g6zwn8y4fyt500000gp/T/abs_f0q92r98ek/croot/conda_1729193891987/_h_env_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehol/bin/conda"
setenv CONDA_PYTHON_EXE "/var/folders/k1/30mswbxs7r1g6zwn8y4fyt500000gp/T/abs_f0q92r98ek/croot/conda_1729193891987/_h_env_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehol/bin/python"
# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
if (! $?_CONDA_EXE) then
  set _CONDA_EXE="${PWD}/conda/shell/bin/conda"
else
  if ("$_CONDA_EXE" == "") then
      set _CONDA_EXE="${PWD}/conda/shell/bin/conda"
  endif
endif

if ("`alias conda`" == "") then
    if ($?_CONDA_EXE) then
        # _CONDA_PFX is named so as not to cause confusion with CONDA_PREFIX
        # If nested backticks were possible we wouldn't use any variables here.
        set _CONDA_PFX=`dirname "${_CONDA_EXE}"`
        set _CONDA_PFX=`dirname "${_CONDA_PFX}"`
        alias conda source "${_CONDA_PFX}/etc/profile.d/conda.csh"
        # And for good measure, get rid of it afterwards.
        unset _CONDA_PFX
    else
        alias conda source "${PWD}/conda/shell/etc/profile.d/conda.csh"
    endif
    setenv CONDA_SHLVL 0
    if (! $?prompt) then
        set prompt=""
    endif
else
    switch ( "${1}" )
        case "activate":
            set ask_conda="`(setenv prompt '${prompt}' ; '${_CONDA_EXE}' shell.csh activate '${2}' ${argv[3-]})`"
            set conda_tmp_status=$status
            if( $conda_tmp_status != 0 ) exit ${conda_tmp_status}
            eval "${ask_conda}"
            rehash
            breaksw
        case "deactivate":
            set ask_conda="`(setenv prompt '${prompt}' ; '${_CONDA_EXE}' shell.csh deactivate '${2}' ${argv[3-]})`"
            set conda_tmp_status=$status
            if( $conda_tmp_status != 0 ) exit ${conda_tmp_status}
            eval "${ask_conda}"
            rehash
            breaksw
        case "install" | "update" | "upgrade" | "remove" | "uninstall":
            $_CONDA_EXE $argv[1-]
            set ask_conda="`(setenv prompt '${prompt}' ; '${_CONDA_EXE}' shell.csh reactivate)`"
            set conda_tmp_status=$status
            if( $conda_tmp_status != 0 ) exit ${conda_tmp_status}
            eval "${ask_conda}"
            rehash
            breaksw
        default:
            $_CONDA_EXE $argv[1-]
            breaksw
    endsw
endif
