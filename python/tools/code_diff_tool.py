import os
import difflib
import shutil
import re
from unidiff import PatchSet # Import PatchSet for patch application
from python.helpers.tool import Tool, Response
from python.helpers.print_style import PrintStyle
from diff_match_patch import diff_match_patch # Import for 3-way merge

class CodeDiffTool(Tool):
    async def execute(self, **kwargs):
        await self.agent.handle_intervention()

        command = self.args.get("command", "").lower().strip()
        
        try:
            if command == "diff":
                response = self._handle_diff()
            elif command == "merge":
                response = self._handle_merge()
            elif command == "patch":
                response = self._handle_patch()
            elif command == "diff3":
                response = self._handle_diff3()
            else:
                response = f"Error: Unknown command '{command}'. Supported commands: diff, merge, patch, diff3."
            
            return Response(message=response, break_loop=False)

        except FileNotFoundError as e:
            return Response(message=f"Error: File not found - {e}", break_loop=False)
        except ValueError as e:
            return Response(message=f"Error: Invalid argument - {e}", break_loop=False)
        except Exception as e:
            return Response(message=f"An unexpected error occurred: {e}", break_loop=False)

    def _get_source_content(self, source_arg, is_path=False, encoding="utf-8"):
        if is_path:
            if not os.path.exists(source_arg):
                raise FileNotFoundError(f"Source path does not exist: {source_arg}")
            if os.path.isdir(source_arg):
                # Handle recursive directory diff later
                raise ValueError(f"Directory diff not yet supported for source: {source_arg}")
            with open(source_arg, 'r', encoding=encoding) as f:
                return f.readlines()
        else:
            return source_arg.splitlines(keepends=True)

    def _handle_diff(self):
        original_source = self.args.get("original_source")
        modified_source = self.args.get("modified_source")
        diff_format = self.args.get("diff_format", "unified").lower()
        ignore_whitespace = self.args.get("ignore_whitespace", False)
        context_lines = int(self.args.get("context_lines", 3))
        recursive = self.args.get("recursive", False)
        output_destination = self.args.get("output_destination")
        encoding = self.args.get("encoding", "utf-8")

        if not original_source or not modified_source:
            raise ValueError("Both 'original_source' and 'modified_source' are required for 'diff' command.")

        # Determine if sources are paths or strings
        is_original_path = os.path.exists(original_source) if isinstance(original_source, str) else False
        is_modified_path = os.path.exists(modified_source) if isinstance(modified_source, str) else False

        if recursive:
            if not is_original_path or not is_modified_path or not os.path.isdir(original_source) or not os.path.isdir(modified_source):
                raise ValueError("Recursive diff requires both sources to be existing directories.")
            return self._recursive_diff(original_source, modified_source, diff_format, ignore_whitespace, context_lines, encoding, output_destination)

        a = self._get_source_content(original_source, is_original_path, encoding)
        b = self._get_source_content(modified_source, is_modified_path, encoding)

        if ignore_whitespace:
            a = [line.strip() for line in a]
            b = [line.strip() for line in b]

        diff_generator = None
        if diff_format == "unified":
            diff_generator = difflib.unified_diff(a, b, fromfile='original', tofile='modified', n=context_lines)
        elif diff_format == "context":
            diff_generator = difflib.context_diff(a, b, fromfile='original', tofile='modified', n=context_lines)
        elif diff_format == "side_by_side":
            diff_result = self._side_by_side_diff(a, b, context_lines)
        else:
            raise ValueError(f"Unsupported diff_format: {diff_format}")

        diff_result = "" # Initialize diff_result

        if diff_format == "unified":
            diff_generator = difflib.unified_diff(a, b, fromfile='original', tofile='modified', n=context_lines)
            diff_result = "".join(list(diff_generator))
        elif diff_format == "context":
            diff_generator = difflib.context_diff(a, b, fromfile='original', tofile='modified', n=context_lines)
            diff_result = "".join(list(diff_generator))
        elif diff_format == "side_by_side":
            diff_result = self._side_by_side_diff(a, b, context_lines)
        else:
            raise ValueError(f"Unsupported diff_format: {diff_format}")

        if output_destination:
            with open(output_destination, 'w', encoding=encoding) as f:
                f.write(diff_result)
            return f"Diff saved to {output_destination}"
        else:
            return diff_result

    def _recursive_diff(self, dir1, dir2, diff_format, ignore_whitespace, context_lines, encoding, output_destination):
        # This is a simplified recursive diff. A full implementation would compare file by file.
        # For now, it will just list files that are different or unique.
        diff_output = []
        for root, _, files in os.walk(dir1):
            for file in files:
                path1 = os.path.join(root, file)
                path2 = os.path.join(dir2, os.path.relpath(path1, dir1))
                if not os.path.exists(path2):
                    diff_output.append(f"Only in {dir1}: {os.path.relpath(path1, dir1)}")
                elif os.path.isfile(path2):
                    try:
                        content1 = self._get_source_content(path1, True, encoding)
                        content2 = self._get_source_content(path2, True, encoding)
                        if ignore_whitespace:
                            content1 = [line.strip() for line in content1]
                            content2 = [line.strip() for line in content2]
                        
                        if content1 != content2:
                            diff_output.append(f"Files differ: {os.path.relpath(path1, dir1)}")
                            # Optionally include the actual diff for each file
                            if diff_format == "unified":
                                file_diff = "".join(list(difflib.unified_diff(content1, content2, fromfile=os.path.relpath(path1, dir1), tofile=os.path.relpath(path2, dir2), n=context_lines)))
                            elif diff_format == "context":
                                file_diff = "".join(list(difflib.context_diff(content1, content2, fromfile=os.path.relpath(path1, dir1), tofile=os.path.relpath(path2, dir2), n=context_lines)))
                            elif diff_format == "side_by_side":
                                file_diff = self._side_by_side_diff(content1, content2, context_lines)
                            else:
                                file_diff = f"Diff format '{diff_format}' not supported for inline recursive diff."
                            diff_output.append(file_diff)
                    except Exception as e:
                        diff_output.append(f"Error comparing {os.path.relpath(path1, dir1)}: {e}")
        
        for root, _, files in os.walk(dir2):
            for file in files:
                path2 = os.path.join(root, file)
                path1 = os.path.join(dir1, os.path.relpath(path2, dir2))
                if not os.path.exists(path1):
                    diff_output.append(f"Only in {dir2}: {os.path.relpath(path2, dir2)}")
        
        result = "\n".join(diff_output)
        if output_destination:
            with open(output_destination, 'w', encoding=encoding) as f:
                f.write(result)
            return f"Recursive diff saved to {output_destination}"
        return result


    def _side_by_side_diff(self, a, b, context_lines):
        output = []
        max_len_a = max(len(line.rstrip()) for line in a) if a else 0
        max_len_b = max(len(line.rstrip()) for line in b) if b else 0
        col_width = max(max_len_a, max_len_b) + 2

        len_a = len(a)
        len_b = len(b)
        i = 0
        j = 0

        while i < len_a or j < len_b:
            line_a = a[i].rstrip() if i < len_a else ""
            line_b = b[j].rstrip() if j < len_b else ""

            if i < len_a and j < len_b and line_a == line_b:
                output.append(f"  {line_a:<{col_width}}   {line_b}")
                i += 1
                j += 1
            elif i < len_a and (j == len_b or line_a not in b[j:]): # Line in A, not in B or not found later in B
                output.append(f"- {line_a:<{col_width}}")
                i += 1
            elif j < len_b and (i == len_a or line_b not in a[i:]): # Line in B, not in A or not found later in A
                output.append(f"  {'':<{col_width}} + {line_b}")
                j += 1
            else: # Mismatch, but both exist, try to align
                output.append(f"- {line_a:<{col_width}} + {line_b}")
                i += 1
                j += 1
        return "\n".join(output)


    def _handle_merge(self):
        original_source = self.args.get("original_source")
        modified_source = self.args.get("modified_source")
        output_destination = self.args.get("output_destination")
        dry_run = self.args.get("dry_run", False)
        encoding = self.args.get("encoding", "utf-8")

        if not original_source or not modified_source:
            raise ValueError("Both 'original_source' and 'modified_source' are required for 'merge' command.")

        a = self._get_source_content(original_source, os.path.exists(original_source) if isinstance(original_source, str) else False, encoding)
        b = self._get_source_content(modified_source, os.path.exists(modified_source) if isinstance(modified_source, str) else False, encoding)

        # Simple 2-way merge: take modified if different, else original
        merged_lines = []
        s = difflib.SequenceMatcher(None, a, b)
        for tag, i1, i2, j1, j2 in s.getopcodes():
            if tag == 'equal':
                merged_lines.extend(a[i1:i2])
            elif tag == 'replace':
                # This is a very basic merge, just taking modified.
                # A real merge would involve conflict markers or more complex logic.
                merged_lines.extend(b[j1:j2])
            elif tag == 'delete':
                pass # deleted from original, not in modified, so skip
            elif tag == 'insert':
                merged_lines.extend(b[j1:j2])
        
        merged_content = "".join(merged_lines)

        if output_destination and not dry_run:
            with open(output_destination, 'w', encoding=encoding) as f:
                f.write(merged_content)
            return f"Merged content saved to {output_destination}"
        else:
            return merged_content

    def _handle_patch(self):
        original_source = self.args.get("original_source")
        patch_content = self.args.get("patch_content")
        output_destination = self.args.get("output_destination")
        dry_run = self.args.get("dry_run", False)
        encoding = self.args.get("encoding", "utf-8")
        validate_patch = self.args.get("validate_patch", True)

        if not original_source or not patch_content:
            raise ValueError("Both 'original_source' and 'patch_content' are required for 'patch' command.")

        original_lines = self._get_source_content(original_source, os.path.exists(original_source) if isinstance(original_source, str) else False, encoding)
        
        try:
            patches = PatchSet(patch_content)
        except Exception as e:
            return f"Error: Invalid patch content. Could not parse patch: {e}"

        if validate_patch:
            # unidiff's PatchSet constructor already performs some validation.
            # Additional validation could be added here if needed.
            pass

        patched_lines = list(original_lines) # Create a mutable copy
        
        # Apply patches by manually processing hunks
        # Iterate through patches in reverse order of their target_start to avoid line number shifts
        # This is a simplified application and might not handle all complex patch scenarios.
        # For a truly robust solution, a dedicated patch application library is recommended.
        
        # Sort hunks by target_start in descending order
        all_hunks = []
        for patch in patches:
            for hunk in patch:
                all_hunks.append(hunk)
        all_hunks.sort(key=lambda h: h.target_start, reverse=True)

        import traceback

        def get_lines(obj, label):
            # Helper to handle both attribute and method cases, and fallback to list conversion
            import collections.abc
            print(f"DEBUG: get_lines({label}) called with obj={obj}, type={type(obj)}")
            # Try attribute access
            if isinstance(obj, list):
                print(f"DEBUG: get_lines({label}) is already a list")
                return obj
            if hasattr(obj, "__call__"):
                try:
                    result = obj()
                    print(f"DEBUG: get_lines({label}) called obj as method, result type={type(result)}")
                    if isinstance(result, list):
                        return result
                    if isinstance(result, collections.abc.Iterable):
                        return list(result)
                except Exception as e:
                    print(f"DEBUG: get_lines({label}) failed to call obj as method: {e}")
            # Try property access (for property objects)
            try:
                prop_val = obj
                print(f"DEBUG: get_lines({label}) property value: {prop_val}, type={type(prop_val)}")
                if isinstance(prop_val, list):
                    print(f"DEBUG: get_lines({label}) property is a list")
                    return prop_val
                if isinstance(prop_val, collections.abc.Iterable):
                    print(f"DEBUG: get_lines({label}) property is iterable, converting to list")
                    return list(prop_val)
            except Exception as e:
                print(f"DEBUG: get_lines({label}) failed to access property: {e}")
            # Try dir() to see if it's a property or method
            try:
                print(f"DEBUG: get_lines({label}) dir: {dir(obj)}")
                # Try to get the property value if it's a property
                if hasattr(obj, 'fget'):
                    prop_val = obj.fget(obj)
                    print(f"DEBUG: get_lines({label}) property fget value: {prop_val}, type={type(prop_val)}")
                    if isinstance(prop_val, list):
                        return prop_val
                    if isinstance(prop_val, collections.abc.Iterable):
                        return list(prop_val)
                # Try to get the property value if it's a property (alternative)
                if hasattr(obj, '__get__'):
                    prop_val = obj.__get__(obj, type(obj))
                    print(f"DEBUG: get_lines({label}) __get__ value: {prop_val}, type={type(prop_val)}")
                    if isinstance(prop_val, list):
                        return prop_val
                    if isinstance(prop_val, collections.abc.Iterable):
                        return list(prop_val)
            except Exception as e:
                print(f"DEBUG: get_lines({label}) failed to dir(obj) or fget/__get__: {e}")
            print(f"DEBUG: get_lines({label}) could not get lines, returning empty list")
            return []

        for hunk in all_hunks:
            # Calculate the actual start index in the patched_lines list
            # unidiff hunk.target_start is 1-indexed
            start_idx = hunk.source_start - 1

            # Build the new content for this hunk by applying the patch logic
            new_hunk_content = []
            original_idx = start_idx

            # The correct way to get the patch lines is to use list(hunk) (the hunk itself is iterable)
            hunk_lines = list(hunk)
            print(f"DEBUG: hunk_lines (from list(hunk)): {hunk_lines}")

            # Patch application logic: context lines must match, removed lines are skipped, added lines are inserted
            for line_obj in hunk_lines:
                line_type = getattr(line_obj, "line_type", None)
                value = getattr(line_obj, "value", "")
                print(f"DEBUG: Patch apply: idx={original_idx}, line_type={line_type}, value={value.rstrip()}")
                if line_type == " ":
                    # Context line: must match original
                    if original_idx >= len(patched_lines) or patched_lines[original_idx].rstrip() != value.rstrip():
                        return f"Error applying patch: Context mismatch at line {original_idx + 1}. Expected '{value.rstrip()}', got '{patched_lines[original_idx].rstrip()}'"
                    new_hunk_content.append(patched_lines[original_idx])
                    original_idx += 1
                elif line_type == "-":
                    # Removed line: must match original, but do not add to result
                    if original_idx >= len(patched_lines) or patched_lines[original_idx].rstrip() != value.rstrip():
                        return f"Error applying patch: Deletion mismatch at line {original_idx + 1}. Expected '{value.rstrip()}', got '{patched_lines[original_idx].rstrip()}'"
                    original_idx += 1
                elif line_type == "+":
                    # Added line: add to result, do not advance original_idx
                    new_hunk_content.append(value + "\n")

            # Replace the original lines covered by the hunk with the new hunk content
            patched_lines = (
                patched_lines[:start_idx]
                + new_hunk_content
                + patched_lines[original_idx:]
            )
        
        # After all hunks are applied
        applied_content = "".join(patched_lines)

        if output_destination and not dry_run:
            with open(output_destination, 'w', encoding=encoding) as f:
                f.write(applied_content)
            return f"Patch applied and saved to {output_destination}"
        else:
            return applied_content

    def _handle_diff3(self):
        base_source = self.args.get("base_source")
        original_source = self.args.get("original_source")
        modified_source = self.args.get("modified_source")
        output_destination = self.args.get("output_destination")
        dry_run = self.args.get("dry_run", False)
        encoding = self.args.get("encoding", "utf-8")

        if not base_source or not original_source or not modified_source:
            raise ValueError("All 'base_source', 'original_source', and 'modified_source' are required for 'diff3' command.")

        base_content = "".join(self._get_source_content(base_source, os.path.exists(base_source) if isinstance(base_source, str) else False, encoding))
        original_content = "".join(self._get_source_content(original_source, os.path.exists(original_source) if isinstance(original_source, str) else False, encoding))
        modified_content = "".join(self._get_source_content(modified_source, os.path.exists(modified_source) if isinstance(modified_source, str) else False, encoding))

        dmp = diff_match_patch()
        
        # Perform 3-way merge
        # The diff_match_patch library's merge_patch method is for applying a list of patches.
        # For a true 3-way merge, we need to use diff_main to get diffs and then merge them.
        # This is a simplified 3-way merge that will produce conflict markers.
        
        # Diff base against original
        diff_base_original = dmp.diff_main(base_content, original_content)
        dmp.diff_cleanupSemantic(diff_base_original)

        # Diff base against modified
        diff_base_modified = dmp.diff_main(base_content, modified_content)
        dmp.diff_cleanupSemantic(diff_base_modified)

        # Merge the two diffs
        # The diff_match_patch library doesn't have a direct diff3 function.
        # A common approach is to use the patch_apply method after creating patches.
        # However, for a true 3-way merge with conflict markers, it's more involved.
        # I will simulate a basic 3-way merge with conflict markers.
        
        # This is a very simplified simulation of 3-way merge.
        # A robust 3-way merge would involve more complex logic to identify common changes
        # and actual conflicts.
        
        merged_result = []
        base_lines = base_content.splitlines(keepends=True)
        original_lines = original_content.splitlines(keepends=True)
        modified_lines = modified_content.splitlines(keepends=True)

        # Simple line-by-line comparison for demonstration
        max_len = max(len(base_lines), len(original_lines), len(modified_lines))
        
        for i in range(max_len):
            b_line = base_lines[i].rstrip() if i < len(base_lines) else ""
            o_line = original_lines[i].rstrip() if i < len(original_lines) else ""
            m_line = modified_lines[i].rstrip() if i < len(modified_lines) else ""

            if o_line == m_line:
                merged_result.append(o_line + "\n")
            elif o_line == b_line:
                merged_result.append(m_line + "\n")
            elif m_line == b_line:
                merged_result.append(o_line + "\n")
            else:
                merged_result.append("<<<<<<< ORIGINAL\n")
                merged_result.append(o_line + "\n")
                merged_result.append("=======\n")
                merged_result.append(m_line + "\n")
                merged_result.append(">>>>>>> MODIFIED\n")
        
        merged_content = "".join(merged_result)

        if output_destination and not dry_run:
            with open(output_destination, 'w', encoding=encoding) as f:
                f.write(merged_content)
            return f"3-way merge result saved to {output_destination}"
        else:
            return merged_content

    def get_log_object(self):
        return self.agent.context.log.log(
            type="info",
            heading=f"{self.agent.agent_name}: Using tool '{self.name}'",
            content="",
            kvps=self.args,
        )

    async def after_execution(self, response, **kwargs):
        self.agent.hist_add_tool_result(self.name, response.message)
