"""
Advanced Prompt Engineering and Optimization System
Comprehensive prompt management, optimization, and performance tracking
"""

from __future__ import annotations

import json
import logging
import re
import statistics
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class PromptType(Enum):
    """Types of prompts in the system."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL_CALL = "tool_call"
    TEMPLATE = "template"
    FEW_SHOT = "few_shot"
    CHAIN_OF_THOUGHT = "chain_of_thought"
    ROLE_BASED = "role_based"


class OptimizationMetric(Enum):
    """Metrics for prompt optimization."""

    COMPLETENESS = "completeness"
    ACCURACY = "accuracy"
    RELEVANCE = "relevance"
    COHERENCE = "coherence"
    ENGAGEMENT = "engagement"
    SUCCESS_RATE = "success_rate"
    EFFICIENCY = "efficiency"


@dataclass
class PromptExample:
    """Example for few-shot learning."""

    input_text: str
    expected_output: str
    explanation: Optional[str] = None
    quality_score: float = 0.0
    usage_count: int = 0
    success_indicators: List[str] = field(default_factory=list)


@dataclass
class PromptTemplate:
    """Prompt template with variables and structure."""

    template_id: str
    name: str
    prompt_type: PromptType
    template: str
    variables: List[str] = field(default_factory=list)
    examples: List[PromptExample] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    context_requirements: List[str] = field(default_factory=list)
    performance_metrics: Dict[str, float] = field(default_factory=dict)
    version: str = "1.0"
    created_at: datetime = field(default_factory=datetime.now)
    last_optimized: Optional[datetime] = None
    optimization_history: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class PromptPerformance:
    """Performance tracking for prompts."""

    template_id: str
    total_uses: int = 0
    successful_uses: int = 0
    average_response_time: float = 0.0
    quality_scores: List[float] = field(default_factory=list)
    user_satisfaction: List[float] = field(default_factory=list)
    error_types: List[str] = field(default_factory=list)
    last_used: Optional[datetime] = None
    performance_trends: Dict[str, List[float]] = field(default_factory=dict)


class PromptOptimizer:
    """AI-powered prompt optimization engine."""

    def __init__(self):
        self.templates = {}
        self.performance_data = {}
        self.optimization_strategies = {
            "clarity": self._optimize_for_clarity,
            "specificity": self._optimize_for_specificity,
            "context": self._optimize_for_context,
            "examples": self._optimize_with_examples,
            "constraints": self._optimize_with_constraints,
            "structure": self._optimize_structure,
        }

    def _optimize_for_clarity(self, template: str) -> str:
        """Optimize template for clarity and readability."""
        # Remove redundant words
        clarity_replacements = {
            r"\b(very|really|actually|basically|simply|just|quite)\b": "",
            r"\b(thing|stuff|aspect|element)\b": "component",
            r"\b(way|method|approach)\b": "strategy",
        }

        optimized = template
        for pattern, replacement in clarity_replacements.items():
            optimized = re.sub(pattern, replacement, optimized, flags=re.IGNORECASE)

        # Improve sentence structure
        optimized = re.sub(r"\s+", " ", optimized).strip()
        return optimized

    def _optimize_for_specificity(self, template: str) -> str:
        """Optimize template for specificity and precision."""
        # Add specific instructions
        specificity_additions = {
            "analyze": "Provide detailed analysis with specific examples and supporting evidence",
            "explain": "Give a comprehensive explanation with step-by-step reasoning",
            "summarize": "Create a concise summary highlighting key points and actionable insights",
            "compare": "Provide detailed comparison with pros, cons, and specific differentiators",
            "recommend": "Offer specific recommendations with implementation details and expected outcomes",
        }

        optimized = template
        for action, addition in specificity_additions.items():
            pattern = rf"\b{action}\b"
            if re.search(pattern, optimized, re.IGNORECASE):
                optimized = re.sub(
                    pattern, f"{action} ({addition})", optimized, flags=re.IGNORECASE
                )

        return optimized

    def _optimize_for_context(self, template: str) -> str:
        """Optimize template with better context provision."""
        context_prefix = """Before responding, consider the following context:
