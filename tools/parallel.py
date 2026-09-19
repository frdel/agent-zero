from helpers.tool import Tool, Response
from helpers.tool import coerce_bool
from helpers import parallel_tools
from helpers.strings import sanitize_string


class ParallelTool(Tool):
    async def before_execution(self, **kwargs):
        self.log = None

    async def after_execution(self, response: Response, **kwargs):
        text = sanitize_string(response.message.strip())
        self.agent.hist_add_tool_result(
            self.name,
            text,
            **(response.additional or {}),
        )
        await parallel_tools.collect_parallel_jobs(
            self.agent,
            getattr(self, "_collect_job_ids", []),
            promote_parent_history=True,
        )

    async def execute(self, **kwargs) -> Response:
        self._collect_job_ids = []
        args = {**self.args, **kwargs}
        action = str(args.get("action") or "").strip().lower()

        try:
            timeout = parallel_tools.coerce_timeout(args.get("timeout"))
            job_ids = parallel_tools.normalize_job_ids(args.get("job_ids"))

            if action == "cancel":
                results = await parallel_tools.cancel_parallel_jobs(self.agent, job_ids)
                return Response(
                    message=parallel_tools.format_parallel_results(results),
                    break_loop=False,
                )

            raw_calls = parallel_tools.extract_tool_calls(args)
            started_jobs = []
            if raw_calls is not None:
                calls = parallel_tools.normalize_parallel_tool_calls(raw_calls)
                started_jobs = await parallel_tools.start_parallel_jobs(self.agent, calls)

            started_job_ids = [job.id for job in started_jobs]
            all_job_ids = [*job_ids, *started_job_ids]

            if not all_job_ids:
                return Response(
                    message=(
                        "Error: provide `tool_calls` to start parallel jobs, "
                        "or `job_ids` to await/cancel existing jobs."
                    ),
                    break_loop=False,
                )

            wait_default = action not in {"start", "background", "collect"}
            wait = coerce_bool(args.get("wait"), wait_default)
            if action in {"await", "wait"}:
                wait = True

            if not wait:
                if not started_jobs and not job_ids:
                    return Response(
                        message="Error: `wait: false` requires `tool_calls` to start new jobs.",
                        break_loop=False,
                    )
                if not job_ids:
                    return Response(
                        message=parallel_tools.format_started_jobs(started_jobs),
                        break_loop=False,
                    )
                results = await parallel_tools.await_parallel_jobs(
                    self.agent,
                    all_job_ids,
                    timeout=timeout,
                    collect=False,
                    wait=False,
                )
                self._collect_job_ids = [result["job_id"] for result in results]
                return Response(
                    message=parallel_tools.format_parallel_results(results),
                    break_loop=False,
                )

            results = await parallel_tools.await_parallel_jobs(
                self.agent,
                all_job_ids,
                timeout=timeout,
                collect=False,
                wait=True,
            )
            self._collect_job_ids = [result["job_id"] for result in results]
            return Response(
                message=parallel_tools.format_parallel_results(results),
                break_loop=False,
            )
        except ValueError as exc:
            return Response(message=f"Error: {exc}", break_loop=False)
