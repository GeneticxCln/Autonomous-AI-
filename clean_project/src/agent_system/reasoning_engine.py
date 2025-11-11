"""
Core AI reasoning engine for autonomous agent.
This implements actual intelligence, not just framework.
"""

from __future__ import annotations

import logging
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from .config_simple import settings
from .unified_config import unified_config

# Initialize variables for optional imports
SENTENCE_TRANSFORMERS_AVAILABLE = False
NUMPY_AVAILABLE = False

# Try to import sentence transformers for semantic similarity
try:
    from sentence_transformers import SentenceTransformer

    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    pass  # Keep as False

# Try to import numpy for similarity calculations
# Numpy import with a typing-friendly fallback
np: Any = None
try:
    import numpy as _np
    np = _np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

    def _np_dot(a: List[float], b: List[float]) -> float:
        return float(sum(x * y for x, y in zip(a, b)))

    def _np_norm(x: List[float]) -> float:
        return float(sum(xi * xi for xi in x) ** 0.5)

    class _LinalgFallback:
        @staticmethod
        def norm(x: List[float]) -> float:
            return _np_norm(x)

    class _NPFallback:
        @staticmethod
        def dot(a: List[float], b: List[float]) -> float:
            return _np_dot(a, b)

    # Compose a minimal object with the required attributes
    np = type("_NP", (), {"dot": staticmethod(_NPFallback.dot), "linalg": _LinalgFallback()})()

logger = logging.getLogger(__name__)


