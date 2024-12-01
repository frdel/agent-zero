#ifndef MAMBA_API_CONSTANTS_HPP
#define MAMBA_API_CONSTANTS_HPP

namespace mamba
{
    const int MAMBA_NO_PREFIX_CHECK = 1 << 0;
    const int MAMBA_ALLOW_EXISTING_PREFIX = 1 << 1;
    const int MAMBA_ALLOW_MISSING_PREFIX = 1 << 2;
    const int MAMBA_ALLOW_NOT_ENV_PREFIX = 1 << 3;
    const int MAMBA_EXPECT_EXISTING_PREFIX = 1 << 4;

    const int MAMBA_NOT_ALLOW_EXISTING_PREFIX = 0;
    const int MAMBA_NOT_ALLOW_MISSING_PREFIX = 0;
    const int MAMBA_NOT_ALLOW_NOT_ENV_PREFIX = 0;
    const int MAMBA_NOT_EXPECT_EXISTING_PREFIX = 0;

    const int MAMBA_CONF_FORCE_COMPUTE = 1 << 0;
    const int MAMBA_CONF_DISABLE_HOOK = 1 << 1;

    const int MAMBA_FORCE = 1 << 0;
    const int MAMBA_REMOVE_FORCE = MAMBA_FORCE;
    const int MAMBA_REMOVE_PRUNE = 1 << 1;
    const int MAMBA_REMOVE_ALL = 1 << 2;
}

#endif