- Business environment and industry
- Stakeholder perspectives and needs
- Potential risks and constraints
- Success criteria and desired outcomes

"""

        # Add context instruction if not present
        if "context" not in template.lower():
            return context_prefix + template

        return template

    def _optimize_with_examples(self, template: str) -> str:
        """Add few-shot examples to template."""
        examples_section = """

Example 1:
Input: [Example input]
Output: [High-quality example output with reasoning]

Example 2:
Input: [Another example input]
Output: [Another high-quality example with different scenario]

Follow the pattern demonstrated in the examples above.
"""

        return template + examples_section

    def _optimize_with_constraints(self, template: str) -> str:
        """Add specific constraints and guidelines."""
        constraints_section = """

Constraints and Guidelines:
- Provide evidence-based responses
- Consider multiple perspectives
- Include specific actionable recommendations
- Maintain professional tone and clarity
- Verify information accuracy
"""

        return template + constraints_section

    def _optimize_structure(self, template: str) -> str:
        """Improve template structure and organization."""
        # Add structure markers
        structured_template = """Please provide your response in the following structure:

1. **Analysis/Assessment**
2. **Key Insights/Findings**
3. **Recommendations/Actions**
4. **Implementation Considerations**

"""

        return structured_template + template


class PromptEngineeringManager:
    """Comprehensive prompt engineering and management system."""

    def __init__(self):
        self.templates = {}
        self.performance_data = {}
        self.optimizer = PromptOptimizer()
        self._initialize_default_templates()

    def _initialize_default_templates(self):
        """Initialize with comprehensive default templates."""
        default_templates = [
            PromptTemplate(
                template_id="business_analysis_v1",
                name="Business Analysis Assistant",
                prompt_type=PromptType.SYSTEM,
                template="""You are an expert business analyst with 15+ years of experience across multiple industries. Your role is to provide strategic, data-driven insights and recommendations.

**Your Expertise:**
- Market analysis and competitive intelligence
- Financial performance evaluation
- Operational efficiency assessment
- Strategic planning and roadmap development
- Risk identification and mitigation

**Analysis Framework:**
1. Situation Assessment: Current state analysis
2. Problem Identification: Key challenges and opportunities
3. Impact Analysis: Potential consequences and benefits
4. Recommendation Development: Specific, actionable solutions
5. Implementation Planning: Timeline and resource requirements

**Communication Style:**
- Use clear, professional language
- Provide specific examples and evidence
- Include quantifiable metrics where possible
- Offer multiple perspectives when relevant
- Focus on practical, implementable solutions""",
                variables=["industry", "company_size", "analysis_type", "timeframe"],
                constraints=[
                    "Base recommendations on available data",
                    "Consider multiple stakeholder perspectives",
                    "Provide implementation timeline",
                    "Include risk assessment",
                ],
                context_requirements=[
                    "Industry context",
                    "Company size and structure",
                    "Current business challenges",
                    "Available resources",
                ],
            ),
            PromptTemplate(
                template_id="customer_success_v1",
                name="Customer Success Manager",
                prompt_type=PromptType.SYSTEM,
                template="""You are an expert customer success manager with deep expertise in customer retention, engagement, and growth strategies.

**Your Mission:**
Ensure customers achieve their desired outcomes while maximizing customer lifetime value and minimizing churn.

**Core Responsibilities:**
- Customer health monitoring and risk assessment
- Proactive engagement and issue resolution
- Value realization and success measurement
- Growth opportunity identification
- Retention strategy development

**Success Framework:**
1. Customer Onboarding Excellence
2. Value Demonstration and Tracking
3. Proactive Support and Issue Resolution
4. Growth and Expansion Opportunities
5. Retention and Loyalty Building

**Communication Approach:**
- Empathetic and solution-focused
- Data-driven recommendations
- Proactive rather than reactive
- Customer-centric perspective
- Clear action items and next steps""",
                variables=["customer_segment", "industry", "business_model", "success_metrics"],
                constraints=[
                    "Focus on customer outcomes",
                    "Use data to support recommendations",
                    "Consider customer resource constraints",
                    "Align with customer business goals",
                ],
            ),
            PromptTemplate(
                template_id="sales_assistant_v1",
                name="Sales Process Optimizer",
                prompt_type=PromptType.SYSTEM,
                template="""You are a senior sales operations expert specializing in B2B sales process optimization, lead qualification, and revenue acceleration.

