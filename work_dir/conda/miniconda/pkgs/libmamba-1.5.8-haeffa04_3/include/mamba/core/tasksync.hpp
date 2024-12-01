// Copyright (c) 2022, QuantStack and Mamba Contributors
//
// Distributed under the terms of the BSD 3-Clause License.
//
// The full license is in the file LICENSE, distributed with this software.

#pragma once

#include <atomic>
#include <cassert>
#include <condition_variable>
#include <functional>
#include <memory>
#include <mutex>

#include "mamba/core/util_scope.hpp"

namespace mamba
{

    // WARNING: this file will be moved to xtl as soon as possible, do not rely on it's existence
    // here!

    /** Synchronize tasks execution in multiple threads with this object's lifetime.

        A synchronized callable will never execute outside the lifetime of this object.
        To achieve this, the callable must be wrapped into a callable with the same
        features that will guarantee that
          - if this object have been destroyed and then the synchronized callable is invoked,
            the callable will not execute it's code;
          - if this object is being joined and/or destroyed, it will block until any already started
            tasks are ended;

        WARNING: When used as a member of a type to syncrhonized tasks of the `this` instance, it is
        best to set the TaskSynchronizer as the last member so that it is the first one to be
       destroyed; alternatively, `.join_tasks()` can be called manually in the destructor too.

        Example:

            class MonSystem
            {
            public:

                // Whatever "scheduler" or "other_sys" is....
                MonSystem(Scheduler scheduler, OtherSystem other_sys) : scheduler(sccheduler)
                {
                    // This callback will do nothing if this object is destroyed.
                    other_sys.on_something(synchronized.synchronized([this]{ ok(); }));
                }

                void ok();

                void launch_work()
                {
                    // This task will do nothing if this object is destroyed.
                    scheduler.push(task_sync.synchronized([this]{
                        ...
                    }));
                }

            private:

                Scheduler scheduler;
                BigData data;

                task_synchronizer task_sync; // When this object is destroyed, join tasks.
            };

    */
    class TaskSynchronizer
    {
        auto make_remote_status()
        {
            return std::weak_ptr<Status>{ m_status };
        }

    public:

        TaskSynchronizer() = default;

        /** Destructor, joining tasks synchronized with this object.
            @see join_tasks()
        */
        ~TaskSynchronizer()
        {
            join_tasks();
        }

        TaskSynchronizer(const TaskSynchronizer&) = delete;
        TaskSynchronizer& operator=(const TaskSynchronizer&) = delete;

        TaskSynchronizer(TaskSynchronizer&& other) noexcept = delete;
        TaskSynchronizer& operator=(TaskSynchronizer&& other) noexcept = delete;

        /** Wrap the provided callable into a similar but synchronized callable.

            The wrapper guarantees that if the resulting callable is invoked:
                - if the joining function of this synchronizer have been called, skip execution;
                - if the joining function of this synchronizer is called while the callback is
           invoked, it will block until the end of the body of the original callable;
                - if no joining function have been called yet, notify the synchronizer that the
                    execution begins, then execute the body;

            @param work Any callable object with no arguments. The return value will be ignored.
            @return A wrapped version of the provided callable object, adding checks
                preventing execution of the original callable body if any joining function
                of this synchronizer was called.
        */
        template <class Work>
        auto synchronized(Work&& work)
        {
            return [this,
                    new_work = std::forward<Work>(work),
                    remote_status = make_remote_status()](auto&&... args) mutable
            {
                // If status is alive then we know the TaskSynchronizer is alive too.
                auto status = remote_status.lock();
                if (status && !status->join_requested)  // Don't add running tasks while join was
                                                        // requested.
                {                                       // We can use 'this' safely in this scope.
                    notify_begin_execution();
                    on_scope_exit _{ [&, this]
                                     {
                                         status.reset();  // Make sure we are not keeping the
                                                          // TaskSynchronizer waiting
                                         notify_end_execution();
                                     } };
                    std::invoke(new_work, std::forward<decltype(args)>(args)...);
                }
            };
        }

        /** Notify all synchronized tasks and blocks until all already started synchronized tasks
           are done.

            This is a joining function: once it is called, no synchronized task body will be
           executed again. Synchronized tasks which body is being executed will notify this
           synchronizer once done.

            Only returns once all the executing tasks have finished finishes.

            After calling this, is_joined() will return true.
        */
        void join_tasks()
        {
            wait_all_running_tasks();
            assert(is_joined());
        }

        /** Join synchronized tasks and reset this object's state to be reusable like if it was just
           constructed.

            Similar to calling join_tasks() but is_joined() will return false after calling this.

            @see join_tasks()
        */
        void reset()
        {
            join_tasks();
            m_status = std::make_shared<Status>();
            assert(!is_joined());
        }

        /** @return true if all synchronized tasks have beeen joined, false otherwise. @see
         * join_tasks(), reset()*/
        bool is_joined() const
        {
            return !m_status && m_running_tasks == 0;
        }

        /** @return Number of synchronized tasks which are currently beeing executed. */
        int64_t running_tasks() const
        {
            return m_running_tasks;
        }

    private:

        struct Status
        {
            std::atomic<bool> join_requested{ false };
        };

        std::atomic<int64_t> m_running_tasks{ 0 };

        std::shared_ptr<Status> m_status = std::make_shared<Status>();

        std::mutex m_mutex;
        std::condition_variable m_task_end_condition;

        void notify_begin_execution()
        {
            ++m_running_tasks;
        }

        void notify_end_execution()
        {
            {
                std::unique_lock exit_lock{ m_mutex };
                --m_running_tasks;
            }
            m_task_end_condition.notify_one();
        }

        void wait_all_running_tasks()
        {
            if (!m_status)
            {
                return;
            }

            std::unique_lock exit_lock{ m_mutex };

            auto remote_status = make_remote_status();
            m_status->join_requested = true;
            m_status.reset();

            m_task_end_condition.wait(
                exit_lock,
                [&] { return m_running_tasks == 0 && remote_status.expired(); }
            );
        }
    };

}
