// Copyright (c) 2019, QuantStack and Mamba Contributors
//
// Distributed under the terms of the BSD 3-Clause License.
//
// The full license is in the file LICENSE, distributed with this software.

#ifndef MAMBA_CORE_SOLVER_HPP
#define MAMBA_CORE_SOLVER_HPP

#include <iosfwd>
#include <memory>
#include <optional>
#include <string>
#include <utility>
#include <vector>

#include <solv/pooltypes.h>
#include <solv/solvable.h>
// Incomplete header
#include <solv/rules.h>

#include "mamba/core/package_info.hpp"
#include "mamba/core/pool.hpp"
#include "mamba/core/satisfiability_error.hpp"

#include "match_spec.hpp"

#define PY_MAMBA_NO_DEPS 0b0001
#define PY_MAMBA_ONLY_DEPS 0b0010
#define PY_MAMBA_FORCE_REINSTALL 0b0100

extern "C"
{
    typedef struct s_Solver Solver;
}

namespace mamba::solv
{
    class ObjQueue;
    class ObjSolver;
}

namespace mamba
{

    struct MSolverProblem
    {
        SolverRuleinfo type;
        Id source_id;
        Id target_id;
        Id dep_id;
        std::optional<PackageInfo> source;
        std::optional<PackageInfo> target;
        std::optional<std::string> dep;
        std::string description;
    };


    class MSolver
    {
    public:

        struct Flags
        {
            /** Keep the dependencies of the install package in the solution. */
            bool keep_dependencies = true;
            /** Keep the original required package in the solution. */
            bool keep_specs = true;
            /** Force reinstallation of jobs. */
            bool force_reinstall = false;
        };

        MSolver(MPool pool, std::vector<std::pair<int, int>> flags = {});
        ~MSolver();

        MSolver(const MSolver&) = delete;
        MSolver& operator=(const MSolver&) = delete;
        MSolver(MSolver&&);
        MSolver& operator=(MSolver&&);

        void add_global_job(int job_flag);
        void add_jobs(const std::vector<std::string>& jobs, int job_flag);
        void add_constraint(const std::string& job);
        void add_pin(const std::string& pin);
        void add_pins(const std::vector<std::string>& pins);

        [[deprecated]] void py_set_postsolve_flags(const std::vector<std::pair<int, int>>& flags);

        void set_flags(const Flags& flags);  // TODO temporary Itf meant to be passed in ctor
        [[nodiscard]] auto flags() const -> const Flags&;
        [[deprecated]] void py_set_libsolv_flags(const std::vector<std::pair<int, int>>& flags);

        [[nodiscard]] bool try_solve();
        void must_solve();
        [[nodiscard]] bool is_solved() const;

        [[nodiscard]] std::string problems_to_str() const;
        [[nodiscard]] std::vector<std::string> all_problems() const;
        [[nodiscard]] std::vector<MSolverProblem> all_problems_structured() const;
        [[nodiscard]] ProblemsGraph problems_graph() const;
        [[nodiscard]] std::string all_problems_to_str() const;
        std::ostream& explain_problems(std::ostream& out) const;
        [[nodiscard]] std::string explain_problems() const;

        [[nodiscard]] const MPool& pool() const&;
        [[nodiscard]] MPool& pool() &;
        [[nodiscard]] MPool&& pool() &&;

        [[nodiscard]] const std::vector<MatchSpec>& install_specs() const;
        [[nodiscard]] const std::vector<MatchSpec>& remove_specs() const;
        [[nodiscard]] const std::vector<MatchSpec>& neuter_specs() const;
        [[nodiscard]] const std::vector<MatchSpec>& pinned_specs() const;

        operator const Solver*() const;
        operator Solver*();
        auto solver() -> solv::ObjSolver&;
        auto solver() const -> const solv::ObjSolver&;

    private:

        std::vector<std::pair<int, int>> m_libsolv_flags;
        std::vector<MatchSpec> m_install_specs;
        std::vector<MatchSpec> m_remove_specs;
        std::vector<MatchSpec> m_neuter_specs;
        std::vector<MatchSpec> m_pinned_specs;
        // Order of m_pool and m_solver is critical since m_pool must outlive m_solver.
        MPool m_pool;
        // Temporary Pimpl all libsolv to keep it private
        std::unique_ptr<solv::ObjSolver> m_solver;
        std::unique_ptr<solv::ObjQueue> m_jobs;
        Flags m_flags = {};
        bool m_is_solved;

        void add_reinstall_job(MatchSpec& ms, int job_flag);
        void apply_libsolv_flags();
    };
}  // namespace mamba

#endif  // MAMBA_SOLVER_HPP