**Sales Process Excellence Areas:**
- Lead qualification and scoring
- Sales pipeline optimization
- Customer engagement strategies
- Objection handling techniques
- Closing methodologies
- Performance analytics

**Systematic Approach:**
1. Lead Assessment: Qualification criteria and scoring
2. Engagement Strategy: Personalized outreach and follow-up
3. Value Proposition: Customized solution presentation
4. Objection Resolution: Proactive addressing of concerns
5. Closing Execution: Effective closing techniques
6. Follow-up Excellence: Post-sale engagement

**Performance Optimization:**
- Data-driven decision making
- Continuous process improvement
- Sales team enablement
- Customer experience enhancement
- Revenue growth acceleration""",
                variables=["sales_stage", "prospect_type", "industry", "deal_size", "timeline"],
                constraints=[
                    "Focus on qualified prospects",
                    "Provide measurable outcomes",
                    "Consider sales team capacity",
                    "Include follow-up strategies",
                ],
            ),
            PromptTemplate(
                template_id="data_analyst_v1",
                name="Business Intelligence Analyst",
                prompt_type=PromptType.SYSTEM,
                template="""You are a senior data analyst and business intelligence expert with expertise in statistical analysis, data visualization, and actionable insight generation.

**Analytical Capabilities:**
- Statistical analysis and modeling
- Data mining and pattern recognition
- Trend analysis and forecasting
- Performance measurement and KPI development
- A/B testing and experimental design
- Predictive analytics and modeling

**Analysis Methodology:**
1. Data Assessment: Quality, completeness, and relevance evaluation
2. Exploratory Analysis: Pattern identification and hypothesis generation
3. Statistical Analysis: Rigorous testing and validation
4. Insight Generation: Actionable findings and recommendations
5. Visualization Creation: Clear, compelling data presentation
6. Strategic Recommendations: Business-focused conclusions

