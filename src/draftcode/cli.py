from __future__ import annotations

import csv
import html
import os
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from draftcode.config import get_settings
from draftcode.dossier import TeamDossier, load_team_dossiers
from draftcode.intel import IntelReport, apply_intel, extract_intel
from draftcode.io import (
    load_draft_order,
    load_mock_signals,
    load_prospects,
    load_team_needs,
    write_twin_report,
)
from draftcode.market import MarketReport, aggregate_mocks, apply_market
from draftcode.pipeline import run_prediction
from draftcode.simulate import MonteCarloDraftTwin, SimulationConfig
from draftcode.warroom import load_gm_adjustments, run_warroom

app = typer.Typer(help="NBA draft prediction agent CLI.")
console = Console()
DEFAULT_DOSSIER_PATH = Path("data/dossiers/team_dossiers.json")
UPLOAD_DATA_FILES = (
    "prospects.csv",
    "draft_order.csv",
    "team_needs.csv",
    "mock_signals.csv",
)


@app.callback()
def root() -> None:
    """Run DraftCode commands."""


@app.command()
def predict(
    data_dir: Path = typer.Option(
        None,
        help="Directory containing prospects/draft_order/team_needs CSVs.",
    ),
    output: Path = typer.Option(None, help="CSV path for final predictions."),
    trace: Path = typer.Option(None, help="JSON path for decision trace."),
) -> None:
    settings = get_settings()
    resolved_data_dir = data_dir or settings.data_dir
    resolved_output = output or settings.output_dir / "predictions.csv"
    resolved_trace = trace or settings.output_dir / "trace.json"

    picks = run_prediction(resolved_data_dir, output=resolved_output, trace_path=resolved_trace)

    table = Table(title="DraftCode prediction run")
    table.add_column("Pick", justify="right")
    table.add_column("Team")
    table.add_column("Prospect")
    table.add_column("Conf.", justify="right")
    table.add_column("Score", justify="right")
    for pick in picks:
        table.add_row(
            str(pick.pick),
            pick.abbreviation,
            pick.prospect_name,
            f"{pick.confidence:.2f}",
            f"{pick.score:.3f}",
        )
    console.print(table)
    console.print(f"[green]Wrote predictions:[/green] {resolved_output}")
    console.print(f"[green]Wrote trace:[/green] {resolved_trace}")


