"""
Cross-session learning system for persistent knowledge between agent runs.
"""
from __future__ import annotations

import json
import logging
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from collections import defaultdict, deque

logger = logging.getLogger(__name__)

# Knowledge storage directory
KNOWLEDGE_DIR = Path(".agent_knowledge")
KNOWLEDGE_DIR.mkdir(exist_ok=True)


@dataclass
class KnowledgePattern:
    """Represents a learned knowledge pattern."""
    pattern_id: str
    pattern_type: str  # 'goal_pattern', 'action_sequence', 'tool_success'
    description: str
    success_rate: float
    usage_count: int
    last_used: datetime
    created_at: datetime
    confidence_score: float
    parameters: Dict[str, Any]
    version: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            'last_used': self.last_used.isoformat(),
            'created_at': self.created_at.isoformat()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> KnowledgePattern:
        data['last_used'] = datetime.fromisoformat(data['last_used'])
        data['created_at'] = datetime.fromisoformat(data['created_at'])
        return cls(**data)


@dataclass
class LearningSession:
    """Represents a learning session."""
    session_id: str
    start_time: datetime
    end_time: Optional[datetime]
    goals_attempted: int
    goals_completed: int
    total_success_rate: float
    knowledge_gained: int
    knowledge_used: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat() if self.end_time else None
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> LearningSession:
        data['start_time'] = datetime.fromisoformat(data['start_time'])
        if data['end_time']:
            data['end_time'] = datetime.fromisoformat(data['end_time'])
        return cls(**data)