**Quality Standards:**
- Methodologically sound analysis
- Reproducible and transparent methodology
- Clear interpretation of statistical significance
- Practical business implications
- Confidence intervals and uncertainty quantification""",
                variables=[
                    "data_type",
                    "analysis_goal",
                    "time_period",
                    "business_context",
                    "stakeholder_type",
                ],
                constraints=[
                    "Validate data quality",
                    "Use appropriate statistical methods",
                    "Interpret results in business context",
                    "Include confidence measures",
                ],
            ),
        ]

        for template in default_templates:
            self.add_template(template)

    def add_template(self, template: PromptTemplate):
        """Add a new prompt template."""
        self.templates[template.template_id] = template
        self.performance_data[template.template_id] = PromptPerformance(
            template_id=template.template_id
        )
        logger.info(f"Added prompt template: {template.name}")

    def get_template(self, template_id: str) -> Optional[PromptTemplate]:
        """Get a specific prompt template."""
        return self.templates.get(template_id)

    def generate_prompt(
        self, template_id: str, variables: Dict[str, Any], context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Generate a complete prompt from template with variables."""
        template = self.get_template(template_id)
        if not template:
            raise ValueError(f"Template {template_id} not found")

        # Fill in template variables
        prompt = template.template
        for var_name, var_value in variables.items():
            if var_name in template.variables:
                placeholder = f"{{{var_name}}}"
                if placeholder in prompt:
                    prompt = prompt.replace(placeholder, str(var_value))

        # Add context if provided
        if context:
            context_section = self._generate_context_section(context)
            if context_section:
                prompt = context_section + "\n\n" + prompt

        # Add few-shot examples if available
        if template.examples:
            examples_section = self._generate_examples_section(template.examples)
            prompt = prompt + "\n\n" + examples_section

        return prompt

    def _generate_context_section(self, context: Dict[str, Any]) -> str:
        """Generate context section for prompt."""
        if not context:
            return ""

        context_lines = ["**Context:**"]
        for key, value in context.items():
            if isinstance(value, (dict, list)):
                value = json.dumps(value, indent=2)
            context_lines.append(f"- {key.replace('_', ' ').title()}: {value}")

        return "\n".join(context_lines)

    def _generate_examples_section(self, examples: List[PromptExample]) -> str:
        """Generate examples section for prompt."""
        if not examples:
            return ""

        lines = ["**Examples:**"]
        for i, example in enumerate(examples[:3], 1):  # Limit to 3 examples
            lines.append(f"\nExample {i}:")
            lines.append(f"Input: {example.input_text}")
            lines.append(f"Output: {example.expected_output}")
            if example.explanation:
                lines.append(f"Reasoning: {example.explanation}")

        return "\n".join(lines)

    def optimize_template(
        self, template_id: str, optimization_strategies: List[str]
    ) -> PromptTemplate:
        """Optimize a template using specified strategies."""
        template = self.get_template(template_id)
        if not template:
            raise ValueError(f"Template {template_id} not found")

        original_template = template.template
        optimized_template = original_template

        # Apply optimization strategies
        for strategy in optimization_strategies:
            if strategy in self.optimizer.optimization_strategies:
                optimized_template = self.optimizer.optimization_strategies[strategy](
                    optimized_template
                )

        # Update template with optimized version
        if optimized_template != original_template:
            template.template = optimized_template
            template.last_optimized = datetime.now()
            template.optimization_history.append(
                {
                    "timestamp": datetime.now().isoformat(),
                    "strategies_applied": optimization_strategies,
                    "original_length": len(original_template),
                    "optimized_length": len(optimized_template),
                }
            )
            logger.info(
                f"Optimized template {template_id} using {', '.join(optimization_strategies)}"
            )

        return template

    def add_example(
        self,
        template_id: str,
        input_text: str,
        expected_output: str,
        explanation: Optional[str] = None,
    ) -> bool:
        """Add a few-shot example to a template."""
        template = self.get_template(template_id)
        if not template:
            return False

        example = PromptExample(
            input_text=input_text, expected_output=expected_output, explanation=explanation
        )

        template.examples.append(example)
        logger.info(f"Added example to template {template_id}")
        return True

    def record_performance(
        self,
        template_id: str,
        success: bool,
        response_time: float,
        quality_score: Optional[float] = None,
        user_satisfaction: Optional[float] = None,
        error_type: Optional[str] = None,
    ):
        """Record performance metrics for a prompt."""
        if template_id not in self.performance_data:
            self.performance_data[template_id] = PromptPerformance(template_id=template_id)

        perf = self.performance_data[template_id]
        perf.total_uses += 1
        perf.last_used = datetime.now()

        if success:
            perf.successful_uses += 1

        # Update response time (rolling average)
        if perf.average_response_time == 0:
            perf.average_response_time = response_time
        else:
            perf.average_response_time = (perf.average_response_time * 0.9) + (response_time * 0.1)

        if quality_score is not None:
            perf.quality_scores.append(quality_score)
            # Keep only last 100 scores
            if len(perf.quality_scores) > 100:
                perf.quality_scores = perf.quality_scores[-100:]

        if user_satisfaction is not None:
            perf.user_satisfaction.append(user_satisfaction)
            # Keep only last 100 scores
            if len(perf.user_satisfaction) > 100:
                perf.user_satisfaction = perf.user_satisfaction[-100:]

        if error_type:
            perf.error_types.append(error_type)

    def get_template_performance(self, template_id: str) -> Optional[Dict[str, Any]]:
        """Get performance metrics for a template."""
        if template_id not in self.performance_data:
            return None

        perf = self.performance_data[template_id]
        success_rate = (perf.successful_uses / perf.total_uses * 100) if perf.total_uses > 0 else 0

        result = {
            "template_id": template_id,
            "total_uses": perf.total_uses,
            "successful_uses": perf.successful_uses,
            "success_rate": success_rate,
            "average_response_time": perf.average_response_time,
            "last_used": perf.last_used.isoformat() if perf.last_used else None,
        }

        if perf.quality_scores:
            result["quality_scores"] = {
                "average": statistics.mean(perf.quality_scores),
                "median": statistics.median(perf.quality_scores),
                "latest": perf.quality_scores[-1],
            }

        if perf.user_satisfaction:
            result["user_satisfaction"] = {
                "average": statistics.mean(perf.user_satisfaction),
                "median": statistics.median(perf.user_satisfaction),
                "latest": perf.user_satisfaction[-1],
            }

        if perf.error_types:
            from collections import Counter

            error_counts = Counter(perf.error_types)
            result["common_errors"] = dict(error_counts.most_common(5))

        return result

    def recommend_templates(self, use_case: str, context: Dict[str, Any]) -> List[PromptTemplate]:
        """Recommend best templates for a specific use case."""
        recommendations = []

        for template in self.templates.values():
            score = self._calculate_template_relevance_score(template, use_case, context)
            if score > 0.3:  # Minimum relevance threshold
                recommendations.append((score, template))

        # Sort by relevance score
        recommendations.sort(key=lambda x: x[0], reverse=True)
        return [template for score, template in recommendations]

    def _calculate_template_relevance_score(
        self, template: PromptTemplate, use_case: str, context: Dict[str, Any]
    ) -> float:
        """Calculate relevance score for template recommendations."""
        score = 0.0
        use_case_lower = use_case.lower()

        # Name matching
        if template.name.lower() in use_case_lower:
            score += 0.5

        # Template content matching
        template_content = template.template.lower()
        for keyword in use_case_lower.split():
            if keyword in template_content:
                score += 0.1

        # Context matching
        for req in template.context_requirements:
            for context_key, context_value in context.items():
                if req.lower() in context_key.lower() or req.lower() in str(context_value).lower():
                    score += 0.2

        # Performance bonus
        if template.template_id in self.performance_data:
            perf = self.performance_data[template.template_id]
            if perf.total_uses > 0 and perf.successful_uses / perf.total_uses > 0.8:
                score += 0.3

        return min(score, 1.0)  # Cap at 1.0

    def create_specialized_template(
        self, name: str, base_template_id: str, customizations: Dict[str, Any], use_case: str
    ) -> str:
        """Create a specialized template based on an existing one."""
        base_template = self.get_template(base_template_id)
        if not base_template:
            raise ValueError(f"Base template {base_template_id} not found")

        # Generate unique ID
        template_id = (
            f"{use_case.lower().replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )

        # Create specialized template
        specialized_template = PromptTemplate(
            template_id=template_id,
            name=f"{name} ({use_case})",
            prompt_type=base_template.prompt_type,
            template=base_template.template,
            variables=base_template.variables.copy(),
            constraints=base_template.constraints.copy(),
            context_requirements=base_template.context_requirements.copy(),
        )

        # Apply customizations
        if "template_modifications" in customizations:
            for old_text, new_text in customizations["template_modifications"].items():
                specialized_template.template = specialized_template.template.replace(
                    old_text, new_text
                )

        if "additional_constraints" in customizations:
            specialized_template.constraints.extend(customizations["additional_constraints"])

        if "context_requirements" in customizations:
            specialized_template.context_requirements.extend(customizations["context_requirements"])

        self.add_template(specialized_template)
        return template_id


# Global prompt engineering manager instance
prompt_manager = PromptEngineeringManager()


def get_prompt_manager() -> PromptEngineeringManager:
    """Get the global prompt engineering manager instance."""
    return prompt_manager


def create_business_prompt(agent_role: str, business_context: Dict[str, Any]) -> str:
    """Create an optimized prompt for a specific business use case."""
    manager = get_prompt_manager()

    # Map agent roles to template IDs
    role_to_template = {
        "sales_assistant": "sales_assistant_v1",
        "customer_success": "customer_success_v1",
        "business_intelligence": "data_analyst_v1",
        "business_analyst": "business_analysis_v1",
    }

    template_id = role_to_template.get(agent_role, "business_analysis_v1")

    # Generate prompt with business context
    variables = {
        "industry": business_context.get("industry", "general"),
        "company_size": business_context.get("company_size", "medium"),
        "business_model": business_context.get("business_model", "B2B"),
        "current_challenges": business_context.get("challenges", "efficiency and growth"),
    }

    return manager.generate_prompt(template_id, variables, business_context)