@app.command()
def simulate(
    data_dir: Path = typer.Option(None, help="Directory containing draft input CSVs."),
    output: Path = typer.Option(None, help="JSON path for the Draft Twin report."),
    draws: int = typer.Option(1000, help="Number of Monte Carlo scenarios."),
    seed: int = typer.Option(42, help="Random seed for deterministic simulation."),
    temperature: float = typer.Option(0.06, help="Softmax selection temperature."),
    top_k: int = typer.Option(5, help="Number of candidates eligible per simulated pick."),
    low_confidence_threshold: float = typer.Option(0.5, help="Low-confidence pick cutoff."),
    gm_preferences: Path = typer.Option(
        Path("outputs/llm/gm_preferences.json"),
        "--gm-preferences",
        help="Optional cached gpt-5.5 GM preference JSON from `draftcode warroom`.",
    ),
) -> None:
    """Run the Milestone-Aware Draft Twin Monte Carlo simulator."""
    settings = get_settings()
    resolved_data_dir = data_dir or settings.data_dir
    resolved_output = output or settings.output_dir / "twin.json"

    config = SimulationConfig(
        draws=draws,
        seed=seed,
        temperature=temperature,
        top_k=top_k,
        low_confidence_threshold=low_confidence_threshold,
    )
    loaded_gm_preferences = _load_optional_gm_preferences(gm_preferences)
    report = MonteCarloDraftTwin(
        prospects=load_prospects(resolved_data_dir),
        draft_order=load_draft_order(resolved_data_dir),
        team_needs=load_team_needs(resolved_data_dir),
        mock_signals=load_mock_signals(resolved_data_dir),
        config=config,
        dossiers=_load_default_dossiers(),
        gm_preferences=loaded_gm_preferences,
    ).run()
    write_twin_report(resolved_output, report)

    pick_table = Table(title="DraftCode assigned unique simulation")
    pick_table.add_column("Pick", justify="right")
    pick_table.add_column("Team")
    pick_table.add_column("Assigned")
    pick_table.add_column("Marginal", justify="right")
    pick_table.add_column("Pick leader")
    pick_table.add_column("Leader prob.", justify="right")
    pick_table.add_column("Low conf.", justify="center")
    for assigned, pick in zip(report.assigned_picks, report.picks, strict=True):
        style = "red" if pick.low_confidence else None
        pick_table.add_row(
            str(assigned.pick),
            assigned.abbreviation,
            assigned.prospect_name,
            f"{assigned.marginal_probability:.2f}",
            pick.most_likely_name,
            f"{pick.probability:.2f}",
            "yes" if pick.low_confidence else "",
            style=style,
        )
    console.print(pick_table)

    milestone_table = Table(title="Milestone summary")
    milestone_table.add_column("ID")
    milestone_table.add_column("Status")
    milestone_table.add_column("Answer")
    milestone_table.add_column("Expected", justify="right")
    milestone_table.add_column("P10", justify="right")
    milestone_table.add_column("P90", justify="right")
    milestone_table.add_column("Confidence", justify="right")
    for milestone in report.milestones:
        milestone_table.add_row(
            milestone.id,
            milestone.status,
            milestone.answer_display,
            _format_optional_float(milestone.expected),
            _format_optional_float(milestone.p10),
            _format_optional_float(milestone.p90),
            _format_optional_float(milestone.confidence),
        )
    console.print(milestone_table)
    console.print(f"[green]Wrote Draft Twin report:[/green] {resolved_output}")


@app.command()
def warroom(
    data_dir: Path = typer.Option(
        Path("data/processed"),
        help="Directory containing processed draft input CSVs.",
    ),
    dossier_path: Path = typer.Option(
        DEFAULT_DOSSIER_PATH,
        help="Team dossier JSON path.",
    ),
    output_dir: Path = typer.Option(
        Path("outputs/llm"),
        help="Directory for LLM-once cache artifacts.",
    ),
    draws: int = typer.Option(1000, help="Number of Monte Carlo scenarios."),
    seed: int = typer.Option(42, help="Random seed for deterministic simulation."),
    max_workers: int = typer.Option(4, help="Concurrent agent workers."),
    offline: bool = typer.Option(
        False,
        "--offline",
        help="Skip all LLM calls and write deterministic fallback artifacts.",
    ),
) -> None:
    """Run the local DraftCode war-room agent pipeline."""
    summary = run_warroom(
        data_dir=data_dir,
        dossier_path=dossier_path,
        output_dir=output_dir,
        draws=draws,
        seed=seed,
        max_workers=max_workers,
        offline=offline,
    )

    status_table = Table(title="DraftCode warroom")
    status_table.add_column("Stage")
    status_table.add_column("Total", justify="right")
    status_table.add_column("LLM", justify="right")
    status_table.add_column("Fallback", justify="right")
    for stage_name in ["gm", "explanations", "redteam"]:
        stage = summary[stage_name]
        status_table.add_row(
            stage_name,
            str(stage["total"]),
            str(stage["llm"]),
            str(stage["fallback"]),
        )
    console.print(status_table)
    console.print(f"[green]Wrote GM preferences:[/green] {summary['paths']['gm_preferences']}")
    console.print(f"[green]Wrote explanations:[/green] {summary['paths']['explanations']}")
    console.print(f"[green]Wrote redteam:[/green] {summary['paths']['redteam']}")


