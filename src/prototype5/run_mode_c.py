"""Command-line entry point for Prototype 5 Mode C local-vs-cloud baseline."""

from __future__ import annotations

from .local_cloud_comparison import run_local_cloud_comparison


def main() -> None:
    result = run_local_cloud_comparison()
    summary = result["summary"]
    print("Prototype 5 Mode C Local-vs-Cloud: COMPLETE")
    print(f"Mode C status: {summary['mode_c_status']}")
    print(f"Cloud baseline status: {summary['cloud_baseline_status']}")
    print(f"Total commands: {summary['total_commands']}")
    print(f"Results: {summary['outputs']['local_vs_cloud_results']}")
    print(f"Summary: {summary['outputs']['local_vs_cloud_summary']}")


if __name__ == "__main__":
    main()
