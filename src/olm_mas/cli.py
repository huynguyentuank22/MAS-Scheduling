"""CLI entry point for OLM-MAS.

Usage:
    python -m olm_mas.cli run-synthetic --config configs/experiments.yaml
"""

from __future__ import annotations

import argparse
import sys

from .benchmark_runner import BenchmarkRunner
from .external_benchmark_runner import ExternalBenchmarkRunner


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="olm-mas",
        description="Orchestrator-Local Memory for Multi-Agent Systems",
    )
    subparsers = parser.add_subparsers(dest="command")

    # run-synthetic sub-command
    run_parser = subparsers.add_parser(
        "run-synthetic",
        help="Run the synthetic benchmark with ablation variants",
    )
    run_parser.add_argument(
        "--config",
        type=str,
        default="configs/experiments.yaml",
        help="Path to experiments YAML config",
    )
    run_parser.add_argument(
        "--output-dir",
        type=str,
        default="experiments",
        help="Directory for output metrics and traces",
    )

    # run-benchmark sub-command
    benchmark_parser = subparsers.add_parser(
        "run-benchmark",
        help="Run an external benchmark adapter variant",
    )
    benchmark_parser.add_argument(
        "--benchmark",
        type=str,
        default="gaia_lite",
        help="Benchmark adapter name (e.g., gaia_lite)",
    )
    benchmark_parser.add_argument(
        "--split",
        type=str,
        default="sample",
        help="Dataset split name",
    )
    benchmark_parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional task limit",
    )
    benchmark_parser.add_argument(
        "--variant",
        type=str,
        default="mas_orchestrator_memory",
        help="Variant to run (mas_no_memory|mas_orchestrator_memory|mas_shuffled_memory|mas_random_memory)",
    )
    benchmark_parser.add_argument(
        "--output-dir",
        type=str,
        default="experiments/gaia_lite_smoke",
        help="Directory for output metrics and traces",
    )

    args = parser.parse_args(argv)

    if args.command == "run-synthetic":
        runner = BenchmarkRunner(
            config_path=args.config,
            output_dir=args.output_dir,
        )
        result = runner.run()
        comparison = result.get("comparison", {})
        delta = comparison.get("delta", {})
        if delta:
            print(f"\n{'='*60}")
            print("COMPARISON SUMMARY")
            print(f"{'='*60}")
            for k, v in delta.items():
                sign = "+" if v > 0 else ""
                print(f"  {k}: {sign}{v}")
        print("\nDone.")
    elif args.command == "run-benchmark":
        runner = ExternalBenchmarkRunner(
            benchmark_name=args.benchmark,
            split=args.split,
            limit=args.limit,
            variant=args.variant,
            output_dir=args.output_dir,
        )
        runner.run()
        print("\nDone.")
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
