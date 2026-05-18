"""GAIA-lite execution path tests for final-answer handling and runtime modes."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from olm_mas.agent_registry import AgentRegistry
from olm_mas.agent_runtime import LLMAgentRuntime
from olm_mas.benchmarks.gaia_lite import GAIALiteAdapter
from olm_mas.external_benchmark_runner import ExternalBenchmarkRunner
from olm_mas.schemas import Artifact


class _FakeHTTPResponse:
    def __init__(self, payload: dict[str, Any], status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code
        self.text = str(payload)

    def json(self) -> dict[str, Any]:
        return self._payload


def test_external_runner_uses_final_answer_artifact():
    artifacts = [
        Artifact(
            workflow_id="wf-1",
            artifact_type="draft",
            content={"answer": "wrong"},
            created_by="writer",
        ),
        Artifact(
            workflow_id="wf-1",
            artifact_type="final_answer",
            content={"answer": "correct"},
            created_by="verifier",
        ),
    ]
    selected = ExternalBenchmarkRunner._select_evaluator_input(artifacts)
    assert selected["source"] == "final_answer"
    assert selected["final_output"] == {"answer": "correct"}
    assert selected["final_answer_present"] is True
    assert selected["final_answer_schema_valid"] is True


def test_gaia_lite_evaluator_normalizes_answer():
    adapter = GAIALiteAdapter()
    task = {
        "task_id": "t-1",
        "question": "Who is the Big Apple?",
        "expected_answer": "new york",
        "task_family": "web_research",
        "task_pattern": "nickname_lookup",
        "constraints": {},
    }
    out = adapter.evaluate(task=task, final_output={"answer": "New, York!!!"}, artifacts=[])
    assert out["success"] is True
    assert out["normalized_match"] is True
    assert out["reason"] == "normalized_exact_match"


def test_missing_final_answer_scores_zero_with_metric():
    adapter = GAIALiteAdapter()
    task = {
        "task_id": "t-2",
        "question": "Compute 2+2",
        "expected_answer": "4",
        "task_family": "numeric_reasoning",
        "task_pattern": "single_step_arithmetic",
        "constraints": {},
    }
    no_artifacts = [
        Artifact(
            workflow_id="wf-2",
            artifact_type="evidence",
            content={"note": "no final output"},
            created_by="researcher",
        )
    ]
    selected = ExternalBenchmarkRunner._select_evaluator_input(no_artifacts)
    assert selected["source"] == "missing"

    eval_out = adapter.evaluate(task=task, final_output=selected["final_output"], artifacts=no_artifacts)
    assert eval_out["success"] is False

    summary = ExternalBenchmarkRunner._summarize(
        variant="mas_orchestrator_memory",
        benchmark="gaia_lite",
        split="sample",
        tasks=[task],
        episode_results=[
            {
                "external_success": False,
                "external_score": 0.0,
                "final_answer_present": False,
                "final_answer_schema_valid": False,
                "answer_normalized_match": False,
                "evaluator_input_source": "missing",
                "evaluator_warning": "missing_final_answer_and_writer_verifier_output",
                "scheduling_scores": {},
                "retrieved_count": 0,
                "eligible_count": 0,
                "blocked_count": 0,
            }
        ],
        tools=[],
        total_memories=0,
        runtime_mode="mock",
        llm_config={},
    )
    assert summary["evaluator_input_source_counts"]["missing"] == 1
    assert summary["missing_final_answer_warning_rate"] == 1.0


def test_llm_runtime_output_still_validated():
    def _ok_response(*args, **kwargs):  # noqa: ANN002, ANN003
        del args, kwargs
        return _FakeHTTPResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"status":"success","summary":"ok","artifact_type":"draft",'
                                '"artifact_payload":{"text":"hello"},"confidence":0.8,"uncertainties":[]}'
                            )
                        }
                    }
                ]
            }
        )

    runtime = LLMAgentRuntime(
        seed=7,
        failure_rate=0.0,
        llm_provider="openai",
        llm_model="gpt-4.1-mini",
        api_key="dummy",
        request_func=_ok_response,
    )
    profile = AgentRegistry().get("writer")
    assert profile is not None
    result = runtime.run(profile=profile, task_description="Write a final summary")
    assert result["agent_output"].schema_valid is True
    assert result["agent_output"].validation_errors == []


def test_deterministic_gaia_runtime_can_pass_sample_task():
    output_dir = Path(tempfile.mkdtemp(prefix="olm_mas_gaia_deterministic_"))
    runner = ExternalBenchmarkRunner(
        benchmark_name="gaia_lite",
        split="sample",
        limit=3,
        variant="mas_orchestrator_memory",
        output_dir=str(output_dir),
        seed=123,
        runtime_mode="deterministic_gaia",
    )
    result = runner.run()["results"]["mas_orchestrator_memory"]
    assert result["success_rate"] > 0.0
    assert result["final_answer_present_rate"] > 0.0
    assert result["agent_output_schema_valid_rate"] == 1.0


def test_deterministic_web_research_emits_final_answer():
    output_dir = Path(tempfile.mkdtemp(prefix="olm_mas_gaia_web_final_answer_"))
    runner = ExternalBenchmarkRunner(
        benchmark_name="gaia_lite",
        split="sample",
        limit=8,
        variant="mas_orchestrator_memory",
        output_dir=str(output_dir),
        seed=123,
        runtime_mode="deterministic_gaia",
    )
    summary = runner.run()["results"]["mas_orchestrator_memory"]
    web_eps = [ep for ep in summary["episodes"] if ep["task_family"] == "web_research"]
    assert len(web_eps) == 4
    assert all(bool(ep["final_answer_present"]) for ep in web_eps)
    assert all(bool(ep["external_success"]) for ep in web_eps)


def test_expected_answer_not_included_in_llm_task_descriptions():
    prompt = "Find the capital of France."
    expected = "PARIS_SECRET_VALUE"
    descs = ExternalBenchmarkRunner._task_descriptions(
        prompt=prompt,
        metadata={"task_family": "web_research", "task_id": "gaia-lite-x"},
        expected_answer=expected,
        runtime_mode="llm",
    )
    assert len(descs) > 0
    assert all("ORACLE_EXPECTED_ANSWER" not in d for d in descs)
    assert all(expected not in d for d in descs)


def test_llm_runtime_missing_api_key_fails_gracefully():
    runtime = LLMAgentRuntime(
        seed=7,
        failure_rate=0.0,
        llm_provider="openai",
        llm_model="gpt-4.1-mini",
        api_key=None,
    )
    profile = AgentRegistry().get("writer")
    assert profile is not None
    result = runtime.run(profile=profile, task_description="Write output")
    assert result["success"] is False
    assert result["agent_output"].status.value == "failed"
    assert result["agent_output"].schema_valid is True
    assert "LLM API key missing" in result["agent_output"].summary


def test_llm_runtime_raw_output_still_goes_through_parser():
    def _bad_response(*args, **kwargs):  # noqa: ANN002, ANN003
        del args, kwargs
        return _FakeHTTPResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"status":"success","summary":"bad","artifact_type":"draft",'
                                '"artifact_payload":{"text":"x"},"confidence":0.7,"uncertainties":[],'
                                '"artifact_id":"llm_injected"}'
                            )
                        }
                    }
                ]
            }
        )

    runtime = LLMAgentRuntime(
        seed=7,
        failure_rate=0.0,
        llm_provider="openai",
        llm_model="gpt-4.1-mini",
        api_key="dummy",
        request_func=_bad_response,
    )
    profile = AgentRegistry().get("writer")
    assert profile is not None
    result = runtime.run(profile=profile, task_description="Write output")
    assert result["success"] is False
    assert result["agent_output"].schema_valid is False
    assert any("runtime_field_not_allowed:artifact_id" in e for e in result["agent_output"].validation_errors)


def test_missing_api_key_increments_llm_setup_error_rate(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)

    output_dir = Path(tempfile.mkdtemp(prefix="olm_mas_gaia_llm_setup_error_"))
    runner = ExternalBenchmarkRunner(
        benchmark_name="gaia_lite",
        split="sample",
        limit=1,
        variant="mas_orchestrator_memory",
        output_dir=str(output_dir),
        seed=123,
        runtime_mode="llm",
        llm_provider="openai",
        llm_model="gpt-4.1-mini",
    )
    summary = runner.run()["results"]["mas_orchestrator_memory"]
    assert summary["llm_setup_error_rate"] > 0.0


def test_schema_valid_failed_setup_output_does_not_count_as_agent_task_success(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)

    output_dir = Path(tempfile.mkdtemp(prefix="olm_mas_gaia_llm_setup_failed_status_"))
    runner = ExternalBenchmarkRunner(
        benchmark_name="gaia_lite",
        split="sample",
        limit=1,
        variant="mas_orchestrator_memory",
        output_dir=str(output_dir),
        seed=456,
        runtime_mode="llm",
        llm_provider="openai",
        llm_model="gpt-4.1-mini",
    )
    summary = runner.run()["results"]["mas_orchestrator_memory"]
    assert summary["agent_output_schema_valid_rate"] == 1.0
    assert summary["agent_task_success_rate"] == 0.0
    assert summary["agent_failed_status_rate"] > 0.0
