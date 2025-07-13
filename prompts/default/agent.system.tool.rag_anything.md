### rag_anything:
This tool provides advanced multimodal document processing capabilities using RAG-Anything integration.
It can extract and analyze images, tables, equations, and text from documents with context awareness.

#### Key capabilities:
 * Extract images, tables, and equations from documents with surrounding context
 * Process multiple document formats (PDF, DOC, DOCX, images, etc.)
 * Store multimodal content in semantic memory for later retrieval
 * Query processed content using natural language
 * Batch process multiple documents efficiently
 * Get processing statistics and system status

#### Available methods:
 * **Default/process**: Process a document to extract multimodal content
 * **query**: Search processed content using semantic similarity
 * **status**: Get processing statistics and system status
 * **batch**: Process multiple documents in batch
 * **delete**: Delete processed content for a document

#### Arguments for process method:
 * "document_path" (string): Full path to the document to process
 * "extract_images" (optional, boolean): Extract and process images (default: true)
 * "extract_tables" (optional, boolean): Extract and process tables (default: true) 
 * "extract_equations" (optional, boolean): Extract and process equations (default: true)
 * "store_in_memory" (optional, boolean): Store results in memory for later querying (default: true)

#### Arguments for query method:
 * "query" (string): Natural language query to search for
 * "document_path" (optional, string): Limit search to specific document
 * "content_types" (optional, string): Comma-separated list of content types to filter ("image,table,equation,text")
 * "limit" (optional, number): Maximum number of results (default: 10)

#### Arguments for batch method:
 * "documents" (string): Comma-separated list of document paths to process
 * "extract_images" (optional, boolean): Extract images from all documents (default: true)
 * "extract_tables" (optional, boolean): Extract tables from all documents (default: true)
 * "extract_equations" (optional, boolean): Extract equations from all documents (default: true)

#### Arguments for delete method:
 * "document_path" (string): Path to document whose processed content should be deleted

#### Usage example 1 - Process a document:
##### Request:
```json
{
    "thoughts": [
        "The user wants me to analyze a PDF document that contains charts and tables",
        "I'll use rag_anything to extract all multimodal content with context"
    ],
    "headline": "Processing document for multimodal analysis",
    "tool_name": "rag_anything",
    "tool_args": {
        "document_path": "/path/to/financial_report.pdf",
        "extract_images": true,
        "extract_tables": true,
        "extract_equations": true,
        "store_in_memory": true
    }
}
```
##### Response:
```plaintext
Document processed successfully: /path/to/financial_report.pdf
Content extracted: {'text': 1, 'images': 5, 'tables': 3, 'equations': 2}
Stored 11 items in memory
Found 5 images
Found 3 tables  
Found 2 equations
```

#### Usage example 2 - Query processed content:
##### Request:
```json
{
    "thoughts": [
        "Now I need to find financial tables from the processed document"
    ],
    "headline": "Searching for financial data in processed content",
    "tool_name": "rag_anything",
    "tool_args": {
        "method": "query",
        "query": "financial performance tables with revenue data",
        "content_types": "table",
        "limit": 5
    }
}
```
##### Response:
```plaintext
Found 3 results for query: financial performance tables with revenue data

1. [table] from financial_report.pdf
   | Quarter | Revenue | Growth |
   |---------|---------|--------|
   | Q1 2024 | $45M    | 12%    |
   | Q2 2024 | $52M    | 15%    |

2. [table] from financial_report.pdf
   | Region  | Sales   | Margin |
   |---------|---------|--------|
   | North   | $28M    | 23%    |
   | South   | $24M    | 19%    |
```

#### Usage example 3 - Get system status:
##### Request:
```json
{
    "thoughts": [
        "Let me check the RAG-Anything system status and what content has been processed"
    ],
    "headline": "Checking RAG-Anything system status",
    "tool_name": "rag_anything",
    "tool_args": {
        "method": "status"
    }
}
```
##### Response:
```plaintext
RAG-Anything System Status:

Model setup: ✓ Valid

Content Statistics:
  Total items: 47
  Unique documents: 3

Content by type:
  text: 15
  image: 18
  table: 12
  equation: 2

Processed documents:
  - financial_report.pdf
  - research_paper.pdf
  - presentation.pptx
```

#### Usage example 4 - Batch process documents:
##### Request:
```json
{
    "thoughts": [
        "I need to process multiple research papers in batch for analysis"
    ],
    "headline": "Batch processing research documents",
    "tool_name": "rag_anything",
    "tool_args": {
        "method": "batch",
        "documents": "/docs/paper1.pdf,/docs/paper2.pdf,/docs/paper3.pdf",
        "extract_images": true,
        "extract_tables": true,
        "extract_equations": true
    }
}
```
##### Response:
```plaintext
Batch processing completed:
  Total documents: 3
  Successful: 3
  Failed: 0

Successfully processed:
  - paper1.pdf
  - paper2.pdf  
  - paper3.pdf
```

!!! This tool requires RAG-Anything to be enabled in settings and vision-enabled models for full functionality
!!! The tool stores processed content in a dedicated memory area for efficient retrieval
!!! Use this tool when you need to analyze documents containing images, charts, tables, equations, or complex layouts