# Deep-Gaza Knowledge System Format for Hacker Mode

## Overview
This document explains the knowledge system format used by the Deep-Gaza AI agent framework, specifically for the hacker mode specialized in cybersecurity and penetration testing.

## Knowledge System Architecture

### Directory Structure
The knowledge system is organized in a hierarchical structure under `/knowledge/`:

```
knowledge/
├── default/          # Default framework knowledge
│   ├── main/         # General knowledge area
│   └── solutions/    # Solution patterns area
└── custom/           # Custom knowledge (user-defined)
    ├── main/         # Custom general knowledge
    └── solutions/    # Custom solution patterns
```

### Knowledge Areas
The system defines four main knowledge areas (defined in `Memory.Area` enum):

1. **MAIN**: General knowledge and documentation
2. **FRAGMENTS**: Memory fragments and contextual information
3. **SOLUTIONS**: Solution patterns and proven techniques
4. **INSTRUMENTS**: Tool descriptions and usage instructions

### File Format Support
The knowledge system supports multiple file formats:
- **Markdown (.md)**: Primary format for documentation
- **Text (.txt)**: Plain text files
- **PDF (.pdf)**: Document files
- **CSV (.csv)**: Structured data
- **HTML (.html)**: Web content
- **JSON (.json)**: Structured data

## Hacker Mode Knowledge Format

### File Naming Convention
Knowledge files should follow descriptive naming conventions:
- `penetration_testing_methodology.md`
- `kali_linux_tools_reference.md`
- `vulnerability_assessment_techniques.md`
- `exploitation_frameworks_guide.md`

### Content Structure
Each knowledge file should follow this structure:

```markdown
# Title

## Overview
Brief description of the content and purpose

## Main Sections
### Subsection 1
Content with practical examples

### Subsection 2
More detailed information

## Code Examples
```bash
# Command examples
nmap -sV target_ip
```

## Best Practices
- Guidelines and recommendations
- Safety considerations
- Legal and ethical notes
```

### Metadata Integration
The knowledge system automatically adds metadata to each document:
- **area**: The knowledge area (main, solutions, etc.)
- **file_path**: Full path to the source file
- **checksum**: File integrity verification
- **last_modified**: Timestamp information

## Penetration Testing Knowledge Categories

### 1. Methodology and Frameworks
Files containing comprehensive testing methodologies:
- PTES (Penetration Testing Execution Standard)
- OWASP Testing Guide
- NIST Cybersecurity Framework
- Custom testing procedures

**Example Structure**:
```markdown
# Penetration Testing Methodology

## Pre-Engagement
- Scope definition
- Legal authorization
- Rules of engagement

## Information Gathering
- Passive reconnaissance
- Active reconnaissance
- OSINT techniques

## Vulnerability Assessment
- Automated scanning
- Manual testing
- Vulnerability validation

## Exploitation
- Exploit development
- Payload generation
- Attack execution

## Post-Exploitation
- Persistence mechanisms
- Lateral movement
- Data exfiltration

## Reporting
- Executive summary
- Technical details
- Remediation recommendations
```

### 2. Tool References and Usage
Comprehensive guides for penetration testing tools:
- Kali Linux tool catalog
- Command syntax and options
- Use case scenarios
- Integration techniques

**Example Structure**:
```markdown
# Tool Name Reference

## Overview
Brief description of the tool

## Installation
Installation instructions

## Basic Usage
```bash
# Basic command syntax
tool_name [options] target
```

## Advanced Techniques
Complex usage scenarios

## Integration
How to use with other tools

## Examples
Real-world usage examples
```

### 3. Vulnerability Exploitation Techniques
Detailed exploitation guides:
- Common vulnerability types
- Exploitation techniques
- Payload development
- Defense evasion

**Example Structure**:
```markdown
# Vulnerability Type Exploitation

## Vulnerability Description
Technical details about the vulnerability

## Detection Methods
How to identify the vulnerability

## Exploitation Techniques
Step-by-step exploitation process

## Payloads and Scripts
Code examples and payloads

## Mitigation Strategies
How to fix or prevent the vulnerability
```

### 4. Solution Patterns
Proven solutions for common scenarios:
- Problem-solution pairs
- Troubleshooting guides
- Best practices
- Lessons learned

**Example Structure**:
```markdown
# Problem Title

**Problem**: Description of the challenge

**Solution**:
Step-by-step solution process

**Code Examples**:
```bash
# Commands or scripts
```

**Alternative Approaches**:
Other ways to solve the problem

**Considerations**:
Important notes and warnings
```

## Knowledge Loading Process

