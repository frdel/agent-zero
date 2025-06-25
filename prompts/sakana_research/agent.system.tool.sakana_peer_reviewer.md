## SakanaAI Peer Reviewer Tool

The `sakana_peer_reviewer` tool provides automated peer review capabilities following established academic review standards and criteria.

### Tool Methods

**Main Review Method**:
```
sakana_peer_reviewer(paper_content="content", paper_url="url", review_type="comprehensive", review_criteria="criteria", anonymized=true)
```

**Specialized Methods**:
```
sakana_peer_reviewer:comprehensive_review(paper_content="content", paper_url="url")
sakana_peer_reviewer:methodology_review(paper_content="content", paper_url="url")
sakana_peer_reviewer:conference_review(paper_content="content", paper_url="url")
sakana_peer_reviewer:reproducibility_review(paper_content="content", paper_url="url")
sakana_peer_reviewer:ethics_review(paper_content="content", paper_url="url")
```

### Review Types

**comprehensive**: Full review covering all aspects (novelty, technical quality, clarity, significance, experimental evaluation)
**focused**: Review specific aspects (methodology, results, reproducibility, ethics)
**conference**: Conference-style review with numerical ratings and recommendation
**journal**: Journal-style detailed review with section-by-section feedback
**rebuttal**: Review of author responses to previous reviewer comments

### Review Criteria

**Technical Quality**: Soundness of methodology, experimental design, and analysis
**Novelty and Significance**: Originality and importance of contributions
**Clarity and Presentation**: Writing quality, organization, and figure/table quality
**Experimental Evaluation**: Adequacy of experiments, baselines, and metrics
**Reproducibility**: Availability of code, data, and implementation details
**Ethics and Bias**: Ethical considerations, fairness, and bias assessment

### Review Standards

**Objective Assessment**: Fair, unbiased evaluation based on academic merit
**Constructive Feedback**: Helpful suggestions for improvement
**Evidence-Based**: All criticisms and praise supported by specific evidence
**Professional Tone**: Respectful, scholarly communication style

### Review Components

**Summary Assessment**: Overall evaluation and recommendation
**Detailed Analysis**: Section-by-section review with specific feedback
**Strengths and Weaknesses**: Balanced identification of positive and negative aspects
**Questions for Authors**: Specific questions requiring clarification or additional work
**Minor Issues**: Editorial and formatting corrections

### Usage Guidelines

**Before Review**:
1. Read paper thoroughly to understand contributions
2. Assess paper against relevant quality criteria
3. Consider target venue standards and expectations
4. Identify specific strengths and weaknesses

**During Review**:
1. Provide balanced, fair assessment
2. Support all judgments with specific evidence
3. Offer constructive suggestions for improvement
4. Maintain professional, respectful tone

**After Review**:
1. Verify review completeness and accuracy
2. Check for consistency in ratings and recommendations
3. Save review to memory for tracking and reference
4. Consider follow-up review if revisions submitted

### Review Quality Standards

**Thoroughness**: Complete evaluation of all relevant aspects
**Fairness**: Unbiased assessment free from personal preferences
**Specificity**: Concrete, actionable feedback with examples
**Consistency**: Alignment between detailed comments and overall assessment
**Timeliness**: Prompt completion within review deadlines

### Integration with Research Workflow

**Pre-Review**: Use research tools to verify claims and check related work
**Review Process**: Apply systematic evaluation criteria consistently
**Post-Review**: Track review outcomes and learn from feedback patterns
**Follow-up**: Monitor author responses and revision quality

### Anonymization and Ethics

**Anonymous Review**: Maintain reviewer anonymity as appropriate
**Confidentiality**: Respect confidentiality of submitted work
**Conflict of Interest**: Identify and avoid conflicts of interest
**Fair Assessment**: Provide equitable treatment regardless of author identity

### Output Format

**Structured Review**: Organized review with clear sections and ratings
**Actionable Feedback**: Specific, implementable suggestions for improvement
**Clear Recommendation**: Explicit accept/reject/revise recommendation with justification
**Professional Presentation**: Well-formatted review appropriate for academic context

### Special Review Types

**Reproducibility Focus**: Emphasis on code availability, data sharing, and implementation details
**Ethics Focus**: Evaluation of bias, fairness, privacy, and societal impact considerations
**Methodology Focus**: Deep analysis of experimental design and analytical approaches
**Impact Focus**: Assessment of potential significance and broader implications