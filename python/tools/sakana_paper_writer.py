import os
import json
import asyncio
import re
from datetime import datetime
from typing import Dict, List, Optional, Any
from python.helpers.tool import Tool, Response
from python.helpers.print_style import PrintStyle
from python.helpers.errors import handle_error
from python.helpers import memory

class SakanaPaperWriter(Tool):
    
    async def execute(self, research_topic="", paper_type="research_paper", 
                     findings="", methodology="", references="", **kwargs):
        """
        Generate academic papers in standard formats.
        
        Paper types:
        - research_paper: Full research paper with all sections
        - conference_paper: Conference format with space constraints
        - journal_article: Journal submission format
        - survey_paper: Comprehensive literature survey
        - position_paper: Argumentative position paper
        - technical_report: Detailed technical documentation
        """
        
        if not research_topic:
            return Response(message="Research topic is required for paper writing", break_loop=False)
        
        paper_context = {
            "research_topic": research_topic,
            "paper_type": paper_type,
            "findings": findings,
            "methodology": methodology,
            "references": references,
            "timestamp": datetime.now().isoformat()
        }
        
        PrintStyle(font_color="#E67E22", bold=True).print(f"Writing {paper_type}: {research_topic}")
        
        # Generate paper based on type
        paper_content = await self._generate_paper(paper_context)
        
        # Save paper to memory
        await self._save_paper(paper_content, paper_context)
        
        await self.agent.handle_intervention(paper_content)
        return Response(message=paper_content, break_loop=False)
    
    async def research_paper(self, topic="", abstract="", introduction="", 
                           methodology="", results="", discussion="", 
                           conclusion="", references="", **kwargs):
        """Write complete research paper"""
        findings = f"Results: {results}\nDiscussion: {discussion}\nConclusion: {conclusion}"
        content = f"Abstract: {abstract}\nIntroduction: {introduction}"
        
        return await self.execute(
            research_topic=topic,
            paper_type="research_paper",
            findings=findings,
            methodology=methodology,
            references=references
        )
    
    async def survey_paper(self, topic="", scope="", literature_findings="", 
                          gaps_identified="", future_directions="", **kwargs):
        """Write literature survey paper"""
        findings = f"Literature Analysis: {literature_findings}\nGaps: {gaps_identified}\nFuture Work: {future_directions}"
        
        return await self.execute(
            research_topic=topic,
            paper_type="survey_paper", 
            findings=findings,
            methodology=f"Survey scope: {scope}"
        )
    
    async def conference_paper(self, topic="", key_contribution="", 
                             experimental_results="", word_limit=8000, **kwargs):
        """Write conference paper with space constraints"""
        findings = f"Key Contribution: {key_contribution}\nResults: {experimental_results}"
        
        return await self.execute(
            research_topic=topic,
            paper_type="conference_paper",
            findings=findings,
            methodology=f"Word limit: {word_limit}"
        )
    
    async def position_paper(self, topic="", position="", arguments="", 
                           counter_arguments="", supporting_evidence="", **kwargs):
        """Write position paper with argumentative structure"""
        findings = f"Position: {position}\nArguments: {arguments}\nCounter-arguments: {counter_arguments}\nEvidence: {supporting_evidence}"
        
        return await self.execute(
            research_topic=topic,
            paper_type="position_paper",
            findings=findings
        )
    
    async def _generate_paper(self, context: Dict) -> str:
        """Main paper generation logic"""
        paper_type = context["paper_type"]
        
        generators = {
            "research_paper": self._generate_research_paper,
            "conference_paper": self._generate_conference_paper,
            "journal_article": self._generate_journal_article,
            "survey_paper": self._generate_survey_paper,
            "position_paper": self._generate_position_paper,
            "technical_report": self._generate_technical_report
        }
        
        if paper_type in generators:
            return await generators[paper_type](context)
        else:
            return await self._generate_generic_paper(context)
    
    async def _generate_research_paper(self, context: Dict) -> str:
        """Generate complete research paper"""
        topic = context["research_topic"]
        findings = context.get("findings", "")
        methodology = context.get("methodology", "")
        references = context.get("references", "")
        
        # Extract components from findings
        findings_components = self._parse_findings(findings)
        
        paper = f"""# {topic}

## Abstract

**Background**: [Context and motivation for the research]

**Objective**: This study aims to [research objective based on topic].

**Methods**: {methodology if methodology else '[Methodology description]'}

**Results**: {findings_components.get('results', '[Key findings and results]')}

**Conclusions**: {findings_components.get('conclusion', '[Main conclusions and implications]')}

**Keywords**: [5-7 relevant keywords]

## 1. Introduction

### 1.1 Background and Motivation

The field of {topic.lower()} has seen significant developments in recent years. [Provide context and background information about the research domain.]

### 1.2 Problem Statement

Despite advances in [relevant area], several challenges remain:
- [Challenge 1]
- [Challenge 2] 
- [Challenge 3]

### 1.3 Research Objectives

This study addresses the following research questions:
1. [Research question 1]
2. [Research question 2]
3. [Research question 3]

### 1.4 Contributions

The main contributions of this work are:
- [Contribution 1]: [Brief description]
- [Contribution 2]: [Brief description]
- [Contribution 3]: [Brief description]

### 1.5 Paper Organization

The remainder of this paper is organized as follows. Section 2 reviews related work. Section 3 presents the methodology. Section 4 describes the experimental setup. Section 5 presents results and analysis. Section 6 discusses implications and limitations. Section 7 concludes the paper.

## 2. Related Work

### 2.1 Foundational Work

[Review of foundational papers and early work in the area]

### 2.2 Recent Developments

[Discussion of recent advances and current state-of-the-art]

### 2.3 Gaps in Current Research

Based on the literature review, we identify the following gaps:
- [Gap 1]: [Description of what is missing]
- [Gap 2]: [Description of what is missing]
- [Gap 3]: [Description of what is missing]

## 3. Methodology

### 3.1 Research Design

{methodology if methodology else '''This study employs [research design approach] to investigate [research questions].

The methodology consists of the following phases:
1. [Phase 1]: [Description]
2. [Phase 2]: [Description]
3. [Phase 3]: [Description]'''}

### 3.2 Data Collection

[Description of data collection procedures, sources, and criteria]

### 3.3 Analysis Framework

[Description of analytical methods and tools used]

### 3.4 Validation Approach

[Description of how results are validated and verified]

## 4. Experimental Setup

### 4.1 Experimental Design

[Detailed description of experimental design and rationale]

### 4.2 Implementation Details

[Technical implementation details, algorithms, and parameters]

### 4.3 Evaluation Metrics

The following metrics are used to evaluate performance:
- [Metric 1]: [Definition and rationale]
- [Metric 2]: [Definition and rationale]
- [Metric 3]: [Definition and rationale]

### 4.4 Baseline Comparisons

[Description of baseline methods and comparison criteria]

## 5. Results and Analysis

### 5.1 Primary Results

{findings_components.get('results', '''[Present main experimental results with appropriate tables and figures]

The results demonstrate that [key finding 1]. Additionally, we observe that [key finding 2]. Furthermore, [key finding 3].''')}

### 5.2 Comparative Analysis

[Comparison with baseline methods and state-of-the-art approaches]

### 5.3 Statistical Analysis

[Statistical significance tests and confidence intervals]

### 5.4 Sensitivity Analysis

[Analysis of robustness and sensitivity to parameters]

## 6. Discussion

### 6.1 Interpretation of Results

{findings_components.get('discussion', '''The results provide several important insights:

1. **[Insight 1]**: [Detailed explanation of first key insight]
2. **[Insight 2]**: [Detailed explanation of second key insight]  
3. **[Insight 3]**: [Detailed explanation of third key insight]''')}

### 6.2 Implications for Theory and Practice

**Theoretical Implications**: [How findings contribute to theoretical understanding]

**Practical Implications**: [How findings can be applied in practice]

### 6.3 Limitations

This study has several limitations that should be acknowledged:
- [Limitation 1]: [Description and impact]
- [Limitation 2]: [Description and impact]  
- [Limitation 3]: [Description and impact]

### 6.4 Threats to Validity

[Discussion of potential threats to internal and external validity]

## 7. Conclusion

### 7.1 Summary of Contributions

{findings_components.get('conclusion', '''This study makes several important contributions to the field of {topic.lower()}:

1. [Contribution summary 1]
2. [Contribution summary 2]
3. [Contribution summary 3]''')}

### 7.2 Future Work

Based on the findings and limitations of this study, several directions for future research are identified:
- [Future direction 1]: [Description and rationale]
- [Future direction 2]: [Description and rationale]
- [Future direction 3]: [Description and rationale]

### 7.3 Final Remarks

[Concluding thoughts on the significance and impact of the work]

## Acknowledgments

[Acknowledgment of funding, collaborators, and other support]

## References

{references if references else '''[1] Author, A. et al. (Year). Title of paper. Journal Name, Volume(Issue), pages.

[2] Author, B. et al. (Year). Title of book. Publisher, Location.

[3] Author, C. et al. (Year). Title of conference paper. In Proceedings of Conference Name, pages.

[Add all relevant references in appropriate format]'''}

## Appendices

### Appendix A: Additional Experimental Results

[Supplementary results and detailed tables]

### Appendix B: Implementation Details

[Code snippets, algorithms, and technical specifications]

### Appendix C: Statistical Analysis Details

[Detailed statistical analysis and test results]

---
*Generated by SakanaAI Paper Writer*
*Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
"""
        
        return paper
    
    async def _generate_survey_paper(self, context: Dict) -> str:
        """Generate literature survey paper"""
        topic = context["research_topic"]
        findings = context.get("findings", "")
        methodology = context.get("methodology", "")
        
        findings_components = self._parse_findings(findings)
        
        paper = f"""# A Comprehensive Survey of {topic}

## Abstract

This survey provides a comprehensive overview of the current state of research in {topic.lower()}. We systematically review [number] papers published between [start year] and [end year], analyzing methodologies, findings, and trends. Our analysis reveals key developments, persistent challenges, and emerging opportunities in the field. We conclude with a discussion of future research directions and open problems.

**Keywords**: {topic.lower()}, survey, literature review, [additional keywords]

## 1. Introduction

### 1.1 Motivation and Scope

The field of {topic.lower()} has experienced rapid growth and evolution. This survey aims to provide researchers and practitioners with a comprehensive understanding of:
- Current state of the field
- Key methodologies and approaches
- Major findings and contributions
- Persistent challenges and limitations
- Future research opportunities

### 1.2 Survey Methodology

{methodology if methodology else '''This survey follows a systematic methodology:

1. **Literature Search**: Comprehensive search across major databases
2. **Inclusion Criteria**: [Criteria for paper selection]
3. **Quality Assessment**: Evaluation of paper quality and relevance
4. **Data Extraction**: Systematic extraction of key information
5. **Analysis Framework**: Thematic analysis and synthesis'''}

### 1.3 Paper Organization

This survey is organized as follows: Section 2 provides background and definitions. Section 3 presents the taxonomy of approaches. Sections 4-6 review major categories of work. Section 7 discusses evaluation methodologies. Section 8 identifies challenges and opportunities. Section 9 concludes with future directions.

## 2. Background and Definitions

### 2.1 Fundamental Concepts

[Definition of key terms and concepts in the field]

### 2.2 Historical Development

[Brief history of the field and major milestones]

### 2.3 Related Fields

[Discussion of connections to related research areas]

## 3. Taxonomy of Approaches

### 3.1 Classification Framework

We propose the following taxonomy for organizing research in {topic.lower()}:

```
{topic}
├── Category 1
│   ├── Subcategory 1.1
│   └── Subcategory 1.2
├── Category 2
│   ├── Subcategory 2.1
│   └── Subcategory 2.2
└── Category 3
    ├── Subcategory 3.1
    └── Subcategory 3.2
```

### 3.2 Category Descriptions

**Category 1**: [Description of first major category]
**Category 2**: [Description of second major category]  
**Category 3**: [Description of third major category]

## 4. [Major Category 1] Approaches

### 4.1 Overview

[Overview of the first major category of approaches]

### 4.2 Key Methods

[Detailed review of key methods in this category]

### 4.3 Representative Works

[Discussion of important papers and their contributions]

### 4.4 Strengths and Limitations

[Analysis of advantages and disadvantages of these approaches]

## 5. [Major Category 2] Approaches

### 5.1 Overview

[Overview of the second major category of approaches]

### 5.2 Key Methods

[Detailed review of key methods in this category]

### 5.3 Representative Works

[Discussion of important papers and their contributions]

### 5.4 Strengths and Limitations

[Analysis of advantages and disadvantages of these approaches]

## 6. [Major Category 3] Approaches

### 6.1 Overview

[Overview of the third major category of approaches]

### 6.2 Key Methods

[Detailed review of key methods in this category]

### 6.3 Representative Works

[Discussion of important papers and their contributions]

### 6.4 Strengths and Limitations

[Analysis of advantages and disadvantages of these approaches]

## 7. Evaluation Methodologies

### 7.1 Common Evaluation Frameworks

[Discussion of standard evaluation approaches in the field]

### 7.2 Datasets and Benchmarks

[Review of commonly used datasets and benchmark problems]

### 7.3 Metrics and Criteria

[Analysis of evaluation metrics and their appropriateness]

### 7.4 Reproducibility Considerations

[Discussion of reproducibility challenges and best practices]

## 8. Challenges and Opportunities

### 8.1 Current Challenges

{findings_components.get('gaps', '''Based on our comprehensive review, we identify the following key challenges:

1. **[Challenge 1]**: [Description and impact]
2. **[Challenge 2]**: [Description and impact]
3. **[Challenge 3]**: [Description and impact]
4. **[Challenge 4]**: [Description and impact]''')}

### 8.2 Emerging Opportunities

{findings_components.get('future_directions', '''Several emerging opportunities present promising research directions:

1. **[Opportunity 1]**: [Description and potential impact]
2. **[Opportunity 2]**: [Description and potential impact]
3. **[Opportunity 3]**: [Description and potential impact]''')}

### 8.3 Cross-Cutting Issues

[Discussion of issues that span multiple categories or approaches]

## 9. Future Research Directions

### 9.1 Short-Term Priorities

[Research directions that can be addressed in the near term]

### 9.2 Long-Term Vision

[Longer-term research goals and vision for the field]

### 9.3 Interdisciplinary Connections

[Opportunities for collaboration with other fields]

### 9.4 Practical Applications

[Translation of research to real-world applications]

## 10. Conclusion

This comprehensive survey of {topic.lower()} reveals a dynamic and rapidly evolving field. Key insights from our analysis include:

- [Key insight 1]
- [Key insight 2]  
- [Key insight 3]

The field has made significant progress in [areas of progress], but important challenges remain in [areas needing work]. Future research should focus on [priority areas] to advance both theoretical understanding and practical applications.

## References

[Comprehensive reference list of all surveyed papers and additional sources]

---
*Survey completed: {datetime.now().strftime('%Y-%m-%d')}*
*Papers reviewed: [Number of papers]*
*Generated by SakanaAI Paper Writer*
"""
        
        return paper
    
    async def _generate_conference_paper(self, context: Dict) -> str:
        """Generate conference paper with space constraints"""
        topic = context["research_topic"]
        findings = context.get("findings", "")
        methodology = context.get("methodology", "")
        
        # Extract word limit from methodology if specified
        word_limit_match = re.search(r'Word limit:\s*(\d+)', methodology)
        word_limit = int(word_limit_match.group(1)) if word_limit_match else 8000
        
        findings_components = self._parse_findings(findings)
        
        paper = f"""# {topic}

## Abstract

**Background**: [Concise background and motivation]
**Problem**: [Clear problem statement]
**Method**: {methodology.replace(f'Word limit: {word_limit}', '').strip() if methodology else '[Brief method description]'}
**Results**: {findings_components.get('results', '[Key results]')}
**Conclusion**: {findings_components.get('conclusion', '[Main conclusion]')}

**Keywords**: [3-5 keywords]

## 1. Introduction

The problem of {topic.lower()} is important because [motivation]. While previous work has addressed [related work], significant challenges remain: [key challenges].

**Contributions**: This paper makes the following contributions:
1. [Contribution 1]
2. [Contribution 2]
3. [Contribution 3]

## 2. Related Work

[Concise review of most relevant prior work, focusing on differences from current approach]

## 3. Methodology

### 3.1 Approach Overview

{methodology.replace(f'Word limit: {word_limit}', '').strip() if methodology else '[Concise description of approach]'}

### 3.2 Key Components

[Brief description of main components or algorithmic steps]

### 3.3 Implementation

[Essential implementation details]

## 4. Experimental Evaluation

### 4.1 Setup

**Datasets**: [Dataset descriptions]
**Baselines**: [Comparison methods]
**Metrics**: [Evaluation metrics]

### 4.2 Results

{findings_components.get('results', '''Table 1 shows the main results. Our method achieves [performance summary] compared to baselines.

| Method | Metric 1 | Metric 2 | Metric 3 |
|--------|----------|----------|----------|
| Baseline 1 | X.XX | X.XX | X.XX |
| Baseline 2 | X.XX | X.XX | X.XX |
| Our Method | **X.XX** | **X.XX** | **X.XX** |

*Table 1: Performance comparison results*''')}

### 4.3 Analysis

[Brief analysis of results and what they demonstrate]

## 5. Discussion

{findings_components.get('discussion', '''The results demonstrate that [key finding]. This suggests [implication]. 

**Limitations**: [Key limitations]
**Future Work**: [Next steps]''')}

## 6. Conclusion

{findings_components.get('conclusion', f'''This paper presented [brief summary of contribution]. Experimental evaluation on [datasets/tasks] shows [key results]. Future work will focus on [directions].''')}

## Acknowledgments

[Brief acknowledgments]

## References

[Selected key references due to space constraints]

---
*Conference Paper ({word_limit} word limit)*
*Generated by SakanaAI Paper Writer*
"""
        
        return paper
    
    async def _generate_position_paper(self, context: Dict) -> str:
        """Generate position paper with argumentative structure"""
        topic = context["research_topic"]
        findings = context.get("findings", "")
        
        findings_components = self._parse_findings(findings)
        position = findings_components.get('position', f'[Position on {topic}]')
        arguments = findings_components.get('arguments', '[Supporting arguments]')
        counter_arguments = findings_components.get('counter_arguments', '[Counter-arguments]')
        evidence = findings_components.get('evidence', '[Supporting evidence]')
        
        paper = f"""# Position Paper: {topic}

## Abstract

This position paper argues that {position.lower()}. We present evidence and reasoning to support this position, address potential counter-arguments, and discuss implications for the field. Our analysis suggests that [key implication].

## 1. Introduction

### 1.1 The Position

We argue that: **{position}**

### 1.2 Importance of This Position

This position is important because:
- [Reason 1]
- [Reason 2]
- [Reason 3]

### 1.3 Paper Structure

This position paper is organized as follows: Section 2 presents our main arguments. Section 3 provides supporting evidence. Section 4 addresses counter-arguments. Section 5 discusses implications. Section 6 concludes.

## 2. Main Arguments

### 2.1 Argument Framework

Our position is supported by the following key arguments:

{arguments if arguments != '[Supporting arguments]' else '''
**Argument 1**: [First supporting argument with rationale]

**Argument 2**: [Second supporting argument with rationale]

**Argument 3**: [Third supporting argument with rationale]
'''}

### 2.2 Logical Foundation

[Logical reasoning connecting the arguments to the position]

## 3. Supporting Evidence

### 3.1 Empirical Evidence

{evidence if evidence != '[Supporting evidence]' else '''
[Presentation of empirical data, studies, and observations that support the position]
'''}

### 3.2 Theoretical Support

[Theoretical frameworks and principles that support the position]

### 3.3 Case Studies

[Specific examples and case studies that illustrate the position]

## 4. Addressing Counter-Arguments

### 4.1 Common Objections

{counter_arguments if counter_arguments != '[Counter-arguments]' else '''
**Objection 1**: [First common objection]
**Response**: [Reasoned response to the objection]

**Objection 2**: [Second common objection]  
**Response**: [Reasoned response to the objection]

**Objection 3**: [Third common objection]
**Response**: [Reasoned response to the objection]
'''}

### 4.2 Limitations of Our Position

We acknowledge the following limitations:
- [Limitation 1 and how it affects the position]
- [Limitation 2 and how it affects the position]

## 5. Implications

### 5.1 For Research

If our position is accepted, research should:
- [Research implication 1]
- [Research implication 2]
- [Research implication 3]

### 5.2 For Practice

Practical implications include:
- [Practical implication 1]
- [Practical implication 2]  
- [Practical implication 3]

### 5.3 For Policy

Policy considerations include:
- [Policy implication 1]
- [Policy implication 2]

## 6. Conclusion

This position paper has argued that {position.lower()}. The evidence presented supports this position through [summary of key evidence]. While we acknowledge [key limitations], we believe the arguments presented make a compelling case for [action or change needed].

**Call to Action**: We encourage the community to [specific actions or considerations].

## References

[References supporting the arguments and evidence presented]

---
*Position Paper*
*Generated by SakanaAI Paper Writer*
"""
        
        return paper
    
    async def _generate_journal_article(self, context: Dict) -> str:
        """Generate journal article format"""
        # Journal articles are similar to research papers but with more detailed sections
        # and often different formatting requirements
        return await self._generate_research_paper(context)
    
    async def _generate_technical_report(self, context: Dict) -> str:
        """Generate technical report"""
        topic = context["research_topic"]
        findings = context.get("findings", "")
        methodology = context.get("methodology", "")
        
        paper = f"""# Technical Report: {topic}

## Executive Summary

[High-level summary of the technical work, key findings, and recommendations]

## 1. Introduction

### 1.1 Background

[Technical background and context]

### 1.2 Objectives

[Specific technical objectives and goals]

### 1.3 Scope

[Scope and boundaries of the technical work]

## 2. Technical Approach

### 2.1 Methodology

{methodology if methodology else '[Detailed technical methodology]'}

### 2.2 Architecture

[System architecture and design decisions]

### 2.3 Implementation Details

[Specific implementation details and technical specifications]

## 3. Results and Analysis

### 3.1 Technical Results

{findings if findings else '[Detailed technical results and measurements]'}

### 3.2 Performance Analysis

[Performance evaluation and analysis]

### 3.3 Validation

[Validation procedures and results]

## 4. Discussion

### 4.1 Technical Insights

[Technical insights and lessons learned]

### 4.2 Limitations

[Technical limitations and constraints]

### 4.3 Recommendations

[Technical recommendations and best practices]

## 5. Conclusion

[Summary of technical contributions and future work]

## Appendices

### Appendix A: Technical Specifications

[Detailed technical specifications]

### Appendix B: Code Documentation  

[Code listings and documentation]

### Appendix C: Test Results

[Comprehensive test results and data]

---
*Technical Report*
*Generated by SakanaAI Paper Writer*
"""
        
        return paper
    
    async def _generate_generic_paper(self, context: Dict) -> str:
        """Generate generic paper format"""
        topic = context["research_topic"]
        findings = context.get("findings", "")
        methodology = context.get("methodology", "")
        
        paper = f"""# {topic}

## Abstract

[Abstract summarizing the paper's contribution, methodology, and key findings]

## 1. Introduction

[Introduction providing background, motivation, and paper contributions]

## 2. Background

[Background information and related work]

## 3. Methodology

{methodology if methodology else '[Description of methodology and approach]'}

## 4. Results

{findings if findings else '[Presentation of results and findings]'}

## 5. Discussion

[Discussion of results, implications, and limitations]

## 6. Conclusion

[Conclusion summarizing contributions and future work]

## References

[References cited in the paper]

---
*Generated by SakanaAI Paper Writer*
"""
        
        return paper
    
    def _parse_findings(self, findings: str) -> Dict[str, str]:
        """Parse findings string into components"""
        components = {}
        if not findings:
            return components
        
        # Look for labeled sections
        patterns = {
            'results': r'Results?:\s*(.*?)(?=\n[A-Z][a-z]+:|$)',
            'discussion': r'Discussion:\s*(.*?)(?=\n[A-Z][a-z]+:|$)',
            'conclusion': r'Conclusions?:\s*(.*?)(?=\n[A-Z][a-z]+:|$)',
            'position': r'Position:\s*(.*?)(?=\n[A-Z][a-z]+:|$)',
            'arguments': r'Arguments:\s*(.*?)(?=\n[A-Z][a-z]+:|$)',
            'counter_arguments': r'Counter-arguments:\s*(.*?)(?=\n[A-Z][a-z]+:|$)',
            'evidence': r'Evidence:\s*(.*?)(?=\n[A-Z][a-z]+:|$)',
            'gaps': r'Gaps:\s*(.*?)(?=\n[A-Z][a-z]+:|$)',
            'future_directions': r'Future Work:\s*(.*?)(?=\n[A-Z][a-z]+:|$)'
        }
        
        for key, pattern in patterns.items():
            match = re.search(pattern, findings, re.IGNORECASE | re.DOTALL)
            if match:
                components[key] = match.group(1).strip()
        
        return components
    
    async def _save_paper(self, paper_content: str, context: Dict):
        """Save paper to memory"""
        try:
            db = await memory.Memory.get(self.agent)
            
            metadata = {
                "type": "academic_paper",
                "paper_type": context.get("paper_type", "generic"),
                "research_topic": context.get("research_topic", ""),
                "timestamp": context.get("timestamp", datetime.now().isoformat()),
                "agent": self.agent.agent_name
            }
            
            await db.insert(
                text=paper_content,
                area=memory.Memory.Area.RESEARCH,
                metadata=metadata
            )
            
            PrintStyle(font_color="#27AE60").print(f"Academic paper saved to memory")
            
        except Exception as e:
            handle_error(e)
            PrintStyle(font_color="#E74C3C").print(f"Failed to save paper: {str(e)}")