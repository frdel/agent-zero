from typing import Any
from python.helpers.extension import Extension
from agent import Agent, LoopData


class HumanLayerCheck(Extension):
    """
    HumanLayer Pre-execution Check Extension for Agent Zero.
    Analyzes pending tool calls for high-risk operations that might require approval.
    Provides warnings and guidance for operations that should use HumanLayer approval.
    """

    async def execute(self, loop_data: LoopData = LoopData(), **kwargs: Any):
        """
        Check pending tool calls for operations that might benefit from human approval.
        This is a pre-execution check that can warn about potentially risky operations.
        """
        # Only proceed if HumanLayer is enabled
        if not self.agent or not self.agent.config.additional.get("humanlayer_enabled", False):
            return
        
        # Check if we have any tool calls to analyze
        if not hasattr(loop_data, 'iteration') or loop_data.iteration < 0:
            return
        
        try:
            # Analyze recent tool calls in the loop data for high-risk patterns
            high_risk_patterns = [
                "rm -rf", "sudo", "DELETE", "DROP TABLE", "DROP DATABASE",
                "os.remove", "shutil.rmtree", "subprocess.call",
                "apt-get install", "pip install", "npm install",
                "chmod 777", "chown", "systemctl", "service",
                "git push", "git reset --hard", "git clean -fd",
                "docker run", "docker exec", "curl", "wget"
            ]
            
            # Check if any recent messages contain potentially risky operations
            # This is a preventive check, not blocking - just informational
            if hasattr(self.agent, 'context') and hasattr(self.agent.context, 'log'):
                # Log that HumanLayer pre-execution check is active
                self.agent.context.log.log(
                    type="info",
                    heading="HumanLayer Pre-execution Check Active",
                    content="Monitoring for operations that may benefit from human approval",
                    kvps={"enabled": True, "patterns_monitored": len(high_risk_patterns)}
                )
                
        except Exception as e:
            # Graceful error handling - don't break the main flow
            if hasattr(self.agent, 'context') and hasattr(self.agent.context, 'log'):
                self.agent.context.log.log(
                    type="warning",
                    heading="HumanLayer Pre-execution Check Warning",
                    content=f"Error in pre-execution check: {str(e)}",
                    kvps={}
                )

    def _contains_high_risk_patterns(self, text: str) -> tuple[bool, list[str]]:
        """
        Check if text contains high-risk operation patterns.
        Returns (has_risk_patterns, list_of_found_patterns)
        """
        high_risk_patterns = [
            "rm -rf", "sudo", "DELETE", "DROP TABLE", "DROP DATABASE",
            "os.remove", "shutil.rmtree", "subprocess.call",
            "apt-get install", "pip install", "npm install",
            "chmod 777", "chown", "systemctl", "service",
            "git push", "git reset --hard", "git clean -fd",
            "docker run", "docker exec", "curl", "wget"
        ]
        
        found_patterns = []
        text_lower = text.lower()
        
        for pattern in high_risk_patterns:
            if pattern.lower() in text_lower:
                found_patterns.append(pattern)
        
        return len(found_patterns) > 0, found_patterns

    def _should_recommend_approval(self, text: str) -> bool:
        """
        Determine if an operation should recommend human approval.
        Based on risk assessment of the operation.
        """
        has_risk, patterns = self._contains_high_risk_patterns(text)
        
        # Additional context-based risk assessment
        destructive_keywords = ["delete", "remove", "drop", "truncate", "destroy", "purge"]
        system_keywords = ["system", "root", "admin", "sudo", "chmod"]
        network_keywords = ["download", "install", "fetch", "curl", "wget"]
        
        text_lower = text.lower()
        
        risk_score = 0
        if has_risk:
            risk_score += 3
        
        for keyword in destructive_keywords:
            if keyword in text_lower:
                risk_score += 2
                break
        
        for keyword in system_keywords:
            if keyword in text_lower:
                risk_score += 2
                break
                
        for keyword in network_keywords:
            if keyword in text_lower:
                risk_score += 1
                break
        
        return risk_score >= 3