@app.command()
def intel(
    data_dir: Path = typer.Option(
        Path("data/processed"),
        help="Directory containing processed draft_order/team_needs CSVs.",
    ),
    news_text: str | None = typer.Option(
        None,
        "--news-text",
        help="Externally fetched news text to structure and apply.",
    ),
    news_file: Path | None = typer.Option(
        None,
        "--news-file",
        help="Path to externally fetched news text.",
    ),
    source: str = typer.Option("", "--source", help="Optional source label or URL for audit."),
    apply_changes: bool = typer.Option(
        False,
        "--apply",
        help="Write draft_order.csv/team_needs.csv. Default is dry-run preview.",
    ),
) -> None:
    """Extract real-time trade intel from supplied text and preview/apply CSV changes."""
    if (news_text is None) == (news_file is None):
        console.print("[red]error:[/red] pass exactly one of --news-text or --news-file")
        raise typer.Exit(code=1)

    resolved_source = source
    if news_file is not None:
        if not news_file.is_file():
            raise typer.BadParameter(f"News file does not exist: {news_file}")
        news_text = news_file.read_text(encoding="utf-8")
        resolved_source = resolved_source or str(news_file)

    assert news_text is not None
    draft_order = load_draft_order(data_dir)
    report = extract_intel(news_text, draft_order, source=resolved_source)
    result = apply_intel(report, data_dir, dry_run=not apply_changes)
    _print_intel_result(report, result)


@app.command()
def market(
    data_dir: Path = typer.Option(
        Path("data/processed"),
        help="Directory containing processed prospects/draft_order/mock_signals CSVs.",
    ),
    mock_file: list[str] | None = typer.Option(
        None,
        "--mock-file",
        help="Externally fetched mock draft as source=path. May be passed multiple times.",
    ),
    mock_dir: Path | None = typer.Option(
        None,
        "--mock-dir",
        help="Directory of externally fetched mock drafts; filename stem is used as source.",
    ),
    apply_changes: bool = typer.Option(
        False,
        "--apply",
        help="Write prospects.csv/mock_signals.csv. Default is dry-run preview.",
    ),
) -> None:
    """Aggregate externally supplied mock drafts into consensus market signals."""
    mocks = _load_market_mocks(mock_file or [], mock_dir)
    if not mocks:
        console.print("[red]error:[/red] pass --mock-file source=path or --mock-dir dir")
        raise typer.Exit(code=1)

    prospect_names = _read_market_prospect_names(data_dir)
    report = aggregate_mocks(mocks, prospect_names)
    result = apply_market(report, data_dir, dry_run=not apply_changes)
    _print_market_result(report, result)


@app.command()
def gateway(
    host: str = typer.Option("0.0.0.0", help="Host interface for the Codex HTTP gateway."),
    port: int = typer.Option(8787, help="Port for the Codex HTTP gateway."),
) -> None:
    """Serve the local Codex CLI as an OpenAI-compatible HTTP endpoint."""
    from draftcode.codex_gateway import serve

    console.print(f"[green]Starting DraftCode Codex gateway:[/green] http://{host}:{port}")
    console.print(
        "[yellow]Set DRAFTCODE_GATEWAY_KEY before exposing this endpoint publicly.[/yellow]"
    )
    try:
        serve(host=host, port=port)
    except KeyboardInterrupt:
        console.print("[yellow]Stopped DraftCode Codex gateway.[/yellow]")


