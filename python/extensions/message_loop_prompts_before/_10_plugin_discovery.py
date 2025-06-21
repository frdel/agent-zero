"""
插件发现和推荐扩展
在每次消息循环开始前分析用户请求，推荐相关的插件工具
"""

from python.helpers.extension import Extension
from python.helpers.mcp_handler import MCPConfig
from agent import LoopData
import re


class PluginDiscovery(Extension):
    """插件发现和推荐扩展"""

    def __init__(self, agent):
        super().__init__(agent)
        self.tool_keywords = {
            # 文件操作相关
            'file': ['file', 'document', 'read', 'write', 'save', 'load', 'edit'],
            'database': ['database', 'sql', 'query', 'table', 'record', 'data'],
            'web': ['web', 'http', 'api', 'request', 'url', 'website', 'scrape'],
            'image': ['image', 'picture', 'photo', 'visual', 'graphic', 'draw'],
            'email': ['email', 'mail', 'send', 'message', 'notification'],
            'calendar': ['calendar', 'schedule', 'appointment', 'meeting', 'event'],
            'search': ['search', 'find', 'lookup', 'query', 'discover'],
            'analysis': ['analyze', 'analysis', 'report', 'statistics', 'data'],
            'automation': ['automate', 'script', 'batch', 'workflow', 'process'],
            'communication': ['chat', 'message', 'communicate', 'talk', 'discuss']
        }

    async def execute(self, loop_data: LoopData = LoopData(), **kwargs):
        """分析用户请求并推荐相关插件"""
        
        # 只在有用户消息时执行
        if not loop_data.user_message:
            return

        user_content = str(loop_data.user_message.content).lower()
        
        # 获取可用的MCP工具
        mcp_config = MCPConfig.get_instance()
        if not mcp_config.servers:
            return

        available_tools = self._get_available_mcp_tools()
        if not available_tools:
            return

        # 分析用户请求并推荐工具
        recommended_tools = self._analyze_and_recommend_tools(user_content, available_tools)
        
        if recommended_tools:
            # 将推荐添加到临时额外信息中
            recommendation_text = self._format_tool_recommendations(recommended_tools)
            loop_data.extras_temporary['plugin_recommendations'] = recommendation_text

    def _get_available_mcp_tools(self) -> dict:
        """获取可用的MCP工具信息"""
        try:
            mcp_config = MCPConfig.get_instance()
            tools_info = {}
            
            for server in mcp_config.servers:
                if not server.disabled:
                    server_tools = server.get_tools()
                    for tool in server_tools:
                        tool_name = f"{server.name}.{tool.get('name', '')}"
                        tools_info[tool_name] = {
                            'name': tool.get('name', ''),
                            'description': tool.get('description', ''),
                            'server': server.name,
                            'parameters': tool.get('inputSchema', {}).get('properties', {})
                        }
            
            return tools_info
        except Exception as e:
            print(f"Error getting MCP tools: {e}")
            return {}

    def _analyze_and_recommend_tools(self, user_content: str, available_tools: dict) -> list:
        """分析用户内容并推荐相关工具"""
        recommendations = []
        
        for tool_name, tool_info in available_tools.items():
            relevance_score = self._calculate_tool_relevance(user_content, tool_info)
            
            if relevance_score > 0.3:  # 相关性阈值
                recommendations.append({
                    'tool_name': tool_name,
                    'tool_info': tool_info,
                    'relevance_score': relevance_score
                })
        
        # 按相关性排序
        recommendations.sort(key=lambda x: x['relevance_score'], reverse=True)
        
        # 返回前3个最相关的工具
        return recommendations[:3]

    def _calculate_tool_relevance(self, user_content: str, tool_info: dict) -> float:
        """计算工具与用户请求的相关性"""
        relevance_score = 0.0
        
        # 检查工具名称匹配
        tool_name = tool_info.get('name', '').lower()
        if tool_name in user_content:
            relevance_score += 0.5
        
        # 检查工具描述匹配
        description = tool_info.get('description', '').lower()
        description_words = description.split()
        user_words = user_content.split()
        
        common_words = set(description_words) & set(user_words)
        if common_words:
            relevance_score += len(common_words) * 0.1
        
        # 检查关键词匹配
        for category, keywords in self.tool_keywords.items():
            if any(keyword in user_content for keyword in keywords):
                if any(keyword in description for keyword in keywords):
                    relevance_score += 0.2
        
        # 检查参数匹配
        parameters = tool_info.get('parameters', {})
        for param_name in parameters.keys():
            if param_name.lower() in user_content:
                relevance_score += 0.1
        
        return min(relevance_score, 1.0)  # 限制最大值为1.0

    def _format_tool_recommendations(self, recommendations: list) -> str:
        """格式化工具推荐信息"""
        if not recommendations:
            return ""
        
        recommendation_text = "## Recommended MCP Tools for this request:\n\n"
        
        for i, rec in enumerate(recommendations, 1):
            tool_info = rec['tool_info']
            recommendation_text += f"{i}. **{rec['tool_name']}** (Relevance: {rec['relevance_score']:.2f})\n"
            recommendation_text += f"   - Description: {tool_info.get('description', 'No description')}\n"
            recommendation_text += f"   - Server: {tool_info.get('server', 'Unknown')}\n"
            
            # 添加参数信息
            parameters = tool_info.get('parameters', {})
            if parameters:
                recommendation_text += f"   - Parameters: {', '.join(parameters.keys())}\n"
            
            recommendation_text += "\n"
        
        recommendation_text += "**Consider using these tools before falling back to standard tools.**\n"
        
        return recommendation_text
