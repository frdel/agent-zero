import asyncio
import aiohttp
import json
from typing import Dict, List, Any, Optional, Tuple
from python.helpers.tool import Tool, Response
from python.helpers.print_style import PrintStyle
from python.helpers.errors import handle_error


class DrugInteractionChecker(Tool):
    """
    Comprehensive drug interaction checker for clinical and research applications.
    Analyzes drug-drug, drug-food, and drug-condition interactions with severity assessment.
    """
    
    async def execute(self, drugs: str = "", patient_conditions: str = "", 
                     include_food_interactions: bool = True, severity_filter: str = "all",
                     check_contraindications: bool = True, age: int = None,
                     pregnancy_status: str = "unknown", **kwargs) -> Response:
        """
        Check for drug interactions and contraindications.
        
        Args:
            drugs: Comma-separated list of drug names or identifiers
            patient_conditions: Comma-separated list of medical conditions
            include_food_interactions: Whether to check food-drug interactions
            severity_filter: Filter by severity ("all", "major", "moderate", "minor")
            check_contraindications: Whether to check for contraindications
            age: Patient age for age-specific warnings
            pregnancy_status: Pregnancy status ("pregnant", "breastfeeding", "unknown")
        """
        
        if not drugs.strip():
            return Response(
                message="Error: At least one drug name must be provided for interaction checking",
                break_loop=False
            )
        
        try:
            # Parse drug list
            drug_list = [drug.strip() for drug in drugs.split(',') if drug.strip()]
            condition_list = [cond.strip() for cond in patient_conditions.split(',') if cond.strip()] if patient_conditions else []
            
            if len(drug_list) < 1:
                return Response(
                    message="Error: At least one valid drug name must be provided",
                    break_loop=False
                )
            
            # Validate severity filter
            valid_severities = ["all", "major", "moderate", "minor"]
            if severity_filter not in valid_severities:
                severity_filter = "all"
            
            # Normalize drug names and get drug information
            normalized_drugs = await self._normalize_drug_names(drug_list)
            
            # Check drug-drug interactions
            drug_interactions = await self._check_drug_drug_interactions(normalized_drugs, severity_filter)
            
            # Check drug-condition interactions
            condition_interactions = []
            if condition_list and check_contraindications:
                condition_interactions = await self._check_drug_condition_interactions(
                    normalized_drugs, condition_list
                )
            
            # Check special population warnings
            special_warnings = []
            if age is not None or pregnancy_status != "unknown":
                special_warnings = await self._check_special_population_warnings(
                    normalized_drugs, age, pregnancy_status
                )
            
            # Check food interactions
            food_interactions = []
            if include_food_interactions:
                food_interactions = await self._check_food_interactions(normalized_drugs)
            
            # Generate comprehensive report
            report = self._generate_interaction_report(
                normalized_drugs, drug_interactions, condition_interactions,
                special_warnings, food_interactions, severity_filter
            )
            
            return Response(message=report, break_loop=False)
            
        except Exception as e:
            handle_error(e)
            return Response(message=f"Drug interaction check failed: {str(e)}", break_loop=False)
    
    async def _normalize_drug_names(self, drug_list: List[str]) -> List[Dict[str, Any]]:
        """Normalize drug names and retrieve basic drug information using RxNorm API."""
        await self.agent.handle_intervention()
        
        normalized_drugs = []
        
        for drug in drug_list:
            drug_lower = drug.lower().strip()
            
            try:
                # Use RxNorm API to get drug information
                drug_info = await self._query_rxnorm_api(drug_lower)
                if drug_info:
                    normalized_drugs.append(drug_info)
                else:
                    # Fallback to local knowledge base
                    drug_info = await self._get_fallback_drug_info(drug, drug_lower)
                    normalized_drugs.append(drug_info)
            except Exception as e:
                # Create basic entry if API fails
                drug_info = {
                    "generic_name": drug_lower,
                    "brand_names": [],
                    "drug_class": "Unknown",
                    "mechanism": "Unknown",
                    "half_life": "Unknown",
                    "input_name": drug,
                    "source": "fallback"
                }
                normalized_drugs.append(drug_info)
        
        return normalized_drugs
    
    async def _query_rxnorm_api(self, drug_name: str) -> Optional[Dict[str, Any]]:
        """Query RxNorm API for drug information."""
        try:
            import aiohttp
            
            # RxNorm REST API endpoint
            base_url = "https://rxnav.nlm.nih.gov/REST"
            
            async with aiohttp.ClientSession() as session:
                # First, search for the drug concept
                search_url = f"{base_url}/drugs.json?name={drug_name}"
                async with session.get(search_url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        if 'drugGroup' in data and 'conceptGroup' in data['drugGroup']:
                            concepts = data['drugGroup']['conceptGroup']
                            
                            # Find the best matching concept
                            for concept_group in concepts:
                                if 'conceptProperties' in concept_group:
                                    for concept in concept_group['conceptProperties']:
                                        if concept['name'].lower() == drug_name.lower():
                                            rxcui = concept['rxcui']
                                            
                                            # Get detailed information
                                            return await self._get_drug_details_from_rxcui(session, rxcui, drug_name)
            
            return None
            
        except Exception as e:
            print(f"RxNorm API error for {drug_name}: {str(e)}")
            return None
    
    async def _get_drug_details_from_rxcui(self, session, rxcui: str, original_name: str) -> Dict[str, Any]:
        """Get detailed drug information from RxCUI."""
        base_url = "https://rxnav.nlm.nih.gov/REST"
        
        try:
            # Get drug properties
            props_url = f"{base_url}/rxcui/{rxcui}/properties.json"
            async with session.get(props_url, timeout=10) as response:
                if response.status == 200:
                    props_data = await response.json()
                    properties = props_data.get('properties', {})
                    
                    # Get related drugs (brand names, etc.)
                    related_url = f"{base_url}/rxcui/{rxcui}/related.json?tty=BN+SBD"
                    brand_names = []
                    async with session.get(related_url, timeout=10) as related_response:
                        if related_response.status == 200:
                            related_data = await related_response.json()
                            if 'relatedGroup' in related_data:
                                for group in related_data['relatedGroup']['conceptGroup']:
                                    if 'conceptProperties' in group:
                                        for concept in group['conceptProperties']:
                                            brand_names.append(concept['name'])
                    
                    return {
                        "generic_name": properties.get('name', original_name).lower(),
                        "brand_names": brand_names[:5],  # Limit to 5 brand names
                        "drug_class": "Unknown",  # RxNorm doesn't provide class info
                        "mechanism": "Unknown",
                        "half_life": "Unknown",
                        "input_name": original_name,
                        "rxcui": rxcui,
                        "source": "rxnorm_api"
                    }
        
        except Exception as e:
            print(f"Error getting drug details for RxCUI {rxcui}: {str(e)}")
        
        return None
    
    async def _get_fallback_drug_info(self, original_drug: str, drug_lower: str) -> Dict[str, Any]:
        """Get drug info from local knowledge base as fallback."""
        # Local knowledge base for common drugs
        drug_database = {
            # Cardiovascular drugs
            "metoprolol": {
                "generic_name": "metoprolol",
                "brand_names": ["Lopressor", "Toprol-XL"],
                "drug_class": "Beta-blocker",
                "mechanism": "Selective beta-1 adrenergic receptor antagonist",
                "half_life": "3-7 hours"
            },
            "lisinopril": {
                "generic_name": "lisinopril",
                "brand_names": ["Prinivil", "Zestril"],
                "drug_class": "ACE inhibitor",
                "mechanism": "Angiotensin-converting enzyme inhibitor",
                "half_life": "12 hours"
            },
            "amlodipine": {
                "generic_name": "amlodipine",
                "brand_names": ["Norvasc"],
                "drug_class": "Calcium channel blocker",
                "mechanism": "Dihydropyridine calcium channel antagonist",
                "half_life": "30-50 hours"
            },
            "atorvastatin": {
                "generic_name": "atorvastatin",
                "brand_names": ["Lipitor"],
                "drug_class": "HMG-CoA reductase inhibitor (statin)",
                "mechanism": "Inhibits cholesterol synthesis",
                "half_life": "14 hours"
            },
            # Diabetes drugs
            "metformin": {
                "generic_name": "metformin",
                "brand_names": ["Glucophage"],
                "drug_class": "Biguanide",
                "mechanism": "Decreases hepatic glucose production",
                "half_life": "6.2 hours"
            },
            "insulin": {
                "generic_name": "insulin",
                "brand_names": ["Humulin", "Novolog"],
                "drug_class": "Hormone",
                "mechanism": "Glucose uptake and metabolism",
                "half_life": "Variable"
            },
            # Anticoagulants
            "warfarin": {
                "generic_name": "warfarin",
                "brand_names": ["Coumadin"],
                "drug_class": "Vitamin K antagonist",
                "mechanism": "Inhibits vitamin K-dependent clotting factors",
                "half_life": "20-60 hours"
            },
            "rivaroxaban": {
                "generic_name": "rivaroxaban",
                "brand_names": ["Xarelto"],
                "drug_class": "Direct factor Xa inhibitor",
                "mechanism": "Selective factor Xa inhibition",
                "half_life": "5-9 hours"
            },
            # Antibiotics
            "amoxicillin": {
                "generic_name": "amoxicillin",
                "brand_names": ["Amoxil"],
                "drug_class": "Penicillin antibiotic",
                "mechanism": "Beta-lactam antibiotic",
                "half_life": "1-1.5 hours"
            },
            "azithromycin": {
                "generic_name": "azithromycin",
                "brand_names": ["Zithromax"],
                "drug_class": "Macrolide antibiotic",
                "mechanism": "Protein synthesis inhibitor",
                "half_life": "68 hours"
            }
        }
        
        normalized_drugs = []
        for drug in drug_list:
            drug_lower = drug.lower().strip()
            
            # Find matching drug in database
            drug_info = None
            for generic_name, info in drug_database.items():
                if (drug_lower == generic_name or 
                    drug_lower in [brand.lower() for brand in info["brand_names"]]):
                    drug_info = info.copy()
                    drug_info["input_name"] = drug
                    break
            
            if not drug_info:
                # Unknown drug - create basic entry
                drug_info = {
                    "generic_name": drug_lower,
                    "brand_names": [],
                    "drug_class": "Unknown",
                    "mechanism": "Unknown",
                    "half_life": "Unknown",
                    "input_name": drug
                }
            
            normalized_drugs.append(drug_info)
        
        return normalized_drugs
    
    async def _check_drug_drug_interactions(self, drugs: List[Dict[str, Any]], 
                                          severity_filter: str) -> List[Dict[str, Any]]:
        """Check for drug-drug interactions."""
        await self.agent.handle_intervention()
        
        if len(drugs) < 2:
            return []
        
        # Predefined interaction database (simplified)
        # In practice, this would be a comprehensive database or API call
        interaction_database = {
            ("warfarin", "azithromycin"): {
                "severity": "major",
                "mechanism": "Azithromycin may increase warfarin effect via CYP450 inhibition",
                "clinical_effect": "Increased bleeding risk",
                "management": "Monitor INR closely, consider dose adjustment",
                "evidence_level": "Moderate"
            },
            ("metoprolol", "insulin"): {
                "severity": "moderate",
                "mechanism": "Beta-blockers may mask hypoglycemic symptoms",
                "clinical_effect": "Reduced awareness of low blood sugar",
                "management": "Monitor blood glucose more frequently",
                "evidence_level": "High"
            },
            ("atorvastatin", "azithromycin"): {
                "severity": "moderate",
                "mechanism": "CYP3A4 inhibition may increase statin levels",
                "clinical_effect": "Increased risk of myopathy",
                "management": "Consider temporary statin discontinuation",
                "evidence_level": "Moderate"
            },
            ("lisinopril", "metformin"): {
                "severity": "minor",
                "mechanism": "ACE inhibitors may reduce renal clearance",
                "clinical_effect": "Slightly increased metformin levels",
                "management": "Monitor renal function",
                "evidence_level": "Low"
            },
            ("warfarin", "atorvastatin"): {
                "severity": "moderate",
                "mechanism": "Potential CYP2C9 interaction",
                "clinical_effect": "Possible increased anticoagulation",
                "management": "Monitor INR when starting/stopping statin",
                "evidence_level": "Moderate"
            }
        }
        
        interactions = []
        
        # Check all drug pairs
        for i in range(len(drugs)):
            for j in range(i + 1, len(drugs)):
                drug1 = drugs[i]["generic_name"]
                drug2 = drugs[j]["generic_name"]
                
                # Check both directions
                interaction_key = None
                if (drug1, drug2) in interaction_database:
                    interaction_key = (drug1, drug2)
                elif (drug2, drug1) in interaction_database:
                    interaction_key = (drug2, drug1)
                
                if interaction_key:
                    interaction = interaction_database[interaction_key].copy()
                    interaction["drug1"] = drugs[i]
                    interaction["drug2"] = drugs[j]
                    
                    # Apply severity filter
                    if severity_filter == "all" or interaction["severity"] == severity_filter:
                        interactions.append(interaction)
        
        return interactions
    
    async def _check_drug_condition_interactions(self, drugs: List[Dict[str, Any]], 
                                               conditions: List[str]) -> List[Dict[str, Any]]:
        """Check for drug-condition contraindications."""
        await self.agent.handle_intervention()
        
        # Contraindication database
        contraindication_database = {
            "metoprolol": {
                "asthma": {
                    "severity": "major",
                    "reason": "Beta-blockers can cause bronchospasm",
                    "recommendation": "Avoid or use with extreme caution"
                },
                "heart block": {
                    "severity": "major",
                    "reason": "May worsen conduction abnormalities",
                    "recommendation": "Contraindicated"
                }
            },
            "metformin": {
                "kidney disease": {
                    "severity": "major",
                    "reason": "Risk of lactic acidosis with reduced clearance",
                    "recommendation": "Contraindicated if eGFR < 30"
                },
                "heart failure": {
                    "severity": "moderate",
                    "reason": "Risk of lactic acidosis in acute decompensation",
                    "recommendation": "Use with caution, monitor closely"
                }
            },
            "warfarin": {
                "pregnancy": {
                    "severity": "major",
                    "reason": "Teratogenic effects",
                    "recommendation": "Contraindicated in pregnancy"
                },
                "liver disease": {
                    "severity": "major",
                    "reason": "Impaired metabolism and bleeding risk",
                    "recommendation": "Use with extreme caution"
                }
            }
        }
        
        interactions = []
        
        for drug in drugs:
            drug_name = drug["generic_name"]
            if drug_name in contraindication_database:
                for condition in conditions:
                    condition_lower = condition.lower().strip()
                    
                    # Check for matching conditions
                    for contraind_condition, details in contraindication_database[drug_name].items():
                        if condition_lower in contraind_condition or contraind_condition in condition_lower:
                            interaction = {
                                "drug": drug,
                                "condition": condition,
                                "severity": details["severity"],
                                "reason": details["reason"],
                                "recommendation": details["recommendation"]
                            }
                            interactions.append(interaction)
        
        return interactions
    
    async def _check_special_population_warnings(self, drugs: List[Dict[str, Any]], 
                                               age: Optional[int], 
                                               pregnancy_status: str) -> List[Dict[str, Any]]:
        """Check for special population warnings."""
        await self.agent.handle_intervention()
        
        warnings = []
        
        # Age-related warnings
        if age is not None:
            for drug in drugs:
                drug_name = drug["generic_name"]
                
                # Pediatric warnings
                if age < 18:
                    if drug_name in ["atorvastatin"]:
                        warnings.append({
                            "drug": drug,
                            "population": "Pediatric",
                            "warning": "Safety and efficacy not established in children",
                            "recommendation": "Use only if benefits outweigh risks"
                        })
                
                # Geriatric warnings
                elif age >= 65:
                    if drug_name in ["metoprolol"]:
                        warnings.append({
                            "drug": drug,
                            "population": "Geriatric",
                            "warning": "Increased sensitivity to beta-blocker effects",
                            "recommendation": "Start with lower doses, monitor closely"
                        })
                    elif drug_name in ["warfarin"]:
                        warnings.append({
                            "drug": drug,
                            "population": "Geriatric",
                            "warning": "Increased bleeding risk in elderly patients",
                            "recommendation": "More frequent INR monitoring required"
                        })
        
        # Pregnancy/breastfeeding warnings
        if pregnancy_status in ["pregnant", "breastfeeding"]:
            pregnancy_categories = {
                "warfarin": {
                    "category": "X",
                    "warning": "Contraindicated in pregnancy - teratogenic",
                    "recommendation": "Switch to alternative anticoagulant"
                },
                "lisinopril": {
                    "category": "D",
                    "warning": "May cause fetal kidney damage",
                    "recommendation": "Discontinue as soon as possible"
                },
                "atorvastatin": {
                    "category": "X",
                    "warning": "Contraindicated in pregnancy",
                    "recommendation": "Discontinue immediately"
                },
                "metformin": {
                    "category": "B",
                    "warning": "Generally considered safe but monitor closely",
                    "recommendation": "Continue if benefits outweigh risks"
                }
            }
            
            for drug in drugs:
                drug_name = drug["generic_name"]
                if drug_name in pregnancy_categories:
                    warning_info = pregnancy_categories[drug_name]
                    warnings.append({
                        "drug": drug,
                        "population": pregnancy_status.title(),
                        "category": warning_info["category"],
                        "warning": warning_info["warning"],
                        "recommendation": warning_info["recommendation"]
                    })
        
        return warnings
    
    async def _check_food_interactions(self, drugs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Check for food-drug interactions."""
        await self.agent.handle_intervention()
        
        food_interactions = {
            "warfarin": [
                {
                    "food": "Vitamin K-rich foods (leafy greens)",
                    "effect": "Decreased anticoagulation effect",
                    "recommendation": "Maintain consistent vitamin K intake"
                },
                {
                    "food": "Alcohol",
                    "effect": "Variable effect on anticoagulation",
                    "recommendation": "Limit alcohol consumption"
                }
            ],
            "atorvastatin": [
                {
                    "food": "Grapefruit juice",
                    "effect": "Increased statin levels, myopathy risk",
                    "recommendation": "Avoid grapefruit juice"
                },
                {
                    "food": "High-fat meals",
                    "effect": "Increased absorption",
                    "recommendation": "Take consistently with or without food"
                }
            ],
            "metformin": [
                {
                    "food": "Alcohol",
                    "effect": "Increased lactic acidosis risk",
                    "recommendation": "Limit alcohol intake"
                }
            ],
            "azithromycin": [
                {
                    "food": "Antacids",
                    "effect": "Decreased absorption",
                    "recommendation": "Take 1 hour before or 2 hours after antacids"
                }
            ]
        }
        
        interactions = []
        
        for drug in drugs:
            drug_name = drug["generic_name"]
            if drug_name in food_interactions:
                for food_interaction in food_interactions[drug_name]:
                    interaction = {
                        "drug": drug,
                        "food": food_interaction["food"],
                        "effect": food_interaction["effect"],
                        "recommendation": food_interaction["recommendation"]
                    }
                    interactions.append(interaction)
        
        return interactions
    
    def _generate_interaction_report(self, drugs: List[Dict[str, Any]], 
                                   drug_interactions: List[Dict[str, Any]],
                                   condition_interactions: List[Dict[str, Any]],
                                   special_warnings: List[Dict[str, Any]],
                                   food_interactions: List[Dict[str, Any]],
                                   severity_filter: str) -> str:
        """Generate comprehensive drug interaction report."""
        
        report = "# Drug Interaction Analysis Report\n\n"
        
        # Drug list summary
        report += "## Analyzed Medications\n\n"
        for i, drug in enumerate(drugs, 1):
            report += f"{i}. **{drug['input_name']}** ({drug['generic_name']})\n"
            report += f"   - Class: {drug['drug_class']}\n"
            report += f"   - Mechanism: {drug['mechanism']}\n"
            report += f"   - Half-life: {drug['half_life']}\n"
            if drug['brand_names']:
                report += f"   - Brand names: {', '.join(drug['brand_names'])}\n"
            report += "\n"
        
        # Risk summary
        major_count = len([i for i in drug_interactions if i['severity'] == 'major'])
        moderate_count = len([i for i in drug_interactions if i['severity'] == 'moderate'])
        minor_count = len([i for i in drug_interactions if i['severity'] == 'minor'])
        
        report += "## Risk Assessment Summary\n\n"
        if major_count > 0:
            report += f"🔴 **HIGH RISK**: {major_count} major interaction(s) identified\n"
        if moderate_count > 0:
            report += f"🟡 **MODERATE RISK**: {moderate_count} moderate interaction(s) identified\n"
        if minor_count > 0:
            report += f"🟢 **LOW RISK**: {minor_count} minor interaction(s) identified\n"
        
        if len(condition_interactions) > 0:
            report += f"⚠️  **CONTRAINDICATIONS**: {len(condition_interactions)} condition-related warning(s)\n"
        
        if len(special_warnings) > 0:
            report += f"👥 **SPECIAL POPULATIONS**: {len(special_warnings)} population-specific warning(s)\n"
        
        report += "\n"
        
        # Drug-drug interactions
        if drug_interactions:
            report += "## Drug-Drug Interactions\n\n"
            
            # Group by severity
            for severity in ['major', 'moderate', 'minor']:
                severity_interactions = [i for i in drug_interactions if i['severity'] == severity]
                if severity_interactions:
                    severity_emoji = {'major': '🔴', 'moderate': '🟡', 'minor': '🟢'}[severity]
                    report += f"### {severity_emoji} {severity.title()} Interactions\n\n"
                    
                    for interaction in severity_interactions:
                        drug1_name = interaction['drug1']['input_name']
                        drug2_name = interaction['drug2']['input_name']
                        
                        report += f"**{drug1_name} + {drug2_name}**\n"
                        report += f"- **Mechanism**: {interaction['mechanism']}\n"
                        report += f"- **Clinical Effect**: {interaction['clinical_effect']}\n"
                        report += f"- **Management**: {interaction['management']}\n"
                        report += f"- **Evidence Level**: {interaction['evidence_level']}\n\n"
        
        # Drug-condition interactions
        if condition_interactions:
            report += "## Drug-Condition Contraindications\n\n"
            
            for interaction in condition_interactions:
                severity_emoji = {'major': '🔴', 'moderate': '🟡', 'minor': '🟢'}[interaction['severity']]
                
                report += f"{severity_emoji} **{interaction['drug']['input_name']} + {interaction['condition']}**\n"
                report += f"- **Severity**: {interaction['severity'].title()}\n"
                report += f"- **Reason**: {interaction['reason']}\n"
                report += f"- **Recommendation**: {interaction['recommendation']}\n\n"
        
        # Special population warnings
        if special_warnings:
            report += "## Special Population Warnings\n\n"
            
            for warning in special_warnings:
                report += f"👥 **{warning['drug']['input_name']} - {warning['population']}**\n"
                if 'category' in warning:
                    report += f"- **Pregnancy Category**: {warning['category']}\n"
                report += f"- **Warning**: {warning['warning']}\n"
                report += f"- **Recommendation**: {warning['recommendation']}\n\n"
        
        # Food interactions
        if food_interactions:
            report += "## Food-Drug Interactions\n\n"
            
            for interaction in food_interactions:
                report += f"🍽️ **{interaction['drug']['input_name']} + {interaction['food']}**\n"
                report += f"- **Effect**: {interaction['effect']}\n"
                report += f"- **Recommendation**: {interaction['recommendation']}\n\n"
        
        # Clinical recommendations
        report += "## Clinical Recommendations\n\n"
        
        if major_count > 0:
            report += "### Immediate Actions Required:\n"
            report += "- Review all major interactions with prescribing physician\n"
            report += "- Consider alternative medications if available\n"
            report += "- Implement enhanced monitoring protocols\n\n"
        
        if moderate_count > 0:
            report += "### Monitoring Recommendations:\n"
            report += "- Increase frequency of clinical assessments\n"
            report += "- Monitor for interaction-specific adverse effects\n"
            report += "- Consider dose adjustments if indicated\n\n"
        
        report += "### General Recommendations:\n"
        report += "- Maintain updated medication list\n"
        report += "- Inform all healthcare providers of complete medication regimen\n"
        report += "- Report any new or worsening symptoms promptly\n"
        report += "- Do not start, stop, or change medications without consulting healthcare provider\n\n"
        
        # Disclaimer
        report += "---\n"
        report += "**Disclaimer**: This interaction analysis is for informational purposes only and does not "
        report += "replace professional medical advice. Always consult with a qualified healthcare provider "
        report += "before making any medication changes.\n"
        
        return report