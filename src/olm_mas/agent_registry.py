"""Agent registry — loads agent templates from configs/agents.yaml.

Provides lookup by agent_type and returns AgentProfile instances.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml

from .schemas import AgentProfile


def _load_agents_yaml(path: str | Path) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}


class AgentRegistry:
    """Fixed set of reusable agent templates."""

    def __init__(self, config_path: str | Path | None = None) -> None:
        self._profiles: dict[str, AgentProfile] = {}
        if config_path:
            self.load_from_yaml(config_path)
        else:
            self._register_defaults()

    def load_from_yaml(self, path: str | Path) -> None:
        data = _load_agents_yaml(path)
        agents = data.get("agents", {})
        for agent_type, cfg in agents.items():
            profile = AgentProfile(
                agent_id=agent_type,
                agent_type=agent_type,
                capability_tags=cfg.get("capability_tags", []),
                allowed_tools=cfg.get("allowed_tools", []),
                disallowed_tools=cfg.get("disallowed_tools", []),
                max_parallelism=cfg.get("max_parallelism", 1),
                cost_model=cfg.get("cost_model", {}),
                trust_score=cfg.get("trust_score", 0.5),
            )
            self._profiles[agent_type] = profile

    def _register_defaults(self) -> None:
        """Fallback defaults matching configs/agents.yaml."""
        defaults = [
            ("planner", ["planning", "decomposition", "task_graph"], 0.75),
            ("researcher", ["retrieval", "browsing", "evidence_collection"], 0.70),
            ("writer", ["drafting", "synthesis", "execution"], 0.70),
            ("critic", ["verification", "critique", "constraint_checking"], 0.80),
            ("recovery", ["recovery", "diagnosis", "replanning"], 0.72),
        ]
        for agent_type, tags, trust in defaults:
            self._profiles[agent_type] = AgentProfile(
                agent_id=agent_type,
                agent_type=agent_type,
                capability_tags=tags,
                trust_score=trust,
            )

    def get(self, agent_type: str) -> Optional[AgentProfile]:
        return self._profiles.get(agent_type)

    def list_agents(self) -> list[AgentProfile]:
        return list(self._profiles.values())

    def best_agent_for_tags(self, tags: list[str]) -> Optional[AgentProfile]:
        """Return the agent with the most capability-tag overlap."""
        best: Optional[AgentProfile] = None
        best_score = 0
        for profile in self._profiles.values():
            overlap = len(set(profile.capability_tags) & set(tags))
            if overlap > best_score:
                best = profile
                best_score = overlap
        return best

    def update_historical_performance(
        self,
        episode_agent_stats: dict[str, dict[str, float]],
        workflow_id: str,
        episode_outcome: str,
    ) -> None:
        """Update aggregate per-agent performance metrics after one episode."""
        for agent_type, stats in episode_agent_stats.items():
            profile = self._profiles.get(agent_type)
            if not profile:
                continue

            hist = dict(profile.historical_performance)

            prior_calls = int(hist.get("total_calls", 0))
            prior_success = int(hist.get("success_calls", 0))
            prior_failure = int(hist.get("failure_calls", 0))
            prior_episodes = int(hist.get("episodes", 0))
            prior_mean_latency = float(hist.get("mean_latency_sec", 0.0))
            prior_mean_cost = float(hist.get("mean_cost", 0.0))

            new_calls = int(stats.get("calls", 0))
            new_success = int(stats.get("success_calls", 0))
            new_failure = int(stats.get("failure_calls", 0))
            new_latency_total = float(stats.get("total_latency_sec", 0.0))
            new_cost_total = float(stats.get("total_cost", 0.0))

            if new_calls <= 0:
                continue

            total_calls = prior_calls + new_calls
            mean_latency = (
                ((prior_mean_latency * prior_calls) + new_latency_total) / total_calls
            )
            mean_cost = (
                ((prior_mean_cost * prior_calls) + new_cost_total) / total_calls
            )

            hist.update(
                {
                    "episodes": prior_episodes + 1,
                    "total_calls": total_calls,
                    "success_calls": prior_success + new_success,
                    "failure_calls": prior_failure + new_failure,
                    "mean_latency_sec": round(mean_latency, 4),
                    "mean_cost": round(mean_cost, 4),
                    "last_workflow_id": workflow_id,
                    "last_episode_outcome": episode_outcome,
                }
            )
            profile.historical_performance = hist