@app.command()
def answer(
    data_dir: Path = typer.Option(
        Path("data/processed"),
        help="Directory containing processed official draft input CSVs.",
    ),
    template: Path = typer.Option(
        Path("data/raw/official/answer_card_template.xlsx"),
        help="Official answer-card template XLSX.",
    ),
    out: Path = typer.Option(
        Path("outputs/answer_card.xlsx"),
        help="Output XLSX path for the filled answer card.",
    ),
    draws: int = typer.Option(1000, help="Number of Monte Carlo scenarios."),
    seed: int = typer.Option(42, help="Random seed for deterministic simulation."),
    team_id: str | None = typer.Option(None, help="Optional official team_id to write."),
) -> None:
    """Generate the official XLSX answer card from the Draft Twin simulator."""
    from draftcode.answer import write_answer_card

    config = SimulationConfig(draws=draws, seed=seed)
    report = MonteCarloDraftTwin(
        prospects=load_prospects(data_dir),
        draft_order=load_draft_order(data_dir),
        team_needs=load_team_needs(data_dir),
        mock_signals=load_mock_signals(data_dir),
        config=config,
        dossiers=_load_default_dossiers(),
    ).run()
    write_answer_card(template=template, out=out, report=report, team_id=team_id)

    pick_table = Table(title="Answer card assigned unique predictions")
    pick_table.add_column("Pick", justify="right")
    pick_table.add_column("Team")
    pick_table.add_column("Prospect")
    pick_table.add_column("Marginal", justify="right")
    for pick in report.assigned_picks:
        pick_table.add_row(
            str(pick.pick),
            pick.abbreviation,
            pick.prospect_name,
            f"{pick.marginal_probability:.2f}",
        )
    console.print(pick_table)

    milestone_table = Table(title="Answer card milestone answers")
    milestone_table.add_column("ID")
    milestone_table.add_column("Answer")
    milestone_table.add_column("Kind")
    milestone_table.add_column("Expected", justify="right")
    milestone_table.add_column("P10", justify="right")
    milestone_table.add_column("P90", justify="right")
    milestone_table.add_column("Confidence", justify="right")
    for milestone in report.milestones:
        milestone_table.add_row(
            milestone.id,
            milestone.answer_display,
            milestone.answer_kind,
            _format_optional_float(milestone.expected),
            _format_optional_float(milestone.p10),
            _format_optional_float(milestone.p90),
            _format_optional_float(milestone.confidence),
        )
    console.print(milestone_table)
    console.print(f"[green]Wrote answer card:[/green] {out}")


@app.command()
def ingest(
    source: Path = typer.Option(
        Path("data/raw/official"),
        help="Directory containing official XLSX files.",
    ),
    out: Path = typer.Option(
        Path("data/processed"),
        help="Directory for normalized CSV/JSON outputs.",
    ),
) -> None:
    """Normalize official 2026 source workbooks into engine-ready data files."""
    from draftcode.official import ingest_official

    report = ingest_official(source, out)
    _print_ingest_report(report)


@app.command("upload-data")
def upload_data(
    source: Path = typer.Option(
        Path("data/processed"),
        help="Directory containing processed prospects/draft_order/team_needs/mock_signals CSVs.",
    ),
    bucket: str | None = typer.Option(
        None,
        "--bucket",
        "-b",
        help="Destination S3 bucket. Defaults to DRAFTCODE_S3_BUCKET.",
    ),
    prefix: str | None = typer.Option(
        None,
        "--prefix",
        "-p",
        help="Destination S3 prefix. Defaults to DRAFTCODE_DATA_S3_PREFIX or processed.",
    ),
) -> None:
    """Upload engine-ready processed CSVs to S3 for Lambda simulation runs."""
    resolved_bucket = bucket or os.getenv("DRAFTCODE_S3_BUCKET")
    if not resolved_bucket:
        console.print(
            "[red]error:[/red] S3 bucket is required. "
            "Pass --bucket or set DRAFTCODE_S3_BUCKET."
        )
        raise typer.Exit(code=1)

    resolved_prefix = (prefix or os.getenv("DRAFTCODE_DATA_S3_PREFIX") or "processed").strip()
    resolved_prefix = resolved_prefix.strip("/")
    if not resolved_prefix:
        console.print(
            "[red]error:[/red] S3 prefix is required. "
            "Pass --prefix or set DRAFTCODE_DATA_S3_PREFIX."
        )
        raise typer.Exit(code=1)

    files = [source / filename for filename in UPLOAD_DATA_FILES]
    missing = [path for path in files if not path.is_file()]
    if missing:
        console.print(
            "[red]error:[/red] missing processed CSVs: "
            + ", ".join(str(path) for path in missing)
        )
        raise typer.Exit(code=1)

    try:
        import boto3  # type: ignore[import-not-found]
        from botocore.exceptions import (  # type: ignore[import-not-found]
            BotoCoreError,
            ClientError,
            NoCredentialsError,
            PartialCredentialsError,
        )
    except ImportError as exc:
        console.print(
            "[red]error:[/red] boto3 is required for upload-data. "
            'Install with `make install-full` or `uv pip install -e ".[aws]"`.'
        )
        raise typer.Exit(code=1) from exc

    try:
        s3 = boto3.client("s3")
        for path in files:
            key = f"{resolved_prefix}/{path.name}"
            s3.upload_file(
                str(path),
                resolved_bucket,
                key,
                ExtraArgs={"ContentType": "text/csv; charset=utf-8"},
            )
            console.print(f"[green]uploaded:[/green] s3://{resolved_bucket}/{key}")
    except (NoCredentialsError, PartialCredentialsError) as exc:
        console.print(
            "[red]error:[/red] AWS credentials were not found. "
            "Run `aws configure sso`, set AWS_PROFILE, or export AWS access keys."
        )
        raise typer.Exit(code=1) from exc
    except (BotoCoreError, ClientError) as exc:
        console.print(f"[red]error:[/red] failed to upload data to S3: {exc}")
        raise typer.Exit(code=1) from exc
    except Exception as exc:
        if "credential" in str(exc).lower():
            console.print(
                "[red]error:[/red] AWS credentials were not found or are invalid. "
                "Run `aws configure sso`, set AWS_PROFILE, or export AWS access keys."
            )
        else:
            console.print(f"[red]error:[/red] failed to upload data to S3: {exc}")
        raise typer.Exit(code=1) from exc


