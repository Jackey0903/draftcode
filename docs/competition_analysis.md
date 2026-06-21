# DraftCode hackathon analysis

Source document: `🏀 24h 黑客松极限赛模拟球探开发 · 终极参赛指南.md`.
Additional source document: `赛前培训直播-会议纪要.md`.

## Absolute timeline

- AWS Summit China 2026 is scheduled for 2026-06-23 to 2026-06-24 at Shanghai World Expo Center. The AWS Summit official page confirms the same dates and venue.
- The guide says the milestone question and answer-card page goes online at 2026-06-23 08:00 Shanghai time.
- The training notes also mention 8 milestone objective questions in a "blind box" style at 2026-06-23 21:00. Treat this as a schedule ambiguity and check Team Portal immediately at both 08:00 and 21:00.
- Coding starts at 2026-06-23 09:00 Shanghai time.
- Roadshow order is announced at 2026-06-23 21:00 Shanghai time.
- Final submission locks at 2026-06-24 08:00 Shanghai time. Anything after 08:00 is invalid.
- Roadshow starts at 2026-06-24 09:00 Shanghai time.

If the current local date is 2026-06-22 in Shanghai, the coding window starts tomorrow, not the day after tomorrow. Use the absolute times above for alarms.

## Core task

Build an Agent that predicts the first-round NBA draft result: which player each team selects, plus milestone objective questions released at 2026-06-23 08:00. The key rule is that the answer must be produced by the Agent, not typed manually by intuition.

The training notes specify the first five 2026 lottery slots as:

1. Washington Wizards
2. Utah Jazz
3. Memphis Grizzlies
4. Chicago Bulls
5. LA Clippers, via Indiana Pacers trade

## Scoring interpretation

- Code quality: 30%. Code is submitted to GitHub and scored by AWS AI tooling across 11 dimensions. The judges reward a real, runnable, deployable system, not only a notebook.
- Roadshow: 30%. The pitch must explain why the predictions are reasonable.
- Milestones: 40%. The answer card matters; we need a fast, auditable path from data ingestion to final picks.

Technical scoring language explicitly favors modern AWS usage: Serverless, containers, infrastructure as code, security, reliability, maintainability, and clear documentation. The current project therefore uses:

- Local deterministic prediction pipeline for speed and reproducibility.
- AWS SAM serverless template for deployable API shape.
- CLI, API, dashboard, tests, and trace logs for demonstration.
- `.env.example` and no committed credentials.

## Required accounts and assets

- Kiro IDE account: organizer-issued to the team lead email.
- AWS Global account: self-registered, new account, credit-card backed, with free credits.
- GitHub repository: must be Private. The organizer has authorization to read it; public repos may be rejected.
- Summit registration: required for venue entry.
- Team Portal: central place for rules, data, tools, and final submission.
- Identity: government ID required for entry.

## Deliverables

- GitHub repository.
- Draft answer card / milestone answer card.
- Roadshow PPT.
- Demo video under 60 seconds.
- Code pushed to GitHub before 2026-06-24 08:00 Shanghai time.

## Main risks

- Missing private GitHub setting.
- AWS CLI not configured until too late.
- Docker Desktop not running when SAM build/local invoke is needed.
- Depending on old AWS accounts instead of the required new AWS Global account.
- Manual, untraceable predictions that fail the "Agent generated" principle.
- Late submission close to 2026-06-24 08:00.
- Roadshow explains features but not the prediction logic.

## Recommended competition strategy

Use a two-track system:

- Prediction track: fast data ingestion, model scoring, simulation, trace, answer export.
- Demo track: dashboard/API/SAM deployment and story around AWS-native Agent architecture.

The model should blend four evidence classes:

- Big board and consensus ranking.
- Pick-slot fit and availability after earlier selections.
- Team needs and roster construction.
- External signals: mock drafts, reporter links, workouts, betting/market movement if allowed.

Official/allowed data notes from training:

- NBA official data source mentioned: `nba.china.com`.
- Team Portal should provide 4 classes of NBA authorized data.
- External public data and scraping are allowed; no advance reporting is required.
