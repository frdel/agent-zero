code_diff_tool:
  Description: Provides advanced code comparison, merging, and patch application functionalities for files and in-memory strings. Designed to handle mixed input/output types, provide dry-run capabilities, and offer robust error reporting.
  Arguments:
    command (string, required): The operation to perform.
      - "diff": Generate a diff between two sources.
        Arguments:
          original_source (string, required): Path to the original file OR the original string content.
          modified_source (string, required): Path to the modified file OR the modified string content.
          diff_format (string, optional, default: "unified"): Format of the diff. Options: "unified", "side_by_side", "context".
          ignore_whitespace (boolean, optional, default: false): If true, ignore whitespace changes.
          context_lines (integer, optional, default: 3): Number of context lines to show.
          recursive (boolean, optional, default: false): If true and sources are directories, perform recursive diff.
          output_destination (string, optional): Path to write the diff result. If not provided, returns as string.
          encoding (string, optional, default: "utf-8"): Encoding to use when reading/writing files.
      - "merge": Perform a 2-way merge.
        Arguments:
          original_source (string, required): Path to the original file OR the original string content.
          modified_source (string, required): Path to the modified file OR the modified string content.
          output_destination (string, optional): Path to write the merged result. If not provided, returns as string.
          dry_run (boolean, optional, default: false): If true, return the merged content without writing to output_destination.
          encoding (string, optional, default: "utf-8"): Encoding to use when reading/writing files.
      - "patch": Apply a patch string.
        Arguments:
          original_source (string, required): Path to the original file OR the original string content.
          patch_content (string, required): The patch string to apply.
          output_destination (string, optional): Path to write the patched result. If not provided, returns as string.
          dry_run (boolean, optional, default: false): If true, return the patched content without writing to output_destination.
          encoding (string, optional, default: "utf-8"): Encoding to use when reading/writing files.
          validate_patch (boolean, optional, default: true): If true, validate the patch before applying and report errors.
      - "diff3": (Advanced/Stretch) Perform a 3-way merge.
        Arguments:
          base_source (string, required): Path to the common ancestor file OR the common ancestor string content.
          original_source (string, required): Path to the first modified file OR the first modified string content.
          modified_source (string, required): Path to the second modified file OR the second modified string content.
          output_destination (string, optional): Path to write the merged result. If not provided, returns as string.
          dry_run (boolean, optional, default: false): If true, return the merged content without writing to output_destination.
          encoding (string, optional, default: "utf-8"): Encoding to use when reading/writing files.
  Returns:
    string: The diff result, merged content, or patched content, or a success/error message. Error messages will include context (e.g., line numbers, reason for failure).
