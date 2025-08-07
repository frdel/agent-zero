import asyncio
from typing import Dict, List, Any, Optional
from python.helpers.tool import Tool, Response
from python.helpers.print_style import PrintStyle
from python.helpers.errors import handle_error
import aiohttp
import json
from datetime import datetime


class ClinicalTrialsSearch(Tool):
    """
    Clinical trials search tool for accessing ClinicalTrials.gov database.
    Provides comprehensive search and analysis of clinical trial data.
    """
    
    async def execute(self, condition: str = "", intervention: str = "", sponsor: str = "",
                     phase: str = "", status: str = "", country: str = "", max_results: int = 20,
                     start_date: str = "", completion_date: str = "", **kwargs) -> Response:
        """
        Search ClinicalTrials.gov database with multiple filter options.
        
        Args:
            condition: Disease or condition (e.g., "diabetes", "cancer")
            intervention: Treatment or intervention (e.g., "metformin", "placebo")
            sponsor: Study sponsor organization
            phase: Trial phase ("Phase 1", "Phase 2", "Phase 3", "Phase 4")
            status: Trial status ("Recruiting", "Completed", "Active", "Terminated")
            country: Country where trial is conducted
            max_results: Maximum number of results (1-100)
            start_date: Trial start date filter (YYYY-MM-DD)
            completion_date: Trial completion date filter (YYYY-MM-DD)
        """
        
        if not any([condition, intervention, sponsor]):
            return Response(
                message="Error: At least one search parameter (condition, intervention, or sponsor) is required",
                break_loop=False
            )
        
        try:
            # Validate and limit max_results
            max_results = min(max(1, int(max_results)), 100)
            
            # Build search parameters
            search_params = self._build_search_params(
                condition, intervention, sponsor, phase, status, 
                country, start_date, completion_date, max_results
            )
            
            # Execute search
            trials_data = await self._search_clinical_trials(search_params)
            
            if not trials_data or not trials_data.get('studies'):
                return Response(
                    message=f"No clinical trials found for the specified criteria",
                    break_loop=False
                )
            
            # Format and analyze results
            formatted_results = self._format_trial_results(trials_data, search_params)
            
            return Response(message=formatted_results, break_loop=False)
            
        except Exception as e:
            handle_error(e)
            return Response(message=f"Clinical trials search failed: {str(e)}", break_loop=False)
    
    def _build_search_params(self, condition: str, intervention: str, sponsor: str,
                           phase: str, status: str, country: str, start_date: str,
                           completion_date: str, max_results: int) -> Dict[str, Any]:
        """Build search parameters for ClinicalTrials.gov API."""
        params = {
            'format': 'json',
            'min_rnk': 1,
            'max_rnk': max_results,
            'fields': [
                'NCTId', 'BriefTitle', 'Condition', 'InterventionName',
                'Phase', 'OverallStatus', 'StartDate', 'CompletionDate',
                'EnrollmentCount', 'LocationCountry', 'LocationFacility',
                'ResponsiblePartyInvestigatorFullName', 'LeadSponsorName',
                'BriefSummary', 'PrimaryOutcome', 'SecondaryOutcome',
                'StudyType', 'DesignAllocation', 'DesignMasking'
            ]
        }
        
        # Add condition filter
        if condition.strip():
            params['cond'] = condition.strip()
        
        # Add intervention filter
        if intervention.strip():
            params['intr'] = intervention.strip()
        
        # Add sponsor filter
        if sponsor.strip():
            params['lead'] = sponsor.strip()
        
        # Add phase filter
        if phase.strip():
            phase_mapping = {
                'Phase 1': '1',
                'Phase 2': '2', 
                'Phase 3': '3',
                'Phase 4': '4',
                'Early Phase 1': '0'
            }
            if phase in phase_mapping:
                params['phase'] = phase_mapping[phase]
        
        # Add status filter
        if status.strip():
            status_mapping = {
                'Recruiting': 'Recruiting',
                'Not yet recruiting': 'Not yet recruiting',
                'Active': 'Active, not recruiting',
                'Completed': 'Completed',
                'Terminated': 'Terminated',
                'Suspended': 'Suspended',
                'Withdrawn': 'Withdrawn'
            }
            if status in status_mapping:
                params['recrs'] = status_mapping[status]
        
        # Add country filter
        if country.strip():
            params['cntry'] = country.strip()
        
        # Add date filters
        if start_date:
            try:
                datetime.strptime(start_date, '%Y-%m-%d')
                params['sfpd_s'] = start_date
            except ValueError:
                pass  # Invalid date format
        
        if completion_date:
            try:
                datetime.strptime(completion_date, '%Y-%m-%d')
                params['sfpd_e'] = completion_date
            except ValueError:
                pass  # Invalid date format
        
        return params
    
    async def _search_clinical_trials(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute search against ClinicalTrials.gov API."""
        base_url = "https://clinicaltrials.gov/api/query/study_fields"
        
        # Convert fields list to comma-separated string
        if 'fields' in params:
            params['fields'] = ','.join(params['fields'])
        
        async with aiohttp.ClientSession() as session:
            await self.agent.handle_intervention()
            
            async with session.get(base_url, params=params, timeout=30) as response:
                if response.status != 200:
                    raise Exception(f"ClinicalTrials.gov API error: HTTP {response.status}")
                
                content = await response.text()
                data = json.loads(content)
                
        return data
    
    def _format_trial_results(self, trials_data: Dict[str, Any], search_params: Dict[str, Any]) -> str:
        """Format clinical trial search results."""
        studies = trials_data.get('studies', [])
        total_count = trials_data.get('NStudiesFound', 0)
        
        if not studies:
            return "No clinical trials found for the specified criteria."
        
        # Build search summary
        search_terms = []
        if search_params.get('cond'):
            search_terms.append(f"Condition: {search_params['cond']}")
        if search_params.get('intr'):
            search_terms.append(f"Intervention: {search_params['intr']}")
        if search_params.get('lead'):
            search_terms.append(f"Sponsor: {search_params['lead']}")
        
        result_text = f"Clinical Trials Search Results\n"
        result_text += f"Search Terms: {' | '.join(search_terms) if search_terms else 'All trials'}\n"
        result_text += f"Total Found: {total_count} trials | Showing: {len(studies)} trials\n\n"
        
        # Add summary statistics
        phase_counts = {}
        status_counts = {}
        country_counts = {}
        
        for study in studies:
            fields = study.get('fields', {})
            
            # Count phases
            phase = self._get_field_value(fields, 'Phase')
            if phase:
                phase_counts[phase] = phase_counts.get(phase, 0) + 1
            
            # Count statuses
            status = self._get_field_value(fields, 'OverallStatus')
            if status:
                status_counts[status] = status_counts.get(status, 0) + 1
            
            # Count countries
            countries = self._get_field_value(fields, 'LocationCountry', is_list=True)
            if countries:
                for country in countries:
                    country_counts[country] = country_counts.get(country, 0) + 1
        
        # Add summary statistics
        if phase_counts:
            result_text += "**Phase Distribution:**\n"
            for phase, count in sorted(phase_counts.items()):
                result_text += f"  {phase}: {count} trials\n"
            result_text += "\n"
        
        if status_counts:
            result_text += "**Status Distribution:**\n"
            for status, count in sorted(status_counts.items()):
                result_text += f"  {status}: {count} trials\n"
            result_text += "\n"
        
        # Detailed trial listings
        result_text += "**Detailed Trial Information:**\n\n"
        
        for i, study in enumerate(studies, 1):
            fields = study.get('fields', {})
            
            # Extract key information
            nct_id = self._get_field_value(fields, 'NCTId')
            title = self._get_field_value(fields, 'BriefTitle')
            conditions = self._get_field_value(fields, 'Condition', is_list=True)
            interventions = self._get_field_value(fields, 'InterventionName', is_list=True)
            phase = self._get_field_value(fields, 'Phase')
            status = self._get_field_value(fields, 'OverallStatus')
            sponsor = self._get_field_value(fields, 'LeadSponsorName')
            enrollment = self._get_field_value(fields, 'EnrollmentCount')
            start_date = self._get_field_value(fields, 'StartDate')
            
            result_text += f"{i}. **{nct_id}**: {title}\n"
            
            if conditions:
                result_text += f"   **Conditions**: {', '.join(conditions[:3])}\n"
            
            if interventions:
                intervention_list = ', '.join(interventions[:3])
                if len(interventions) > 3:
                    intervention_list += f" (+{len(interventions)-3} more)"
                result_text += f"   **Interventions**: {intervention_list}\n"
            
            if phase:
                result_text += f"   **Phase**: {phase}\n"
            
            if status:
                result_text += f"   **Status**: {status}\n"
            
            if sponsor:
                result_text += f"   **Sponsor**: {sponsor}\n"
            
            if enrollment:
                result_text += f"   **Target Enrollment**: {enrollment}\n"
            
            if start_date:
                result_text += f"   **Start Date**: {start_date}\n"
            
            # Add ClinicalTrials.gov URL
            if nct_id:
                result_text += f"   **URL**: https://clinicaltrials.gov/ct2/show/{nct_id}\n"
            
            result_text += "\n"
        
        # Add search refinement tips
        result_text += "\n**Search Refinement Tips:**\n"
        result_text += "- Use specific condition names (e.g., 'Type 2 Diabetes' vs 'diabetes')\n"
        result_text += "- Filter by phase to focus on relevant development stage\n"
        result_text += "- Use status filters to find actively recruiting trials\n"
        result_text += "- Combine condition and intervention for targeted searches\n"
        result_text += "- Filter by country/location for geographic relevance\n"
        
        return result_text
    
    def _get_field_value(self, fields: Dict[str, Any], field_name: str, is_list: bool = False) -> Optional[Any]:
        """Extract field value from ClinicalTrials.gov API response."""
        field_data = fields.get(field_name, [])
        
        if not field_data:
            return None
        
        if is_list:
            return field_data
        else:
            return field_data[0] if field_data else None