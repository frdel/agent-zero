import os
import json
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any
from python.helpers.tool import Tool, Response
from python.helpers.print_style import PrintStyle
from python.helpers.errors import handle_error
from python.helpers import memory

class SakanaExperimentDesigner(Tool):
    
    async def execute(self, research_question="", experiment_type="ml_experiment", 
                     domain="", methodology="", constraints="", **kwargs):
        """
        Design experiments based on research questions and methodological requirements.
        
        Experiment types:
        - ml_experiment: Machine learning experiment design
        - ablation_study: Component contribution analysis
        - comparative_study: Method comparison framework
        - parameter_study: Parameter sensitivity analysis
        - validation_study: Model validation design
        """
        
        if not research_question:
            return Response(message="Research question is required for experiment design", break_loop=False)
        
        design_context = {
            "research_question": research_question,
            "experiment_type": experiment_type,
            "domain": domain,
            "methodology": methodology,
            "constraints": constraints.split(",") if constraints else [],
            "timestamp": datetime.now().isoformat()
        }
        
        PrintStyle(font_color="#8E44AD", bold=True).print(f"Designing {experiment_type}: {research_question}")
        
        experiment_design = await self._design_experiment(design_context)
        
        # Save design to memory
        await self._save_experiment_design(experiment_design, design_context)
        
        await self.agent.handle_intervention(experiment_design)
        return Response(message=experiment_design, break_loop=False)
    
    async def ml_experiment(self, research_question="", dataset="", model_type="", 
                           evaluation_metrics="", **kwargs):
        """Design machine learning experiments"""
        return await self.execute(
            research_question=research_question,
            experiment_type="ml_experiment",
            methodology=f"dataset:{dataset},model:{model_type},metrics:{evaluation_metrics}"
        )
    
    async def ablation_study(self, base_model="", components="", evaluation_criteria="", **kwargs):
        """Design ablation studies to understand component contributions"""
        return await self.execute(
            research_question=f"What is the contribution of each component in {base_model}?",
            experiment_type="ablation_study",
            methodology=f"base_model:{base_model},components:{components},criteria:{evaluation_criteria}"
        )
    
    async def comparative_study(self, methods="", evaluation_framework="", datasets="", **kwargs):
        """Design comparative studies between different methods"""
        return await self.execute(
            research_question=f"How do {methods} compare across different conditions?",
            experiment_type="comparative_study", 
            methodology=f"methods:{methods},framework:{evaluation_framework},datasets:{datasets}"
        )
    
    async def validation_experiment(self, model="", validation_type="cross_validation", 
                                  test_scenarios="", **kwargs):
        """Design model validation experiments"""
        return await self.execute(
            research_question=f"How well does {model} generalize to unseen data?",
            experiment_type="validation_study",
            methodology=f"model:{model},validation:{validation_type},scenarios:{test_scenarios}"
        )
    
    async def _design_experiment(self, context: Dict) -> str:
        """Main experiment design logic"""
        experiment_type = context["experiment_type"]
        
        design_methods = {
            "ml_experiment": self._design_ml_experiment,
            "ablation_study": self._design_ablation_study,
            "comparative_study": self._design_comparative_study,
            "parameter_study": self._design_parameter_study,
            "validation_study": self._design_validation_study
        }
        
        if experiment_type in design_methods:
            return await design_methods[experiment_type](context)
        else:
            return await self._design_generic_experiment(context)
    
    async def _design_ml_experiment(self, context: Dict) -> str:
        """Design machine learning experiments"""
        research_question = context["research_question"]
        methodology = context.get("methodology", "")
        domain = context.get("domain", "")
        constraints = context.get("constraints", [])
        
        # Parse methodology parameters
        method_params = self._parse_methodology(methodology)
        dataset = method_params.get("dataset", "specify_dataset")
        model_type = method_params.get("model", "specify_model")
        metrics = method_params.get("metrics", "accuracy,precision,recall,f1")
        
        design = f"""# Machine Learning Experiment Design

**Research Question**: {research_question}
**Domain**: {domain if domain else "General Machine Learning"}
**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Experiment Overview

### Objective
Design and execute a machine learning experiment to answer: "{research_question}"

### Hypothesis
Based on the research question, we hypothesize that [specify expected outcome based on methodology and domain knowledge].

## Experimental Design

### 1. Dataset Specification
**Primary Dataset**: {dataset}
**Data Requirements**:
- Size: Specify minimum sample size for statistical significance
- Quality: Data cleaning and preprocessing requirements
- Splits: Training (70%), Validation (15%), Test (15%)
- Balance: Check for class imbalance and mitigation strategies

**Data Preprocessing Pipeline**:
```python
# Data preprocessing steps
1. Data cleaning and outlier detection
2. Feature engineering and selection
3. Normalization/standardization
4. Train-validation-test split
5. Data augmentation (if applicable)
```

### 2. Model Architecture
**Primary Model**: {model_type}
**Architecture Considerations**:
- Model complexity appropriate for dataset size
- Baseline model for comparison
- State-of-the-art alternatives for benchmarking

**Hyperparameter Space**:
- Define search space for key hyperparameters
- Use systematic search (grid search, random search, or Bayesian optimization)
- Document parameter selection rationale

### 3. Evaluation Framework
**Primary Metrics**: {metrics}
**Additional Metrics**:
- Cross-validation scores
- Statistical significance tests
- Computational efficiency (training time, inference time)
- Model interpretability measures

**Evaluation Protocol**:
1. Train model on training set
2. Hyperparameter tuning on validation set
3. Final evaluation on held-out test set
4. Cross-validation for robust estimates
5. Statistical significance testing

### 4. Experimental Controls
**Fixed Variables**:
- Random seeds for reproducibility
- Hardware specifications
- Software versions and dependencies
- Training procedures and stopping criteria

**Variable Factors**:
- Model architectures
- Hyperparameter configurations
- Data preprocessing choices
- Training strategies

## Implementation Plan

### Phase 1: Setup and Baseline (Days 1-2)
- [ ] Data collection and preprocessing
- [ ] Baseline model implementation
- [ ] Evaluation pipeline setup
- [ ] Initial exploratory data analysis

### Phase 2: Model Development (Days 3-5)
- [ ] Primary model implementation
- [ ] Hyperparameter optimization
- [ ] Cross-validation experiments
- [ ] Performance optimization

### Phase 3: Evaluation and Analysis (Days 6-7)
- [ ] Comprehensive evaluation
- [ ] Statistical analysis
- [ ] Results visualization
- [ ] Error analysis and interpretation

### Phase 4: Documentation (Day 8)
- [ ] Results documentation
- [ ] Code documentation and sharing
- [ ] Reproducibility verification
- [ ] Report writing

## Success Criteria

**Technical Success**:
- Model achieves target performance metrics
- Results are statistically significant
- Experiments are reproducible
- Code is well-documented

**Scientific Success**:
- Research question is adequately answered
- Findings contribute to domain knowledge
- Limitations are clearly identified
- Future work is outlined

## Risk Mitigation

**Data Risks**:
- Data unavailability → Identify alternative datasets
- Data quality issues → Implement robust preprocessing
- Insufficient data → Consider data augmentation or transfer learning

**Technical Risks**:
- Model convergence issues → Multiple initialization strategies
- Computational constraints → Model simplification or distributed training
- Implementation bugs → Extensive testing and code review

**Timeline Risks**:
- Delayed data access → Parallel work on synthetic data
- Longer training times → Early stopping and checkpointing
- Scope creep → Clear success criteria and regular reviews

## Resource Requirements

**Computational**:
- Training hardware specifications
- Estimated training time
- Storage requirements for data and models
- Cloud computing costs (if applicable)

**Human Resources**:
- Researcher time allocation
- Required expertise areas
- Collaboration needs
- Review and validation personnel

## Ethical Considerations

**Data Ethics**:
- Data privacy and consent
- Bias identification and mitigation
- Fair representation in datasets
- Responsible data sharing

**Model Ethics**:
- Algorithmic fairness
- Transparency and interpretability
- Potential for misuse
- Societal impact assessment

## Expected Outcomes

**Primary Deliverables**:
1. Trained model with performance benchmarks
2. Comprehensive experimental results
3. Reproducible code and documentation
4. Research paper draft or technical report

**Knowledge Contributions**:
- Empirical validation of hypotheses
- Performance comparisons with existing methods
- Insights into model behavior and limitations
- Methodological improvements or novel approaches

---
*Generated by SakanaAI Experiment Designer*
"""
        
        # Add constraint-specific modifications
        if constraints:
            design += "\n## Constraint Considerations\n\n"
            for constraint in constraints:
                design += f"- **{constraint.strip()}**: Adjust experimental design accordingly\n"
        
        return design
    
    async def _design_ablation_study(self, context: Dict) -> str:
        """Design ablation studies"""
        research_question = context["research_question"]
        methodology = context.get("methodology", "")
        
        method_params = self._parse_methodology(methodology)
        base_model = method_params.get("base_model", "specify_model")
        components = method_params.get("components", "component1,component2,component3").split(",")
        criteria = method_params.get("criteria", "performance,efficiency,robustness")
        
        design = f"""# Ablation Study Design

**Research Question**: {research_question}
**Base Model**: {base_model}
**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Study Overview

### Objective
Systematically evaluate the contribution of each component in {base_model} to understand:
- Which components are essential for performance
- How components interact with each other
- Where improvements can be made

### Components to Ablate
"""
        
        for i, component in enumerate(components, 1):
            design += f"{i}. **{component.strip()}**: [Description of component function]\n"
        
        design += f"""
## Ablation Methodology

### 1. Baseline Establishment
**Full Model**: Complete {base_model} with all components
- Establish performance baseline on test dataset
- Document all hyperparameters and configurations
- Ensure reproducible training procedure

### 2. Component Removal Strategy
**Single Component Ablation**: Remove one component at a time
- Test each component's individual contribution
- Maintain all other components unchanged
- Use identical training and evaluation procedures

**Multiple Component Ablation**: Remove combinations of components
- Test component interactions
- Identify critical component dependencies
- Explore minimal viable model configurations

### 3. Evaluation Criteria
**Primary Metrics**: {criteria}
**Detailed Assessment**:
- Performance degradation per component removal
- Statistical significance of differences
- Computational efficiency changes
- Model interpretability impact

## Experimental Matrix

### Single Component Ablations
"""
        
        for component in components:
            design += f"- **Without {component.strip()}**: Measure impact on all evaluation criteria\n"
        
        design += """
### Component Interaction Analysis
- Pairwise component removal
- Three-way interaction effects (if applicable)
- Hierarchical component importance

## Implementation Protocol

### 1. Preparation Phase
- [ ] Implement modular architecture allowing component removal
- [ ] Establish baseline performance with full model
- [ ] Prepare evaluation pipeline for consistent assessment
- [ ] Define statistical testing procedures

### 2. Execution Phase
- [ ] Systematic component ablation experiments
- [ ] Multiple runs for statistical reliability
- [ ] Performance tracking and logging
- [ ] Intermediate result analysis

### 3. Analysis Phase
- [ ] Statistical analysis of results
- [ ] Component importance ranking
- [ ] Interaction effect identification
- [ ] Visualization of findings

## Expected Findings

**Component Importance Ranking**: Ordered list of components by contribution to overall performance

**Critical Dependencies**: Identification of components that are essential for model function

**Interaction Effects**: Understanding of how components work together

**Optimization Opportunities**: Components that can be simplified or removed without significant performance loss

## Quality Assurance

**Reproducibility**: Multiple runs with different random seeds
**Statistical Rigor**: Appropriate statistical tests for significance
**Control Variables**: Consistent training procedures across all ablations
**Documentation**: Detailed logging of all experimental parameters

---
*Generated by SakanaAI Ablation Study Designer*
"""
        
        return design
    
    async def _design_comparative_study(self, context: Dict) -> str:
        """Design comparative studies"""
        research_question = context["research_question"]
        methodology = context.get("methodology", "")
        
        method_params = self._parse_methodology(methodology)
        methods = method_params.get("methods", "method1,method2,method3").split(",")
        framework = method_params.get("framework", "performance,efficiency,robustness")
        datasets = method_params.get("datasets", "dataset1,dataset2,dataset3").split(",")
        
        design = f"""# Comparative Study Design

**Research Question**: {research_question}
**Methods Under Comparison**: {', '.join([m.strip() for m in methods])}
**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Study Overview

### Objective
Systematically compare multiple methods to determine:
- Relative performance across different conditions
- Strengths and weaknesses of each approach
- Optimal method selection criteria
- Context-dependent performance variations

### Methods to Compare
"""
        
        for i, method in enumerate(methods, 1):
            design += f"{i}. **{method.strip()}**: [Brief description and key characteristics]\n"
        
        design += f"""
## Comparative Framework

### 1. Evaluation Dimensions
**Primary Dimensions**: {framework}
**Detailed Metrics**:
- Performance accuracy and reliability
- Computational efficiency (time, memory)
- Robustness to noise and outliers
- Scalability characteristics
- Interpretability and explainability
- Implementation complexity

### 2. Test Datasets
**Datasets for Comparison**:
"""
        
        for i, dataset in enumerate(datasets, 1):
            design += f"{i}. **{dataset.strip()}**: [Dataset characteristics and why selected]\n"
        
        design += """
**Dataset Selection Criteria**:
- Diversity in problem characteristics
- Different scales and complexities
- Varying noise levels and data quality
- Representative of real-world applications

### 3. Experimental Controls
**Standardized Conditions**:
- Identical preprocessing pipelines
- Consistent evaluation protocols
- Same hardware and software environment
- Fixed random seeds for reproducibility

**Fair Comparison Principles**:
- Optimal hyperparameters for each method
- Appropriate training procedures per method
- Equal computational budgets where applicable
- Method-specific best practices followed

## Implementation Design

### 1. Method Implementation
**Standardization**:
- Common interface for all methods
- Consistent input/output formats
- Uniform error handling
- Comprehensive logging

**Optimization**:
- Individual hyperparameter tuning per method
- Method-specific optimization strategies
- Performance profiling and optimization
- Documentation of implementation choices

### 2. Evaluation Pipeline
**Automated Testing**:
```python
# Comparative evaluation framework
for dataset in datasets:
    for method in methods:
        # Load and preprocess dataset
        # Apply method with optimal parameters
        # Evaluate on multiple metrics
        # Store results with metadata
        # Perform statistical analysis
```

### 3. Statistical Analysis Framework
**Significance Testing**:
- Paired t-tests for performance differences
- Multiple comparison corrections (Bonferroni, Holm)
- Effect size calculations (Cohen's d)
- Confidence intervals for all metrics

**Robustness Analysis**:
- Bootstrap sampling for uncertainty estimation
- Cross-validation for stable estimates
- Sensitivity analysis for hyperparameters
- Outlier impact assessment

## Results Framework

### 1. Performance Matrices
**Method × Dataset Performance**: Complete performance matrix across all conditions

**Statistical Significance**: Pairwise significance tests between all method pairs

**Effect Sizes**: Practical significance of performance differences

### 2. Visualization Strategy
**Performance Profiles**: Line plots showing method performance across datasets

**Ranking Analysis**: Method rankings with confidence intervals

**Trade-off Analysis**: Pareto frontier plots for multi-objective comparison

**Heatmaps**: Performance matrices with statistical annotations

### 3. Contextual Analysis
**Winner-Take-All**: Best method per dataset and metric

**Conditional Performance**: When each method performs best

**Robustness Assessment**: Performance stability across conditions

**Practical Recommendations**: Method selection guidelines

## Quality Assurance Protocol

### 1. Implementation Verification
- [ ] Code review for all method implementations
- [ ] Unit tests for critical components
- [ ] Benchmark against published results
- [ ] Cross-platform compatibility testing

### 2. Experimental Validation
- [ ] Pilot studies on subset of conditions
- [ ] Intermediate result validation
- [ ] Anomaly detection in results
- [ ] Reproducibility verification

### 3. Statistical Rigor
- [ ] Power analysis for sample sizes
- [ ] Multiple testing corrections
- [ ] Assumption checking for statistical tests
- [ ] Sensitivity analysis for conclusions

## Expected Deliverables

**Comprehensive Report**:
1. Method performance comparison tables
2. Statistical analysis results
3. Visualization of key findings
4. Method selection recommendations
5. Implementation details and code

**Practical Guidelines**:
- Decision framework for method selection
- Performance-context mapping
- Implementation difficulty assessment
- Resource requirement analysis

---
*Generated by SakanaAI Comparative Study Designer*
"""
        
        return design
    
    async def _design_parameter_study(self, context: Dict) -> str:
        """Design parameter sensitivity studies"""
        research_question = context["research_question"]
        
        design = f"""# Parameter Sensitivity Study Design

**Research Question**: {research_question}
**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Study Overview

### Objective
Systematically analyze the sensitivity of model performance to parameter variations to:
- Identify critical parameters requiring careful tuning
- Understand parameter interaction effects
- Establish robust parameter ranges
- Guide hyperparameter optimization strategies

## Parameter Analysis Framework

### 1. Parameter Categorization
**Critical Parameters**: Parameters with high impact on performance
**Robustness Parameters**: Parameters affecting model stability
**Efficiency Parameters**: Parameters influencing computational cost
**Architecture Parameters**: Structural model parameters

### 2. Sensitivity Analysis Methods
**One-at-a-time (OAT)**: Vary one parameter while keeping others fixed
**Global Sensitivity Analysis**: Simultaneous variation of all parameters
**Morris Screening**: Efficient screening of parameter importance
**Sobol Indices**: Variance-based sensitivity measures

### 3. Parameter Space Exploration
**Grid Search**: Systematic sampling across parameter ranges
**Random Search**: Random sampling for high-dimensional spaces
**Latin Hypercube Sampling**: Efficient space-filling designs
**Adaptive Sampling**: Focus on interesting parameter regions

## Experimental Design

### 1. Parameter Selection
- [ ] Identify all tunable parameters
- [ ] Define reasonable parameter ranges
- [ ] Categorize parameters by expected importance
- [ ] Consider parameter constraints and dependencies

### 2. Sampling Strategy
- [ ] Design sampling plan for parameter space
- [ ] Determine sample size for statistical power
- [ ] Plan for multiple replications
- [ ] Account for computational constraints

### 3. Evaluation Protocol
- [ ] Define performance metrics for sensitivity analysis
- [ ] Establish baseline parameter configuration
- [ ] Plan statistical analysis procedures
- [ ] Design visualization strategy

## Implementation Plan

### Phase 1: Parameter Space Definition
- Map all relevant parameters
- Establish parameter ranges and constraints
- Create parameter sampling framework
- Implement parameter validation

### Phase 2: Sensitivity Experiments
- Execute parameter sweep experiments
- Collect performance data across parameter space
- Monitor for convergence and stability
- Identify parameter interaction effects

### Phase 3: Analysis and Interpretation
- Compute sensitivity indices
- Rank parameters by importance
- Identify robust parameter regions
- Develop parameter selection guidelines

---
*Generated by SakanaAI Parameter Study Designer*
"""
        
        return design
    
    async def _design_validation_study(self, context: Dict) -> str:
        """Design validation studies"""
        research_question = context["research_question"]
        methodology = context.get("methodology", "")
        
        method_params = self._parse_methodology(methodology)
        model = method_params.get("model", "specify_model")
        validation_type = method_params.get("validation", "cross_validation")
        scenarios = method_params.get("scenarios", "in_domain,out_of_domain,adversarial").split(",")
        
        design = f"""# Model Validation Study Design

**Research Question**: {research_question}
**Model**: {model}
**Validation Type**: {validation_type}
**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Validation Overview

### Objective
Comprehensively validate {model} performance and reliability across multiple dimensions:
- Generalization to unseen data
- Robustness to distribution shifts
- Stability across different conditions
- Practical deployment readiness

### Validation Scenarios
"""
        
        for i, scenario in enumerate(scenarios, 1):
            design += f"{i}. **{scenario.strip()}**: [Description of validation scenario]\n"
        
        design += f"""
## Validation Framework

### 1. Internal Validation
**Cross-Validation Strategy**: {validation_type}
- K-fold cross-validation for stable estimates
- Stratified sampling for balanced evaluation
- Time-series validation for temporal data
- Nested cross-validation for hyperparameter selection

### 2. External Validation
**Independent Test Sets**:
- Hold-out validation on unseen data
- Multi-site validation across different sources
- Temporal validation on future data
- Cross-domain validation on related tasks

### 3. Robustness Testing
**Distribution Shift Analysis**:
- Performance under covariate shift
- Label shift robustness testing
- Domain adaptation capabilities
- Adversarial robustness evaluation

## Validation Protocol

### 1. Data Preparation
**Training Data**: Model development dataset
**Validation Data**: Hyperparameter tuning and model selection
**Test Data**: Final performance evaluation
**Robustness Data**: Distribution shift and stress testing

### 2. Performance Metrics
**Primary Metrics**: Task-specific performance measures
**Reliability Metrics**: Confidence calibration, uncertainty quantification
**Fairness Metrics**: Performance across different groups
**Efficiency Metrics**: Computational requirements and scalability

### 3. Statistical Analysis
**Confidence Intervals**: Bootstrap confidence intervals for all metrics
**Significance Testing**: Statistical significance of performance differences
**Power Analysis**: Sample size adequacy for conclusions
**Multiple Comparisons**: Correction for multiple testing

## Quality Assurance

### 1. Methodological Rigor
- [ ] Proper train-validation-test splits
- [ ] No data leakage between splits
- [ ] Appropriate statistical procedures
- [ ] Comprehensive error analysis

### 2. Reproducibility
- [ ] Fixed random seeds
- [ ] Documented software versions
- [ ] Shared code and data (where possible)
- [ ] Detailed experimental protocols

### 3. Transparency
- [ ] Clear reporting of all results
- [ ] Honest discussion of limitations
- [ ] Availability of implementation details
- [ ] Open access to validation results

## Expected Outcomes

**Validation Report**:
1. Comprehensive performance assessment
2. Robustness and reliability analysis
3. Deployment readiness evaluation
4. Recommendations for practical use

**Decision Framework**:
- Clear criteria for model acceptance
- Risk assessment for deployment
- Monitoring requirements for production
- Update and revalidation protocols

---
*Generated by SakanaAI Validation Study Designer*
"""
        
        return design
    
    async def _design_generic_experiment(self, context: Dict) -> str:
        """Design generic experiments for non-standard cases"""
        research_question = context["research_question"]
        domain = context.get("domain", "")
        methodology = context.get("methodology", "")
        
        design = f"""# Generic Experiment Design

**Research Question**: {research_question}
**Domain**: {domain if domain else "General"}
**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Experimental Framework

### 1. Research Objectives
**Primary Objective**: Answer the research question: "{research_question}"
**Secondary Objectives**: 
- Understand underlying mechanisms
- Identify practical implications
- Generate hypotheses for future work

### 2. Experimental Strategy
**Methodology**: {methodology if methodology else "To be determined based on research question"}
**Approach**: Systematic investigation with appropriate controls and measurements

### 3. Success Criteria
**Quantitative Measures**: Define specific metrics for success
**Qualitative Assessments**: Subjective evaluation criteria
**Statistical Significance**: Required confidence levels
**Practical Significance**: Real-world impact thresholds

## Implementation Guidelines

### 1. Experimental Design Principles
- Clear hypothesis formulation
- Appropriate control conditions
- Sufficient sample sizes
- Proper randomization procedures
- Bias minimization strategies

### 2. Data Collection Protocol
- Systematic data gathering procedures
- Quality control measures
- Data validation and cleaning
- Metadata documentation
- Backup and security procedures

### 3. Analysis Plan
- Statistical analysis methods
- Visualization strategies
- Interpretation frameworks
- Limitation acknowledgment
- Future work identification

## Quality Assurance Framework

### 1. Validity Considerations
**Internal Validity**: Control for confounding variables
**External Validity**: Generalizability to broader contexts
**Construct Validity**: Measures accurately represent concepts
**Statistical Conclusion Validity**: Appropriate statistical methods

### 2. Reliability Measures
**Test-Retest Reliability**: Consistency across time
**Inter-Rater Reliability**: Agreement between evaluators
**Internal Consistency**: Coherence of measurement instruments
**Parallel Forms Reliability**: Equivalence of alternative measures

### 3. Ethical Considerations
- Ethical approval requirements
- Informed consent procedures
- Data privacy and protection
- Risk-benefit assessment
- Responsible disclosure practices

---
*Generated by SakanaAI Generic Experiment Designer*
"""
        
        return design
    
    def _parse_methodology(self, methodology: str) -> Dict[str, str]:
        """Parse methodology string into key-value pairs"""
        params = {}
        if not methodology:
            return params
        
        for param in methodology.split(","):
            if ":" in param:
                key, value = param.split(":", 1)
                params[key.strip()] = value.strip()
        
        return params
    
    async def _save_experiment_design(self, design: str, context: Dict):
        """Save experiment design to memory"""
        try:
            db = await memory.Memory.get(self.agent)
            
            metadata = {
                "type": "experiment_design",
                "experiment_type": context.get("experiment_type", "generic"),
                "research_question": context.get("research_question", ""),
                "timestamp": context.get("timestamp", datetime.now().isoformat()),
                "agent": self.agent.agent_name
            }
            
            await db.insert(
                text=design,
                area=memory.Memory.Area.RESEARCH,
                metadata=metadata
            )
            
            PrintStyle(font_color="#27AE60").print(f"Experiment design saved to memory")
            
        except Exception as e:
            handle_error(e)
            PrintStyle(font_color="#E74C3C").print(f"Failed to save experiment design: {str(e)}")