## Research Memory Tool

The `research_memory` tool provides comprehensive management of research artifacts and session tracking for the SakanaAI research workflow.

### Tool Methods

**Main Management Method**:
```
research_memory(action="search", query="", artifact_type="", limit=10)
```

**Specialized Methods**:
```
research_memory:search(query="research topic", artifact_type="research_findings", limit=10)
research_memory:list_papers(limit=20)
research_memory:list_experiments(limit=10)
research_memory:list_reviews(limit=10)
research_memory:session_status()
research_memory:timeline()
```

### Available Actions

**search**: Search research artifacts by query with optional type filtering
**list_papers**: List all academic papers stored in research memory
**list_experiments**: List all experiment designs and protocols
**list_reviews**: List all peer reviews conducted
**list_findings**: List research findings with optional query filtering
**session_status**: Get current research session status and statistics
**session_summary**: Generate summary of current research session
**timeline**: Get chronological view of recent research activities
**clear**: Remove research artifacts by type (use with caution)

### Artifact Types

**research_findings**: Results from literature reviews and research analysis
**experiment_design**: Experimental protocols and design specifications
**academic_paper**: Generated research papers and manuscripts
**peer_review**: Review reports and evaluations
**research_session**: Session summaries and workflow tracking

### Search Capabilities

**Query-Based Search**: Find artifacts matching specific research topics or keywords
**Type Filtering**: Filter results by specific artifact types
**Relevance Ranking**: Results ranked by semantic similarity to query
**Metadata Filtering**: Search within specific research areas or time periods

### Session Tracking

**Active Session Monitoring**: Track ongoing research sessions automatically
**Tool Usage Statistics**: Monitor which research tools are being used
**Artifact Creation Tracking**: Log when research artifacts are generated
**Timeline Management**: Maintain chronological record of research activities

### Usage Guidelines

**Research Discovery**:
1. Use `search` to find relevant previous work
2. Use `list_*` methods to browse artifacts by type
3. Use `timeline` to understand research progression
4. Check `session_status` for current activity overview

**Session Management**:
1. Sessions start automatically when using research tools
2. Track progress with `session_status`
3. Generate summaries with `session_summary`
4. Review timeline for historical perspective

**Memory Optimization**:
1. Regularly review and organize artifacts
2. Use clear, descriptive queries for better search results
3. Leverage type filtering for targeted searches
4. Archive completed research sessions

### Integration with Research Tools

**Automatic Storage**: All SakanaAI research tools automatically save artifacts to research memory
**Cross-Reference**: Find related artifacts across different research phases
**Session Continuity**: Maintain context across multiple research sessions
**Knowledge Building**: Build cumulative research knowledge base over time

### Best Practices

**Regular Review**: Periodically review stored artifacts to maintain organization
**Descriptive Queries**: Use specific, descriptive search terms for better results
**Session Hygiene**: Generate session summaries to maintain clear research records
**Collaborative Memory**: Share and build upon previous research findings

### Privacy and Security

**Local Storage**: All research artifacts stored locally in Agent Zero memory
**Anonymization**: Personal information automatically anonymized in research contexts
**Access Control**: Memory access controlled through Agent Zero security framework
**Data Persistence**: Research artifacts persist across sessions for continuity