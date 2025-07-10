text_replace_tool:
  Description: Provides advanced text search and replace functionalities with regex support for files and in-memory strings. Supports mixed input/output types, dry-run, and batch operations.
  Arguments:
    command (string, required): The operation to perform.
      - "replace": Perform search and replace.
        Arguments:
          source (string, required): Path to the file to operate on OR the string content to operate on directly.
          search (string, required): The text or regex pattern to search for.
          replace (string, required): The replacement string.
          regex (boolean, optional, default: false): If true, treat search as a regex pattern.
          inplace (boolean, optional, default: false): If true, modify the file in place. Requires source to be a file path.
          dry_run (boolean, optional, default: false): If true, return a preview of changes without writing.
          count_only (boolean, optional, default: false): If true, only return the number of replacements.
          recursive (boolean, optional, default: false): If true and source is a directory, apply recursively to all files.
          file_glob (string, optional): Glob pattern for files in recursive mode (e.g., '*.py').
          case_sensitive (boolean, optional, default: true): If false, perform case-insensitive search.
          encoding (string, optional, default: "utf-8"): Encoding to use when reading/writing files.
      - "batch_replace": (Advanced) Perform multiple search and replace operations.
        Arguments:
          source (string, required): Path to the file/directory to operate on OR the string content to operate on directly.
          operations (array of objects, required): List of search/replace operations. Each object:
            search (string, required)
            replace (string, required)
            regex (boolean, optional, default: false)
            case_sensitive (boolean, optional, default: true)
          inplace (boolean, optional, default: false): If true, modify the file in place. Requires source to be a file path.
          dry_run (boolean, optional, default: false): If true, return a preview of changes without writing.
          recursive (boolean, optional, default: false): If true and source is a directory, apply recursively to all files.
          file_glob (string, optional): Glob pattern for files in recursive mode (e.g., '*.py').
          encoding (string, optional, default: "utf-8"): Encoding to use when reading/writing files.
  Returns:
    string: A summary of replacements (count, preview of changes, etc.), or a success/error message. Error messages will include context (e.g., line numbers, invalid regex).
