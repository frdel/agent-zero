#include "mamba/core/error_handling.hpp"

namespace mamba
{
    class MPool;
    class MultiPackageCache;

    expected_t<void, mamba_aggregated_error>
    load_channels(MPool& pool, MultiPackageCache& package_caches, int is_retry);
}
