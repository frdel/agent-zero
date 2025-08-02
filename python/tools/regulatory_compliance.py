import asyncio
from typing import Dict, List, Any, Optional, Tuple
from python.helpers.tool import Tool, Response
from python.helpers.print_style import PrintStyle
from python.helpers.errors import handle_error
from datetime import datetime, timedelta
import json


class RegulatoryCompliance(Tool):
    """
    Comprehensive regulatory compliance checker for biomedical research and drug development.
    Provides guidance on FDA, EMA, ICH, and other regulatory requirements.
    """
    
    async def execute(self, regulation_type: str = "fda", product_type: str = "drug",
                     development_phase: str = "preclinical", indication: str = "",
                     jurisdiction: str = "usa", compliance_check: str = "comprehensive",
                     submission_type: str = "ind", **kwargs) -> Response:
        """
        Perform regulatory compliance analysis and guidance.
        
        Args:
            regulation_type: Regulatory authority ("fda", "ema", "ich", "pmda", "hc")
            product_type: Product type ("drug", "biologic", "device", "diagnostic", "vaccine")
            development_phase: Development phase ("preclinical", "phase1", "phase2", "phase3", "nda")
            indication: Therapeutic indication or disease area
            jurisdiction: Regulatory jurisdiction ("usa", "eu", "japan", "canada", "global")
            compliance_check: Type of check ("comprehensive", "submission", "gmp", "clinical")
            submission_type: Submission type ("ind", "nda", "bla", "cta", "ma")
        """
        
        try:
            # Validate inputs
            valid_regulation_types = ["fda", "ema", "ich", "pmda", "hc"]
            valid_product_types = ["drug", "biologic", "device", "diagnostic", "vaccine"]
            valid_phases = ["preclinical", "phase1", "phase2", "phase3", "nda", "post_market"]
            valid_jurisdictions = ["usa", "eu", "japan", "canada", "global"]
            
            if regulation_type not in valid_regulation_types:
                return Response(
                    message=f"Error: Invalid regulation type. Must be one of: {', '.join(valid_regulation_types)}",
                    break_loop=False
                )
            
            if product_type not in valid_product_types:
                return Response(
                    message=f"Error: Invalid product type. Must be one of: {', '.join(valid_product_types)}",
                    break_loop=False
                )
            
            # Perform compliance analysis
            compliance_results = await self._analyze_regulatory_compliance(
                regulation_type, product_type, development_phase, indication,
                jurisdiction, compliance_check, submission_type
            )
            
            return Response(message=compliance_results, break_loop=False)
            
        except Exception as e:
            handle_error(e)
            return Response(message=f"Regulatory compliance analysis failed: {str(e)}", break_loop=False)
    
    async def _analyze_regulatory_compliance(self, regulation_type: str, product_type: str,
                                           development_phase: str, indication: str,
                                           jurisdiction: str, compliance_check: str,
                                           submission_type: str) -> str:
        """Perform comprehensive regulatory compliance analysis."""
        await self.agent.handle_intervention()
        
        results = "# Regulatory Compliance Analysis Report\n\n"
        
        # Header information
        results += "## Compliance Assessment Overview\n\n"
        results += f"**Regulatory Authority**: {regulation_type.upper()}\n"
        results += f"**Product Type**: {product_type.title()}\n"
        results += f"**Development Phase**: {development_phase.title()}\n"
        results += f"**Jurisdiction**: {jurisdiction.upper()}\n"
        results += f"**Indication**: {indication if indication else 'General'}\n"
        results += f"**Assessment Date**: {datetime.now().strftime('%Y-%m-%d')}\n"
        results += f"**Compliance Check Type**: {compliance_check.title()}\n\n"
        
        # Get regulatory framework
        regulatory_framework = await self._get_regulatory_framework(
            regulation_type, product_type, jurisdiction
        )
        results += regulatory_framework
        
        # Phase-specific requirements
        phase_requirements = await self._get_phase_requirements(
            regulation_type, product_type, development_phase
        )
        results += phase_requirements
        
        # Submission requirements
        submission_requirements = await self._get_submission_requirements(
            regulation_type, product_type, submission_type, development_phase
        )
        results += submission_requirements
        
        # Compliance checklist
        compliance_checklist = await self._generate_compliance_checklist(
            regulation_type, product_type, development_phase, compliance_check
        )
        results += compliance_checklist
        
        # Timeline and milestones
        timeline = await self._generate_regulatory_timeline(
            regulation_type, product_type, development_phase
        )
        results += timeline
        
        # Risk assessment
        risk_assessment = await self._assess_regulatory_risks(
            regulation_type, product_type, development_phase, indication
        )
        results += risk_assessment
        
        # Recommendations
        recommendations = await self._generate_recommendations(
            regulation_type, product_type, development_phase, jurisdiction
        )
        results += recommendations
        
        return results
    
    async def _get_regulatory_framework(self, regulation_type: str, product_type: str,
                                      jurisdiction: str) -> str:
        """Get applicable regulatory framework."""
        await self.agent.handle_intervention()
        
        results = "## Applicable Regulatory Framework\n\n"
        
        if regulation_type == "fda":
            results += "### FDA Regulatory Framework\n\n"
            
            if product_type == "drug":
                results += "**Applicable Regulations**:\n"
                results += "- 21 CFR Part 312: Investigational New Drug Application\n"
                results += "- 21 CFR Part 314: Applications for FDA Approval to Market a New Drug\n"
                results += "- 21 CFR Part 211: Current Good Manufacturing Practice for Finished Pharmaceuticals\n"
                results += "- ICH Guidelines: E6 (GCP), E2A (Pharmacovigilance), Q8-Q12 (Quality)\n\n"
                
                results += "**FDA Guidance Documents**:\n"
                results += "- IND Submissions: Content and Format\n"
                results += "- Clinical Trial Design and Analysis\n"
                results += "- Nonclinical Safety Studies for Drug Development\n"
                results += "- Chemistry, Manufacturing, and Controls (CMC)\n\n"
            
            elif product_type == "biologic":
                results += "**Applicable Regulations**:\n"
                results += "- 21 CFR Part 600: Biological Products\n"
                results += "- 21 CFR Part 601: Licensing\n"
                results += "- 21 CFR Part 610: General Biological Product Standards\n"
                results += "- ICH Q5 Guidelines: Biotechnological Products\n\n"
            
            elif product_type == "device":
                results += "**Applicable Regulations**:\n"
                results += "- 21 CFR Part 820: Quality System Regulation\n"
                results += "- 21 CFR Part 807: Establishment Registration and Device Listing\n"
                results += "- 21 CFR Part 814: Premarket Approval\n"
                results += "- ISO 13485: Medical Device Quality Management\n\n"
        
        elif regulation_type == "ema":
            results += "### EMA Regulatory Framework\n\n"
            
            results += "**Applicable Regulations**:\n"
            results += "- Regulation (EC) No 726/2004: Centralized Authorization Procedure\n"
            results += "- Directive 2001/83/EC: Community Code on Medicinal Products\n"
            results += "- Directive 2001/20/EC: Clinical Trials Directive\n"
            results += "- ICH Guidelines (adopted by EMA)\n\n"
            
            results += "**EMA Guidelines**:\n"
            results += "- Common Technical Document (CTD) Format\n"
            results += "- Clinical Trial Regulation (EU) No 536/2014\n"
            results += "- Good Manufacturing Practice (GMP)\n"
            results += "- Pharmacovigilance Guidelines\n\n"
        
        elif regulation_type == "ich":
            results += "### ICH Guidelines Framework\n\n"
            
            results += "**Quality Guidelines (Q)**:\n"
            results += "- Q1: Stability Testing\n"
            results += "- Q2: Analytical Validation\n"
            results += "- Q3: Impurities\n"
            results += "- Q8-Q12: Pharmaceutical Development and Quality Systems\n\n"
            
            results += "**Safety Guidelines (S)**:\n"
            results += "- S1: Carcinogenicity Studies\n"
            results += "- S2: Genotoxicity Studies\n"
            results += "- S3: Toxicokinetics and Pharmacokinetics\n"
            results += "- S4-S11: Specialized Safety Studies\n\n"
            
            results += "**Efficacy Guidelines (E)**:\n"
            results += "- E1: Extent of Population Exposure\n"
            results += "- E2: Pharmacovigilance\n"
            results += "- E3: Clinical Study Reports\n"
            results += "- E6: Good Clinical Practice\n"
            results += "- E8: General Considerations for Clinical Trials\n"
            results += "- E9: Statistical Principles\n\n"
        
        return results
    
    async def _get_phase_requirements(self, regulation_type: str, product_type: str,
                                    development_phase: str) -> str:
        """Get phase-specific regulatory requirements."""
        await self.agent.handle_intervention()
        
        results = f"## {development_phase.title()} Phase Requirements\n\n"
        
        if development_phase == "preclinical":
            results += "### Preclinical Development Requirements\n\n"
            
            results += "**Nonclinical Safety Studies**:\n"
            results += "- Pharmacology Studies (Primary and Safety)\n"
            results += "- Toxicokinetics and ADME Studies\n"
            results += "- General Toxicity Studies (Single and Repeat Dose)\n"
            results += "- Genotoxicity Studies (Ames, Micronucleus, etc.)\n"
            results += "- Safety Pharmacology (CNS, CV, Respiratory)\n\n"
            
            results += "**Chemistry, Manufacturing, and Controls (CMC)**:\n"
            results += "- Drug Substance Information (Structure, Synthesis)\n"
            results += "- Drug Product Information (Composition, Manufacturing)\n"
            results += "- Analytical Methods Development and Validation\n"
            results += "- Stability Studies (ICH Q1A guidelines)\n"
            results += "- Quality Control and Specifications\n\n"
            
            results += "**Regulatory Documentation**:\n"
            results += "- Investigator's Brochure\n"
            results += "- Clinical Protocol Development\n"
            results += "- IND-Enabling Package Preparation\n"
            results += "- Risk Assessment and Management\n\n"
        
        elif development_phase == "phase1":
            results += "### Phase 1 Clinical Development Requirements\n\n"
            
            results += "**Clinical Trial Requirements**:\n"
            results += "- IND Submission and FDA Approval\n"
            results += "- IRB/Ethics Committee Approval\n"
            results += "- Informed Consent Process\n"
            results += "- Good Clinical Practice (GCP) Compliance\n"
            results += "- Clinical Site Qualification\n\n"
            
            results += "**Safety Monitoring**:\n"
            results += "- Data Safety Monitoring Board (DSMB)\n"
            results += "- Adverse Event Reporting (7-day and 15-day reports)\n"
            results += "- Safety Run-in and Dose Escalation Protocols\n"
            results += "- Stopping Rules and Criteria\n\n"
            
            results += "**Data Management**:\n"
            results += "- Clinical Data Management Plan\n"
            results += "- Electronic Data Capture (EDC) Systems\n"
            results += "- Source Data Verification\n"
            results += "- Data Quality Assurance\n\n"
        
        elif development_phase == "phase2":
            results += "### Phase 2 Clinical Development Requirements\n\n"
            
            results += "**Efficacy Assessment**:\n"
            results += "- Primary and Secondary Endpoint Definition\n"
            results += "- Statistical Analysis Plan\n"
            results += "- Sample Size Calculations and Power Analysis\n"
            results += "- Interim Analysis Planning\n\n"
            
            results += "**Regulatory Interactions**:\n"
            results += "- End-of-Phase 2 Meeting with FDA\n"
            results += "- Special Protocol Assessment (SPA) Consideration\n"
            results += "- Orphan Drug Designation (if applicable)\n"
            results += "- Fast Track Designation (if applicable)\n\n"
        
        elif development_phase == "phase3":
            results += "### Phase 3 Clinical Development Requirements\n\n"
            
            results += "**Pivotal Trial Design**:\n"
            results += "- Adequate and Well-Controlled Studies\n"
            results += "- Multi-center, Randomized Design\n"
            results += "- Primary Endpoint Clinically Meaningful\n"
            results += "- Intent-to-Treat and Per-Protocol Analyses\n\n"
            
            results += "**Registration Preparation**:\n"
            results += "- NDA/BLA Module Compilation\n"
            results += "- Risk Evaluation and Mitigation Strategy (REMS)\n"
            results += "- Labeling Negotiations\n"
            results += "- Post-Marketing Study Commitments\n\n"
        
        elif development_phase == "nda":
            results += "### NDA/BLA Submission Requirements\n\n"
            
            results += "**Common Technical Document (CTD) Modules**:\n"
            results += "- Module 1: Administrative Information and Prescribing Information\n"
            results += "- Module 2: Quality Overall Summary (QOS), Nonclinical and Clinical Overviews\n"
            results += "- Module 3: Quality (Chemistry, Manufacturing, and Controls)\n"
            results += "- Module 4: Nonclinical Study Reports\n"
            results += "- Module 5: Clinical Study Reports\n\n"
            
            results += "**Review Timeline**:\n"
            results += "- Standard Review: 10-12 months\n"
            results += "- Priority Review: 6-8 months\n"
            results += "- Breakthrough Therapy: Expedited review\n"
            results += "- Accelerated Approval: Based on surrogate endpoints\n\n"
        
        return results
    
    async def _get_submission_requirements(self, regulation_type: str, product_type: str,
                                         submission_type: str, development_phase: str) -> str:
        """Get specific submission requirements."""
        await self.agent.handle_intervention()
        
        results = f"## {submission_type.upper()} Submission Requirements\n\n"
        
        if submission_type.lower() == "ind":
            results += "### Investigational New Drug (IND) Application\n\n"
            
            results += "**Required Sections**:\n"
            results += "1. **Cover Sheet (Form FDA 1571)**\n"
            results += "   - Product name and indication\n"
            results += "   - Sponsor information\n"
            results += "   - Clinical investigator information\n\n"
            
            results += "2. **Table of Contents**\n\n"
            
            results += "3. **Introductory Statement and General Investigational Plan**\n"
            results += "   - Name and structure of drug\n"
            results += "   - Objectives and planned duration\n"
            results += "   - General approach to studying the drug\n\n"
            
            results += "4. **Investigator's Brochure**\n"
            results += "   - Comprehensive document for investigators\n"
            results += "   - Pharmacology, toxicology, and clinical data\n"
            results += "   - Instructions for drug handling\n\n"
            
            results += "5. **Clinical Protocols and Investigator Information**\n"
            results += "   - Detailed protocol for each study\n"
            results += "   - Investigator qualifications (CV, Form FDA 1572)\n"
            results += "   - Clinical site information\n\n"
            
            results += "6. **Chemistry, Manufacturing, and Controls (CMC)**\n"
            results += "   - Drug substance and drug product information\n"
            results += "   - Manufacturing information\n"
            results += "   - Analytical methods and specifications\n"
            results += "   - Labeling and stability data\n\n"
            
            results += "7. **Pharmacology and Toxicology**\n"
            results += "   - Nonclinical study reports\n"
            results += "   - Safety assessment\n"
            results += "   - Justification for human exposure\n\n"
        
        elif submission_type.lower() == "nda":
            results += "### New Drug Application (NDA)\n\n"
            
            results += "**CTD Module Structure**:\n\n"
            
            results += "**Module 1: Administrative and Prescribing Information**\n"
            results += "- Form FDA 356h (Application Form)\n"
            results += "- Proposed Labeling\n"
            results += "- Risk Evaluation and Mitigation Strategy (REMS)\n"
            results += "- Financial Certification/Disclosure\n\n"
            
            results += "**Module 2: Summaries**\n"
            results += "- Quality Overall Summary (QOS)\n"
            results += "- Nonclinical Overview and Written Summaries\n"
            results += "- Clinical Overview and Written Summaries\n\n"
            
            results += "**Module 3: Quality**\n"
            results += "- S: Drug Substance\n"
            results += "- P: Drug Product\n"
            results += "- A: Appendices (facilities, certificates)\n"
            results += "- R: Regional Information\n\n"
            
            results += "**Module 4: Nonclinical Study Reports**\n"
            results += "- Pharmacology Studies\n"
            results += "- Pharmacokinetics and ADME\n"
            results += "- Toxicology Studies\n\n"
            
            results += "**Module 5: Clinical Study Reports**\n"
            results += "- Clinical Pharmacology Studies\n"
            results += "- Efficacy and Safety Studies\n"
            results += "- Post-marketing Experience\n\n"
        
        elif submission_type.lower() == "bla":
            results += "### Biologics License Application (BLA)\n\n"
            
            results += "**Additional BLA-Specific Requirements**:\n"
            results += "- Establishment License Application (ELA) information\n"
            results += "- Product License Application (PLA) information\n"
            results += "- Environmental Assessment\n"
            results += "- Lot Release Protocols\n"
            results += "- Comparability Protocols (if applicable)\n\n"
            
            results += "**Biologic-Specific Quality Requirements**:\n"
            results += "- Cell line/seed lot information\n"
            results += "- Manufacturing process validation\n"
            results += "- Characterization studies\n"
            results += "- Viral safety evaluation\n"
            results += "- Container/closure system\n\n"
        
        return results
    
    async def _generate_compliance_checklist(self, regulation_type: str, product_type: str,
                                           development_phase: str, compliance_check: str) -> str:
        """Generate comprehensive compliance checklist."""
        await self.agent.handle_intervention()
        
        results = "## Regulatory Compliance Checklist\n\n"
        
        # Pre-submission checklist
        results += "### Pre-Submission Checklist\n\n"
        checklist_items = [
            ("Regulatory strategy finalized", "High"),
            ("Development plan aligned with regulatory requirements", "High"),
            ("Pre-submission meetings scheduled (if needed)", "Medium"),
            ("Quality system implementation", "High"),
            ("GMP compliance assessment", "High"),
            ("Clinical protocol finalization", "High"),
            ("Investigator's brochure updated", "High"),
            ("Safety database current", "High")
        ]
        
        for item, priority in checklist_items:
            priority_icon = "🔴" if priority == "High" else "🟡" if priority == "Medium" else "🟢"
            results += f"- [ ] {priority_icon} {item}\n"
        
        results += "\n### Documentation Checklist\n\n"
        doc_items = [
            ("All study reports finalized and QC'd", "High"),
            ("Statistical analysis plans complete", "High"),
            ("Case report forms finalized", "Medium"),
            ("Informed consent forms approved", "High"),
            ("Regulatory submission documents drafted", "High"),
            ("CMC documentation complete", "High"),
            ("Labeling discussions initiated", "Medium"),
            ("Risk management plan developed", "High")
        ]
        
        for item, priority in doc_items:
            priority_icon = "🔴" if priority == "High" else "🟡" if priority == "Medium" else "🟢"
            results += f"- [ ] {priority_icon} {item}\n"
        
        results += "\n### Quality Assurance Checklist\n\n"
        qa_items = [
            ("GCP compliance verified", "High"),
            ("Data integrity measures implemented", "High"),
            ("Audit trail maintenance", "High"),
            ("Training records current", "Medium"),
            ("SOPs updated and approved", "Medium"),
            ("Change control procedures active", "Medium"),
            ("Deviation handling process", "Medium"),
            ("CAPA system functional", "High")
        ]
        
        for item, priority in qa_items:
            priority_icon = "🔴" if priority == "High" else "🟡" if priority == "Medium" else "🟢"
            results += f"- [ ] {priority_icon} {item}\n"
        
        return results
    
    async def _generate_regulatory_timeline(self, regulation_type: str, product_type: str,
                                          development_phase: str) -> str:
        """Generate regulatory timeline and milestones."""
        await self.agent.handle_intervention()
        
        results = "## Regulatory Timeline and Milestones\n\n"
        
        # Current date
        current_date = datetime.now()
        
        results += "### Key Regulatory Milestones\n\n"
        
        if development_phase == "preclinical":
            milestones = [
                ("IND-enabling studies completion", 6),
                ("CMC package finalization", 4),
                ("IND submission preparation", 2),
                ("IND submission", 1),
                ("FDA response (30 days)", 0)
            ]
        elif development_phase == "phase1":
            milestones = [
                ("Phase 1 study completion", 12),
                ("Safety database lock", 10),
                ("End-of-Phase 1 meeting request", 9),
                ("Phase 2 protocol development", 6),
                ("Phase 2 IND amendment", 3)
            ]
        elif development_phase == "phase2":
            milestones = [
                ("Phase 2 study completion", 18),
                ("End-of-Phase 2 meeting", 15),
                ("Phase 3 protocol agreement", 12),
                ("SPA submission (if applicable)", 10),
                ("Phase 3 initiation", 6)
            ]
        elif development_phase == "phase3":
            milestones = [
                ("Pivotal studies completion", 24),
                ("Database lock and analysis", 21),
                ("Pre-NDA meeting", 18),
                ("NDA submission preparation", 15),
                ("NDA submission", 12),
                ("FDA review completion", 6)
            ]
        else:
            milestones = [
                ("Submission preparation", 6),
                ("Regulatory submission", 3),
                ("Agency review", 0)
            ]
        
        results += "| Milestone | Timeline | Target Date |\n"
        results += "|-----------|----------|-------------|\n"
        
        for milestone, months_offset in milestones:
            target_date = current_date + timedelta(days=30 * months_offset)
            results += f"| {milestone} | {months_offset} months | {target_date.strftime('%Y-%m-%d')} |\n"
        
        results += "\n### Critical Path Activities\n\n"
        results += "**High Priority**:\n"
        results += "- Complete all required nonclinical studies\n"
        results += "- Finalize manufacturing and quality documentation\n"
        results += "- Prepare comprehensive clinical development plan\n\n"
        
        results += "**Medium Priority**:\n"
        results += "- Establish regulatory communication strategy\n"
        results += "- Develop risk management framework\n"
        results += "- Plan post-marketing commitments\n\n"
        
        return results
    
    async def _assess_regulatory_risks(self, regulation_type: str, product_type: str,
                                     development_phase: str, indication: str) -> str:
        """Assess regulatory risks and mitigation strategies."""
        await self.agent.handle_intervention()
        
        results = "## Regulatory Risk Assessment\n\n"
        
        # Identify potential risks
        risks = []
        
        # Common risks based on phase
        if development_phase == "preclinical":
            risks.extend([
                {
                    "risk": "Inadequate nonclinical safety package",
                    "probability": "Medium",
                    "impact": "High",
                    "mitigation": "Comprehensive toxicology study design with regulatory consultation"
                },
                {
                    "risk": "CMC package deficiencies",
                    "probability": "Medium",
                    "impact": "Medium",
                    "mitigation": "Early CMC strategy development and quality system implementation"
                },
                {
                    "risk": "Clinical hold after IND submission",
                    "probability": "Low",
                    "impact": "High",
                    "mitigation": "Thorough pre-submission review and potential pre-IND meeting"
                }
            ])
        
        elif development_phase in ["phase1", "phase2", "phase3"]:
            risks.extend([
                {
                    "risk": "Safety signal requiring study halt",
                    "probability": "Low",
                    "impact": "High",
                    "mitigation": "Robust safety monitoring and DSMB oversight"
                },
                {
                    "risk": "Efficacy endpoints not met",
                    "probability": "Medium",
                    "impact": "High",
                    "mitigation": "Careful endpoint selection and adaptive trial design"
                },
                {
                    "risk": "Regulatory feedback requiring protocol changes",
                    "probability": "Medium",
                    "impact": "Medium",
                    "mitigation": "Early and frequent regulatory interaction"
                }
            ])
        
        elif development_phase == "nda":
            risks.extend([
                {
                    "risk": "Complete Response Letter (CRL)",
                    "probability": "Medium",
                    "impact": "High",
                    "mitigation": "Comprehensive submission with high-quality data and analyses"
                },
                {
                    "risk": "Advisory Committee meeting required",
                    "probability": "Medium",
                    "impact": "Medium",
                    "mitigation": "Prepare comprehensive benefit-risk presentation"
                },
                {
                    "risk": "Post-marketing requirements imposed",
                    "probability": "High",
                    "impact": "Medium",
                    "mitigation": "Proactive proposal of reasonable post-marketing studies"
                }
            ])
        
        # Format risk assessment table
        results += "### Risk Analysis Matrix\n\n"
        results += "| Risk | Probability | Impact | Mitigation Strategy |\n"
        results += "|------|-------------|--------|--------------------|\n"
        
        for risk in risks:
            prob_icon = {"High": "🔴", "Medium": "🟡", "Low": "🟢"}[risk["probability"]]
            impact_icon = {"High": "🔴", "Medium": "🟡", "Low": "🟢"}[risk["impact"]]
            
            results += f"| {risk['risk']} | {prob_icon} {risk['probability']} | {impact_icon} {risk['impact']} | {risk['mitigation']} |\n"
        
        results += "\n### Risk Mitigation Strategies\n\n"
        
        results += "**Proactive Measures**:\n"
        results += "- Establish early communication with regulatory authorities\n"
        results += "- Implement robust quality systems and data integrity measures\n"
        results += "- Conduct thorough risk-benefit assessments\n"
        results += "- Maintain current regulatory intelligence\n\n"
        
        results += "**Contingency Planning**:\n"
        results += "- Develop alternative study designs and endpoints\n"
        results += "- Prepare comprehensive response strategies for potential issues\n"
        results += "- Establish backup manufacturing and supply chain options\n"
        results += "- Create cross-functional crisis management team\n\n"
        
        return results
    
    async def _generate_recommendations(self, regulation_type: str, product_type: str,
                                      development_phase: str, jurisdiction: str) -> str:
        """Generate regulatory strategy recommendations."""
        await self.agent.handle_intervention()
        
        results = "## Strategic Recommendations\n\n"
        
        results += "### Immediate Actions (Next 30 Days)\n\n"
        immediate_actions = [
            "Schedule regulatory strategy planning meeting",
            "Review and update regulatory submission timeline",
            "Identify critical data gaps requiring attention",
            "Establish regulatory communication plan",
            "Conduct regulatory intelligence update"
        ]
        
        for i, action in enumerate(immediate_actions, 1):
            results += f"{i}. {action}\n"
        
        results += "\n### Short-term Actions (Next 3 Months)\n\n"
        short_term_actions = [
            "Complete regulatory submission document templates",
            "Initiate pre-submission meetings with authorities",
            "Finalize clinical development plan",
            "Implement quality system enhancements",
            "Conduct regulatory compliance audit"
        ]
        
        for i, action in enumerate(short_term_actions, 1):
            results += f"{i}. {action}\n"
        
        results += "\n### Long-term Strategic Considerations\n\n"
        
        results += "**Regulatory Science Opportunities**:\n"
        results += "- Consider novel trial designs (adaptive, master protocols)\n"
        results += "- Explore accelerated approval pathways if applicable\n"
        results += "- Evaluate real-world evidence strategies\n"
        results += "- Assess digital health technologies integration\n\n"
        
        results += "**Global Regulatory Strategy**:\n"
        if jurisdiction == "usa":
            results += "- Consider ICH regions for parallel development\n"
            results += "- Evaluate FDA breakthrough therapy designation\n"
            results += "- Plan for orphan drug status if applicable\n"
        elif jurisdiction == "eu":
            results += "- Utilize EMA scientific advice procedures\n"
            results += "- Consider PRIME designation for innovative medicines\n"
            results += "- Plan for centralized vs. decentralized approval\n"
        
        results += "- Develop harmonized global dossier strategy\n"
        results += "- Plan for reference listed drug considerations\n\n"
        
        results += "**Quality and Manufacturing**:\n"
        results += "- Implement Quality by Design (QbD) principles\n"
        results += "- Plan for commercial manufacturing scale-up\n"
        results += "- Establish supply chain risk management\n"
        results += "- Consider continuous manufacturing opportunities\n\n"
        
        results += "**Post-Market Considerations**:\n"
        results += "- Develop pharmacovigilance plan\n"
        results += "- Plan for Risk Evaluation and Mitigation Strategy (REMS)\n"
        results += "- Establish post-marketing study protocols\n"
        results += "- Prepare for potential label expansions\n\n"
        
        # Contact information
        results += "## Regulatory Authority Contacts\n\n"
        
        if regulation_type == "fda":
            results += "**FDA Office Contacts**:\n"
            results += "- Office of New Drugs (OND): For small molecule drugs\n"
            results += "- Office of Tissues and Advanced Therapies (OTAT): For biologics\n"
            results += "- Office of Pharmaceutical Quality (OPQ): For CMC questions\n"
            results += "- Division-specific contacts based on therapeutic area\n\n"
        
        elif regulation_type == "ema":
            results += "**EMA Contacts**:\n"
            results += "- Committee for Medicinal Products for Human Use (CHMP)\n"
            results += "- Committee for Advanced Therapies (CAT)\n"
            results += "- Pharmacovigilance Risk Assessment Committee (PRAC)\n"
            results += "- Scientific Advice Working Party (SAWP)\n\n"
        
        results += "**Additional Resources**:\n"
        results += "- Regulatory consultants and legal advisors\n"
        results += "- Industry trade associations\n"
        results += "- Regulatory intelligence services\n"
        results += "- Clinical research organizations (CROs)\n\n"
        
        # Disclaimer
        results += "---\n"
        results += "**Disclaimer**: This regulatory compliance analysis is for informational purposes only and does not constitute legal or regulatory advice. Always consult with qualified regulatory professionals and legal counsel for specific regulatory matters. Regulatory requirements may change, and this analysis reflects current understanding as of the assessment date.\n"
        
        return results