class CrossSessionLearningSystem:
    """Manages learning and knowledge transfer between agent sessions."""

    def __init__(self):
        self.knowledge_patterns: Dict[str, KnowledgePattern] = {}
        self.session_history: List[LearningSession] = []
        self.current_session: Optional[LearningSession] = None
        self.knowledge_decay_rate = 0.05  # Knowledge loses value over time
        self.max_patterns = 1000  # Maximum patterns to store
        self.confidence_threshold = 0.6  # Minimum confidence for pattern adoption

        # Load existing knowledge
        self._load_knowledge_base()
        self._start_new_session()

    def _generate_pattern_id(self, pattern_data: Dict[str, Any]) -> str:
        """Generate unique pattern ID from pattern data."""
        content = json.dumps(pattern_data, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _load_knowledge_base(self) -> None:
        """Load knowledge patterns from disk."""
        try:
            knowledge_file = KNOWLEDGE_DIR / "knowledge_patterns.json"
            if knowledge_file.exists():
                with open(knowledge_file, 'r') as f:
                    data = json.load(f)
                    for pattern_id, pattern_data in data.items():
                        self.knowledge_patterns[pattern_id] = KnowledgePattern.from_dict(pattern_data)
                logger.info(f"Loaded {len(self.knowledge_patterns)} knowledge patterns")

            # Load session history
            sessions_file = KNOWLEDGE_DIR / "session_history.json"
            if sessions_file.exists():
                with open(sessions_file, 'r') as f:
                    data = json.load(f)
                    self.session_history = [LearningSession.from_dict(s) for s in data]
                logger.info(f"Loaded {len(self.session_history)} historical sessions")

        except Exception as e:
            logger.error(f"Error loading knowledge base: {e}")

    def _save_knowledge_base(self) -> None:
        """Save knowledge patterns to disk."""
        try:
            # Save patterns
            patterns_data = {
                pattern_id: pattern.to_dict()
                for pattern_id, pattern in self.knowledge_patterns.items()
            }
            knowledge_file = KNOWLEDGE_DIR / "knowledge_patterns.json"
            with open(knowledge_file, 'w') as f:
                json.dump(patterns_data, f, indent=2)

            # Save session history
            sessions_data = [session.to_dict() for session in self.session_history]
            sessions_file = KNOWLEDGE_DIR / "session_history.json"
            with open(sessions_file, 'w') as f:
                json.dump(sessions_data, f, indent=2)

        except Exception as e:
            logger.error(f"Error saving knowledge base: {e}")

    def _start_new_session(self) -> None:
        """Start a new learning session."""
        session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.current_session = LearningSession(
            session_id=session_id,
            start_time=datetime.now(),
            end_time=None,
            goals_attempted=0,
            goals_completed=0,
            total_success_rate=0.0,
            knowledge_gained=0,
            knowledge_used=0
        )

    def end_current_session(self) -> None:
        """End the current learning session."""
        if self.current_session:
            self.current_session.end_time = datetime.now()
            self.session_history.append(self.current_session)
            self._save_knowledge_base()
            logger.info(f"Ended session {self.current_session.session_id} with {self.current_session.knowledge_gained} patterns learned")

    def learn_from_goal(self, goal_description: str, actions: List[Dict], success_score: float) -> str:
        """Learn a new pattern from goal completion."""
        pattern_data = {
            'goal_description': goal_description,
            'action_sequence': [action.get('name', action.get('id', str(action))) for action in actions],
            'success_score': success_score,
            'timestamp': datetime.now().isoformat()
        }

        pattern_id = self._generate_pattern_id(pattern_data)

        # Update or create pattern
        if pattern_id in self.knowledge_patterns:
            pattern = self.knowledge_patterns[pattern_id]
            # Update existing pattern
            pattern.usage_count += 1
            pattern.last_used = datetime.now()
            # Update success rate with exponential moving average
            pattern.success_rate = (0.7 * pattern.success_rate) + (0.3 * success_score)
            pattern.confidence_score = min(1.0, pattern.confidence_score + 0.1)
        else:
            # Create new pattern
            pattern = KnowledgePattern(
                pattern_id=pattern_id,
                pattern_type="goal_pattern",
                description=f"Goal: {goal_description[:50]}...",
                success_rate=success_score,
                usage_count=1,
                last_used=datetime.now(),
                created_at=datetime.now(),
                confidence_score=min(0.8, 0.4 + success_score),
                parameters=pattern_data
            )
            self.knowledge_patterns[pattern_id] = pattern
            if self.current_session:
                self.current_session.knowledge_gained += 1

        # Apply knowledge decay
        self._apply_knowledge_decay(pattern)

        # Clean up old patterns if we have too many
        self._cleanup_old_patterns()

        # Update session stats
        if self.current_session:
            self.current_session.goals_attempted += 1
            if success_score > 0.7:
                self.current_session.goals_completed += 1
            # Update rolling success rate
            total_attempts = self.current_session.goals_attempted
            current_rate = self.current_session.total_success_rate
            self.current_session.total_success_rate = (current_rate * (total_attempts - 1) + success_score) / total_attempts

        return pattern_id

    def _apply_knowledge_decay(self, pattern: KnowledgePattern) -> None:
        """Apply time-based decay to pattern value."""
        days_since_use = (datetime.now() - pattern.last_used).days
        decay_factor = max(0.1, 1.0 - (days_since_use * self.knowledge_decay_rate))
        pattern.confidence_score *= decay_factor

    def _cleanup_old_patterns(self) -> None:
        """Remove old/low-value patterns to manage memory."""
        if len(self.knowledge_patterns) <= self.max_patterns:
            return

        # Sort patterns by value (confidence * usage_count)
        pattern_values = []
        for pattern in self.knowledge_patterns.values():
            value = pattern.confidence_score * pattern.usage_count
            pattern_values.append((value, pattern.pattern_id))

        # Remove lowest value patterns
        pattern_values.sort(key=lambda x: x[0])
        patterns_to_remove = len(self.knowledge_patterns) - self.max_patterns

        for _, pattern_id in pattern_values[:patterns_to_remove]:
            del self.knowledge_patterns[pattern_id]

    def find_similar_patterns(self, goal_description: str, limit: int = 5) -> List[Tuple[KnowledgePattern, float]]:
        """Find patterns similar to the current goal."""
        goal_lower = goal_description.lower()
        similar_patterns = []

        for pattern in self.knowledge_patterns.values():
            if pattern.pattern_type == "goal_pattern":
                # Simple text similarity (could be enhanced with embeddings)
                pattern_desc = pattern.description.lower()
                similarity = self._calculate_text_similarity(goal_lower, pattern_desc)
                if similarity > 0.3:  # Minimum similarity threshold
                    similar_patterns.append((pattern, similarity))

        # Sort by similarity and return top matches
        similar_patterns.sort(key=lambda x: x[1], reverse=True)
        return similar_patterns[:limit]

    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """Calculate simple text similarity based on word overlap."""
        words1 = set(text1.split())
        words2 = set(text2.split())

        if not words1 and not words2:
            return 1.0
        if not words1 or not words2:
            return 0.0

        intersection = words1.intersection(words2)
        union = words1.union(words2)

        return len(intersection) / len(union)

    def get_best_action_sequence(self, goal_description: str) -> Optional[List[str]]:
        """Get the best action sequence for a similar goal."""
        similar_patterns = self.find_similar_patterns(goal_description, limit=1)

        if similar_patterns and similar_patterns[0][1] > self.confidence_threshold:
            pattern = similar_patterns[0][0]
            if self.current_session:
                self.current_session.knowledge_used += 1
            return pattern.parameters.get('action_sequence', [])

        return None

    def get_knowledge_statistics(self) -> Dict[str, Any]:
        """Get statistics about the knowledge base."""
        now = datetime.now()

        # Pattern statistics
        total_patterns = len(self.knowledge_patterns)
        high_confidence_patterns = sum(1 for p in self.knowledge_patterns.values() if p.confidence_score > 0.7)
        recently_used_patterns = sum(1 for p in self.knowledge_patterns.values()
                                   if (now - p.last_used).days < 7)

        # Session statistics
        total_sessions = len(self.session_history)
        if self.session_history:
            avg_success_rate = sum(s.total_success_rate for s in self.session_history) / len(self.session_history)
            avg_goals_per_session = sum(s.goals_completed for s in self.session_history) / len(self.session_history)
        else:
            avg_success_rate = 0.0
            avg_goals_per_session = 0.0

        # Knowledge base health
        knowledge_health = (high_confidence_patterns / max(1, total_patterns)) * 100

        return {
            'total_patterns': total_patterns,
            'high_confidence_patterns': high_confidence_patterns,
            'recently_used_patterns': recently_used_patterns,
            'total_sessions': total_sessions,
            'avg_success_rate': avg_success_rate,
            'avg_goals_per_session': avg_goals_per_session,
            'knowledge_health': knowledge_health,
            'current_session_id': self.current_session.session_id if self.current_session else None,
            'patterns_by_type': defaultdict(int)
        }

    def export_knowledge_for_sharing(self) -> Dict[str, Any]:
        """Export knowledge patterns for sharing with other agents."""
        export_data = {
            'export_timestamp': datetime.now().isoformat(),
            'patterns': [
                {
                    'pattern_id': pattern.pattern_id,
                    'pattern_type': pattern.pattern_type,
                    'description': pattern.description,
                    'success_rate': pattern.success_rate,
                    'usage_count': pattern.usage_count,
                    'confidence_score': pattern.confidence_score,
                    'action_sequence': pattern.parameters.get('action_sequence', []),
                    'goal_example': pattern.parameters.get('goal_description', '')
                }
                for pattern in self.knowledge_patterns.values()
                if pattern.confidence_score > 0.5  # Only export confident patterns
            ],
            'statistics': self.get_knowledge_statistics()
        }
        return export_data

    def import_knowledge_from_sharing(self, imported_data: Dict[str, Any]) -> int:
        """Import knowledge patterns from another agent."""
        imported_count = 0
        current_patterns = {p.description: p for p in self.knowledge_patterns.values()}

        for pattern_data in imported_data.get('patterns', []):
            # Skip if we already have a similar pattern
            if pattern_data['description'] in current_patterns:
                continue

            # Create new pattern
            pattern = KnowledgePattern(
                pattern_id=self._generate_pattern_id(pattern_data),
                pattern_type=pattern_data['pattern_type'],
                description=pattern_data['description'],
                success_rate=pattern_data['success_rate'],
                usage_count=pattern_data['usage_count'],
                last_used=datetime.now(),
                created_at=datetime.now(),
                confidence_score=pattern_data['confidence_score'],
                parameters={
                    'action_sequence': pattern_data['action_sequence'],
                    'goal_description': pattern_data['goal_example'],
                    'imported': True
                }
            )

            self.knowledge_patterns[pattern.pattern_id] = pattern
            imported_count += 1

        if imported_count > 0:
            self._save_knowledge_base()
            logger.info(f"Imported {imported_count} new patterns from shared knowledge")

        return imported_count

    def get_learning_insights(self) -> List[str]:
        """Generate insights about learning progress."""
        insights = []
        stats = self.get_knowledge_statistics()

        # Knowledge growth insight
        if stats['total_patterns'] > 0:
            growth_rate = (stats['high_confidence_patterns'] / stats['total_patterns']) * 100
            if growth_rate > 70:
                insights.append(f"High-quality knowledge base: {growth_rate:.1f}% of patterns are highly confident")
            elif growth_rate > 40:
                insights.append(f"Growing knowledge base: {growth_rate:.1f}% of patterns are highly confident")
            else:
                insights.append(f"Knowledge base needs refinement: only {growth_rate:.1f}% of patterns are highly confident")

        # Usage pattern insight
        if stats['recently_used_patterns'] > stats['total_patterns'] * 0.3:
            insights.append("Agent is actively reusing learned knowledge")
        elif stats['recently_used_patterns'] < stats['total_patterns'] * 0.1:
            insights.append("Consider reviewing and using existing knowledge patterns more often")

        # Performance insight
        if stats['avg_success_rate'] > 0.8:
            insights.append(f"Excellent learning performance: {stats['avg_success_rate']:.1%} average success rate")
        elif stats['avg_success_rate'] > 0.6:
            insights.append(f"Good learning performance: {stats['avg_success_rate']:.1%} average success rate")
        else:
            insights.append(f"Learning performance could be improved: {stats['avg_success_rate']:.1%} average success rate")

        return insights


# Global cross-session learning system
cross_session_learning = CrossSessionLearningSystem()