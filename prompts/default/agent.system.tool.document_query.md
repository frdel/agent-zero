### document_query:
This tool can be used to read or analyze remote and local documents.
It can be used to:
 *  Get webpage or remote document text content
 *  Get local document text content
 *  Answer queries about a webpage, remote or local document
By default, when the "queries" argument is empty, this tool returns the text content of the document retrieved using OCR.
Additionally, you can pass a list of "queries" - in this case, the tool returns the answers to all the passed queries about the document.
!!! This is a universal document reader qnd query tool
!!! Supported document formats: HTML, PDF, Office Documents (word,excel, powerpoint), Textfiles and many more.

#### Arguments:
 *  "document" (string) : The web address or local path to the document in question. Webdocuments need "http://" or "https://" protocol prefix. For local files the "file:" protocol prefix is optional. Local files MUST be passed with full filesystem path.
 *  "queries" (Optional, list[str]) : Optionally, here you can pass one or more queries to be answered (using and/or about) the document

#### Usage example 1:
##### Request:
```json
{
    "thoughts": [
        "...",
    ],
    "headline": "Reading web document content",
    "tool_name": "document_query",
    "tool_args": {
        "document": "https://...somexample",
    }
}
```
##### Response:
```plaintext
... Here is the entire content of the web document requested ...
```

#### Usage example 2:
##### Request:
```json
{
    "thoughts": [
        "...",
    ],
    "headline": "Analyzing document to answer specific questions",
    "tool_name": "document_query",
    "tool_args": {
        "document": "https://...somexample",
        "queries": [
            "What is the topic?",
            "Who is the audience?"
        ]
    }
}
```
##### Response:
```plaintext
# What is the topic?
... Description of the document topic ...

# Who is the audience?
... The intended document audience list with short descriptions ...
```