### 1. File Discovery
The system scans knowledge directories for supported file types:
```python
# File types supported
file_types_loaders = {
    "txt": TextLoader,
    "pdf": PyPDFLoader,
    "csv": CSVLoader,
    "html": UnstructuredHTMLLoader,
    "json": TextLoader,
    "md": TextLoader,
}
```

### 2. Content Processing
Files are processed and split into chunks:
- Text extraction from various formats
- Document splitting for optimal retrieval
- Metadata attachment
- Checksum calculation for change detection

### 3. Vector Embedding
Content is embedded using the configured embedding model:
- FAISS vector database storage
- Similarity search capabilities
- Threshold-based retrieval
- Semantic understanding

### 4. Knowledge Retrieval
The knowledge tool combines multiple sources:
- Local knowledge base search
- Online search integration (SearXNG)
- Memory system integration
- Document Q&A enhancement

## Best Practices for Knowledge Creation

### 1. Content Quality
- **Accuracy**: Ensure all technical information is correct
- **Completeness**: Cover all aspects of the topic
- **Clarity**: Use clear, concise language
- **Examples**: Include practical examples and code snippets

### 2. Structure and Organization
- **Consistent Format**: Follow the established structure
- **Logical Flow**: Organize content in a logical sequence
- **Cross-References**: Link related topics
- **Searchable Content**: Use descriptive headings and keywords

### 3. Code and Commands
- **Syntax Highlighting**: Use appropriate code blocks
- **Working Examples**: Test all commands and scripts
- **Parameter Explanation**: Explain command options
- **Safety Notes**: Include warnings for dangerous operations

### 4. Maintenance and Updates
- **Version Control**: Track changes to knowledge files
- **Regular Updates**: Keep content current with latest tools and techniques
- **Validation**: Regularly test procedures and commands
- **Community Input**: Incorporate feedback and improvements

## Security and Ethical Considerations

### 1. Legal Compliance
- Only include techniques for authorized testing
- Emphasize the importance of proper authorization
- Include responsible disclosure guidelines
- Respect intellectual property rights

### 2. Safety Measures
- Include warnings for potentially dangerous operations
- Provide rollback procedures
- Emphasize testing in isolated environments
- Include incident response procedures

### 3. Ethical Guidelines
- Promote responsible security research
- Emphasize the defensive purpose of penetration testing
- Include guidelines for protecting client data
- Promote continuous learning and improvement

## Integration with Hacker Mode

### 1. Prompt Integration
The hacker mode prompts reference the knowledge system:
- System role defines the agent as a penetration tester
- Environment setup includes Kali Linux tools
- Behavioral rules emphasize following instructions

### 2. Tool Integration
Knowledge integrates with the agent's tools:
- Code execution for running commands
- Browser tools for web application testing
- Memory system for storing findings
- Search capabilities for additional information

### 3. Workflow Enhancement
Knowledge supports the penetration testing workflow:
- Methodology guidance for systematic testing
- Tool references for proper usage
- Solution patterns for common challenges
- Reporting templates for documentation

## Example Knowledge Files

### 1. Methodology File
```markdown
# Web Application Penetration Testing Methodology

## Overview
Comprehensive methodology for testing web applications

## Information Gathering
### Passive Reconnaissance
- Google dorking
- Social media analysis
- DNS enumeration

### Active Reconnaissance
- Port scanning
- Service enumeration
- Directory enumeration

## Vulnerability Assessment
### Automated Scanning
- Nikto web scanner
- OWASP ZAP
- Burp Suite scanner

### Manual Testing
- Input validation testing
- Authentication bypass
- Authorization flaws
```

### 2. Tool Reference File
```markdown
# Nmap Reference Guide

## Overview
Network exploration and security auditing tool

## Basic Scanning
```bash
# Basic scan
nmap target_ip

# Service version detection
nmap -sV target_ip

# OS detection
nmap -O target_ip
```

## Advanced Techniques
```bash
# Script scanning
nmap --script vuln target_ip

# Stealth scan
nmap -sS target_ip
```
```

### 3. Solution Pattern File
```markdown
# SQL Injection Exploitation Solutions

## Problem: Identifying SQL Injection
**Solution**: Use both automated and manual testing

## Problem: Bypassing WAF
**Solution**: Encoding and obfuscation techniques

## Problem: Extracting Data
**Solution**: Union-based and blind injection techniques
```

## Conclusion

The Deep-Gaza knowledge system provides a powerful foundation for the hacker mode, enabling the AI agent to access comprehensive penetration testing knowledge. By following the established format and best practices, users can create effective knowledge bases that enhance the agent's capabilities while maintaining security and ethical standards.

The system's flexibility allows for continuous expansion and improvement, making it an invaluable resource for cybersecurity professionals and penetration testers using the Deep-Gaza framework.
