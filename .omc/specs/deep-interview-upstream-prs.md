# Deep Interview Spec: Four Upstream PRs to ezbooz/Path-Of-Exile-2-RPC

## Metadata
- Interview ID: di-2026-05-05-upstream-prs
- Rounds: 3
- Final Ambiguity Score: 6.25%
- Type: brownfield
- Generated: 2026-05-05
- Threshold: 0.20
- Initial Context Summarized: no
- Status: PASSED

## Clarity Breakdown
| Dimension | Score | Weight | Weighted |
|-----------|-------|--------|----------|
| Goal Clarity | 0.95 | 0.35 | 0.333 |
| Constraint Clarity | 0.90 | 0.25 | 0.225 |
| Success Criteria | 0.95 | 0.25 | 0.238 |
| Context Clarity | 0.95 | 0.15 | 0.143 |
| **Total Clarity** | | | **0.938** |
| **Ambiguity** | | | **0.063** |

## Goal

Implement all 4 open README features in our hexagonal codebase (`src/poe2_rpc/`), then backport each as a minimal-diff patch against upstream `ezbooz/Path-Of-Exile-2-RPC`'s single-file `main.py` and submit four sequential pull requests after the user's Windows live-smoke validates each.

## Constraints

- Develop primarily in our hexagonal package (`src/poe2_rpc/...`); upstream PR is a manually written minimal-diff against their `main.py`, NOT an architectural rewrite.
- Upstream maintainer last commit 2025-07-29 (10 months ago) — PRs may sit; do not block local progress on merge.
- Each PR sends only the feature change to upstream; tests, mypy strict, ruff, and lint-imports stay in our repo, not in PR diffs.
- No new heavyweight runtime deps for upstream PRs (upstream's `requirements.txt` is 17 bytes — keep their footprint tiny). New deps allowed in our `pyproject.toml`.
- Process detection must accept a list of candidate executable names (Steam + standalone), not a single hardcoded string.
- Owner detection runs without configuration by default (auto-pin via `: You have entered`), config override optional.
- Background launcher uses Startup folder shortcut + `pystray` system tray icon; no Windows Service, no admin requirement.
- AFK presence change must be reversible (off-event must restore prior state).
- Hexagonal layering enforced by `lint-imports` is non-negotiable.

## Non-Goals

- Sending a "rewrite to hexagonal" PR to upstream (low merge probability).
- Forking upstream as a permanently independent product (we still target merge).
- Background service via NSSM/pywin32 (overkill for desktop tool).
- Detecting party-member level events (we filter them OUT).
- Showing AFK autoreply text in presence (just `[AFK]` suffix + icon).
- Localising tray menu / presence beyond English.
- Migrating upstream's CI to ruff/mypy in this work.

## Acceptance Criteria

### Per-feature DoD (applies to all 4)

- [ ] Feature implemented in `src/poe2_rpc/` respecting hexagonal layering (passes `lint-imports`).
- [ ] Unit tests in `tests/unit/test_<feature>.py` cover the new logic and pass `pytest tests -ra`.
- [ ] `mypy --strict src/poe2_rpc` is clean.
- [ ] `ruff check src tests` and `ruff format --check src tests` are clean.
- [ ] Manual Windows live-smoke: user runs `PathOfExile2DiscordRPC.exe` against real PoE2 client, attaches Discord presence screenshot to PR description as evidence.
- [ ] Backport branch `upstream-pr/<feature-slug>` exists, branched from `upstream/main`, containing only minimal-diff against `main.py` (no test files, no package layout).
- [ ] Both CIs green: our `.github/workflows/build.yml` + upstream's `build.yml` (Windows pyinstaller build) on the backport branch.
- [ ] PR description includes: feature summary, regex citations (where relevant), Windows screenshot evidence, manual repro steps.

### PR-1: Official PoE2 Client Support
- [ ] `AppSettings.process_name` becomes `process_name: list[str]` (default `["PathOfExileSteam.exe", "PathOfExile.exe"]`).
- [ ] `PsutilGameDetector` iterates candidates, returns first match.
- [ ] `log_path()` resolves correctly for both Steam (`...\steamapps\common\Path of Exile 2\logs\Client.txt`) and standalone (`...\Grinding Gear Games\Path of Exile 2\logs\Client.txt`).
- [ ] Backwards compatible: a string env `POE2RPC_PROCESS_NAME=Foo.exe` is coerced into `["Foo.exe"]` for upgrade safety.
- [ ] Unit test: `test_detection.py` parametrized over both process names with mocked `process_iter`.

### PR-2: Owner Detection (Auto-Pin)
- [ ] New `domain/owner.py` with `OwnerTracker` value object: state machine `UNKNOWN → AREA_ENTERED → PINNED(name)`.
- [ ] `: You have entered <area>` line sets state to `AREA_ENTERED`.
- [ ] `<X> has joined the area` while `AREA_ENTERED` invalidates pin candidacy for that round.
- [ ] First `is now level` line in a clean `AREA_ENTERED` window pins `<X>` as owner.
- [ ] Once pinned, only `level` events for the pinned name update presence; others are dropped.
- [ ] Optional `AppSettings.character_name: str | None` overrides auto-pin if set.
- [ ] Unit test: parties of 2-3 fake players with interleaved level lines verify only owner triggers presence.

### PR-3: AFK Status
- [ ] New regex in `infrastructure/parsing.py`: `r'.*\[INFO Client \d+\] : (DND|AFK) mode is now (?:(ON)\. Autoreply "(.*)"|(OFF))'`.
- [ ] New domain event `AFKStatusChanged(mode: Literal["AFK","DND"], on: bool)`.
- [ ] Handler `on_afk_changed` modifies presence: appends ` [AFK]` to state string, swaps `small_image` to `"afk"` asset key, stores prior `small_image` for restore on OFF.
- [ ] Discord developer portal: user uploads `afk.png` asset (out-of-band; documented in README addendum).
- [ ] Unit test: ON-OFF round-trip restores exact prior presence payload.

### PR-4: Background Launcher (Startup + Tray)
- [ ] New `infrastructure/tray.py` using `pystray` (added to `pyproject.toml` dependencies).
- [ ] Tray menu: `Status: <waiting | running | error>`, `Open log file`, `Restart`, `Quit`.
- [ ] New CLI subcommand `poe2-rpc tray` that boots the tray and runs the orchestrator in a background thread.
- [ ] New CLI subcommand `poe2-rpc install-autostart` that creates a Windows Startup folder `.lnk` pointing at `<exe> tray --quiet`.
- [ ] Mirror `poe2-rpc uninstall-autostart` removes the shortcut.
- [ ] `--quiet` flag suppresses console popup (PyInstaller `--noconsole` for tray-mode build OR runtime `subprocess.CREATE_NO_WINDOW`).
- [ ] Unit test: shortcut creation/removal mocked via `pylnk3` or `winshell` fake (no real registry hit).

## Assumptions Exposed & Resolved

| Assumption | Challenge | Resolution |
|------------|-----------|------------|
| "All 4 features fit one PR" | Maintainer is slow, big PRs get rejected | 4 sequential PRs ordered easiest→hardest |
| "Upstream uses our hexagonal package" | Upstream is single 11KB main.py | Backport via minimal-diff against main.py |
| "Owner = whoever levels" | Party-member levels would falsely trigger | Auto-pin via `You have entered` + party-join invalidation |
| "AFK is just a chat message" | poe-log-monitor `away` regex shows it's a structured log line | Use exact regex from `klayveR/poe-log-monitor/resource/events.json` |
| "Background = Windows Service" | Service requires admin and pywin32 (~5MB) | Startup folder shortcut + pystray tray (lightweight, per-user) |
| "Standalone process is `PathOfExile2.exe`" | Search results inconclusive; both PoE1/PoE2 use `PathOfExile.exe` per community | Settings becomes `list[str]`, first-match wins; Windows-smoke confirms exact name |

## Technical Context

### Codebase findings (brownfield)

- Hexagonal package at `src/poe2_rpc/` with `domain/`, `application/`, `infrastructure/`, `cli.py` (composition root).
- `infrastructure/settings.py:44` hardcodes `process_name: str = "PathOfExileSteam.exe"` — change to `list[str]`.
- `infrastructure/detection.py:50-53` iterates `psutil.process_iter(["name", "exe"])` matching one name — generalize to membership-in-list.
- `infrastructure/parsing.py` defines `regex_level` and `regex_instance` only; needs `regex_afk`, `regex_local_area_entered`, `regex_party_joined`.
- `application/orchestrator.py` composes bus + throttle + handlers; `on_level_changed` will gain owner-filter; new `on_afk_changed` handler needed.
- `application/handlers.py` uses `structlog.bind_contextvars(username=, character_class=, area=)` — extend with `afk: bool` context.
- `infrastructure/presence.py::PypresencePublisher` needs `update(small_image=, ...)` parameterization for AFK swap.
- `pyproject.toml` exposes Typer app `poe2-rpc` as console script; new subcommands `tray`, `install-autostart`, `uninstall-autostart` register here.
- Windows live-smoke gate already tracked as bd issue `panvex-12l` (G-4); each PR's smoke goes through it.

### Upstream findings

- Repo: `git@github.com:ezbooz/Path-Of-Exile-2-RPC.git` (already configured as `upstream` remote in our local repo).
- Default branch: `main`.
- File set: `main.py` (11 KB), `requirements.txt` (17 B), `locations.json`, `LICENSE`, `README.md`, `.github/`.
- Last commit: 2025-07-29 (`6ab8a27` "Update README.md").
- Prior feature commits: `5ae14e6` (small_image formatting), `fe9c494` (Smith of Kitava + Lich + Tactician).
- No tests, no ruff, no mypy, no import-linter on upstream.
- CI is `.github/workflows/build.yml` (PyInstaller Windows build only).

### Regex contracts (verbatim from klayveR/poe-log-monitor v0)

```
level:        .*\[INFO Client \d+\] : (.*) \((.*)\) is now level (\d+)
area_local:   .*\[INFO Client \d+\] : You have entered (.*)\.
area_join:    .*\[INFO Client \d+\] : (\S+) has joined the area\.
area_leave:   .*\[INFO Client \d+\] : (\S+) has left the area\.
afk_dnd:      .*\[INFO Client \d+\] : (DND|AFK) mode is now (?:(ON)\. Autoreply "(.*)"|(OFF))
login:        .*\[INFO Client \d+\] Connected to ([a-z0-9]+\.login\.pathofexile\.com) in (\d+)ms\.
```

## Ontology (Key Entities)

| Entity | Type | Fields | Relationships |
|--------|------|--------|---------------|
| LocalPlayer | core domain | name, character_class, level, area | owns presence updates |
| PartyMember | supporting | name | filtered out of presence |
| Character | core domain | name, character_class, level | LocalPlayer.character |
| AreaInstance | core domain | code, display_name, entered_at | sets owner-pin window |
| AFKStatus | core domain | mode (AFK/DND), on, autoreply | mutates presence |
| LogEvent | core domain | timestamp, kind, payload | parsed from Client.txt |
| ProcessCandidate | supporting | name, exe_path | resolved by detector |
| BackgroundLauncher | supporting | mode (tray/startup), shortcut_path | new infrastructure |
| OwnerTracker | core domain | state, pinned_name, area_window | filters level events |
| UpstreamPR | external system | branch_name, feature_slug, evidence_url | merge target |

## Ontology Convergence

| Round | Entity Count | New | Changed | Stable | Stability Ratio |
|-------|-------------|-----|---------|--------|----------------|
| 1 | 1 | 1 | - | - | N/A |
| 2 | 9 | 8 | 0 | 1 | N/A (low-base) |
| 3 | 10 | 1 | 0 | 9 | 100% |

Domain model fully converged at round 3 (UpstreamArchMismatch entity merged into UpstreamPR).

## PR Sequence Plan (recommended order)

1. **PR-1: Official PoE2 client** — smallest mech change, highest user value, easiest to review (~30 LOC in main.py).
2. **PR-2: Owner detection** — small but logic-heavy; prerequisite for AFK pin to local player.
3. **PR-3: AFK status** — small (1 regex + presence-mutation hook); depends on PR-2 conceptually for "whose AFK?".
4. **PR-4: Background launcher** — biggest (new module + 2 CLI commands + new dep `pystray`); land last so it doesn't gate the others.

## Interview Transcript

<details>
<summary>Full Q&A (3 rounds)</summary>

### Round 1 — Goal Clarity
**Q:** Какая структура PR в upstream? Один большой vs четыре маленьких?
**A:** Все 4 сделаем. Воспользуйся web search и context7 для ресерча.
**Ambiguity after:** 60% (Goal: 0.85, Constraints: 0.30, Criteria: 0.40, Context: 0.85)

### Round 2 — Constraint Clarity
**Q1:** PR-структура (4 sequential / 2 / 1 big / 4 parallel)?
**A1:** 4 отдельных PR последовательно.

**Q2:** Механизм автозапуска (startup+tray / startup-only / Task Scheduler / Service)?
**A2:** Startup folder shortcut + tray icon (pystray).

**Q3:** Owner detection (auto-pin / config / hybrid / login-anchor)?
**A3:** Auto-pin: первый area-entry → следующий level event.
**Ambiguity after:** 32% (rose due to exposed upstream-arch divergence assumption)

### Round 3 — Constraint Clarity (Contrarian Mode)
**Q1:** Dev↔PR mapping (hexagonal+backport / upstream-style / fork-only / rewrite-PR)?
**A1:** Develop в hexagonal → backport минимальным diff.

**Q2:** AFK display (suffix+icon / replace state / autoreply text / icon-only)?
**A2:** Suffix '[AFK]' + small icon override.

**Q3:** Acceptance per PR (multi-select)?
**A3:** All four selected: unit tests + Windows live-smoke + backport branch ready + lint/CI clean.
**Ambiguity after:** 6.25% — threshold met.

</details>
