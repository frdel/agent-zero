# Context Window Plugin DOX

## Purpose

- Own context-window token accounting, the usage API, the composer indicator,
  its popover, its Interface visibility row, and per-call output speed.

## Ownership

- `helpers/usage.py` owns per-prompt bucket measurement and reconciliation.
- `helpers/currency.py` owns optional USD exchange-rate lookup and validation.
- `helpers/output_speed.py` owns output-speed timing and measurement.
- `extensions/python/` records prompt parts at their source extension points,
  preserves terminal streamed usage, captures optional provider usage, and
  times streamed output.
- `api/context_window.py` exposes the active chat's token usage and effective
  model limit plus display flags and price-currency metadata without returning
  prompt content or modifying stored provider usage.
- `webui/` and `extensions/webui/` own the Alpine store, indicator, popover,
  model-override refresh, plugin display settings, Interface visibility row,
  and generation-step speed label.

## Local Contracts

- The six used-token buckets are `messages`, `system_tools`, `skills`,
  `mcp_tools`, `system_prompt`, and `extras`.
- Tools, MCP tools, and the available-skills catalog are measured from their
  extensible prompt builders, never inferred from rendered headings.
- Loaded skill instructions are removed from Messages and added to Skills.
- Protocol and prompt extras are reported together as Extras.
- Messages reuse the history record token ledger; independently rendered
  fragments use a bounded, content-addressed, runtime-only cache.
- Bucket totals reconcile to the already-stored prompt token total; the
  unclaimed remainder belongs to System prompt.
- If the history ledger would consume the whole prompt estimate, recompute only
  the rendered message portion before reconciliation; ordinary prompt builds
  keep the fast ledger path.
- The prompt estimate never guesses provider-specific image token costs or
  counts embedded image bytes as text.
- Provider price, cache hit, input/output tokens, and output speed form a flat
  summary without diagnostic detail rows and share the same regular-weight
  typography.
- Output speed is (provider output tokens - 1) divided by the seconds between
  the first and last streamed delta of one main model call, stamped when Agent
  Zero receives each delta. It excludes time to first token. When the
  provider reports reasoning tokens that were not streamed (hidden or only
  summarized), they ran outside the stream, so only the answer counts: output
  tokens minus reasoning tokens over the answer deltas. It is omitted, never
  estimated, when the provider reports no output tokens, the call was paused,
  or the window is under one second. A pause is flagged at
  `handle_intervention`, where the agent actually waits.
- Timing relies on two core behaviors: stream callbacks wait out a pause inside
  `handle_intervention`, and `call_chat_model_turn` hands the timed callbacks to
  `unified_turn`, whose usage drain keeps calling them to the terminal chunk.
- The speed joins the generation log item's kvps as `output_speed` at
  `message_loop_result`, after the core and Context Doctor rewrites, so it
  persists with the chat and labels each finished generation step. It is logged
  for handled (`skip_default_processing`) turns too: it describes the call, not
  the result.
- Step speed labels follow the `contextWindowUsage` visibility setting through
  a root `hide-output-speed` class.
- Provider rows are exposed only when the provider or transport reports their
  values; unavailable price and cache data render no row.
- Global `show_breakdown`, `show_price`, `show_cache_hit`, and `show_tokens`
  settings default to true and apply on each usage refresh or popover opening.
  Hiding the breakdown also hides its empty state; hiding all provider rows
  removes their container and divider. Accounting and the summary remain intact.
- `price_currency` defaults to USD; USD never invokes the rate helper or makes
  an external request. Fetch Frankfurter's daily reference rate only for a
  visible, nonzero provider cost in a selected non-USD currency. Cache valid
  rates for 24 hours and failed lookups for five minutes. Only currency codes
  leave the server. Validate pair, positive finite rate, and date; on failure,
  show the original USD amount with an explicit USD label and explanation.
- Streaming main turns request LiteLLM's terminal usage event for every
  provider through the transport's `stream_options.include_usage` injection,
  so provider input/output and cache tokens reach the summary. The response
  callback still runs normally; only an actual Chat Completions result
  restores the accepted response after the accounting tail is drained.
- Responses API turns keep their native result and callback behavior unchanged.
- Older chats without a stored breakdown show the explanatory empty state.
- The indicator refreshes once per new Agent 0 generation, after four root-agent
  tool calls without another refresh, when the final response completes the run,
  and when the active chat log GUID changes (including Clear Chat). Streamed
  updates to an existing generation or tool log do not refetch it.
- Snapshot-triggered usage refreshes must not delay message rendering. Apply
  results only from the latest request while its chat is still selected.
- `_model_config` supplies the effective model limit and the
  `model-context-strip-end` WebUI slot; it does not own this feature's state.
- The `contextWindowUsage` Interface setting defaults to visible on mobile and
  desktop.

## Work Guidance

- Keep prompt accounting out of rendered-text heuristics.
- Keep provider-reported usage separate from the six estimated context buckets.
- Keep the API response limited to usage counts, whitelisted display flags,
  and effective price-currency metadata.
- Preserve the upward, right-aligned popover beside the model/profile selectors. Its minimum strip footprint is bounded by the available width; shared `x-overflow` positions the same popover when the indicator enters the overflow menu. `data-overflow-label` names the entry; `data-overflow-icon` retains its live percentage ring.

## Verification

- Run `conda run -n a0 pytest plugins/_context_window/tests`.
- Smoke-test the indicator, popover, chat switching, post-run refresh,
  generation-step speed labels, and mobile/desktop visibility against the live
  WebUI.

## Child DOX Index

No child DOX files.
