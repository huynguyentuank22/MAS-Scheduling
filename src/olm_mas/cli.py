"""CLI entry point for OLM-MAS.

Usage:
    python -m olm_mas.cli run-synthetic --config configs/experiments.yaml
"""

from __future__ import annotations

import argparse
import sys

from .benchmark_runner import BenchmarkRunner


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
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