class ReasoningEngine:
    """Core AI reasoning engine for goal analysis and action planning."""

    def __init__(self) -> None:
        self.goal_patterns: Dict[str, Any] = self._load_goal_patterns()
        self.action_templates: Dict[str, Dict[str, Any]] = self._load_action_templates()
        self.success_patterns: Dict[str, List[Dict[str, Any]]] = {}
        self.semantic_similarity_enabled: bool = False
        self.model: Any | None = None
        self.pattern_embeddings: Dict[str, Any] = {}

        # Determine whether semantic similarity should be enabled (requires network + optional deps)
        disable_flag = os.getenv("DISABLE_SEMANTIC_SIMILARITY", "").lower() == "true"
        self.semantic_similarity_enabled = (
            unified_config.ai.enable_semantic_similarity
            and not getattr(settings, "TERMINAL_ONLY", False)
            and not disable_flag
        )

        # Enforce strict mode for embeddings availability
        if unified_config.strict_mode and self.semantic_similarity_enabled:
            if not SENTENCE_TRANSFORMERS_AVAILABLE or not NUMPY_AVAILABLE:
                raise RuntimeError(
                    "Strict mode: sentence-transformers and numpy are required for semantic similarity"
                )

        # Initialize semantic similarity components
        if self.semantic_similarity_enabled and SENTENCE_TRANSFORMERS_AVAILABLE and NUMPY_AVAILABLE:
            logger.info(
                "Loading sentence transformer model for semantic similarity (model=%s)",
                unified_config.ai.sentence_transformer_model,
            )
            try:
                self.model = SentenceTransformer(unified_config.ai.sentence_transformer_model)
                self.pattern_embeddings = self._precompute_embeddings()
            except Exception as e:
                logger.warning(
                    "Failed to load sentence transformer (%s). Using fallback similarity.",
                    e,
                )
                if unified_config.strict_mode:
                    raise
                self.model = None
                self.pattern_embeddings = {}
                self._setup_fallback_similarity()
        else:
            if not self.semantic_similarity_enabled:
                logger.info(
                    "Semantic similarity disabled (terminal_only=%s, disable_flag=%s). "
                    "Using fallback heuristics.",
                    getattr(settings, "TERMINAL_ONLY", False),
                    disable_flag,
                )
            elif not SENTENCE_TRANSFORMERS_AVAILABLE or not NUMPY_AVAILABLE:
                if unified_config.strict_mode:
                    raise RuntimeError(
                        "Strict mode: sentence-transformers and numpy are required for semantic similarity"
                    )
                logger.warning("Sentence transformers or numpy not available, using fallback similarity")
            self.model = None
            self.pattern_embeddings = {}
            self._setup_fallback_similarity()

    def _load_goal_patterns(self) -> Dict[str, Any]:
        """Load common goal patterns for intelligent decomposition."""
        return {
            "research": {
                "keywords": ["research", "find", "investigate", "analyze", "study", "explore"],
                "actions": [
                    "search_information",
                    "gather_data",
                    "analyze_sources",
                    "synthesize_findings",
                ],
                "outcome": "comprehensive_report",
            },
            "file_analysis": {
                "keywords": ["analyze file", "read file", "process data", "extract information"],
                "actions": ["load_data", "parse_content", "extract_insights", "generate_summary"],
                "outcome": "analysis_report",
            },
            "code_generation": {
                "keywords": ["generate code", "create script", "write program", "implement"],
                "actions": ["design_solution", "write_code", "test_implementation", "optimize"],
                "outcome": "working_code",
            },
            "web_search": {
                "keywords": ["search web", "find online", "browse", "query"],
                "actions": [
                    "formulate_query",
                    "execute_search",
                    "filter_results",
                    "compile_findings",
                ],
                "outcome": "search_results",
            },
        }

    def _load_action_templates(self) -> Dict[str, Dict[str, Any]]:
        """Load action templates with parameters."""
        search_tool = "generic_tool" if settings.TERMINAL_ONLY else "web_search"
        return {
            "search_information": {
                "tool": search_tool,
                "parameters": {"query": "", "max_results": 10},
                "description": "Search for information on a specific topic",
            },
            "load_data": {
                "tool": "file_reader",
                "parameters": {"filepath": "", "format": "auto"},
                "description": "Load and parse data from a file",
            },
            "execute_code": {
                "tool": "code_executor",
                "parameters": {"code": "", "language": "python"},
                "description": "Execute code to perform calculations or transformations",
            },
            "save_results": {
                "tool": "file_writer",
                "parameters": {"filepath": "", "content": "", "format": "json"},
                "description": "Save analysis results to file",
            },
        }

    def analyze_goal(self, goal_description: str) -> Dict[str, Any]:
        """Intelligently analyze a goal and suggest approach."""

        goal_lower = goal_description.lower()

        # Find matching pattern
        best_match = None
        best_score = 0

        for pattern_name, pattern in self.goal_patterns.items():
            score = 0
            for keyword in pattern["keywords"]:
                if keyword in goal_lower:
                    score += 1

            if score > best_score:
                best_score = score
                best_match = pattern_name

        if best_match:
            pattern = self.goal_patterns[best_match]

            # Extract specific parameters from goal
            parameters = self._extract_parameters(goal_description, pattern)

            return {
                "pattern": best_match,
                "pattern_name": best_match,
                "confidence": best_score / len(pattern["keywords"]),
                "suggested_actions": pattern["actions"],
                "outcome_type": pattern["outcome"],
                "parameters": parameters,
                "complexity": self._assess_complexity(goal_description),
            }

        # Fallback for unrecognized goals
        return {
            "pattern": "generic",
            "confidence": 0.1,
            "suggested_actions": ["analyze_requirements", "plan_approach", "execute_plan"],
            "outcome_type": "task_completion",
            "parameters": {"description": goal_description},
            "complexity": self._assess_complexity(goal_description),
        }

    def _extract_parameters(self, goal_description: str, pattern: Dict[str, Any]) -> Dict[str, Any]:
        """Extract specific parameters from goal description."""
        parameters = {}

        # Extract file paths
        file_patterns = [
            r'["\']([^"\']*\.txt)["\']',
            r'["\']([^"\']*\.json)["\']',
            r'["\']([^"\']*\.csv)["\']',
            r'["\']([^"\']*\.py)["\']',
        ]

        for file_pattern in file_patterns:
            matches = re.findall(file_pattern, goal_description)
            if matches:
                parameters["target_files"] = matches

        # Extract numbers for calculations
        number_matches = re.findall(r"\b(\d+(?:\.\d+)?)\b", goal_description)
        if number_matches:
            parameters["numeric_values"] = [float(n) for n in number_matches]

        # Extract keywords for search
        # Note: We don't have the pattern name here, so we'll check the description
        if (
            "research" in goal_description.lower()
            or "find" in goal_description.lower()
            or "search" in goal_description.lower()
        ):
            search_terms = []
            # Remove common words and extract meaningful terms
            words = goal_description.split()
            for word in words:
                if len(word) > 3 and word.lower() not in [
                    "the",
                    "and",
                    "for",
                    "with",
                    "from",
                    "about",
                ]:
                    search_terms.append(word)
            if search_terms:
                parameters["search_terms"] = search_terms[:5]  # Limit to top 5

        return parameters

    def _assess_complexity(self, goal_description: str) -> str:
        """Assess goal complexity based on various factors."""
        complexity_score = 0

        # Length factor
        if len(goal_description) > 100:
            complexity_score += 2
        elif len(goal_description) > 50:
            complexity_score += 1

        # Multiple requirements
        if "and" in goal_description.lower():
            complexity_score += 2

        # Technical terms
        technical_terms = ["api", "database", "algorithm", "analysis", "optimization"]
        for term in technical_terms:
            if term in goal_description.lower():
                complexity_score += 1

        # Decision logic
        if complexity_score <= 1:
            return "simple"
        elif complexity_score <= 3:
            return "moderate"
        else:
            return "complex"

    def generate_action_plan(self, goal_analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate intelligent action plan based on goal analysis."""

        plan: List[Dict[str, Any]] = []
        pattern = goal_analysis["pattern"]
        parameters = goal_analysis["parameters"]
        actions = goal_analysis["suggested_actions"]

        for i, action_name in enumerate(actions):
            if action_name in self.action_templates:
                template = self.action_templates[action_name]
                action = {
                    "id": f"{pattern}_{action_name}_{i}",
                    "name": action_name,
                    "tool_name": template["tool"],
                    "description": template["description"],
                    "parameters": self._customize_parameters(
                        template["parameters"], parameters, action_name
                    ),
                    "prerequisites": [plan[-1]["id"]] if plan else [],
                    "estimated_outcome": self._predict_outcome(action_name, pattern),
                }
                plan.append(action)

        return plan

    def _customize_parameters(
        self, base_params: Dict[str, Any], goal_params: Dict[str, Any], action_name: str
    ) -> Dict[str, Any]:
        """Customize action parameters based on goal context."""

        params = base_params.copy()

        if action_name == "search_information":
            if "search_terms" in goal_params:
                params["query"] = " ".join(goal_params["search_terms"])
            elif "description" in goal_params:
                params["query"] = goal_params["description"]
            # Enrich search for real-world usage
            params.setdefault("max_results", 5)
            params.setdefault("fetch", True)
            params.setdefault("fetch_limit", 1)

        elif action_name == "load_data":
            if "target_files" in goal_params:
                params["filepath"] = goal_params["target_files"][0]  # Use first file

        elif action_name == "execute_code":
            if action_name == "execute_code":
                if "numeric_values" in goal_params:
                    # Generate calculation code based on numbers found
                    numbers = goal_params["numeric_values"]
                    if len(numbers) >= 2:
                        params[
                            "code"
                        ] = f"""
# Calculate statistics for: {numbers}
data = {numbers}
result = {{
    'sum': sum(data),
    'average': sum(data) / len(data),
    'min': min(data),
    'max': max(data),
    'count': len(data)
}}
print(f"Statistics: {{result}}")
"""

        return params

    def _predict_outcome(self, action_name: str, pattern: str) -> str:
        """Predict likely outcome for an action."""

        outcome_map = {
            "search_information": "relevant_information_found",
            "load_data": "data_successfully_loaded",
            "execute_code": "calculations_completed",
            "analyze_sources": "insights_extracted",
            "synthesize_findings": "comprehensive_analysis",
            "save_results": "results_persisted",
        }

        return outcome_map.get(action_name, "task_completed")

    def evaluate_action_success(self, action: Dict[str, Any], observation: Dict[str, Any]) -> float:
        """Evaluate how successful an action was (0.0 to 1.0)."""

        expected_outcome = action.get("estimated_outcome", "")

        # Base score from observation status
        status = observation.get("status", "failure")
        if status == "success":
            base_score = 0.8
        elif status == "partial":
            base_score = 0.5
        else:
            base_score = 0.1

        # Adjust based on outcome matching
        result = observation.get("result", {})
        if isinstance(result, dict):
            if expected_outcome in str(result).lower():
                base_score += 0.2
            if "error" in str(result).lower():
                base_score -= 0.3

        return min(1.0, max(0.0, base_score))

    def learn_from_episode(
        self, goal_analysis: Dict[str, Any], actions: List[Dict[str, Any]], success_score: float
    ) -> None:
        """Learn from completed episodes to improve future performance."""

        pattern = goal_analysis["pattern"]
        action_sequence = [action["name"] for action in actions]

        # Store successful patterns
        if success_score > 0.7:
            if pattern not in self.success_patterns:
                self.success_patterns[pattern] = []

            self.success_patterns[pattern].append(
                {
                    "sequence": action_sequence,
                    "score": success_score,
                    "timestamp": datetime.now().isoformat(),
                    "parameters": goal_analysis.get("parameters", {}),
                }
            )

            # Keep only best patterns (limit to 10)
            self.success_patterns[pattern].sort(key=lambda x: x["score"], reverse=True)
            self.success_patterns[pattern] = self.success_patterns[pattern][:10]

            logger.info(f"Learned pattern for {pattern}: {' -> '.join(action_sequence)}")

    def get_best_practice(self, pattern: str) -> Optional[Dict[str, Any]]:
        """Get best practice for a given pattern."""

        if pattern in self.success_patterns and self.success_patterns[pattern]:
            return self.success_patterns[pattern][0]  # Return highest scoring pattern

        return None

    def _precompute_embeddings(self) -> Dict[str, Any]:
        """Precompute embeddings for all goal patterns for faster similarity calculation."""
        embeddings = {}

        for pattern_name, pattern in self.goal_patterns.items():
            # Create a representative text for each pattern
            pattern_text = f"{pattern_name.replace('_', ' ')} {pattern.get('description', '')} {', '.join(pattern.get('keywords', []))}"
            if self.model:
                embeddings[pattern_name] = self.model.encode(pattern_text)
            else:
                # Fallback: create mock embeddings
                embeddings[pattern_name] = np.random.rand(384)  # Standard dimension

        return embeddings

    def _setup_fallback_similarity(self) -> None:
        """Setup fallback similarity using TF-IDF-like approach."""
        self.pattern_keywords = {}
        for pattern_name, pattern in self.goal_patterns.items():
            keywords = pattern.get("keywords", [])
            # Create TF-IDF style weights
            self.pattern_keywords[pattern_name] = {
                "keywords": keywords,
                "weights": {kw: 1.0 for kw in keywords},
                "expanded_terms": self._expand_keywords(keywords),
            }

    def _expand_keywords(self, keywords: List[str]) -> List[str]:
        """Expand keywords with related terms for better matching."""
        expansion_map = {
            "research": ["investigate", "explore", "study", "analyze", "find", "discover"],
            "analyze": ["examine", "evaluate", "assess", "investigate", "study"],
            "search": ["find", "query", "lookup", "discover", "locate"],
            "code": ["program", "script", "develop", "implement", "build"],
            "file": ["document", "read", "process", "parse", "load"],
            "data": ["information", "content", "dataset", "records"],
            "web": ["internet", "online", "browser", "website"],
            "generate": ["create", "build", "make", "produce", "write"],
            "find": ["locate", "discover", "search", "search_for", "query"],
        }

        expanded = set(keywords)
        for keyword in keywords:
            if keyword in expansion_map:
                expanded.update(expansion_map[keyword])

        return list(expanded)

    def calculate_similarity_score(self, goal_text: str, pattern_name: str) -> float:
        """Calculate similarity score between goal and pattern using semantic similarity."""
        if not self.model or pattern_name not in self.pattern_embeddings:
            return self._fallback_similarity(goal_text, pattern_name)

        try:
            # Encode the goal text
            goal_embedding = self.model.encode(goal_text)
            pattern_embedding = self.pattern_embeddings[pattern_name]

            # Calculate cosine similarity using numpy
            if NUMPY_AVAILABLE:
                similarity = float(
                    np.dot(goal_embedding, pattern_embedding)
                    / (np.linalg.norm(goal_embedding) * np.linalg.norm(pattern_embedding))
                )
            else:
                # Manual cosine similarity calculation
                dot_product = sum(a * b for a, b in zip(goal_embedding, pattern_embedding))
                norm_goal = sum(a * a for a in goal_embedding) ** 0.5
                norm_pattern = sum(a * a for a in pattern_embedding) ** 0.5
                similarity = (
                    dot_product / (norm_goal * norm_pattern) if norm_goal * norm_pattern > 0 else 0
                )

            return float(max(0.0, float(similarity)))  # Ensure non-negative
        except Exception as e:
            logger.warning(f"Error calculating similarity: {e}")
            return self._fallback_similarity(goal_text, pattern_name)

    def _fallback_similarity(self, goal_text: str, pattern_name: str) -> float:
        """Fallback similarity calculation using keyword expansion and weighting."""
        if not hasattr(self, "pattern_keywords"):
            return 0.0

        goal_lower = goal_text.lower()
        pattern_info = self.pattern_keywords.get(pattern_name, {})
        keywords = pattern_info.get("keywords", [])
        expanded_terms = pattern_info.get("expanded_terms", [])

        # Score based on direct keyword matches
        direct_matches = sum(1 for kw in keywords if kw in goal_lower)

        # Score based on expanded term matches
        expanded_matches = sum(0.5 for term in expanded_terms if term in goal_lower)

        # Normalize by total possible matches
        total_possible = len(keywords) + len(expanded_terms) * 0.5
        if total_possible > 0:
            return (direct_matches + expanded_matches) / total_possible

        return 0.0

    def enhanced_analyze_goal(self, goal_description: str) -> Dict[str, Any]:
        """Enhanced goal analysis using both keyword matching and semantic similarity."""

        goal_lower = goal_description.lower()

        # Method 1: Keyword-based matching (current approach)
        keyword_scores = self._keyword_match_analysis(goal_lower)

        # Method 2: Semantic similarity (new approach)
        semantic_scores = {}
        if self.model:
            for pattern_name in self.goal_patterns.keys():
                semantic_scores[pattern_name] = self.calculate_similarity_score(
                    goal_description, pattern_name
                )

        # Combine scores
        combined_scores = self._combine_matching_methods(keyword_scores, semantic_scores)

        # Find best match
        if combined_scores:
            best_match = max(combined_scores.items(), key=lambda x: x[1]["combined_score"])
            pattern_name, score_info = best_match

            if score_info["combined_score"] > 0.1:  # Minimum confidence threshold
                pattern = self.goal_patterns[pattern_name]

                # Extract specific parameters from goal
                parameters = self._extract_parameters(goal_description, pattern)

                return {
                    "pattern": pattern_name,
                    "pattern_name": pattern_name,
                    "confidence": score_info["combined_score"],
                    "keyword_confidence": score_info.get("keyword_score", 0),
                    "semantic_confidence": score_info.get("semantic_score", 0),
                    "suggested_actions": pattern["actions"],
                    "outcome_type": pattern["outcome"],
                    "parameters": parameters,
                    "complexity": self._assess_complexity(goal_description),
                    "analysis_method": "enhanced_semantic",
                    "explanation": self._generate_analysis_explanation(
                        goal_description, pattern_name, score_info
                    ),
                }

        # Fallback for unrecognized goals
        return {
            "pattern": "generic",
            "confidence": 0.1,
            "keyword_confidence": 0.1,
            "semantic_confidence": 0.0,
            "suggested_actions": ["analyze_requirements", "plan_approach", "execute_plan"],
            "outcome_type": "task_completion",
            "parameters": {"description": goal_description},
            "complexity": self._assess_complexity(goal_description),
            "analysis_method": "fallback",
            "explanation": "No strong pattern match found, using generic approach",
        }

    def _keyword_match_analysis(self, goal_lower: str) -> Dict[str, float]:
        """Analyze goal using keyword matching (original approach)."""
        scores = {}

        for pattern_name, pattern in self.goal_patterns.items():
            score = 0
            for keyword in pattern["keywords"]:
                if keyword in goal_lower:
                    score += 1
            scores[pattern_name] = score / len(pattern["keywords"]) if pattern["keywords"] else 0

        return scores

    def _combine_matching_methods(
        self, keyword_scores: Dict[str, float], semantic_scores: Dict[str, float]
    ) -> Dict[str, Dict[str, float]]:
        """Combine keyword and semantic matching scores intelligently."""
        combined = {}

        for pattern_name in self.goal_patterns.keys():
            keyword_score = keyword_scores.get(pattern_name, 0)
            semantic_score = semantic_scores.get(pattern_name, 0) if semantic_scores else 0

            # Weighted combination: 60% semantic, 40% keyword
            if semantic_scores and self.model:
                combined_score = (0.6 * semantic_score) + (0.4 * keyword_score)
            else:
                # Fallback to keyword-only if semantic not available
                combined_score = keyword_score

            combined[pattern_name] = {
                "combined_score": combined_score,
                "keyword_score": keyword_score,
                "semantic_score": semantic_score,
            }

        return combined

    def _generate_analysis_explanation(
        self, goal_text: str, pattern_name: str, score_info: Dict[str, float]
    ) -> str:
        """Generate human-readable explanation of the analysis."""
        keyword_score = score_info.get("keyword_score", 0)
        semantic_score = score_info.get("semantic_score", 0)

        if semantic_score > 0.7:
            confidence_level = "very high"
        elif semantic_score > 0.5:
            confidence_level = "high"
        elif semantic_score > 0.3:
            confidence_level = "moderate"
        else:
            confidence_level = "low"

        return (
            f"Goal matched to '{pattern_name}' pattern with {confidence_level} confidence. "
            f"Semantic similarity: {semantic_score:.2f}, Keyword match: {keyword_score:.2f}. "
            f"Text analysis shows {len(goal_text.split())} words focusing on {self._extract_main_topics(goal_text)}."
        )

    def _extract_main_topics(self, goal_text: str) -> str:
        """Extract main topics from goal text for explanation."""
        # Simple topic extraction based on pattern keywords
        goal_lower = goal_text.lower()
        topics = []

        topic_keywords = {
            "research": ["research", "investigate", "explore", "study"],
            "analysis": ["analyze", "examine", "evaluate", "assess"],
            "code": ["code", "program", "script", "develop", "implement"],
            "data": ["data", "file", "process", "parse", "load"],
            "web": ["web", "search", "browse", "online", "internet"],
        }

        for topic, keywords in topic_keywords.items():
            if any(kw in goal_lower for kw in keywords):
                topics.append(topic)

        return ", ".join(topics) if topics else "general task"


# Global reasoning engine instance
reasoning_engine = ReasoningEngine()
