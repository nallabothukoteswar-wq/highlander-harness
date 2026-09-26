"""Runner CLI for Highlander experiments."""

import os
import sys
import uuid
import json
import time
import argparse
from datetime import datetime
from typing import Optional

import typer
import psycopg

from runner.platform_local import LocalPlatform
from runner.platform_kind import KindPlatform
from runner.trials import TrialRunner
from runner.manifest import ManifestRecorder


app = typer.Typer()


@app.command()
def run(
    platform: str = typer.Option("local", "--platform", help="Target platform (local or kind)"),
    series: str = typer.Option("all", "--series", help="Series to run (all, A, B, C, D, E, F, G)"),
    trials_per_cell: int = typer.Option(30, "--trials-per-cell", help="Number of trials per cell"),
    pilot: bool = typer.Option(False, "--pilot", help="Run as pilot (watermarked outputs)"),
    resume: bool = typer.Option(False, "--resume", help="Resume from existing campaign"),
    campaign_dir: Optional[str] = typer.Option(None, "--campaign-dir", help="Campaign directory"),
):
    """Run Highlander experiments."""
    # Initialize platform
    if platform == "local":
        platform_impl = LocalPlatform()
    elif platform == "kind":
        platform_impl = KindPlatform()
    else:
        typer.echo(f"Unknown platform: {platform}")
        raise typer.Exit(1)

    # Create campaign directory
    if campaign_dir is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        campaign_dir = f"data/campaign-{timestamp}"

    os.makedirs(campaign_dir, exist_ok=True)

    # Record manifest
    manifest = ManifestRecorder(campaign_dir)
    manifest.record_start()

    # Initialize trial runner
    trial_runner = TrialRunner(platform_impl, campaign_dir, pilot, trials_per_cell)

    # Run series
    if series == "all":
        series_list = ["A", "B", "C", "D", "E", "F", "G"]
    else:
        series_list = [series]

    for s in series_list:
        typer.echo(f"Running Series {s}...")
        trial_runner.run_series(s)

    # Record manifest end
    manifest.record_end()

    typer.echo(f"Campaign complete. Results in {campaign_dir}")


@app.command()
def analyze(
    campaign_dir: str = typer.Argument(..., help="Campaign directory to analyze"),
):
    """Analyze campaign results."""
    from analysis.report import generate_report

    generate_report(campaign_dir)


@app.command()
def env_check():
    """Check environment requirements."""
    import subprocess

    checks = []

    # Python version
    result = subprocess.run(["python3", "--version"], capture_output=True, text=True)
    python_version = result.stdout.strip()
    checks.append(("Python 3.11+", "3.11" in python_version, python_version))

    # Docker
    try:
        result = subprocess.run(["docker", "--version"], capture_output=True, text=True)
        checks.append(("Docker", True, result.stdout.strip()))
    except FileNotFoundError:
        checks.append(("Docker", False, "Not found"))

    # kubectl
    try:
        result = subprocess.run(["kubectl", "version", "--client"], capture_output=True, text=True)
        checks.append(("kubectl", True, result.stdout.strip()))
    except FileNotFoundError:
        checks.append(("kubectl", False, "Not found"))

    # kind
    try:
        result = subprocess.run(["kind", "version"], capture_output=True, text=True)
        checks.append(("kind", True, result.stdout.strip()))
    except FileNotFoundError:
        checks.append(("kind", False, "Not found"))

    # Print results
    typer.echo("Environment Check:")
    typer.echo("-" * 50)
    for name, passed, detail in checks:
        status = "✓" if passed else "✗"
        typer.echo(f"{status} {name}: {detail}")

    all_passed = all(passed for _, passed, _ in checks)
    if not all_passed:
        typer.echo("\nSome checks failed. Please install missing dependencies.")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
