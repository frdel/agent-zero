Your previous tool call was cut off before its complete arguments or closing delimiters arrived. No recovered call was executed. Re-emit the entire request as one complete JSON object with no surrounding prose, markup, or code fence:
{"thoughts":["Brief reasoning"],"tool_name":"available_tool_name","tool_args":{}}
Keep reasoning brief. If an argument is too large for one response, split the work into complete, independently valid tool calls across turns. Never omit required arguments or truncate their values.