@app.command("validate-output")
def validate_output(
    predictions: Path = typer.Option(..., help="Predictions CSV generated by the agent."),
    expected_picks: int = typer.Option(30, help="Expected number of first-round picks."),
) -> None:
    if not predictions.exists():
        raise typer.BadParameter(f"Predictions file does not exist: {predictions}")

    with predictions.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    errors: list[str] = []
    if len(rows) != expected_picks:
        errors.append(f"expected {expected_picks} rows, found {len(rows)}")

    pick_numbers = [row.get("pick", "") for row in rows]
    prospect_ids = [row.get("prospect_id", "") for row in rows]
    required = ["pick", "team", "abbreviation", "prospect_id", "prospect_name", "reason"]

    if len(set(pick_numbers)) != len(pick_numbers):
        errors.append("duplicate pick numbers found")
    if len(set(prospect_ids)) != len(prospect_ids):
        errors.append("duplicate prospect IDs found")
    for index, row in enumerate(rows, start=1):
        missing = [field for field in required if not row.get(field)]
        if missing:
            errors.append(f"row {index} missing fields: {', '.join(missing)}")

    if errors:
        for error in errors:
            console.print(f"[red]error:[/red] {error}")
        raise typer.Exit(code=1)

    console.print(f"[green]ok:[/green] {predictions} passes submission shape checks")


