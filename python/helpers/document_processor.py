import os
import base64
from pathlib import Path
from mimetypes import guess_type
import io
import json
from typing import Dict, List, Optional, Tuple

# Document processing imports
try:
    import PyPDF2
    HAS_PDF = True
except ImportError:
    HAS_PDF = False

try:
    from PIL import Image
    import pytesseract
    HAS_OCR = True
except ImportError:
    HAS_OCR = False

try:
    import docx
    HAS_DOCX = True
except ImportError:
    HAS_DOCX = False

try:
    import openpyxl
    import pandas as pd
    HAS_EXCEL = True
except ImportError:
    HAS_EXCEL = False

try:
    from python.helpers import images
    HAS_IMAGE_HELPER = True
except ImportError:
    HAS_IMAGE_HELPER = False


class DocumentProcessor:
    """
    Processes uploaded documents directly without requiring external tools.
    Extracts text, analyzes images, and converts documents to agent-readable format.
    """
    
    def __init__(self):
        self.max_text_length = 50000  # Maximum text length to include
        self.max_image_size = 768000  # Maximum pixels for image processing
        self.supported_formats = {
            'text': ['.txt', '.md', '.py', '.js', '.html', '.css', '.json', '.xml', '.csv'],
            'pdf': ['.pdf'],
            'image': ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp'],
            'doc': ['.docx'],
            'excel': ['.xlsx', '.xls'],
        }
    
    async def process_attachments(self, attachment_paths: List[str]) -> Dict[str, any]:
        """
        Process all attachments and return structured data for the agent.
        """
        processed_data = {
            'processed_files': [],
            'text_content': [],
            'image_analyses': [],
            'structured_data': [],
            'errors': []
        }
        
        for path in attachment_paths:
            try:
                result = await self.process_single_file(path)
                if result:
                    processed_data['processed_files'].append(result)
                    
                    # Categorize the results
                    if result.get('text'):
                        processed_data['text_content'].append({
                            'filename': result['filename'],
                            'text': result['text']
                        })
                    
                    if result.get('image_analysis'):
                        processed_data['image_analyses'].append({
                            'filename': result['filename'],
                            'analysis': result['image_analysis']
                        })
                    
                    if result.get('structured_data'):
                        processed_data['structured_data'].append({
                            'filename': result['filename'],
                            'data': result['structured_data']
                        })
                        
            except Exception as e:
                processed_data['errors'].append({
                    'file': os.path.basename(path),
                    'error': str(e)
                })
        
        return processed_data
    
    async def process_single_file(self, file_path: str) -> Optional[Dict[str, any]]:
        """
        Process a single file and extract its content.
        """
        if not os.path.exists(file_path):
            return None
        
        filename = os.path.basename(file_path)
        file_ext = Path(file_path).suffix.lower()
        file_size = os.path.getsize(file_path)
        
        result = {
            'filename': filename,
            'extension': file_ext,
            'size': file_size,
            'type': self._get_file_type(file_ext)
        }
        
        # Process based on file type
        if result['type'] == 'text':
            result['text'] = await self._extract_text_file(file_path)
        elif result['type'] == 'pdf' and HAS_PDF:
            result['text'] = await self._extract_pdf_text(file_path)
        elif result['type'] == 'image':
            result['image_analysis'] = await self._analyze_image(file_path)
        elif result['type'] == 'doc' and HAS_DOCX:
            result['text'] = await self._extract_docx_text(file_path)
        elif result['type'] == 'excel' and HAS_EXCEL:
            result['structured_data'] = await self._extract_excel_data(file_path)
        else:
            # Try to read as text if small enough
            if file_size < 1024 * 1024:  # 1MB limit for unknown files
                try:
                    result['text'] = await self._extract_text_file(file_path)
                except:
                    result['error'] = f"Unsupported file type: {file_ext}"
        
        return result
    
    def _get_file_type(self, extension: str) -> str:
        """Determine the type of file based on extension."""
        for file_type, extensions in self.supported_formats.items():
            if extension in extensions:
                return file_type
        return 'unknown'
    
    async def _extract_text_file(self, file_path: str) -> str:
        """Extract text from plain text files."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Truncate if too long
            if len(content) > self.max_text_length:
                content = content[:self.max_text_length] + "\n... (truncated)"
            
            return content
        except UnicodeDecodeError:
            # Try with different encoding
            try:
                with open(file_path, 'r', encoding='latin-1') as f:
                    content = f.read()
                return content[:self.max_text_length] if len(content) > self.max_text_length else content
            except:
                return "Error: Could not decode file as text"
    
    async def _extract_pdf_text(self, file_path: str) -> str:
        """Extract text from PDF files."""
        if not HAS_PDF:
            return "Error: PDF processing not available (PyPDF2 not installed)"
        
        try:
            text_content = []
            with open(file_path, 'rb') as f:
                pdf_reader = PyPDF2.PdfReader(f)
                for page_num, page in enumerate(pdf_reader.pages):
                    if page_num >= 10:  # Limit to first 10 pages
                        text_content.append("\n... (remaining pages truncated)")
                        break
                    try:
                        text_content.append(f"\n--- Page {page_num + 1} ---\n")
                        text_content.append(page.extract_text())
                    except:
                        text_content.append(f"\n--- Page {page_num + 1} (extraction failed) ---\n")
            
            full_text = "\n".join(text_content)
            if len(full_text) > self.max_text_length:
                full_text = full_text[:self.max_text_length] + "\n... (truncated)"
            
            return full_text
        except Exception as e:
            return f"Error extracting PDF: {str(e)}"
    
    async def _analyze_image(self, file_path: str) -> Dict[str, any]:
        """Analyze image files and extract text if possible."""
        analysis = {
            'has_text': False,
            'text': '',
            'description': '',
            'properties': {}
        }
        
        try:
            # Get basic image properties
            with Image.open(file_path) as img:
                analysis['properties'] = {
                    'width': img.width,
                    'height': img.height,
                    'mode': img.mode,
                    'format': img.format
                }
                
                # Try OCR if available
                if HAS_OCR:
                    try:
                        extracted_text = pytesseract.image_to_string(img)
                        if extracted_text.strip():
                            analysis['has_text'] = True
                            analysis['text'] = extracted_text.strip()
                    except:
                        pass
                
                # Generate basic description
                analysis['description'] = f"Image file: {img.width}x{img.height} {img.mode} {img.format}"
                
                # Check if image is very large
                if img.width * img.height > self.max_image_size:
                    analysis['description'] += " (large image)"
        
        except Exception as e:
            analysis['error'] = f"Error analyzing image: {str(e)}"
        
        return analysis
    
    async def _extract_docx_text(self, file_path: str) -> str:
        """Extract text from DOCX files."""
        if not HAS_DOCX:
            return "Error: DOCX processing not available (python-docx not installed)"
        
        try:
            doc = docx.Document(file_path)
            paragraphs = []
            
            for paragraph in doc.paragraphs:
                if paragraph.text.strip():
                    paragraphs.append(paragraph.text)
            
            full_text = "\n".join(paragraphs)
            if len(full_text) > self.max_text_length:
                full_text = full_text[:self.max_text_length] + "\n... (truncated)"
            
            return full_text
        except Exception as e:
            return f"Error extracting DOCX: {str(e)}"
    
    async def _extract_excel_data(self, file_path: str) -> Dict[str, any]:
        """Extract data from Excel files."""
        if not HAS_EXCEL:
            return {"error": "Excel processing not available (openpyxl/pandas not installed)"}
        
        try:
            # Read with pandas for better structure
            xl_file = pd.ExcelFile(file_path)
            sheets_data = {}
            
            for sheet_name in xl_file.sheet_names[:5]:  # Limit to first 5 sheets
                df = pd.read_excel(file_path, sheet_name=sheet_name)
                
                # Limit rows to prevent huge outputs
                if len(df) > 100:
                    df = df.head(100)
                    truncated = True
                else:
                    truncated = False
                
                sheets_data[sheet_name] = {
                    'rows': len(df),
                    'columns': list(df.columns),
                    'data': df.to_dict('records'),
                    'truncated': truncated
                }
            
            return {
                'sheets': list(sheets_data.keys()),
                'data': sheets_data
            }
        except Exception as e:
            return {"error": f"Error extracting Excel: {str(e)}"}
    
    def format_for_agent(self, processed_data: Dict[str, any]) -> str:
        """
        Format the processed data into a readable string for the agent.
        """
        if not processed_data['processed_files']:
            return "No files were successfully processed."
        
        output = []
        output.append("=== PROCESSED ATTACHMENTS ===\n")
        
        # Text content
        if processed_data['text_content']:
            output.append("📄 TEXT CONTENT:")
            for item in processed_data['text_content']:
                output.append(f"\n--- {item['filename']} ---")
                output.append(item['text'])
                output.append("")
        
        # Image analyses
        if processed_data['image_analyses']:
            output.append("🖼️ IMAGE ANALYSES:")
            for item in processed_data['image_analyses']:
                output.append(f"\n--- {item['filename']} ---")
                analysis = item['analysis']
                output.append(analysis['description'])
                if analysis['has_text']:
                    output.append("Extracted text:")
                    output.append(analysis['text'])
                output.append("")
        
        # Structured data
        if processed_data['structured_data']:
            output.append("📊 STRUCTURED DATA:")
            for item in processed_data['structured_data']:
                output.append(f"\n--- {item['filename']} ---")
                data = item['data']
                if 'sheets' in data:
                    output.append(f"Excel file with sheets: {', '.join(data['sheets'])}")
                    for sheet_name, sheet_data in data['data'].items():
                        output.append(f"\nSheet '{sheet_name}':")
                        output.append(f"Columns: {', '.join(sheet_data['columns'])}")
                        output.append(f"Rows: {sheet_data['rows']}")
                        if sheet_data['truncated']:
                            output.append("(showing first 100 rows)")
                        # Show first few rows as example
                        if sheet_data['data']:
                            output.append("Sample data:")
                            for i, row in enumerate(sheet_data['data'][:3]):
                                output.append(f"  Row {i+1}: {row}")
                output.append("")
        
        # Errors
        if processed_data['errors']:
            output.append("❌ PROCESSING ERRORS:")
            for error in processed_data['errors']:
                output.append(f"- {error['file']}: {error['error']}")
            output.append("")
        
        output.append("=== END PROCESSED ATTACHMENTS ===")
        
        return "\n".join(output)
