### coding_agent:

#### Operation Manual
this tool controls an autonomous coding agent, your professional developer assistant
the underlying framework of this tool is the "aider-chat" - ai powered software development framework written in python
each task for the coding agent is a new tool call
the coding agent does not retain memories between calls
you can give the agent development tasks he will complete in one go
always provide a very comprehensive and exhaustive context and requirements in the task text
give the agent a persona + provide all necessary background info + formulate hard and soft requirements + formulate the task in an actionable way = provide this, well formatted, in the task argument
always ensure the root_path exists for new development without existig codebase
to first test the changes without changing code on disk, use the dry_run boolean parameter to simulate agent's output
if you want the agent to create or edit only specific files in the root_path you must pass the list of those files in the "files" parameter, path relative to root_path. you can also give agent readonly files in the "readonly_files" parameter

#### Arguments:
* *task* (string, mandatory) - The task description including persona, background info, requirements
* *root_path* (string, mandatory) - Absolute path to the folder the agent will work in. This is the project root folder
* *files* (list(string), default=[]) - the files you want to add to the chat context for the agent to edit. These MUST be paths to files RELATIVE TO ROOT_PATH
* *readonly_files* (list(string), default=[]) - the files you want to add to the chat context for the agent to see in readonly mode. Gives the agent hints which files to read for the task. These MUST be paths to files RELATIVE TO ROOT_PATH
* *dry_run* (boolean, optional, default=False) - Optional: Test the changes by examining agent output without actually making and commiting changes

#### Usage:
```json
{
  "thoughts": ["I need to develop a..."],
  "tool_name": "coding_agent",
  "tool_args": {
    "task": "You are a ..... \n\nThis project is .... \n\nPlease implement .... and make sure that .... in the attached files ...",
    "root_path": "/path/to/project/folder",
    "files": ["main.py", "pyhton/settings.py"],
    "readonly_files": ["do_not_edit.py"],
    "dry_run": false
  }
}
```

```json
{
  "thoughts": ["I need to develop a..."],
  "tool_name": "coding_agent",
  "tool_args": {
    "task": "You are a ..... \n\n\nThis project is .... \n\nPlease implement .... ",
    "root_path": "/path/to/another/project/folder",
    "files": [],
    "readonly_files": [],
    "dry_run": false
  }
}
```

```json
{
  "thoughts": ["Let's see what the agent would do if ..."],
  "tool_name": "coding_agent",
  "tool_args": {
    "task": "You are a ..... \n\n\nThis project is .... \n\nPlease implement .... ",
    "root_path": "/path/to/another/project/folder",
    "dry_run": true
  }
}
```