@app.command("render-report")
def render_report(
    predictions: Path = typer.Option(..., help="Predictions CSV generated by the agent."),
    output: Path = typer.Option(Path("outputs/report.html"), help="HTML report path."),
) -> None:
    if not predictions.exists():
        raise typer.BadParameter(f"Predictions file does not exist: {predictions}")

    with predictions.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    table_rows = "\n".join(
        "<tr>"
        f"<td>{html.escape(row.get('pick', ''))}</td>"
        f"<td>{html.escape(row.get('abbreviation', ''))}</td>"
        f"<td>{html.escape(row.get('prospect_name', ''))}</td>"
        f"<td><div class='bar'><span style='width:"
        f"{float(row.get('confidence', 0)) * 100:.0f}%'></span></div>"
        f"{float(row.get('confidence', 0)):.2f}</td>"
        f"<td>{html.escape(row.get('reason', ''))}</td>"
        "</tr>"
        for row in rows
    )
    page = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>DraftCode Prediction Report</title>
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      margin: 32px;
      color: #161616;
    }}
    header {{ max-width: 960px; margin-bottom: 24px; }}
    h1 {{ margin: 0 0 8px; font-size: 32px; }}
    p {{ color: #555; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th, td {{
      border-bottom: 1px solid #ddd;
      padding: 10px 12px;
      text-align: left;
      vertical-align: top;
    }}
    th {{ background: #f4f6f8; color: #333; }}
    td:first-child, th:first-child {{ width: 56px; text-align: right; }}
    .bar {{
      width: 88px;
      height: 8px;
      background: #e8edf2;
      border-radius: 999px;
      overflow: hidden;
      display: inline-block;
      margin-right: 8px;
    }}
    .bar span {{ display: block; height: 100%; background: #0f766e; }}
  </style>
</head>
<body>
  <header>
    <h1>DraftCode Prediction Report</h1>
    <p>Generated from the agent output. Use this as an offline roadshow fallback and audit view.</p>
  </header>
  <table>
    <thead>
      <tr><th>Pick</th><th>Team</th><th>Prospect</th><th>Confidence</th><th>Agent reason</th></tr>
    </thead>
    <tbody>
      {table_rows}
    </tbody>
  </table>
</body>
</html>
"""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(page, encoding="utf-8")
    console.print(f"[green]Wrote report:[/green] {output}")


def _load_market_mocks(mock_files: list[str], mock_dir: Path | None) -> list[tuple[str, str]]:
    mocks: list[tuple[str, str]] = []
    for spec in mock_files:
        if "=" not in spec:
            console.print("[red]error:[/red] --mock-file must use source=path")
            raise typer.Exit(code=1)
        source, raw_path = spec.split("=", 1)
        source = source.strip()
        raw_path = raw_path.strip()
        if not source or not raw_path:
            console.print("[red]error:[/red] --mock-file must use source=path")
            raise typer.Exit(code=1)
        path = Path(raw_path)
        if not path.is_file():
            raise typer.BadParameter(f"Mock file does not exist: {path}")
        mocks.append((source, path.read_text(encoding="utf-8")))

    if mock_dir is not None:
        if not mock_dir.is_dir():
            raise typer.BadParameter(f"Mock directory does not exist: {mock_dir}")
        for path in sorted(item for item in mock_dir.iterdir() if item.is_file()):
            mocks.append((path.stem, path.read_text(encoding="utf-8")))
    return mocks


def _read_market_prospect_names(data_dir: Path) -> list[str]:
    path = data_dir / "prospects.csv"
    if not path.is_file():
        raise typer.BadParameter(f"Prospects file does not exist: {path}")
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    names = [row.get("name", "").strip() for row in rows if row.get("name", "").strip()]
    if not names:
        console.print(f"[red]error:[/red] no prospect names found in {path}")
        raise typer.Exit(code=1)
    return names


def _print_ingest_report(report: dict[str, object]) -> None:
    summary = Table(title="DraftCode official ingest")
    summary.add_column("Item")
    summary.add_column("Value", justify="right")
    summary.add_row("Pool prospects", str(report["pool_count"]))
    summary.add_row("Handbook mappings", str(report["handbook_mapping_count"]))
    summary.add_row("Q6 options", str(report["q6_option_count"]))
    market_coverage = report["market_coverage"]
    assert isinstance(market_coverage, dict)
    summary.add_row(
        "Market coverage",
        f"{market_coverage['market_rank_count']}/{market_coverage['pool_count']}",
    )
    summary.add_row("Output dir", str(report["output_dir"]))
    console.print(summary)

    match_table = Table(title="Source table matches")
    match_table.add_column("Sheet")
    match_table.add_column("Raw rows", justify="right")
    match_table.add_column("Unique", justify="right")
    match_table.add_column("Matched", justify="right")
    match_table.add_column("Missing", justify="right")
    match_table.add_column("Duplicate keys")
    table_matches = report["table_matches"]
    assert isinstance(table_matches, dict)
    for sheet_name, values in table_matches.items():
        assert isinstance(values, dict)
        duplicates = values["duplicate_raw_names"]
        duplicate_text = ", ".join(duplicates) if isinstance(duplicates, list) else ""
        match_table.add_row(
            str(sheet_name),
            str(values["raw_rows"]),
            str(values["raw_unique_names"]),
            str(values["matched_pool_rows"]),
            str(values["missing_pool_rows"]),
            duplicate_text,
        )
    console.print(match_table)

    mapping_table = Table(title="Handbook mapping audit")
    mapping_table.add_column("English")
    mapping_table.add_column("#", justify="right")
    mapping_table.add_column("Pool name")
    mapping_table.add_column("School / Pos")
    mapping_table.add_column("Rank", justify="right")
    mapping_table.add_column("Status")
    mappings = report["handbook_mappings"]
    assert isinstance(mappings, list)
    for mapping in mappings:
        assert isinstance(mapping, dict)
        school_pos = f"{mapping['actual_school']} / {mapping['actual_position']}"
        mapping_table.add_row(
            str(mapping["english_name"]),
            str(mapping["pool_index"]),
            str(mapping["actual_pool_name"]),
            school_pos,
            str(mapping["consensus_rank"]),
            str(mapping["status"]),
        )
    console.print(mapping_table)

    stats = report["missing_stats"]
    preview = report["milestone_raw_preview"]
    assert isinstance(stats, dict)
    assert isinstance(preview, dict)
    quality = Table(title="Quality counters")
    quality.add_column("Metric")
    quality.add_column("Value", justify="right")
    quality.add_row("Height + wingspan", str(stats["height_and_wingspan_count"]))
    quality.add_row("Max vertical", str(stats["max_vertical_count"]))
    quality.add_row("Hand length", str(stats["hand_length_count"]))
    quality.add_row(
        "Wingspan - height >= 5",
        str(preview["wingspan_minus_barefoot_height_gte_5_count"]),
    )
    quality.add_row("Centers", str(preview["center_count"]))
    quality.add_row("International", str(preview["international_count"]))
    quality.add_row("Unknown country", str(preview["unknown_country_count"]))
    console.print(quality)

    divergence_stats = report["divergence_stats"]
    divergence_top5 = report["divergence_top5"]
    assert isinstance(divergence_stats, dict)
    assert isinstance(divergence_top5, list)
    divergence = Table(title="Divergence top 5")
    divergence.add_column("Player")
    divergence.add_column("Type")
    divergence.add_column("Gap", justify="right")
    divergence.add_column("Rank", justify="right")
    divergence.add_column("Reason")
    for record in divergence_top5:
        assert isinstance(record, dict)
        divergence.add_row(
            str(record["name"]),
            str(record["divergence_type"]),
            str(record["divergence_gap"]),
            str(record["consensus_rank"]),
            str(record["divergence_reason"]),
        )
    console.print(divergence)
    console.print(
        "[green]Divergence stats:[/green] "
        f"aligned={divergence_stats['aligned']}, "
        f"market_fade={divergence_stats['market_fade']}, "
        f"market_hype={divergence_stats['market_hype']}"
    )
    console.print(f"[green]Wrote normalized data:[/green] {report['output_dir']}")


def _format_optional_float(value: float | None) -> str:
    return "" if value is None else f"{value:.2f}"


def _print_intel_result(report: IntelReport, result: dict[str, object]) -> None:
    mode = "dry-run" if result["dry_run"] else "apply"
    console.print(f"[bold]Intel mode:[/bold] {mode}")
    console.print(
        "[bold]Affects draft order:[/bold] "
        + ("yes" if report.affects_draft_order else "no")
    )

    draft_changes = result["draft_order_changes"]
    assert isinstance(draft_changes, list)
    pick_table = Table(title="Draft-order pick moves")
    pick_table.add_column("Pick", justify="right")
    pick_table.add_column("From")
    pick_table.add_column("To")
    pick_table.add_column("Original")
    pick_table.add_column("Status")
    if draft_changes:
        for change in draft_changes:
            assert isinstance(change, dict)
            pick_table.add_row(
                str(change.get("pick", "")),
                str(change.get("from", change.get("current_abbreviation", ""))),
                str(change.get("to", change.get("new_abbreviation", ""))),
                str(change.get("original_team", "")),
                str(change.get("status", "")),
            )
    else:
        pick_table.add_row("", "No pick moves extracted", "", "", "")
    console.print(pick_table)

    needs_changes = result["needs_changes"]
    assert isinstance(needs_changes, list)
    needs_table = Table(title="Team-need changes")
    needs_table.add_column("Team")
    needs_table.add_column("Pos")
    needs_table.add_column("Before", justify="right")
    needs_table.add_column("After", justify="right")
    needs_table.add_column("Timeline")
    needs_table.add_column("Focus")
    needs_table.add_column("Status")
    if needs_changes:
        for change in needs_changes:
            assert isinstance(change, dict)
            before = change.get("before_weight")
            after = change.get("after_weight")
            needs_table.add_row(
                str(change.get("team", "")),
                str(change.get("position", "")),
                "" if before is None else f"{float(before):.2f}",
                "" if after is None else f"{float(after):.2f}",
                str(change.get("timeline", "")),
                str(change.get("focus", "")),
                str(change.get("status", "")),
            )
    else:
        needs_table.add_row("No needs delta extracted", "", "", "", "", "", "")
    console.print(needs_table)
    console.print(f"[green]Wrote intel audit:[/green] {result['audit_path']}")


def _print_market_result(report: MarketReport, result: dict[str, object]) -> None:
    mode = "dry-run" if result["dry_run"] else "apply"
    console.print(f"[bold]Market mode:[/bold] {mode}")

    consensus_table = Table(title="Consensus market")
    consensus_table.add_column("Prospect")
    consensus_table.add_column("Consensus pick", justify="right")
    consensus_table.add_column("Sources", justify="right")
    consensus_table.add_column("Source names")
    if report.rankings:
        for ranking in report.rankings:
            consensus_table.add_row(
                ranking.prospect_name,
                _format_optional_float(ranking.consensus_pick),
                str(ranking.n_sources),
                ", ".join(ranking.sources),
            )
    else:
        consensus_table.add_row("No market rankings extracted", "", "", "")
    console.print(consensus_table)

    before = result["market_rank_coverage_before"]
    after = result["market_rank_coverage_after"]
    console.print(f"[bold]Market coverage:[/bold] {before} -> {after}")
    console.print(f"[bold]Mock signal rows:[/bold] {result['mock_signal_rows']}")
    if result["wrote_csv"]:
        console.print("[green]Updated prospects.csv and mock_signals.csv.[/green]")
    elif report.rankings:
        console.print("[yellow]Dry-run only; pass --apply to write CSV changes.[/yellow]")
    else:
        console.print("[yellow]No consensus rankings; CSV files left untouched.[/yellow]")
    console.print(f"[green]Wrote market audit:[/green] {result['audit_path']}")


def _load_optional_gm_preferences(path: Path) -> dict[str, dict[str, float]]:
    if not path.is_file():
        console.print(
            f"[yellow]gpt-5.5 GM preferences disabled:[/yellow] cache not found at {path}"
        )
        return {}

    preferences = load_gm_adjustments(path)
    delta_count = sum(len(adjustments) for adjustments in preferences.values())
    if delta_count == 0:
        console.print(
            f"[yellow]gpt-5.5 GM preferences disabled:[/yellow] no valid deltas in {path}"
        )
        return {}

    console.print(
        "[green]gpt-5.5 GM preferences enabled:[/green] "
        f"{path} ({len(preferences)} teams, {delta_count} deltas)"
    )
    return preferences


def _load_default_dossiers() -> dict[str, TeamDossier] | None:
    if not DEFAULT_DOSSIER_PATH.is_file():
        return None
    return load_team_dossiers(DEFAULT_DOSSIER_PATH)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
