# NBA model strategy

## Prediction target

The contest asks for team-player matches, not simply a ranking of best prospects. The model should therefore simulate the draft sequentially: once a player is selected, every later team must choose from the remaining board.

## Evidence hierarchy

1. Consensus board and mock-draft market.
2. Team need and roster construction.
3. Prospect production and role translation.
4. Team-specific signals: workouts, reported interest, medical flags, front-office tendencies, trade context.
5. Late-breaking information released through the Team Portal or official milestone questions.

## Feature plan

- Prospect baseline: consensus rank, age, size, position, archetype, statistical production.
- Scoring translation: true shooting, assist rate, rebound rate, stock rate, usage, competition context.
- Combine measurements: height, weight, wingspan, standing reach, hand size, body fat.
- Combine athletic tests: no-step/maximum vertical, lane agility, shuttle, three-quarter sprint, bench press.
- Skill tests: off-dribble 15-foot shooting, off-dribble college threes, spot locations, movement shooting, free throws.
- Medical and interview flags when available.
- Fit: primary position, on-ball/off-ball role, spacing, defensive versatility.
- Team context: current roster depth, contract timeline, rebuilding/contending state, recent draft history.
- Signal model: source reliability, recency, agreement across mocks, reporter specificity.
- Risk: injury, age outlier, shooting sample, positional ambiguity, transfer/international context.

## Modeling approach

Start deterministic, then add uncertainty:

- Baseline: weighted score per team-pick-prospect.
- Sequential simulator: selects best available for every pick in order.
- Trace: preserve top alternatives and component scores.
- Monte Carlo extension: sample weights and source reliability to estimate pick probabilities.
- LLM/Bedrock extension: generate concise narrative only after deterministic scoring, never as the sole source of truth.

## Roadshow framing

The strongest story is not "we used many services." It is:

- The Agent converts heterogeneous draft evidence into normalized signals.
- It simulates the actual draft process in order.
- Every pick has a trace with alternatives and component scores.
- AWS makes the workflow reproducible, deployable, logged, and easy to rerun when new information arrives.

## Practical fallback

If Portal data is messy or time is tight:

- Normalize only four tables first: prospects, draft order, team needs, mock signals.
- Hard-code no picks manually. If a pick needs judgment, update a data row, source weight, or team need and rerun the Agent.
- Run the deterministic model.
- Improve the weakest confidence picks manually through data updates, not by editing the final answer file.
- Keep a final trace so the roadshow can defend decisions.

## Known draft-order seed from training notes

The training notes state that the 2026 lottery top five are:

1. Washington Wizards
2. Utah Jazz
3. Memphis Grizzlies
4. Chicago Bulls
5. LA Clippers, via Indiana Pacers trade

Use the Team Portal or official NBA source to fill and verify the full first-round order before the final run.
