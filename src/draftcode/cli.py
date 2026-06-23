from __future__ import annotations

import csv
import html
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from draftcode.config import get_settings
from draftcode.io import (
    load_draft_order,
    load_mock_signals,
    load_prospects,
    load_team_needs,
    write_twin_report,
)
from draftcode.pipeline import run_prediction
from draftcode.simulate import MonteCarloDraftTwin, SimulationConfig

app = typer.Typer(help="NBA draft prediction agent CLI.")
console = Console()


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
    report = MonteCarloDraftTwin(
        prospects=load_prospects(resolved_data_dir),
        draft_order=load_draft_order(resolved_data_dir),
        team_needs=load_team_needs(resolved_data_dir),
        mock_signals=load_mock_signals(resolved_data_dir),
        config=config,
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


def main() -> None:
    app()


if __name__ == "__main__":
    main()
