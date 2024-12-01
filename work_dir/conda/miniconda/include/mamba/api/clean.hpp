// Copyright (c) 2019, QuantStack and Mamba Contributors
//
// Distributed under the terms of the BSD 3-Clause License.
//
// The full license is in the file LICENSE, distributed with this software.

#ifndef MAMBA_API_CLEAN_HPP
#define MAMBA_API_CLEAN_HPP


namespace mamba
{
    const int MAMBA_CLEAN_ALL = 1 << 0;
    const int MAMBA_CLEAN_INDEX = 1 << 1;
    const int MAMBA_CLEAN_PKGS = 1 << 2;
    const int MAMBA_CLEAN_TARBALLS = 1 << 3;
    const int MAMBA_CLEAN_LOCKS = 1 << 4;
    const int MAMBA_CLEAN_TRASH = 1 << 5;
    const int MAMBA_CLEAN_FORCE_PKGS_DIRS = 1 << 6;

    class Configuration;
    void clean(Configuration& config, int options);
}

#endif
