// Copyright (c) 2023, QuantStack and Mamba Contributors
//
// Distributed under the terms of the BSD 3-Clause License.
//
// The full license is in the file LICENSE, distributed with this software.

#include <map>
#include <optional>
#include <string>
#include <vector>

#include <nlohmann/json_fwd.hpp>

#include "mamba/specs/platform.hpp"
#include "mamba/specs/version.hpp"

namespace mamba::specs
{
    /**
     * Noarch packages are packages that are not architecture specific.
     *
     * Noarch packages only have to be built once.
     */
    enum struct NoArchType
    {
        /** Noarch generic packages allow users to distribute docs, datasets, and source code. */
        Generic,

        /**
         * A noarch python package is a python package without any precompiled python files.
         *
         * Normally, precompiled files (`.pyc` or `__pycache__`) are bundled with the package.
         * However, these files are tied to a specific version of Python and must therefore be
         * generated for every target platform and architecture.
         * This complicates the build process.
         * For noarch Python packages these files are generated when installing the package by
         * invoking the compilation process through the python binary that is installed in the
         * same environment.
         *
         * @see https://www.anaconda.com/blog/condas-new-noarch-packages
         * @see
         * https://docs.conda.io/projects/conda/en/latest/user-guide/concepts/packages.html#noarch-python
         */
        Python,
    };

    /**
     * A single record in the Conda ``repodata.json``.
     *
     * A single record refers to a single binary distribution of a package on a Conda channel.
     *
     * Looking at the `RepoDataPackage` class in the Conda source code a record can also include
     * the following fields but it is unclear what they do.
     *  - std::optional<std::string> preferred_env;
     *  - std::optional<std::string> date;
     *  - ? package_type
     * Repodata also contains some of the following keys, although they are not parsed by Conda.
     * - std::optional<std::string> app_type;
     * - std::optional<std::string> app_entry;
     *
     * @see conda.models.records
     *      https://github.com/conda/conda/blob/main/conda/models/records.py
     * @see rattler_conda_types::repo_data::PackageRecord
     *      https://github.com/mamba-org/rattler/blob/main/crates/rattler_conda_types/src/repo_data/mod.rs
     */
    struct RepoDataPackage
    {
        /** The name of the package. */
        std::string name = {};

        /** The version of the package. */
        Version version = Version(0, { { { 0 } } });

        /** The build string of the package. */
        std::string build_string = {};

        /** The build number of the package. */
        std::size_t build_number = {};

        /**
         * The subdirectory where the package can be found.
         *
         * This is likely not used as it contains not so useful strings such as "linux".
         */
        std::optional<std::string> subdir = {};

        /** Optionally a MD5 hash of the package archive. */
        std::optional<std::string> md5 = {};

        /** Optionally a SHA256 hash of the package archive. */
        std::optional<std::string> sha256 = {};

        /** A deprecated md5 hash. */
        std::optional<std::string> legacy_bz2_md5 = {};

        /** A deprecated package archive size. */
        std::optional<std::size_t> legacy_bz2_size = {};

        /** Optionally the size of the package archive in bytes. */
        std::optional<std::size_t> size = {};

        /** Optionally the architecture the package supports. */
        std::optional<std::string> arch = {};

        /** Optionally the platform the package supports. */
        std::optional<std::string> platform = {};

        /** Specification of packages this package depends on. */
        std::vector<std::string> depends = {};

        /**
         * Additional constraints on packages.
         *
         * `constrains` are different from `depends` in that packages specified in `depends` must
         * be installed next to this package, whereas packages specified in `constrains` are not
         * required to be installed, but if they are installed they must follow these constraints.
         */
        std::vector<std::string> constrains = {};

        /**
         * Track features are nowadays only used to deprioritize packages.
         *
         * To that effect, the number of track features is counted (number of commas) and the
         * package is downweighted by the number of track_features.
         */
        std::vector<std::string> track_features = {};

        /**
         * Features are a deprecated way to specify different feature sets for the conda solver.
         *
         * This is not supported anymore and should not be used.
         * Instead, `mutex` packages should be used to specify mutually exclusive features.
         */
        std::optional<std::string> features = {};

        /** If this package is independent of architecture this field specifies in what way. */
        std::optional<NoArchType> noarch = {};

        /** The specific license of the package. */
        std::optional<std::string> license = {};

        /** The license family. */
        std::optional<std::string> license_family = {};

        /**
         * The UNIX Epoch timestamp when this package was created.
         *
         * Note that sometimes this is specified in seconds and sometimes in milliseconds.
         */
        std::optional<std::size_t> timestamp = {};
    };

    /**
     * Serialize to JSON.
     *
     * Optional members are omitted from json.
     */
    void to_json(nlohmann::json& j, const RepoDataPackage& p);

    /**
     * Deserialize from JSON
     *
     * Missing json entries fill optionals with a null values and collections as empty.
     * Special handling of the following fields is performed:
     * - ``"noarch"`` can be a string or a boolean (old behaviour), in which case ``false``
     *   parse to ``std::nullopt`` and ``true`` to ``NoArchType::Generic``.
     * - ``"track_features"`` can be a string or list of string. In the former case, it is
     *   considered as a single element list.
     */
    void from_json(const nlohmann::json& j, RepoDataPackage& p);


    /** Information about subdirectory of channel in the Conda RepoData. */
    struct ChannelInfo
    {
        /** The channel's subdirectory. */
        Platform subdir = {};
    };

    /** Serialize to JSON. */
    void to_json(nlohmann::json& j, const ChannelInfo& info);

    /** Deserialize from JSON. */
    void from_json(const nlohmann::json& j, ChannelInfo& info);

    /**
     * The repository data structure.
     *
     * This schema maps to the repository ``repodata.json``.
     **/
    struct RepoData
    {
        /** The version of the repodata format. */
        std::optional<std::size_t> version = {};

        /** The channel information contained in the repodata.json file.
         */
        std::optional<ChannelInfo> info = {};

        /**
         * The tar.bz2 packages contained in the repodata.json file.
         *
         * Maps a filename sucha as ``libmamba-0.13.0-h3a044de_0.tar.bz2`` to its RepoDataPackage.
         **/
        std::map<std::string, RepoDataPackage> packages = {};

        /**
         * The conda packages contained in the repodata.json file.
         *
         * Maps a filename such as ``libmamba-1.3.0-hcea66bb_1.conda`` to its RepoDataPackage.
         * This is put under a different key for backwards compatibility with previous conda
         * versions.
         */
        std::map<std::string, RepoDataPackage> conda_packages = {};

        /**
         * Removed packages
         *
         * These files are still accessible, but they are not installable like regular packages.
         */
        std::vector<std::string> removed = {};
    };

    /**
     * Serialize to JSON.
     *
     * Optional members are omitted from json.
     */
    void to_json(nlohmann::json& j, const RepoData& data);

    /**
     * Deserialize from JSON
     *
     * Missing json entries fill optionals with a null values and collections as empty.
     */
    void from_json(const nlohmann::json& j, RepoData& data);
}
