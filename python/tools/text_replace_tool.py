import os
import os
import re
import shutil
import fnmatch # Import fnmatch for glob pattern matching
from python.helpers.tool import Tool, Response
from python.helpers.print_style import PrintStyle

class TextReplaceTool(Tool):
    async def execute(self, **kwargs):
        await self.agent.handle_intervention()

        command = self.args.get("command", "").lower().strip()
        
        try:
            if command == "replace":
                response = self._handle_replace()
            elif command == "batch_replace":
                response = self._handle_batch_replace()
            else:
                response = f"Error: Unknown command '{command}'. Supported commands: replace, batch_replace."
            
            return Response(message=response, break_loop=False)

        except FileNotFoundError as e:
            return Response(message=f"Error: File not found - {e}", break_loop=False)
        except ValueError as e:
            return Response(message=f"Error: Invalid argument - {e}", break_loop=False)
        except re.error as e:
            return Response(message=f"Error: Invalid regex pattern - {e}", break_loop=False)
        except Exception as e:
            return Response(message=f"An unexpected error occurred: {e}", break_loop=False)

    def _get_source_content(self, source_arg, encoding="utf-8"):
        if os.path.isfile(source_arg):
            with open(source_arg, 'r', encoding=encoding) as f:
                return f.read()
        elif isinstance(source_arg, str):
            return source_arg
        else:
            raise ValueError(f"Invalid source: {source_arg}. Must be a file path or a string.")

    def _apply_replacement(self, content, search_pattern, replace_string, regex, case_sensitive):
        flags = 0
        if not case_sensitive:
            flags |= re.IGNORECASE
        
        if not search_pattern:
            raise ValueError("Search pattern cannot be empty.")

        if regex:
            compiled_pattern = re.compile(search_pattern, flags)
            new_content, count = compiled_pattern.subn(replace_string, content)
        else:
            # Escape special characters for literal string search if not regex
            escaped_search = re.escape(search_pattern)
            compiled_pattern = re.compile(escaped_search, flags)
            new_content, count = compiled_pattern.subn(replace_string, content)
        
        return new_content, count

    def _handle_replace(self):
        source = self.args.get("source")
        search = self.args.get("search")
        replace = self.args.get("replace")
        regex = self.args.get("regex", False)
        inplace = self.args.get("inplace", False)
        dry_run = self.args.get("dry_run", False)
        count_only = self.args.get("count_only", False)
        recursive = self.args.get("recursive", False)
        file_glob = self.args.get("file_glob")
        case_sensitive = self.args.get("case_sensitive", True)
        encoding = self.args.get("encoding", "utf-8")

        if not source or not search or replace is None:
            raise ValueError("Arguments 'source', 'search', and 'replace' are required for 'replace' command.")

        if recursive:
            if not os.path.isdir(source):
                raise ValueError("Recursive mode requires 'source' to be a directory path.")
            return self._recursive_replace(source, search, replace, regex, inplace, dry_run, count_only, file_glob, case_sensitive, encoding)

        # Handle single file or string
        original_content = self._get_source_content(source, encoding)
        new_content, count = self._apply_replacement(original_content, search, replace, regex, case_sensitive)

        summary = f"Replacements made: {count}\n"
        if count_only:
            return summary
        
        if inplace and os.path.isfile(source) and not dry_run:
            with open(source, 'w', encoding=encoding) as f:
                f.write(new_content)
            summary += f"Changes applied in-place to {source}."
        elif dry_run:
            summary += "--- Preview of changes ---\n"
            summary += new_content
        else:
            summary += "--- Resulting content ---\n"
            summary += new_content
        
        return summary

    def _recursive_replace(self, base_path, search, replace, regex, inplace, dry_run, count_only, file_glob, case_sensitive, encoding):
        total_replacements = 0
        detailed_summary = []

        for root, _, files in os.walk(base_path):
            for file_name in files:
                if file_glob and not fnmatch.fnmatch(file_name, file_glob): # Use fnmatch for glob patterns
                    continue
                
                file_path = os.path.join(root, file_name)
                try:
                    original_content = self._get_source_content(file_path, encoding)
                    new_content, count = self._apply_replacement(original_content, search, replace, regex, case_sensitive)
                    
                    if count > 0:
                        total_replacements += count
                        detailed_summary.append(f"File: {file_path}, Replacements: {count}")
                        if not count_only:
                            if inplace and not dry_run:
                                with open(file_path, 'w', encoding=encoding) as f:
                                    f.write(new_content)
                                detailed_summary[-1] += " (Applied)"
                            elif dry_run:
                                detailed_summary[-1] += " (Dry Run Preview):\n" + new_content[:500] + "..." if len(new_content) > 500 else new_content
                except Exception as e:
                    detailed_summary.append(f"Error processing file {file_path}: {e}")
        
        summary = f"Total replacements across files: {total_replacements}\n"
        summary += "\n".join(detailed_summary)
        return summary

    def _handle_batch_replace(self):
        source = self.args.get("source")
        operations = self.args.get("operations")
        inplace = self.args.get("inplace", False)
        dry_run = self.args.get("dry_run", False)
        recursive = self.args.get("recursive", False)
        file_glob = self.args.get("file_glob")
        encoding = self.args.get("encoding", "utf-8")

        if not source or not operations:
            raise ValueError("Arguments 'source' and 'operations' are required for 'batch_replace' command.")
        if not isinstance(operations, list):
            raise ValueError("'operations' must be a list of dictionaries.")

        if recursive:
            if not os.path.isdir(source):
                raise ValueError("Recursive mode requires 'source' to be a directory path.")
            return self._recursive_batch_replace(source, operations, inplace, dry_run, file_glob, encoding)

        # Handle single file or string
        original_content = self._get_source_content(source, encoding)
        current_content = original_content
        total_replacements = 0
        operation_summaries = []

        for i, op_dict in enumerate(operations): # Renamed 'op' to 'op_dict' for clarity
            if not isinstance(op_dict, dict):
                raise ValueError(f"Operation at index {i} is not a dictionary.")
            
            search = op_dict.get("search")
            replace = op_dict.get("replace")
            regex = op_dict.get("regex", False)
            case_sensitive = op_dict.get("case_sensitive", True)

            if search is None or replace is None:
                raise ValueError(f"Operation {i} is missing 'search' or 'replace' argument.")
            
            new_content, count = self._apply_replacement(current_content, search, replace, regex, case_sensitive)
            total_replacements += count
            current_content = new_content
            operation_summaries.append(f"Operation {i+1} ('{search}' -> '{replace}'): {count} replacements.")
        
        summary = f"Total replacements: {total_replacements}\n"
        summary += "\n".join(operation_summaries) + "\n"

        if inplace and os.path.isfile(source) and not dry_run:
            with open(source, 'w', encoding=encoding) as f:
                f.write(current_content)
            summary += f"Changes applied in-place to {source}."
        elif dry_run:
            summary += "--- Preview of final changes ---\n"
            summary += current_content
        else:
            summary += "--- Final resulting content ---\n"
            summary += current_content
        
        return summary

    def _recursive_batch_replace(self, base_path, operations, inplace, dry_run, file_glob, encoding):
        total_replacements_overall = 0
        detailed_file_summaries = []

        for root, _, files in os.walk(base_path):
            for file_name in files:
                if file_glob and not fnmatch.fnmatch(file_name, file_glob): # Use fnmatch for glob patterns
                    continue
                
                file_path = os.path.join(root, file_name)
                try:
                    original_content = self._get_source_content(file_path, encoding)
                    current_content = original_content
                    file_replacements = 0
                    file_operation_summaries = []

                    for i, op in enumerate(operations):
                        search = op.get("search")
                        replace = op.get("replace")
                        regex = op.get("regex", False)
                        case_sensitive = op.get("case_sensitive", True)

                        if search is None or replace is None:
                            raise ValueError(f"Operation {i} is missing 'search' or 'replace' argument.")
                        
                        new_content, count = self._apply_replacement(current_content, search, replace, regex, case_sensitive)
                        file_replacements += count
                        current_content = new_content
                        file_operation_summaries.append(f"Op {i+1} ('{search}' -> '{replace}'): {count} replacements.")
                    
                    if file_replacements > 0:
                        total_replacements_overall += file_replacements
                        detailed_file_summaries.append(f"File: {file_path}, Total Replacements: {file_replacements}")
                        detailed_file_summaries.extend([f"  {s}" for s in file_operation_summaries])
                        
                        if inplace and not dry_run:
                            with open(file_path, 'w', encoding=encoding) as f:
                                f.write(current_content)
                            detailed_file_summaries[-1] += " (Applied)"
                        elif dry_run:
                            detailed_file_summaries[-1] += " (Dry Run Preview):\n" + current_content[:500] + "..." if len(current_content) > 500 else current_content
                except Exception as e:
                    detailed_file_summaries.append(f"Error processing file {file_path}: {e}")
        
        summary = f"Total replacements across all files: {total_replacements_overall}\n"
        summary += "\n".join(detailed_file_summaries)
        return summary

    def get_log_object(self):
        return self.agent.context.log.log(
            type="info",
            heading=f"{self.agent.agent_name}: Using tool '{self.name}'",
            content="",
            kvps=self.args,
        )

    async def after_execution(self, response, **kwargs):
        self.agent.hist_add_tool_result(self.name, response.message)
