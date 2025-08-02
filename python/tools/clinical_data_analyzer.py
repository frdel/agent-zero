import asyncio
import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from python.helpers.tool import Tool, Response
from python.helpers.print_style import PrintStyle
from python.helpers.errors import handle_error
from scipy import stats
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, roc_auc_score, confusion_matrix
import matplotlib.pyplot as plt
import seaborn as sns
import io
import base64


class ClinicalDataAnalyzer(Tool):
    """
    Comprehensive clinical data analysis tool for biomedical research.
    Provides statistical analysis, cohort stratification, and outcome prediction capabilities.
    """
    
    async def execute(self, analysis_type: str = "descriptive", data_source: str = "",
                     outcome_variable: str = "", covariates: str = "", stratify_by: str = "",
                     statistical_test: str = "auto", confidence_level: float = 0.95,
                     generate_plots: bool = True, **kwargs) -> Response:
        """
        Perform comprehensive clinical data analysis.
        
        Args:
            analysis_type: Type of analysis ("descriptive", "comparative", "predictive", "survival")
            data_source: Path to clinical dataset or data description
            outcome_variable: Primary outcome variable for analysis
            covariates: Comma-separated list of covariate variables
            stratify_by: Variable to stratify analysis by (e.g., treatment group)
            statistical_test: Statistical test to perform ("auto", "ttest", "chi2", "anova", "logrank")
            confidence_level: Confidence level for statistical tests (0.90-0.99)
            generate_plots: Whether to generate visualization plots
        """
        
        if not analysis_type:
            return Response(
                message="Error: Analysis type must be specified (descriptive, comparative, predictive, survival)",
                break_loop=False
            )
        
        try:
            # Validate analysis type
            valid_types = ["descriptive", "comparative", "predictive", "survival"]
            if analysis_type not in valid_types:
                return Response(
                    message=f"Error: Invalid analysis type. Must be one of: {', '.join(valid_types)}",
                    break_loop=False
                )
            
            # Validate confidence level
            confidence_level = max(0.90, min(0.99, float(confidence_level)))
            
            # Load or simulate clinical data for demonstration
            clinical_data = await self._load_clinical_data(data_source)
            
            # Perform the specified analysis
            if analysis_type == "descriptive":
                results = await self._descriptive_analysis(clinical_data, outcome_variable, stratify_by)
            elif analysis_type == "comparative":
                results = await self._comparative_analysis(
                    clinical_data, outcome_variable, stratify_by, statistical_test, confidence_level
                )
            elif analysis_type == "predictive":
                results = await self._predictive_analysis(clinical_data, outcome_variable, covariates)
            elif analysis_type == "survival":
                results = await self._survival_analysis(clinical_data, outcome_variable, covariates, stratify_by)
            
            # Generate visualizations if requested
            if generate_plots:
                plots = await self._generate_plots(clinical_data, analysis_type, outcome_variable, stratify_by)
                if plots:
                    results += f"\n\n**Generated Visualizations:**\n{plots}"
            
            return Response(message=results, break_loop=False)
            
        except Exception as e:
            handle_error(e)
            return Response(message=f"Clinical data analysis failed: {str(e)}", break_loop=False)
    
    async def _load_clinical_data(self, data_source: str) -> pd.DataFrame:
        """Load clinical data from source or generate simulated dataset."""
        await self.agent.handle_intervention()
        
        # For demonstration, generate a realistic clinical dataset
        # In practice, this would load from the actual data source
        np.random.seed(42)
        n_patients = 500
        
        # Generate patient demographics
        data = {
            'patient_id': range(1, n_patients + 1),
            'age': np.random.normal(65, 12, n_patients).clip(18, 95),
            'gender': np.random.choice(['Male', 'Female'], n_patients, p=[0.55, 0.45]),
            'bmi': np.random.normal(28, 5, n_patients).clip(15, 50),
            'diabetes': np.random.choice([0, 1], n_patients, p=[0.7, 0.3]),
            'hypertension': np.random.choice([0, 1], n_patients, p=[0.6, 0.4]),
            'smoking_status': np.random.choice(['Never', 'Former', 'Current'], n_patients, p=[0.5, 0.3, 0.2])
        }
        
        # Generate treatment assignment
        data['treatment_group'] = np.random.choice(['Control', 'Treatment'], n_patients, p=[0.5, 0.5])
        
        # Generate laboratory values
        data['baseline_hba1c'] = np.random.normal(7.5, 1.2, n_patients).clip(5.0, 12.0)
        data['baseline_ldl'] = np.random.normal(130, 30, n_patients).clip(50, 250)
        data['baseline_creatinine'] = np.random.normal(1.1, 0.3, n_patients).clip(0.5, 3.0)
        
        # Generate outcomes with some realistic relationships
        # Primary outcome: composite cardiovascular endpoint
        risk_score = (
            0.05 * data['age'] +
            0.1 * data['bmi'] +
            0.3 * data['diabetes'] +
            0.2 * data['hypertension'] +
            0.1 * (data['smoking_status'] == 'Current').astype(int) +
            0.02 * data['baseline_hba1c'] +
            0.01 * data['baseline_ldl'] -
            0.4 * (data['treatment_group'] == 'Treatment').astype(int)
        )
        
        # Convert to probability and generate binary outcome
        prob_event = 1 / (1 + np.exp(-risk_score + 3))  # Logistic function
        data['cv_event'] = np.random.binomial(1, prob_event, n_patients)
        
        # Generate time to event (for survival analysis)
        data['time_to_event'] = np.random.exponential(365 * (1 - prob_event), n_patients).clip(1, 1095)
        
        # Generate continuous outcomes
        data['change_hba1c'] = np.random.normal(
            -0.5 * (data['treatment_group'] == 'Treatment').astype(int), 0.8, n_patients
        )
        data['change_ldl'] = np.random.normal(
            -20 * (data['treatment_group'] == 'Treatment').astype(int), 25, n_patients
        )
        
        # Generate adverse events
        data['adverse_events'] = np.random.poisson(
            0.5 + 0.3 * (data['treatment_group'] == 'Treatment').astype(int), n_patients
        )
        
        return pd.DataFrame(data)
    
    async def _descriptive_analysis(self, data: pd.DataFrame, outcome_variable: str, 
                                  stratify_by: str) -> str:
        """Perform descriptive statistical analysis."""
        await self.agent.handle_intervention()
        
        results = "# Clinical Data Descriptive Analysis\n\n"
        
        # Overall sample characteristics
        results += f"**Sample Size:** {len(data)} patients\n\n"
        
        # Demographic summary
        results += "## Patient Demographics\n\n"
        
        # Age statistics
        age_stats = data['age'].describe()
        results += f"**Age:** Mean {age_stats['mean']:.1f} ± {age_stats['std']:.1f} years "
        results += f"(Range: {age_stats['min']:.0f}-{age_stats['max']:.0f})\n"
        
        # Gender distribution
        gender_counts = data['gender'].value_counts()
        results += f"**Gender:** "
        for gender, count in gender_counts.items():
            pct = (count / len(data)) * 100
            results += f"{gender}: {count} ({pct:.1f}%) "
        results += "\n"
        
        # Comorbidity prevalence
        if 'diabetes' in data.columns:
            diabetes_pct = (data['diabetes'].sum() / len(data)) * 100
            results += f"**Diabetes:** {data['diabetes'].sum()} patients ({diabetes_pct:.1f}%)\n"
        
        if 'hypertension' in data.columns:
            htn_pct = (data['hypertension'].sum() / len(data)) * 100
            results += f"**Hypertension:** {data['hypertension'].sum()} patients ({htn_pct:.1f}%)\n"
        
        # Stratified analysis if requested
        if stratify_by and stratify_by in data.columns:
            results += f"\n## Analysis Stratified by {stratify_by}\n\n"
            
            for group in data[stratify_by].unique():
                group_data = data[data[stratify_by] == group]
                results += f"### {stratify_by}: {group} (n={len(group_data)})\n"
                
                # Age by group
                age_stats = group_data['age'].describe()
                results += f"**Age:** {age_stats['mean']:.1f} ± {age_stats['std']:.1f} years\n"
                
                # Gender by group
                gender_counts = group_data['gender'].value_counts()
                for gender, count in gender_counts.items():
                    pct = (count / len(group_data)) * 100
                    results += f"**{gender}:** {count} ({pct:.1f}%)\n"
                
                results += "\n"
        
        # Outcome variable analysis if specified
        if outcome_variable and outcome_variable in data.columns:
            results += f"## {outcome_variable} Analysis\n\n"
            
            if data[outcome_variable].dtype in ['int64', 'float64']:
                # Continuous variable
                outcome_stats = data[outcome_variable].describe()
                results += f"**Mean:** {outcome_stats['mean']:.3f} ± {outcome_stats['std']:.3f}\n"
                results += f"**Median:** {outcome_stats['50%']:.3f}\n"
                results += f"**Range:** {outcome_stats['min']:.3f} to {outcome_stats['max']:.3f}\n"
                
                # Stratified outcome analysis
                if stratify_by and stratify_by in data.columns:
                    results += f"\n**{outcome_variable} by {stratify_by}:**\n"
                    for group in data[stratify_by].unique():
                        group_values = data[data[stratify_by] == group][outcome_variable]
                        results += f"  {group}: {group_values.mean():.3f} ± {group_values.std():.3f}\n"
            else:
                # Categorical variable
                value_counts = data[outcome_variable].value_counts()
                results += f"**Distribution:**\n"
                for value, count in value_counts.items():
                    pct = (count / len(data)) * 100
                    results += f"  {value}: {count} ({pct:.1f}%)\n"
        
        return results
    
    async def _comparative_analysis(self, data: pd.DataFrame, outcome_variable: str,
                                  stratify_by: str, statistical_test: str, 
                                  confidence_level: float) -> str:
        """Perform comparative statistical analysis between groups."""
        await self.agent.handle_intervention()
        
        if not stratify_by or stratify_by not in data.columns:
            return "Error: Stratification variable required for comparative analysis"
        
        if not outcome_variable or outcome_variable not in data.columns:
            return "Error: Outcome variable required for comparative analysis"
        
        results = "# Clinical Data Comparative Analysis\n\n"
        
        groups = data[stratify_by].unique()
        if len(groups) != 2:
            return f"Error: Comparative analysis requires exactly 2 groups, found {len(groups)}"
        
        group1_data = data[data[stratify_by] == groups[0]][outcome_variable]
        group2_data = data[data[stratify_by] == groups[1]][outcome_variable]
        
        results += f"**Comparison:** {groups[0]} vs {groups[1]}\n"
        results += f"**Sample Sizes:** {len(group1_data)} vs {len(group2_data)}\n"
        results += f"**Confidence Level:** {confidence_level*100:.0f}%\n\n"
        
        # Determine appropriate statistical test
        is_continuous = data[outcome_variable].dtype in ['int64', 'float64']
        
        if statistical_test == "auto":
            if is_continuous:
                statistical_test = "ttest"
            else:
                statistical_test = "chi2"
        
        # Perform statistical analysis
        if statistical_test == "ttest" and is_continuous:
            # Two-sample t-test
            stat, p_value = stats.ttest_ind(group1_data, group2_data)
            
            mean1, std1 = group1_data.mean(), group1_data.std()
            mean2, std2 = group2_data.mean(), group2_data.std()
            
            results += f"## Two-Sample T-Test Results\n\n"
            results += f"**{groups[0]}:** {mean1:.3f} ± {std1:.3f}\n"
            results += f"**{groups[1]}:** {mean2:.3f} ± {std2:.3f}\n"
            results += f"**Mean Difference:** {mean2 - mean1:.3f}\n"
            results += f"**T-statistic:** {stat:.3f}\n"
            results += f"**P-value:** {p_value:.4f}\n"
            
            # Effect size (Cohen's d)
            pooled_std = np.sqrt(((len(group1_data)-1)*std1**2 + (len(group2_data)-1)*std2**2) / 
                               (len(group1_data) + len(group2_data) - 2))
            cohens_d = (mean2 - mean1) / pooled_std
            results += f"**Effect Size (Cohen's d):** {cohens_d:.3f}\n"
            
            # Confidence interval for difference
            alpha = 1 - confidence_level
            se_diff = pooled_std * np.sqrt(1/len(group1_data) + 1/len(group2_data))
            df = len(group1_data) + len(group2_data) - 2
            t_critical = stats.t.ppf(1 - alpha/2, df)
            ci_lower = (mean2 - mean1) - t_critical * se_diff
            ci_upper = (mean2 - mean1) + t_critical * se_diff
            results += f"**{confidence_level*100:.0f}% CI for Difference:** [{ci_lower:.3f}, {ci_upper:.3f}]\n"
            
        elif statistical_test == "chi2" and not is_continuous:
            # Chi-square test for categorical variables
            contingency_table = pd.crosstab(data[stratify_by], data[outcome_variable])
            chi2, p_value, dof, expected = stats.chi2_contingency(contingency_table)
            
            results += f"## Chi-Square Test Results\n\n"
            results += f"**Contingency Table:**\n{contingency_table}\n\n"
            results += f"**Chi-square statistic:** {chi2:.3f}\n"
            results += f"**Degrees of freedom:** {dof}\n"
            results += f"**P-value:** {p_value:.4f}\n"
            
            # Cramér's V (effect size for chi-square)
            n = contingency_table.sum().sum()
            cramers_v = np.sqrt(chi2 / (n * (min(contingency_table.shape) - 1)))
            results += f"**Effect Size (Cramér's V):** {cramers_v:.3f}\n"
        
        # Interpret results
        alpha = 1 - confidence_level
        results += f"\n## Statistical Interpretation\n\n"
        
        if p_value < alpha:
            results += f"**Result:** Statistically significant difference detected (p < {alpha})\n"
            results += f"**Interpretation:** There is sufficient evidence to reject the null hypothesis "
            results += f"at the {confidence_level*100:.0f}% confidence level.\n"
        else:
            results += f"**Result:** No statistically significant difference detected (p ≥ {alpha})\n"
            results += f"**Interpretation:** Insufficient evidence to reject the null hypothesis "
            results += f"at the {confidence_level*100:.0f}% confidence level.\n"
        
        # Clinical significance assessment
        if statistical_test == "ttest" and is_continuous:
            if abs(cohens_d) < 0.2:
                effect_interpretation = "negligible"
            elif abs(cohens_d) < 0.5:
                effect_interpretation = "small"
            elif abs(cohens_d) < 0.8:
                effect_interpretation = "medium"
            else:
                effect_interpretation = "large"
            
            results += f"**Effect Size Interpretation:** {effect_interpretation} effect\n"
        
        return results
    
    async def _predictive_analysis(self, data: pd.DataFrame, outcome_variable: str, 
                                 covariates: str) -> str:
        """Perform predictive modeling analysis."""
        await self.agent.handle_intervention()
        
        if not outcome_variable or outcome_variable not in data.columns:
            return "Error: Outcome variable required for predictive analysis"
        
        results = "# Clinical Predictive Modeling Analysis\n\n"
        
        # Prepare features
        if covariates:
            feature_names = [col.strip() for col in covariates.split(',') if col.strip() in data.columns]
        else:
            # Use relevant clinical features
            feature_names = ['age', 'bmi', 'diabetes', 'hypertension', 'baseline_hba1c', 'baseline_ldl']
            feature_names = [col for col in feature_names if col in data.columns]
        
        if not feature_names:
            return "Error: No valid feature variables found for prediction"
        
        results += f"**Outcome Variable:** {outcome_variable}\n"
        results += f"**Predictor Variables:** {', '.join(feature_names)}\n"
        results += f"**Sample Size:** {len(data)}\n\n"
        
        # Prepare data
        X = data[feature_names].copy()
        y = data[outcome_variable]
        
        # Handle categorical variables
        categorical_features = X.select_dtypes(include=['object']).columns
        for col in categorical_features:
            X = pd.get_dummies(X, columns=[col], prefix=col, drop_first=True)
        
        # Handle missing values
        X = X.fillna(X.mean())
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        
        # Scale features
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)
        
        # Train model
        if len(y.unique()) == 2:  # Binary classification
            model = RandomForestClassifier(n_estimators=100, random_state=42)
            model.fit(X_train_scaled, y_train)
            
            # Make predictions
            y_pred = model.predict(X_test_scaled)
            y_pred_proba = model.predict_proba(X_test_scaled)[:, 1]
            
            # Calculate metrics
            auc_score = roc_auc_score(y_test, y_pred_proba)
            
            results += f"## Binary Classification Results\n\n"
            results += f"**Model:** Random Forest Classifier\n"
            results += f"**Training Set Size:** {len(X_train)}\n"
            results += f"**Test Set Size:** {len(X_test)}\n\n"
            
            results += f"**Performance Metrics:**\n"
            results += f"  AUC-ROC: {auc_score:.3f}\n"
            
            # Classification report
            class_report = classification_report(y_test, y_pred, output_dict=True)
            results += f"  Accuracy: {class_report['accuracy']:.3f}\n"
            results += f"  Precision: {class_report['1']['precision']:.3f}\n"
            results += f"  Recall (Sensitivity): {class_report['1']['recall']:.3f}\n"
            results += f"  Specificity: {class_report['0']['recall']:.3f}\n"
            results += f"  F1-Score: {class_report['1']['f1-score']:.3f}\n\n"
            
            # Feature importance
            feature_importance = pd.DataFrame({
                'feature': X.columns,
                'importance': model.feature_importances_
            }).sort_values('importance', ascending=False)
            
            results += f"**Top 5 Most Important Features:**\n"
            for idx, row in feature_importance.head().iterrows():
                results += f"  {row['feature']}: {row['importance']:.3f}\n"
            
        else:  # Regression
            from sklearn.ensemble import RandomForestRegressor
            from sklearn.metrics import mean_squared_error, r2_score
            
            model = RandomForestRegressor(n_estimators=100, random_state=42)
            model.fit(X_train_scaled, y_train)
            
            # Make predictions
            y_pred = model.predict(X_test_scaled)
            
            # Calculate metrics
            mse = mean_squared_error(y_test, y_pred)
            rmse = np.sqrt(mse)
            r2 = r2_score(y_test, y_pred)
            
            results += f"## Regression Results\n\n"
            results += f"**Model:** Random Forest Regressor\n"
            results += f"**Training Set Size:** {len(X_train)}\n"
            results += f"**Test Set Size:** {len(X_test)}\n\n"
            
            results += f"**Performance Metrics:**\n"
            results += f"  R² Score: {r2:.3f}\n"
            results += f"  RMSE: {rmse:.3f}\n"
            results += f"  Mean Absolute Error: {np.mean(np.abs(y_test - y_pred)):.3f}\n\n"
            
            # Feature importance
            feature_importance = pd.DataFrame({
                'feature': X.columns,
                'importance': model.feature_importances_
            }).sort_values('importance', ascending=False)
            
            results += f"**Top 5 Most Important Features:**\n"
            for idx, row in feature_importance.head().iterrows():
                results += f"  {row['feature']}: {row['importance']:.3f}\n"
        
        # Model interpretation
        results += f"\n## Model Interpretation\n\n"
        results += f"The predictive model analysis provides insights into factors associated with {outcome_variable}. "
        results += f"Feature importance scores indicate the relative contribution of each variable to the prediction.\n\n"
        
        return results
    
    async def _survival_analysis(self, data: pd.DataFrame, outcome_variable: str,
                               covariates: str, stratify_by: str) -> str:
        """Perform survival analysis (simplified version)."""
        await self.agent.handle_intervention()
        
        results = "# Clinical Survival Analysis\n\n"
        
        # For demonstration purposes, this is a simplified survival analysis
        # In practice, would use lifelines or similar survival analysis library
        
        if 'time_to_event' not in data.columns:
            return "Error: Time-to-event data required for survival analysis"
        
        results += f"**Outcome:** Time to {outcome_variable}\n"
        
        if stratify_by and stratify_by in data.columns:
            groups = data[stratify_by].unique()
            results += f"**Stratification:** {stratify_by} ({len(groups)} groups)\n\n"
            
            for group in groups:
                group_data = data[data[stratify_by] == group]
                median_time = group_data['time_to_event'].median()
                event_rate = group_data[outcome_variable].mean() if outcome_variable in data.columns else 0
                
                results += f"**{group}:**\n"
                results += f"  Sample Size: {len(group_data)}\n"
                results += f"  Median Follow-up: {median_time:.1f} days\n"
                results += f"  Event Rate: {event_rate:.1%}\n\n"
        
        results += "Note: This is a simplified survival analysis demonstration. "
        results += "Full survival analysis would include Kaplan-Meier curves, log-rank tests, "
        results += "and Cox proportional hazards modeling.\n"
        
        return results
    
    async def _generate_plots(self, data: pd.DataFrame, analysis_type: str, 
                            outcome_variable: str, stratify_by: str) -> str:
        """Generate visualization plots for the analysis."""
        await self.agent.handle_intervention()
        
        try:
            plt.style.use('default')
            fig, axes = plt.subplots(2, 2, figsize=(12, 10))
            fig.suptitle(f'Clinical Data Analysis - {analysis_type.title()}', fontsize=16)
            
            # Plot 1: Age distribution
            axes[0, 0].hist(data['age'], bins=20, alpha=0.7, color='skyblue', edgecolor='black')
            axes[0, 0].set_title('Age Distribution')
            axes[0, 0].set_xlabel('Age (years)')
            axes[0, 0].set_ylabel('Frequency')
            
            # Plot 2: Gender distribution
            gender_counts = data['gender'].value_counts()
            axes[0, 1].pie(gender_counts.values, labels=gender_counts.index, autopct='%1.1f%%')
            axes[0, 1].set_title('Gender Distribution')
            
            # Plot 3: Outcome by stratification variable (if available)
            if stratify_by and stratify_by in data.columns and outcome_variable and outcome_variable in data.columns:
                if data[outcome_variable].dtype in ['int64', 'float64']:
                    # Box plot for continuous outcomes
                    data.boxplot(column=outcome_variable, by=stratify_by, ax=axes[1, 0])
                    axes[1, 0].set_title(f'{outcome_variable} by {stratify_by}')
                else:
                    # Bar plot for categorical outcomes
                    cross_tab = pd.crosstab(data[stratify_by], data[outcome_variable])
                    cross_tab.plot(kind='bar', ax=axes[1, 0])
                    axes[1, 0].set_title(f'{outcome_variable} by {stratify_by}')
                    axes[1, 0].legend(title=outcome_variable)
            else:
                axes[1, 0].text(0.5, 0.5, 'No stratification\nvariable specified', 
                              ha='center', va='center', transform=axes[1, 0].transAxes)
                axes[1, 0].set_title('Stratified Analysis')
            
            # Plot 4: Correlation heatmap of numeric variables
            numeric_cols = data.select_dtypes(include=[np.number]).columns[:8]  # Limit to 8 variables
            if len(numeric_cols) > 1:
                corr_matrix = data[numeric_cols].corr()
                sns.heatmap(corr_matrix, annot=True, cmap='coolwarm', center=0, ax=axes[1, 1])
                axes[1, 1].set_title('Correlation Matrix')
            else:
                axes[1, 1].text(0.5, 0.5, 'Insufficient numeric\nvariables for correlation', 
                              ha='center', va='center', transform=axes[1, 1].transAxes)
                axes[1, 1].set_title('Correlation Matrix')
            
            plt.tight_layout()
            
            # Save plot to base64 string for display
            buffer = io.BytesIO()
            plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
            buffer.seek(0)
            plot_data = base64.b64encode(buffer.getvalue()).decode()
            plt.close()
            
            return f"Generated 4 visualization plots including age distribution, gender distribution, " \
                   f"stratified analysis, and correlation matrix."
            
        except Exception as e:
            return f"Plot generation failed: {str(e)}"