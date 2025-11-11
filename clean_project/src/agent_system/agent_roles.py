"""
Agent Role Definitions and Business Value Propositions
Defines specific agent roles with clear use cases and domain focus
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class AgentDomain(Enum):
    """Core business domains for agent specialization."""

    CUSTOMER_SUPPORT = "customer_support"
    SALES_OPTIMIZATION = "sales_optimization"
    CONTENT_CREATION = "content_creation"
    DATA_ANALYSIS = "data_analysis"
    PROCESS_AUTOMATION = "process_automation"
    RESEARCH_ASSISTANCE = "research_assistance"
    CODE_DEVELOPMENT = "code_development"
    BUSINESS_INTELLIGENCE = "business_intelligence"
    COMPLIANCE_MONITORING = "compliance_monitoring"
    SUPPLY_CHAIN = "supply_chain"


class AgentSpecialization(Enum):
    """Agent specialization levels."""

    GENERALIST = "generalist"
    SPECIALIST = "specialist"
    EXPERT = "expert"
    CONSULTANT = "consultant"


@dataclass
class BusinessValue:
    """Business value proposition for an agent role."""

    problem_solved: str
    value_delivered: str
    roi_estimate: str
    time_savings: str
    cost_reduction: str
    efficiency_gain: str


@dataclass
class AgentRole:
    """Complete agent role definition."""

    name: str
    domain: AgentDomain
    specialization: AgentSpecialization
    description: str
    business_value: BusinessValue
    target_audience: str
    key_capabilities: List[str] = field(default_factory=list)
    success_metrics: List[str] = field(default_factory=list)
    implementation_complexity: str = "medium"
    market_demand: str = "high"
    competitive_advantage: str = ""


# Core Agent Role Definitions
AGENT_ROLES = {
    # Sales and Revenue Agents
    "sales_assistant": AgentRole(
        name="Sales Assistant Agent",
        domain=AgentDomain.SALES_OPTIMIZATION,
        specialization=AgentSpecialization.SPECIALIST,
        description="AI-powered sales assistant that analyzes customer data, identifies opportunities, and automates follow-ups to increase conversion rates and revenue.",
        business_value=BusinessValue(
            problem_solved="Low conversion rates and inefficient sales processes leading to lost revenue and overworked sales teams",
            value_delivered="30-50% increase in conversion rates through intelligent lead scoring, personalized outreach, and automated follow-up sequences",
            roi_estimate="3-5x ROI within 6 months through increased sales efficiency and reduced manual effort",
            time_savings="Save 15-20 hours per week per sales rep through automation of routine tasks",
            cost_reduction="Reduce customer acquisition cost by 25-40% through better targeting and automation",
            efficiency_gain="Improve sales team productivity by 40-60% through intelligent task prioritization",
        ),
        target_audience="B2B sales teams, account executives, sales managers at companies with 10+ sales reps",
        key_capabilities=[
            "Lead scoring and qualification automation",
            "Personalized email and outreach campaigns",
            "Sales pipeline analysis and forecasting",
            "Competitive intelligence gathering",
            "CRM data analysis and insights",
            "Automated proposal generation",
            "Follow-up schedule optimization",
        ],
        success_metrics=[
            "Lead-to-opportunity conversion rate",
            "Sales cycle length reduction",
            "Revenue per sales rep increase",
            "Email open and response rates",
            "Pipeline velocity improvement",
        ],
    ),
    # Customer Support Agents
    "customer_success_agent": AgentRole(
        name="Customer Success Agent",
        domain=AgentDomain.CUSTOMER_SUPPORT,
        specialization=AgentSpecialization.SPECIALIST,
        description="AI customer success agent that proactively monitors customer health, identifies churn risk, and automates retention strategies to reduce customer churn and increase lifetime value.",
        business_value=BusinessValue(
            problem_solved="High customer churn rates and reactive support causing revenue loss and poor customer experience",
            value_delivered="40-60% reduction in customer churn through proactive monitoring, early intervention, and automated retention campaigns",
            roi_estimate="2-4x ROI through increased customer retention and lifetime value",
            time_savings="Reduce manual customer monitoring by 20-30 hours per week per customer success manager",
            cost_reduction="Decrease customer churn cost by 30-50% through early detection and intervention",
            efficiency_gain="Improve customer success team efficiency by 35-45% through automation",
        ),
        target_audience="Customer success teams, SaaS companies, subscription businesses with 100+ customers",
        key_capabilities=[
            "Customer health scoring and monitoring",
            "Churn risk prediction and alerts",
            "Automated retention campaigns",
            "Upsell and cross-sell opportunity identification",
            "Customer onboarding optimization",
            "Support ticket analysis and routing",
            "Sentiment analysis and feedback processing",
        ],
        success_metrics=[
            "Customer churn rate reduction",
            "Customer lifetime value increase",
            "Net Promoter Score improvement",
            "Time-to-resolution reduction",
            "Customer satisfaction scores",
        ],
    ),
    # Content Creation Agents
    "content_creator_agent": AgentRole(
        name="Content Creator Agent",
        domain=AgentDomain.CONTENT_CREATION,
        specialization=AgentSpecialization.EXPERT,
        description="AI content creator that generates, optimizes, and distributes high-quality content across multiple channels, with SEO optimization and performance tracking.",
        business_value=BusinessValue(
            problem_solved="Inconsistent content quality, slow production cycles, and poor SEO performance limiting content marketing effectiveness",
            value_delivered="50-70% faster content production with 30-40% better SEO performance and consistent brand voice",
            roi_estimate="4-6x ROI through increased content output quality and reduced creation costs",
            time_savings="Save 25-30 hours per week in content creation and optimization",
            cost_reduction="Reduce content creation costs by 40-60% through automation",
            efficiency_gain="Increase content marketing efficiency by 60-80% through automation and optimization",
        ),
        target_audience="Content marketers, digital marketing agencies, e-commerce businesses, bloggers",
        key_capabilities=[
            "Multi-format content generation (blogs, social, email, ads)",
            "SEO optimization and keyword research",
            "Brand voice consistency and tone adjustment",
            "Content performance analysis and optimization",
            "A/B testing automation for content",
            "Multi-channel distribution management",
            "Content calendar planning and scheduling",
        ],
        success_metrics=[
            "Content production velocity",
            "SEO ranking improvements",
            "Engagement rates and click-through rates",
            "Content performance ROI",
            "Brand consistency scores",
        ],
    ),
    # Data Analysis Agents
    "business_intelligence_agent": AgentRole(
        name="Business Intelligence Agent",
        domain=AgentDomain.DATA_ANALYSIS,
        specialization=AgentSpecialization.CONSULTANT,
        description="AI business intelligence agent that analyzes complex datasets, generates insights, creates visualizations, and provides actionable recommendations for data-driven decision making.",
        business_value=BusinessValue(
            problem_solved="Data analysis bottlenecks, slow insight generation, and missed opportunities due to manual data processing and limited analytical capabilities",
            value_delivered="80-90% faster data analysis with 50-70% more accurate insights through advanced pattern recognition and automated reporting",
            roi_estimate="5-8x ROI through faster decision making and improved business outcomes",
            time_savings="Reduce analysis time by 35-45 hours per week for data analysts",
            cost_reduction="Decrease business intelligence costs by 30-50% through automation",
            efficiency_gain="Improve decision-making speed by 60-80% with real-time insights",
        ),
        target_audience="Data analysts, business analysts, executives, operations teams, financial services",
        key_capabilities=[
            "Automated data analysis and pattern recognition",
            "Predictive modeling and forecasting",
            "Interactive dashboard creation and maintenance",
            "Anomaly detection and alerting",
            "Report generation and distribution",
            "Data quality assessment and cleaning",
            "Custom KPI monitoring and tracking",
        ],
        success_metrics=[
            "Time-to-insight reduction",
            "Data accuracy improvements",
            "Business outcome correlations",
            "Report generation speed",
            "Decision-making velocity",
        ],
    ),
    # Process Automation Agents
    "process_optimizer_agent": AgentRole(
        name="Process Optimizer Agent",
        domain=AgentDomain.PROCESS_AUTOMATION,
        specialization=AgentSpecialization.EXPERT,
        description="AI process optimizer that identifies inefficiencies, automates workflows, and continuously improves business processes for maximum operational efficiency.",
        business_value=BusinessValue(
            problem_solved="Manual, error-prone processes causing delays, costs, and reduced productivity across business operations",
            value_delivered="40-60% process efficiency improvement through automation, error reduction, and workflow optimization",
            roi_estimate="3-7x ROI through operational cost reduction and productivity gains",
            time_savings="Save 30-50 hours per week per process owner through automation",
            cost_reduction="Reduce operational costs by 25-45% through process optimization",
            efficiency_gain="Improve operational efficiency by 50-70% through intelligent automation",
        ),
        target_audience="Operations teams, process owners, manufacturing, logistics, service organizations",
        key_capabilities=[
            "Process mapping and analysis",
            "Workflow automation design and implementation",
            "Bottleneck identification and resolution",
            "Quality control and error reduction",
            "Resource allocation optimization",
            "Compliance monitoring and reporting",
            "Continuous improvement recommendations",
        ],
        success_metrics=[
            "Process completion time",
            "Error rate reduction",
            "Cost per transaction",
            "Resource utilization efficiency",
            "Compliance adherence rates",
        ],
    ),
    # Research Assistant Agents
    "research_specialist_agent": AgentRole(
        name="Research Specialist Agent",
        domain=AgentDomain.RESEARCH_ASSISTANCE,
        specialization=AgentSpecialization.EXPERT,
        description="AI research specialist that conducts comprehensive research, synthesizes information from multiple sources, and generates detailed reports for decision making.",
        business_value=BusinessValue(
            problem_solved="Time-consuming manual research, information overload, and difficulty in synthesizing complex data from multiple sources",
            value_delivered="70-85% faster research completion with 40-60% better information quality and comprehensive source analysis",
            roi_estimate="4-6x ROI through faster decision making and improved research quality",
            time_savings="Save 25-40 hours per research project through automation",
            cost_reduction="Reduce research costs by 50-70% through efficient information processing",
            efficiency_gain="Improve research productivity by 60-80% through intelligent summarization",
        ),
        target_audience="Market researchers, business analysts, consultants, academic researchers, product managers",
        key_capabilities=[
            "Multi-source information gathering and verification",
            "Literature review and synthesis",
            "Data extraction and analysis",
            "Citation and source management",
            "Report writing and formatting",
            "Trend analysis and forecasting",
            "Competitive intelligence gathering",
        ],
        success_metrics=[
            "Research completion time",
            "Source quality and reliability",
            "Report comprehensiveness",
            "Citation accuracy",
            "Decision impact measurement",
        ],
    ),
    # Code Development Agents
    "developer_assistant_agent": AgentRole(
        name="Developer Assistant Agent",
        domain=AgentDomain.CODE_DEVELOPMENT,
        specialization=AgentSpecialization.CONSULTANT,
        description="AI developer assistant that accelerates software development through code generation, debugging, testing, and documentation automation.",
        business_value=BusinessValue(
            problem_solved="Slow development cycles, code quality issues, and repetitive programming tasks limiting software delivery speed and quality",
            value_delivered="40-60% faster development with 30-50% fewer bugs through AI-powered code generation, testing, and optimization",
            roi_estimate="2-5x ROI through increased developer productivity and reduced technical debt",
            time_savings="Save 20-35 hours per week per developer through automation",
            cost_reduction="Reduce development costs by 25-40% through efficiency gains",
            efficiency_gain="Improve code quality and consistency by 50-70%",
        ),
        target_audience="Software development teams, startups, enterprises with development projects",
        key_capabilities=[
            "Code generation from natural language specifications",
            "Automated testing and test case generation",
            "Bug detection and debugging assistance",
            "Code review and optimization",
            "Documentation generation and maintenance",
            "Architecture design and planning",
            "Legacy code modernization",
        ],
        success_metrics=[
            "Development velocity increase",
            "Code quality improvements",
            "Bug density reduction",
            "Testing coverage enhancement",
            "Time-to-market acceleration",
        ],
    ),
}


class AgentRoleManager:
    """Manages agent role definitions and business value propositions."""

    def __init__(self) -> None:
        self.roles = AGENT_ROLES
        self.current_role: Optional[AgentRole] = None

    def get_role(self, role_name: str) -> Optional[AgentRole]:
        """Get a specific agent role by name."""
        return self.roles.get(role_name)

    def get_roles_by_domain(self, domain: AgentDomain) -> List[AgentRole]:
        """Get all roles for a specific domain."""
        return [role for role in self.roles.values() if role.domain == domain]

    def get_roles_by_specialization(self, specialization: AgentSpecialization) -> List[AgentRole]:
        """Get all roles for a specific specialization level."""
        return [role for role in self.roles.values() if role.specialization == specialization]

    def recommend_role(self, business_context: Dict[str, Any]) -> AgentRole:
        """Recommend the most suitable agent role based on business context."""
        _company_size = business_context.get("company_size", "medium")
        _industry = business_context.get("industry", "general")
        primary_goals = business_context.get("primary_goals", [])
        _pain_points = business_context.get("pain_points", [])

        # Simple recommendation logic - can be enhanced with ML
        if "sales" in primary_goals or "revenue" in primary_goals:
            return self.roles["sales_assistant"]
        elif "customer satisfaction" in primary_goals or "retention" in primary_goals:
            return self.roles["customer_success_agent"]
        elif "content" in primary_goals or "marketing" in primary_goals:
            return self.roles["content_creator_agent"]
        elif "data" in primary_goals or "analytics" in primary_goals:
            return self.roles["business_intelligence_agent"]
        elif "efficiency" in primary_goals or "automation" in primary_goals:
            return self.roles["process_optimizer_agent"]
        else:
            # Default to business intelligence for general cases
            return self.roles["business_intelligence_agent"]

    def set_current_role(self, role_name: str) -> bool:
        """Set the current agent role for the system."""
        if role_name in self.roles:
            self.current_role = self.roles[role_name]
            logger.info(f"Agent role set to: {role_name}")
            return True
        else:
            logger.error(f"Unknown agent role: {role_name}")
            return False

    def get_current_role(self) -> Optional[AgentRole]:
        """Get the currently active agent role."""
        return self.current_role

    def generate_role_presentation(self, role_name: str) -> Dict[str, Any]:
        """Generate a comprehensive presentation of agent role value."""
        role = self.get_role(role_name)
        if not role:
            return {"error": f"Role {role_name} not found"}

        return {
            "role_name": role.name,
            "executive_summary": role.description,
            "business_problem": {
                "problem": role.business_value.problem_solved,
                "impact": "This problem costs companies significant time, money, and competitive advantage",
            },
            "solution": {
                "approach": f"Deploy {role.name} with {role.specialization.value} capabilities",
                "key_capabilities": role.key_capabilities,
            },
            "business_value": {
                "roi": role.business_value.roi_estimate,
                "time_savings": role.business_value.time_savings,
                "cost_reduction": role.business_value.cost_reduction,
                "efficiency_gain": role.business_value.efficiency_gain,
            },
            "target_audience": role.target_audience,
            "success_metrics": role.success_metrics,
            "implementation": {
                "complexity": role.implementation_complexity,
                "market_demand": role.market_demand,
            },
        }


# Global agent role manager instance
agent_role_manager = AgentRoleManager()


def get_agent_roles() -> Dict[str, AgentRole]:
    """Get all available agent roles."""
    return agent_role_manager.roles


def recommend_best_role(business_context: Dict[str, Any]) -> AgentRole:
    """Recommend the best agent role for given business context."""
    return agent_role_manager.recommend_role(business_context)


def get_role_presentation(role_name: str) -> Dict[str, Any]:
    """Get comprehensive role presentation."""
    return agent_role_manager.generate_role_presentation(role_name)
