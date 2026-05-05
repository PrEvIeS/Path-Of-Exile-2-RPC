# RALPLAN: Four Upstream PRs to ezbooz/Path-Of-Exile-2-RPC

> Source spec: `.omc/specs/deep-interview-upstream-prs.md` (di-2026-05-05-upstream-prs, ambiguity 6.25%, PASSED)
> Mode: SHORT (deliberate elements added on PR-2 owner detection due to logic complexity)
> Target: 4 sequential PRs, develop-in-hexagonal then backport minimal-diff to upstream `main.py`

---

## RALPLAN-DR Summary

### Principles (5)

1. **Hexagonal layering is non-negotiable.** All four features ship through `domain/` (pure VOs, ports), `application/` (orchestration, handlers, owner state machine), `infrastructure/` (psutil/pypresence/pystray adapters), `cli.py` (composition root). `lint-imports` failure = no merge. Reference: `pyproject.toml` `[tool.importlinter]`.
2. **Minimal-diff for upstream.** Each PR's upstream branch (`upstream-pr/<slug>`) is hand-written against `main.py`, not a port of our hexagonal modules. Tests/mypy/ruff/lint-imports never appear in upstream diffs (their `requirements.txt` is 17 bytes — keep it that way).
3. **Verbatim regex contracts.** Every regex new to this work is copied character-for-character from `klayveR/poe-log-monitor/resource/events.json` (cited in spec §"Regex contracts"). Existing `regex_level` and `regex_instance` (parsing.py:9-10) are not touched.
4. **Backwards-compatible config evolution.** PR-1 turns `process_name: str` into `list[str]` but coerces a legacy string env var into a single-element list — never breaks an existing `POE2RPC_PROCESS_NAME=Foo.exe` user. (Env prefix is `POE2RPC_` per `infrastructure/settings.py:38` `env_prefix="POE2RPC_"` — NO underscore between `POE2` and `RPC`.)
5. **Reversible state mutations.** AFK and owner pin both must round-trip cleanly: AFK ON→OFF restores prior `small_image` (threaded through publisher kwargs, not stashed-and-ignored); owner-pin reset on each new `: You have entered <area>` window.

### Decision Drivers (top 4)

1. **Maintainer is slow (last commit 2025-07-29, 10mo).** Bias toward small reviewable PRs (~30-150 LOC each in `main.py`) and zero new heavyweight runtime deps in upstream's tree. We DO NOT block local progress on merges.
2. **Hexagonal-vs-single-file architectural mismatch.** Our development happens in `src/poe2_rpc/`; upstream is one 11KB `main.py`. Each PR carries the cost of a manual minimal-diff backport. Decision: accept that cost (one branch per PR), do not propose a rewrite PR.
3. **Windows-smoke is the gate.** Every feature requires a real PoE2 client + Discord screenshot in the PR description. Bd issue `panvex-12l` (G-4) is the existing live-smoke channel; each PR plugs into that workflow.
4. **Sync orchestrator with closeable stream over async refactor (PR-4 stop semantics).** Existing `Orchestrator.run_once()` is sync (`for line in stream.lines()` over `_SyncLineIterator` adapter — see `cli.py` composition root). PR-4 tray Quit needs cancellation; the cheap path is adding `LogStream.close()` to the Protocol (~30 LOC + 25 LOC tests) instead of an async refactor (~120 LOC + 60 LOC tests touching every adapter and the cli composition). Sync-close keeps the blast radius inside three files (`ports.py`, `log_stream.py`, `orchestrator.py`) and preserves the existing `_SyncLineIterator` bridge — async refactor would force every test that touches the orchestrator to become `pytest.mark.asyncio`.

### Viable Options (genuinely contested decisions)

#### Decision A: Tray library

| Option | Pros | Cons |
|---|---|---|
| **pystray (chosen)** | Pure-Python, MIT, Pillow-based icons, ~70KB; Windows + macOS + Linux backends; spec explicitly names it (constraint §"Background launcher") | Pillow dep adds ~3MB; needs explicit `Pillow` in `pyproject.toml` |
| infi.systray | Windows-only, smaller (~50KB), no Pillow | Win32-only — kills cross-platform dev; less active maintenance |
| pywin32 + manual systray | Zero new pure-Python deps | ~5MB Win32 install, requires admin for some flows; spec §non-goals explicitly excludes pywin32 path |

**Decision: pystray.** Pillow cost amortized across icon swap (AFK could reuse it later); cross-platform keeps macOS dev-loop alive. **Move to optional extras** (`[project.optional-dependencies] tray = [...]`) so headless-only installs stay slim — see PR-4 file table.

#### Decision B: Backport workflow

| Option | Pros | Cons |
|---|---|---|
| **Per-feature branch (chosen)** — `upstream-pr/official-client`, `upstream-pr/owner-detection`, etc., each branched from `upstream/main` | Independent merge timing; one PR can land while others iterate; clear blast radius per branch | 4 manual diffs to maintain; risk of drift if upstream lands changes between PRs |
| Single `upstream-pr/all-four` branch with cherrypicked features | One review burden | Maintainer rejection of one feature blocks the rest; large diff = lower merge probability |
| `git format-patch` series mailed/attached | Clean per-commit history | GitHub PR UI doesn't surface patch series well; maintainer expects PRs |

**Decision: per-feature branch.** Aligns with spec §"PR Sequence Plan" (4 sequential PRs) and minimises rejection blast radius.

#### Decision C: Owner detection state machine location

| Option | Pros | Cons |
|---|---|---|
| **`domain/owner.py` frozen VO + `application/` driver (chosen)** | Pure domain logic testable without IO; matches existing `domain/models.py` pattern (frozen pydantic VOs); orchestrator wires the transitions | Adds a new domain module + slight orchestration coupling |
| All-in-one in `application/handlers.py` | Simpler diff | Mixes state-machine logic with side-effecting handlers; harder to unit-test transitions in isolation |
| Pure-functional reducer in `application/` only | No new domain module | Owner = a domain concept (LocalPlayer); belongs in `domain/` per spec ontology table |

**Decision: domain VO + application driver.** Spec ontology row `OwnerTracker | core domain` mandates domain placement.

#### Decision D: AFK presence-restore mechanism

| Option | Pros | Cons |
|---|---|---|
| **Stash-and-thread: capture `small_image` on `AFKStatus.on=True` into `MutableState.prior_small_image`; on OFF, pass it back via `publisher.publish(..., small_image_override=prior)` (chosen)** | Reversible by construction; the captured value is actually consumed by the publisher (no dead code); semantics survive level-change events that occur DURING AFK ON | Adds `prior_small_image: str \| None` field to MutableState AND a `small_image_override` kwarg to `publisher.publish()` / `_build_update_kwargs()` |
| Recompute `small_image` from current LevelInfo each time (the rejected dead-stash variant) | Stateless | Loses the pre-AFK class info if the player levels during AFK (e.g. AFK-XP-share); recomputation returns the new ascendency, not the snapshot — fails spec AC §"ON-OFF round-trip restores exact prior presence payload" |
| Suffix `[AFK]` only, never swap icon | Simplest diff | Spec AC explicitly requires `swaps small_image to "afk" asset key` |

**Decision: stash-and-thread.** Mandated by spec AC; iteration 1 of this plan added the field but failed to wire it into the publisher (dead code). Iteration 2 fixes that — see PR-3 §Symbols and `test_afk_restore_after_level_during_afk`.

---

## Per-PR Task Breakdown

Branch model:
- Develop on `feature/<slug>` in our repo (ours).
- Backport branch `upstream-pr/<slug>` rooted at `upstream/main` (added as remote per spec §"Upstream findings"; verify with `git remote -v`).

LOC estimates are deltas vs. mainline `src/poe2_rpc/` and vs. upstream `main.py` respectively.

---

### PR-1: Official PoE2 Client Support

**Branch:** `feature/official-client` (ours) → `upstream-pr/official-client` (upstream)
**Bd epic:** `panvex-pr1` (parent), with sub-tasks `panvex-pr1.1` (settings), `panvex-pr1.2` (detector), `panvex-pr1.3` (tests), `panvex-pr1.4` (backport+PR)
**Estimated total:** ~80 LOC ours / ~30 LOC upstream

#### Files to modify (ours)

| File | Change | LOC |
|---|---|---|
| `src/poe2_rpc/infrastructure/settings.py` | `process_name: str = "PathOfExileSteam.exe"` → `process_name: list[str] = ["PathOfExileSteam.exe", "PathOfExile.exe"]` + pydantic `field_validator` to coerce a string into `[string]` for backwards compat with `POE2RPC_PROCESS_NAME=Foo.exe` (env prefix is `POE2RPC_`, not `POE2_RPC_` — verified at `settings.py:38`) | +12 / -1 |
| `src/poe2_rpc/infrastructure/detection.py` | `_iter_processes_safely` line 53: `info.get("name") == self._settings.process_name` → `info.get("name") in self._settings.process_name`; `log_path()` log call line 46: `process=self._settings.process_name` already a list, fine | +2 / -1 |
| `tests/unit/test_detection.py` (new) | Two parametrized cases: `("PathOfExileSteam.exe", "...steamapps/common/Path of Exile 2/logs/Client.txt")` and `("PathOfExile.exe", "...Grinding Gear Games/Path of Exile 2/logs/Client.txt")`. Mock `psutil.process_iter` to return one fake proc per case. Plus `test_string_process_name_coerced_to_list()` for back-compat. | +60 |
| `tests/unit/test_settings.py` (extend) | `test_process_name_string_env_coerced_to_list(monkeypatch)`: set `POE2RPC_PROCESS_NAME=Foo.exe`, assert `AppSettings().process_name == ["Foo.exe"]` | +12 |

PR description must use the env var name `POE2RPC_PROCESS_NAME` (no underscore between `POE2` and `RPC`). The README already uses the correct prefix.

#### Symbols (Python type-annotated)

```python
# src/poe2_rpc/infrastructure/settings.py
from pydantic import field_validator

class AppSettings(BaseSettings):
    process_name: list[str] = ["PathOfExileSteam.exe", "PathOfExile.exe"]

    @field_validator("process_name", mode="before")
    @classmethod
    def _coerce_string_to_list(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            return [v]
        return v
```

```python
# src/poe2_rpc/infrastructure/detection.py
def _iter_processes_safely(self) -> Iterator[Path | None]:
    candidates = self._settings.process_name  # list[str]
    for proc in self._process_iter(["name", "exe"]):
        try:
            info = proc.info
            if info.get("name") in candidates:
                exe = info.get("exe")
                if exe:
                    yield Path(exe).parent / "logs" / "Client.txt"
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
```

#### Test stubs (`tests/unit/test_detection.py`)

```python
import pytest
from pathlib import Path
from unittest.mock import MagicMock
from poe2_rpc.infrastructure.detection import PsutilGameDetector
from poe2_rpc.infrastructure.settings import AppSettings


@pytest.mark.parametrize(
    "process_name,exe_dir,expected_log",
    [
        ("PathOfExileSteam.exe", r"C:\Steam\steamapps\common\Path of Exile 2",
         r"C:\Steam\steamapps\common\Path of Exile 2\logs\Client.txt"),
        ("PathOfExile.exe", r"C:\Grinding Gear Games\Path of Exile 2",
         r"C:\Grinding Gear Games\Path of Exile 2\logs\Client.txt"),
    ],
)
def test_detector_resolves_log_path_for_both_clients(process_name, exe_dir, expected_log):
    fake_proc = MagicMock()
    fake_proc.info = {"name": process_name, "exe": f"{exe_dir}\\{process_name}"}
    settings = AppSettings()
    detector = PsutilGameDetector(settings, process_iter_factory=lambda fields: iter([fake_proc]))
    assert detector.find_log_path() == Path(expected_log)


def test_detector_returns_none_when_no_match():
    fake_proc = MagicMock()
    fake_proc.info = {"name": "Notepad.exe", "exe": r"C:\Windows\Notepad.exe"}
    settings = AppSettings()
    detector = PsutilGameDetector(settings, process_iter_factory=lambda fields: iter([fake_proc]))
    assert detector.find_log_path() is None


def test_string_process_name_coerced_to_list(monkeypatch):
    monkeypatch.setenv("POE2RPC_PROCESS_NAME", "Foo.exe")
    settings = AppSettings()
    assert settings.process_name == ["Foo.exe"]
```

#### Backport (upstream-pr/official-client)

Upstream `main.py` (per spec §"Upstream findings", lines roughly): the process check is the inline `for proc in psutil.process_iter(...)` block matching `proc.info["name"] == "PathOfExileSteam.exe"`. Equivalent change:

```python
# upstream main.py change (manual minimal diff)
PROCESS_CANDIDATES = ["PathOfExileSteam.exe", "PathOfExile.exe"]

# inside the existing process loop:
if proc.info["name"] in PROCESS_CANDIDATES:
    ...
```

Branch protocol:
```bash
git fetch upstream
git checkout -b upstream-pr/official-client upstream/main
# hand-edit main.py (no test files, no src/ layout)
git add main.py
git commit -m "Support official PoE2 client (PathOfExile.exe) alongside Steam build"
git push origin upstream-pr/official-client
gh pr create --repo ezbooz/Path-Of-Exile-2-RPC --base main \
  --title "Support official PoE2 client (PathOfExile.exe) alongside Steam" \
  --body "<see PR-description template below; include footer 'More features in this series follow (owner-pin, AFK, tray-launcher) — happy to flag intent so you can signal scope appetite.'>"
```

The PR-1 description footer signal is the cheapest implementation of the "draft-PR-first" alternative considered in the ADR — opens the engagement channel without delaying ready PRs.

#### Acceptance criteria (testable)

- [ ] `pytest tests/unit/test_detection.py -ra` passes 3 tests including parametrized case for both process names.
- [ ] `pytest tests/unit/test_settings.py::test_process_name_string_env_coerced_to_list` passes.
- [ ] `mypy --strict src/poe2_rpc` clean.
- [ ] `ruff check src tests && ruff format --check src tests` clean.
- [ ] `lint-imports` clean.
- [ ] Backport branch `upstream-pr/official-client` exists, contains only `main.py` diff (`git diff upstream/main..upstream-pr/official-client --stat` shows one file).
- [ ] Upstream PR description includes Windows screenshot proving Steam-build still works (regression evidence).
- [ ] Upstream PR description footer flags "more features in this series follow" so maintainer can signal scope appetite before PR-2 lands.
- [ ] Bd `panvex-pr1` closed only after upstream PR opened.

---

### PR-2: Owner Detection (Auto-Pin)

**Branch:** `feature/owner-detection` → `upstream-pr/owner-detection`
**Bd epic:** `panvex-pr2` (parent), sub-tasks: `.1` (domain), `.2` (parser regex + Protocol extension), `.3` (orchestrator wiring), `.4` (tests party-of-3 + Protocol conformance), `.5` (backport+PR)
**Estimated total:** ~280 LOC ours / ~80 LOC upstream
**Mode flag:** DELIBERATE — see pre-mortem below.

#### Files to create/modify (ours)

| File | Change | LOC |
|---|---|---|
| `src/poe2_rpc/domain/owner.py` (new) | `OwnerTracker` frozen pydantic VO + `OwnerState` enum (`UNKNOWN`/`AREA_ENTERED`/`PINNED`/`INVALIDATED`); transition methods returning new instances (immutable per `tests/unit/test_no_mutable_state.py` AST guard) | +90 |
| `src/poe2_rpc/domain/events.py` | Add `LocalAreaEntered(area_name: str)` and `PartyMemberJoined(name: str)` | +20 |
| `src/poe2_rpc/domain/ports.py` | Extend `LogParser` Protocol with `parse_local_area_entered(line: str) -> str \| None` and `parse_party_joined(line: str) -> str \| None`. Protocol stays `runtime_checkable` so `isinstance(RegexLogParser(...), LogParser)` works in the conformance test. | +4 |
| `src/poe2_rpc/infrastructure/parsing.py` | Add 3 regexes verbatim from spec: `regex_local_area_entered`, `regex_party_joined`, `regex_party_left` (last for symmetry, even though only join+local matter for pin); add corresponding `RegexLogParser.parse_local_area_entered` and `parse_party_joined` methods so it satisfies the extended `LogParser` Protocol | +35 |
| `src/poe2_rpc/infrastructure/settings.py` | `character_name: str \| None = None` (spec AC §"Optional override") | +1 |
| `src/poe2_rpc/application/handlers.py` | `MutableState` gains `owner_tracker: OwnerTracker = OwnerTracker.unknown()`; `on_level_changed` consults `owner_tracker.should_emit(li.username)` and returns early on miss; new `on_local_area_entered` and `on_party_joined` handlers transition the tracker | +50 |
| `src/poe2_rpc/application/orchestrator.py` | Subscribe new events; in main parse loop add 2 new branches before existing instance-event branch | +15 |
| `tests/unit/test_owner.py` (new) | State-machine tests + party-of-3 integration test | +120 |
| `tests/unit/test_log_parser_protocol.py` (new) | `test_regex_log_parser_satisfies_protocol`: `assert isinstance(RegexLogParser(catalog), LogParser)` — proves the concrete adapter still conforms after Protocol extension. Add a second test that passes a deliberately-incomplete fake parser and asserts `isinstance(...) is False` to verify Protocol membership is structural. | +25 |

#### Symbols

```python
# src/poe2_rpc/domain/ports.py — LogParser extension
@runtime_checkable
class LogParser(Protocol):
    def parse_level(self, line: str) -> LevelInfo | None: ...
    def parse_instance(self, line: str) -> InstanceInfo | None: ...
    def parse_local_area_entered(self, line: str) -> str | None: ...
    def parse_party_joined(self, line: str) -> str | None: ...
```

```python
# src/poe2_rpc/domain/owner.py
from __future__ import annotations
from enum import Enum
from typing import Literal
from pydantic import BaseModel, ConfigDict


class OwnerState(str, Enum):
    UNKNOWN = "unknown"
    AREA_ENTERED = "area_entered"
    PINNED = "pinned"
    INVALIDATED = "invalidated"  # set when a party member joined within an AREA_ENTERED window


class OwnerTracker(BaseModel):
    model_config = ConfigDict(frozen=True)

    state: OwnerState = OwnerState.UNKNOWN
    pinned_name: str | None = None
    override_name: str | None = None  # from AppSettings.character_name

    @classmethod
    def unknown(cls, override_name: str | None = None) -> "OwnerTracker":
        return cls(state=OwnerState.UNKNOWN, pinned_name=override_name, override_name=override_name)

    def on_local_area_entered(self) -> "OwnerTracker":
        # Override always wins; state machine pre-pins to override_name
        if self.override_name is not None:
            return self.model_copy(update={"state": OwnerState.PINNED, "pinned_name": self.override_name})
        return self.model_copy(update={"state": OwnerState.AREA_ENTERED, "pinned_name": None})

    def on_party_member_joined(self) -> "OwnerTracker":
        if self.state == OwnerState.AREA_ENTERED:
            return self.model_copy(update={"state": OwnerState.INVALIDATED})
        if self.state == OwnerState.PINNED:
            # Documented semantics (see pre-mortem #4): a join while PINNED does NOT
            # destroy the pin. The override (or already-confirmed-solo level event)
            # is more authoritative than a late join. We log a warning at the handler
            # layer and keep the pin; pin will re-validate on the NEXT area entry.
            return self
        return self  # UNKNOWN ignores party joins (no active window)

    def on_level_event(self, username: str) -> "OwnerTracker":
        if self.state == OwnerState.AREA_ENTERED:
            return self.model_copy(update={"state": OwnerState.PINNED, "pinned_name": username})
        return self  # PINNED + UNKNOWN + INVALIDATED don't pin

    def should_emit(self, username: str) -> bool:
        if self.state == OwnerState.PINNED:
            return self.pinned_name == username
        if self.state == OwnerState.AREA_ENTERED:
            return True  # first level event in clean window pins AND emits
        # UNKNOWN: emit (legacy behavior, no party context yet)
        # INVALIDATED: drop (party members in zone, can't tell who)
        return self.state == OwnerState.UNKNOWN
```

```python
# src/poe2_rpc/infrastructure/parsing.py — additions
regex_local_area_entered = re.compile(r": You have entered (.*)\.")
regex_party_joined = re.compile(r": (\S+) has joined the area\.")
regex_party_left = re.compile(r": (\S+) has left the area\.")


class RegexLogParser:
    # ... existing parse_level / parse_instance unchanged ...

    def parse_local_area_entered(self, line: str) -> str | None:
        m = regex_local_area_entered.search(line)
        return m.group(1) if m else None

    def parse_party_joined(self, line: str) -> str | None:
        m = regex_party_joined.search(line)
        return m.group(1) if m else None
```

#### Test stubs (`tests/unit/test_owner.py`)

```python
import pytest
from poe2_rpc.domain.owner import OwnerTracker, OwnerState


def test_initial_state_is_unknown():
    t = OwnerTracker.unknown()
    assert t.state == OwnerState.UNKNOWN
    assert t.pinned_name is None


def test_local_area_entered_no_override_transitions_to_area_entered():
    t = OwnerTracker.unknown().on_local_area_entered()
    assert t.state == OwnerState.AREA_ENTERED


def test_local_area_entered_with_override_pins_immediately():
    t = OwnerTracker.unknown(override_name="MyChar").on_local_area_entered()
    assert t.state == OwnerState.PINNED
    assert t.pinned_name == "MyChar"


def test_party_join_in_area_window_invalidates():
    t = OwnerTracker.unknown().on_local_area_entered().on_party_member_joined()
    assert t.state == OwnerState.INVALIDATED


def test_first_level_in_clean_window_pins():
    t = OwnerTracker.unknown().on_local_area_entered().on_level_event("Alice")
    assert t.state == OwnerState.PINNED
    assert t.pinned_name == "Alice"


def test_should_emit_only_for_pinned_name():
    t = OwnerTracker(state=OwnerState.PINNED, pinned_name="Alice")
    assert t.should_emit("Alice") is True
    assert t.should_emit("Bob") is False


def test_invalidated_state_drops_all_emit():
    t = OwnerTracker(state=OwnerState.INVALIDATED)
    assert t.should_emit("Alice") is False
    assert t.should_emit("Bob") is False


def test_party_join_while_pinned_keeps_pin():
    # Documented semantics: a join while PINNED does not invalidate the pin.
    # Handler layer logs a warning; pin re-validates on next area entry.
    t = (OwnerTracker.unknown()
         .on_local_area_entered()
         .on_level_event("Alice")
         .on_party_member_joined())
    assert t.state == OwnerState.PINNED
    assert t.pinned_name == "Alice"


@pytest.mark.parametrize(
    "lines,expected_pinned",
    [
        # Solo: enter area → level → pinned to player
        ([("area", "Lioneye's Watch"), ("level", "Alice")], "Alice"),
        # Party of 2: enter area → party joins → level → invalidated, no pin
        ([("area", "Lioneye's Watch"), ("party_join", "Bob"), ("level", "Bob")], None),
        # Party of 3: enter area, then 2 join, then level → invalidated
        ([("area", "Lioneye's Watch"), ("party_join", "Bob"), ("party_join", "Charlie"),
          ("level", "Bob")], None),
    ],
)
def test_party_scenarios(lines, expected_pinned):
    t = OwnerTracker.unknown()
    for kind, payload in lines:
        if kind == "area":
            t = t.on_local_area_entered()
        elif kind == "party_join":
            t = t.on_party_member_joined()
        elif kind == "level":
            t = t.on_level_event(payload)
    assert t.pinned_name == expected_pinned


def test_re_entering_area_resets_invalidated_state():
    t = OwnerTracker.unknown().on_local_area_entered().on_party_member_joined()
    assert t.state == OwnerState.INVALIDATED
    t = t.on_local_area_entered()  # left zone, re-entered solo
    assert t.state == OwnerState.AREA_ENTERED  # fresh window
```

```python
# tests/unit/test_log_parser_protocol.py
from poe2_rpc.domain.ports import LogParser
from poe2_rpc.infrastructure.parsing import RegexLogParser


def test_regex_log_parser_satisfies_protocol():
    """Protocol-conformance: RegexLogParser must satisfy the extended LogParser Protocol.

    Guards against future Protocol/impl drift — adding a method to the Protocol
    without implementing it on the adapter would silently pass mypy in
    structural-typing mode but blow up at runtime.
    """
    parser = RegexLogParser()  # constructor uses module-level regex constants
    assert isinstance(parser, LogParser)


def test_incomplete_parser_fails_protocol_check():
    """Sanity: Protocol membership is structural, not nominal."""
    class FakeParser:
        def parse_level(self, line):  # missing parse_instance + new methods
            return None

    assert not isinstance(FakeParser(), LogParser)
```

#### Backport (upstream-pr/owner-detection)

Upstream `main.py` minimal-diff:
- Add 2 module-level regex `re.compile(...)` for `area_local` and `area_join` (verbatim from spec).
- Add 3 module-level state vars: `_owner_state = "UNKNOWN"`, `_pinned_name = None`, `_override_name = os.environ.get("POE2_CHARACTER_NAME")`.
- In the line-processing loop, before the existing `regex_level` match: check `area_local` regex → set `_owner_state = "AREA_ENTERED"`; check `area_join` → if `_owner_state == "AREA_ENTERED"` set to `"INVALIDATED"`; if `_owner_state == "PINNED"` log `print("[warn] party member joined while pinned; will re-validate next area entry")` (no state change — see pre-mortem #4).
- After the level regex matches but before presence update: if `_owner_state == "PINNED"` and `username != _pinned_name`, `continue`. If `_owner_state == "AREA_ENTERED"`, `_pinned_name = username; _owner_state = "PINNED"`.

**Architectural divergence note for backport:** upstream uses module-level `_owner_state` / `_pinned_name` / `_override_name` mutable globals because there is no class to hang them on (single-script style). Our hexagonal repo uses an immutable `OwnerTracker` VO carried in `MutableState`. This is an intentional divergence — do NOT try to port `OwnerTracker` upstream; it would balloon the diff and conflict with upstream's idioms. The state-transition table is the contract; representation differs by branch.

Branch:
```bash
git fetch upstream
git checkout -b upstream-pr/owner-detection upstream/main
# hand-edit main.py
git commit -am "Auto-pin owner via area-entered + level event; filter party-member level events"
gh pr create --repo ezbooz/Path-Of-Exile-2-RPC --base main \
  --title "Auto-pin local player; filter party-member level events from presence"
```

#### Pre-mortem (DELIBERATE mode, 4 scenarios)

1. **Failure: Player enters zone solo, party joins later, then player levels.** State: `AREA_ENTERED → INVALIDATED → INVALIDATED`. Player's own level event is dropped — false negative.
   **Mitigation:** Document in README that owner-pin requires either (a) entering a zone alone or (b) setting `POE2RPC_CHARACTER_NAME`. Override always wins.

2. **Failure: Two characters with the same name.** Pinned name matches a party member with identical username. Wrong-player level events flow through.
   **Mitigation:** Out of scope (spec §"Detect which player started the script" only requires party-conflict mitigation, not name-collision). Document.

3. **Failure: `: You have entered` appears multiple times in rapid succession (e.g. portal hops).** Each call resets state, potentially mid-pin.
   **Mitigation:** Decision: each new area-entered DOES reset pin (safer) — re-pin happens on the next level event. Document this in the docstring. Covered by `test_re_entering_area_resets_invalidated_state`.

4. **Failure: Party member joins AFTER pin (`PINNED` state).** A literal reading of "any join invalidates" would destroy a confirmed pin.
   **Mitigation chosen — log-and-keep:** `on_party_member_joined()` while `PINNED` returns `self` (no state change); the handler layer logs a warning (`structlog.warning("party_member_joined_while_pinned", joiner=name, pinned=current.pinned_name)`) and the pin will naturally re-validate on the next `: You have entered` (which resets the window). This preserves the legitimate solo-then-joined case without needing user intervention. Covered by `test_party_join_while_pinned_keeps_pin`. Alternative (silent-pass) was rejected because operators have no signal that party-mode started — the warning is the diagnostic trail.

#### Acceptance criteria (testable)

- [ ] `tests/unit/test_owner.py` 10 tests pass including parametrized 3-row party scenario AND `test_party_join_while_pinned_keeps_pin`.
- [ ] `tests/unit/test_log_parser_protocol.py` 2 tests pass (positive conformance + structural negative).
- [ ] State-machine table matches spec §"PR-2 Owner Detection" AC items verbatim (`UNKNOWN → AREA_ENTERED → PINNED`).
- [ ] `lint-imports` enforces no `infrastructure` import from `domain/owner.py`.
- [ ] AST guard `tests/unit/test_no_mutable_state.py` passes (OwnerTracker is frozen pydantic).
- [ ] Override `POE2RPC_CHARACTER_NAME=Alice` short-circuits to PINNED on first area entry — covered by `test_local_area_entered_with_override_pins_immediately`.
- [ ] Manual Windows live-smoke: 2-player party, only the local player's level-up updates Discord. Screenshot in PR.

---

### PR-3: AFK Status

**Branch:** `feature/afk-status` → `upstream-pr/afk-status`
**Bd epic:** `panvex-pr3`, sub-tasks `.1` (regex+event), `.2` (handler+restore), `.3` (presence kwargs), `.4` (tests), `.5` (backport+PR+README)
**Estimated total:** ~170 LOC ours / ~50 LOC upstream

#### Files to create/modify (ours)

| File | Change | LOC |
|---|---|---|
| `src/poe2_rpc/infrastructure/parsing.py` | Add `regex_afk` verbatim from spec; add `parse_afk_event() -> AFKStatus \| None` | +20 |
| `src/poe2_rpc/domain/models.py` | Add `AFKStatus` frozen VO: `mode: Literal["AFK","DND"]`, `on: bool`, `autoreply: str \| None` | +15 |
| `src/poe2_rpc/domain/events.py` | Add `AFKStatusChanged(status: AFKStatus)` event | +8 |
| `src/poe2_rpc/domain/ports.py` | Extend `PresencePublisher.publish` signature with `small_image_override: str \| None = None` (defaults preserve back-compat for non-AFK call sites). Protocol-conformance test in PR-2's `test_log_parser_protocol.py` style is added for `PypresencePublisher`. | +2 |
| `src/poe2_rpc/application/handlers.py` | `MutableState` gains `afk_on: bool = False`, `prior_small_image: str \| None = None`; new `on_afk_changed` handler captures `prior_small_image` from current `level_info` on AFK ON, then **threads it through** the publisher call on AFK OFF via `small_image_override=current_state.prior_small_image`. On AFK ON, calls `publish(..., small_image_override="afk")`. | +40 |
| `src/poe2_rpc/infrastructure/presence.py` | `publish()` and `_build_update_kwargs()` both accept `small_image_override: str \| None = None`; when set, the override REPLACES the recomputed `small_image` (None means recompute as before). When `afk_on=True`, the orchestrator passes `small_image_override="afk"`; on AFK OFF, the orchestrator passes the captured `prior_small_image` (which is the snapshot taken at AFK ON time, NOT the value recomputed from any post-ON level changes). | +25 |
| `src/poe2_rpc/application/orchestrator.py` | Subscribe `AFKStatusChanged`; in parse loop add branch for AFK regex | +15 |
| `tests/unit/test_afk.py` (new) | Parametrized cases: AFK ON, DND ON, AFK OFF round-trip; presence-kwargs assertions; **plus `test_afk_restore_after_level_during_afk`** proving the captured snapshot survives a level-change inside the AFK window; **plus `test_afk_on_off_with_no_prior_level_info`** covering the architect-flagged edge where AFK ON arrives before any `is now level` event (state.level_info is None). | +135 |
| `README.md` (addendum) | Section "Discord assets: upload `afk.png`" with steps for Discord developer portal | +25 |

#### Symbols

```python
# src/poe2_rpc/domain/models.py — addition
class AFKStatus(BaseModel):
    model_config = ConfigDict(frozen=True)
    mode: Literal["AFK", "DND"]
    on: bool
    autoreply: str | None = None
```

```python
# src/poe2_rpc/infrastructure/parsing.py — addition
# Verbatim from spec §"Regex contracts":
regex_afk = re.compile(
    r'.*\[INFO Client \d+\] : (DND|AFK) mode is now (?:(ON)\. Autoreply "(.*)"|(OFF))'
)


def parse_afk_event(line: str) -> AFKStatus | None:
    m = regex_afk.search(line)
    if not m:
        return None
    mode = m.group(1)  # "AFK" or "DND"
    on_token = m.group(2)  # "ON" or None
    autoreply = m.group(3)  # str or None
    off_token = m.group(4)  # "OFF" or None
    if on_token == "ON":
        return AFKStatus(mode=mode, on=True, autoreply=autoreply)
    if off_token == "OFF":
        return AFKStatus(mode=mode, on=False, autoreply=None)
    return None
```

```python
# src/poe2_rpc/domain/ports.py — extend PresencePublisher
@runtime_checkable
class PresencePublisher(Protocol):
    async def connect(self) -> None: ...
    async def publish(
        self,
        level_info: LevelInfo | None,
        instance_info: InstanceInfo | None,
        *,
        afk_on: bool = False,
        small_image_override: str | None = None,
    ) -> None: ...
    def close(self) -> None: ...
```

```python
# src/poe2_rpc/application/handlers.py — addition
async def on_afk_changed(
    event: AFKStatusChanged,
    *,
    publisher: PresencePublisher,
    throttle: PresenceThrottle,
    current_state: MutableState,
) -> None:
    status = event.status
    structlog.contextvars.bind_contextvars(afk=status.on, afk_mode=status.mode)
    if status.on:
        # Snapshot current small_image so OFF can restore EXACTLY this value,
        # even if level changes during the AFK window.
        if current_state.level_info is not None:
            asc = (current_state.level_info.ascension_class
                   or current_state.level_info.base_class)
            current_state.prior_small_image = asc.lower().replace(" ", "_")
        current_state.afk_on = True
        _log.info("afk_on", mode=status.mode, snapshot=current_state.prior_small_image)
        await publisher.publish(
            current_state.level_info,
            current_state.instance_info,
            afk_on=True,
            small_image_override="afk",
        )
    else:
        current_state.afk_on = False
        restore = current_state.prior_small_image  # may be None if no level seen pre-AFK
        _log.info("afk_off", mode=status.mode, restored=restore)
        await publisher.publish(
            current_state.level_info,
            current_state.instance_info,
            afk_on=False,
            small_image_override=restore,
        )
        # Optional: clear the snapshot so a stale value doesn't leak into a
        # future AFK cycle that starts before any new level event.
        current_state.prior_small_image = None
```

```python
# src/poe2_rpc/infrastructure/presence.py — extend
async def publish(
    self,
    level_info: LevelInfo | None,
    instance_info: InstanceInfo | None,
    *,
    afk_on: bool = False,
    small_image_override: str | None = None,
) -> None:
    ...
    kwargs = self._build_update_kwargs(
        level_info, instance_info,
        afk_on=afk_on,
        small_image_override=small_image_override,
    )
    ...

@staticmethod
def _build_update_kwargs(
    level_info: LevelInfo | None,
    instance_info: InstanceInfo | None,
    *,
    afk_on: bool = False,
    small_image_override: str | None = None,
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {"start": int(datetime.now(tz=UTC).timestamp())}
    if level_info is not None:
        # ... existing details/small_image construction (computes default key) ...
        # default_small = (level_info.ascension_class or level_info.base_class)
        #                 .lower().replace(" ", "_")
        # kwargs["small_image"] = default_small
        if small_image_override is not None:
            # The handler decided what to show — could be "afk" or a snapshot
            # captured at AFK-ON time. Override wins over recomputation.
            kwargs["small_image"] = small_image_override
    if instance_info is not None:
        state_str = f"In: {instance_info.area_display_name} (Lvl {instance_info.level})"
        if afk_on:
            state_str += " [AFK]"
        kwargs["state"] = state_str
    return kwargs
```

#### Test stubs (`tests/unit/test_afk.py`)

```python
import pytest
from poe2_rpc.infrastructure.parsing import parse_afk_event
from poe2_rpc.infrastructure.presence import PypresencePublisher
from poe2_rpc.domain.models import AFKStatus, LevelInfo, InstanceInfo


@pytest.mark.parametrize(
    "line,expected",
    [
        ('2026-05-05 12:00:00 12345 [INFO Client 1234] : AFK mode is now ON. Autoreply "brb"',
         AFKStatus(mode="AFK", on=True, autoreply="brb")),
        ('2026-05-05 12:00:00 12345 [INFO Client 1234] : AFK mode is now OFF',
         AFKStatus(mode="AFK", on=False, autoreply=None)),
        ('2026-05-05 12:00:00 12345 [INFO Client 1234] : DND mode is now ON. Autoreply "busy"',
         AFKStatus(mode="DND", on=True, autoreply="busy")),
        ('2026-05-05 12:00:00 12345 [INFO Client 1234] : DND mode is now OFF',
         AFKStatus(mode="DND", on=False, autoreply=None)),
    ],
)
def test_parse_afk_event_table(line, expected):
    assert parse_afk_event(line) == expected


def test_parse_afk_event_returns_none_for_unrelated_line():
    assert parse_afk_event("2026-05-05 12:00:00 [INFO Client 1234] : Connected to ...") is None


def test_presence_kwargs_afk_on_appends_afk_suffix_and_swaps_small_image():
    li = LevelInfo(username="Alice", base_class="Witch", ascension_class=None, level=10)
    ii = InstanceInfo(level=5, area_code="G1_1", area_display_name="Lioneye's Watch", seed=1)
    kwargs = PypresencePublisher._build_update_kwargs(
        li, ii, afk_on=True, small_image_override="afk",
    )
    assert kwargs["small_image"] == "afk"
    assert kwargs["state"].endswith("[AFK]")


def test_presence_kwargs_afk_off_with_restore_override():
    """OFF with explicit override restores the captured snapshot, not the recomputed default."""
    li = LevelInfo(username="Alice", base_class="Witch", ascension_class=None, level=10)
    ii = InstanceInfo(level=5, area_code="G1_1", area_display_name="Lioneye's Watch", seed=1)
    kwargs = PypresencePublisher._build_update_kwargs(
        li, ii, afk_on=False, small_image_override="witch",
    )
    assert kwargs["small_image"] == "witch"
    assert "[AFK]" not in kwargs["state"]


def test_afk_restore_after_level_during_afk():
    """Critical regression test: snapshot survives a level change inside the AFK window.

    Scenario:
      1. Player is Witch at level 10 (small_image="witch").
      2. Player goes AFK ON: handler captures prior_small_image="witch".
      3. Party-XP-share or quest reward levels them up; ascendency selected -> "Infernalist".
         (LevelInfo now has ascension_class="Infernalist", small_image would
         recompute to "infernalist".)
      4. Player goes AFK OFF: handler must pass small_image_override="witch"
         (the snapshot), NOT the freshly-recomputed "infernalist".

    This proves stash-and-restore semantics — the dead-stash variant from iteration 1
    of this plan would have failed this test because nothing consumed prior_small_image.
    """
    from poe2_rpc.application.handlers import MutableState, on_afk_changed
    from poe2_rpc.domain.events import AFKStatusChanged
    from unittest.mock import AsyncMock, MagicMock

    state = MutableState()
    state.level_info = LevelInfo(
        username="Alice", base_class="Witch", ascension_class=None, level=10,
    )
    state.instance_info = InstanceInfo(
        level=5, area_code="G1_1", area_display_name="Lioneye's Watch", seed=1,
    )
    publisher = AsyncMock()
    throttle = MagicMock()

    # Step 2: AFK ON — snapshot taken
    import asyncio
    asyncio.run(on_afk_changed(
        AFKStatusChanged(status=AFKStatus(mode="AFK", on=True)),
        publisher=publisher, throttle=throttle, current_state=state,
    ))
    assert state.prior_small_image == "witch"
    publisher.publish.assert_awaited_with(
        state.level_info, state.instance_info,
        afk_on=True, small_image_override="afk",
    )
    publisher.publish.reset_mock()

    # Step 3: Level/ascendency changes mid-AFK
    state.level_info = LevelInfo(
        username="Alice", base_class="Witch",
        ascension_class="Infernalist", level=11,
    )

    # Step 4: AFK OFF — must restore snapshot, NOT recompute
    asyncio.run(on_afk_changed(
        AFKStatusChanged(status=AFKStatus(mode="AFK", on=False)),
        publisher=publisher, throttle=throttle, current_state=state,
    ))
    publisher.publish.assert_awaited_with(
        state.level_info, state.instance_info,
        afk_on=False, small_image_override="witch",  # the captured snapshot
    )


def test_afk_on_off_with_no_prior_level_info():
    """Architect-flagged edge: AFK ON arrives BEFORE any 'is now level' event.

    Scenario: user launches the game directly into a town/menu, types `/afk on`
    without having entered a level event yet. state.level_info is None.

    Contract:
      - AFK ON: publisher.publish receives level_info=None, small_image_override="afk".
        prior_small_image stays None (nothing to snapshot — no class known).
      - AFK OFF: publisher.publish receives level_info=None,
        small_image_override=None (publisher MUST handle None by omitting
        small_image entirely OR defaulting to a neutral asset; covered by the
        publisher contract test in tests/unit/test_presence.py).
      - No exception, no AttributeError on `state.level_info.base_class`.
    """
    from poe2_rpc.application.handlers import MutableState, on_afk_changed
    from poe2_rpc.domain.events import AFKStatusChanged
    from unittest.mock import AsyncMock, MagicMock

    state = MutableState()  # level_info defaults to None
    state.instance_info = None
    publisher = AsyncMock()
    throttle = MagicMock()

    import asyncio
    # AFK ON with no level_info — handler must not crash
    asyncio.run(on_afk_changed(
        AFKStatusChanged(status=AFKStatus(mode="AFK", on=True)),
        publisher=publisher, throttle=throttle, current_state=state,
    ))
    assert state.prior_small_image is None  # nothing to snapshot
    publisher.publish.assert_awaited_with(
        None, None, afk_on=True, small_image_override="afk",
    )
    publisher.publish.reset_mock()

    # AFK OFF — restore is None, publisher must handle it
    asyncio.run(on_afk_changed(
        AFKStatusChanged(status=AFKStatus(mode="AFK", on=False)),
        publisher=publisher, throttle=throttle, current_state=state,
    ))
    publisher.publish.assert_awaited_with(
        None, None, afk_on=False, small_image_override=None,
    )
```

#### Backport (upstream-pr/afk-status)

Upstream `main.py` minimal-diff:
- Add `regex_afk = re.compile(...)` verbatim.
- Add module-level `_afk_on = False` and `_prior_small_image: str | None = None`.
- In line loop add branch: if `regex_afk.search(line)` matches with ON → `_prior_small_image = <derived from current class>; _afk_on = True; update_presence(suffix="[AFK]", small_image="afk")`; OFF → `_afk_on = False; update_presence(small_image=_prior_small_image)`.

#### Acceptance criteria (testable)

- [ ] `tests/unit/test_afk.py` 8 tests pass (4 parametrized parse + 1 none + 2 presence-kwargs + 1 `test_afk_restore_after_level_during_afk` + 1 `test_afk_on_off_with_no_prior_level_info` for the architect-flagged level_info=None edge).
- [ ] `regex_afk` matches verbatim against spec §"Regex contracts".
- [ ] AFK ON → publisher called with `small_image_override="afk"` AND `_build_update_kwargs` returns `small_image="afk"` and `state.endswith("[AFK]")`.
- [ ] AFK OFF → publisher called with `small_image_override=<snapshot>`; the snapshot is the value captured at AFK ON time, EVEN IF the player levelled during the AFK window.
- [ ] No dead `prior_small_image` writes (grep `prior_small_image` in plan must show every write paired with a downstream read in `_build_update_kwargs` via `small_image_override`).
- [ ] README addendum lists Discord developer portal upload steps.
- [ ] Windows live-smoke: type `/afk on` then `/afk off` in chat; Discord screenshot before/during/after attached to PR.

---

### PR-4: Background Launcher (Startup + Tray)

**Branch:** `feature/background-launcher` → `upstream-pr/background-launcher`
**Bd epic:** `panvex-pr4`, sub-tasks `.1` (pystray extras), `.2` (tray module + import gate), `.3` (CLI subcommands + extras-missing exit), `.4` (autostart shortcut + frozen-exe path), `.5` (orchestrator stop), `.6` (tests), `.7` (PyInstaller + runtime CREATE_NO_WINDOW), `.8` (backport+PR)
**Estimated total:** ~480 LOC ours / ~150 LOC upstream

#### Files to create/modify (ours)

| File | Change | LOC |
|---|---|---|
| `pyproject.toml` | **(a)** Move `pystray>=0.19`, `Pillow>=10`, `pylnk3>=0.4` into a NEW `[project.optional-dependencies] tray = [...]` group (NOT `[project] dependencies` — headless installs stay slim). **(b)** Extend `[[tool.mypy.overrides]] module = [...]` at lines 99-101 to include `"pystray.*"`, `"PIL.*"`, `"pylnk3.*"` so `mypy --strict` passes when extras are not installed. | +6 / -0 |
| `src/poe2_rpc/infrastructure/tray.py` (new) | `TrayController` class wrapping `pystray.Icon`; menu items (`Status: ...`, `Open log file`, `Restart`, `Quit`); status string updated via thread-safe attribute. **Import-gate** at module top: `try: import pystray; from PIL import Image; except ImportError as e: raise ImportError("Tray support requires extras: pip install poe2-rpc[tray]") from e`. (Module-level gate is fine because the module is only imported by the `tray` CLI command; non-tray code paths never touch it.) | +130 |
| `src/poe2_rpc/infrastructure/autostart.py` (new) | `install_startup_shortcut(exe_path: Path, target_args: list[str]) -> Path` and `uninstall_startup_shortcut() -> bool`; uses `pylnk3` to write `.lnk` to `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\`. Same import gate as `tray.py`. | +85 |
| `src/poe2_rpc/domain/ports.py` | Extend `LogStream` Protocol with `close() -> None` (idempotent contract; documented to be safe to call from any thread). The existing `lines() -> Iterator[str]` Protocol method is unchanged. | +3 |
| `src/poe2_rpc/infrastructure/log_stream.py` | Add a thread-safe `close()` method on `WatchdogLogStream` that (a) sets an `_is_closed: bool` flag guarded by `self._lock`, (b) calls `self._observer.stop()` + `self._observer.join()` exactly once (idempotent), (c) drains/cancels the asyncio queue iterator. The `cli.py::_SyncLineIterator` adapter that already bridges the async stream to the sync `LogStream.lines()` Protocol must check `is_closed()` between yields and exit cleanly when set. | +10 |
| `src/poe2_rpc/application/orchestrator.py` | **Sync, closeable-stream design (NOT async refactor — see ADR row).** Add `Orchestrator.stop()` method that calls `self._current_stream.close()` if a stream is currently active (set in `run_once()`). The existing `for line in stream.lines():` loop at L87 exits naturally when the underlying `_SyncLineIterator` observes `is_closed()`. Wrap stream creation in `try/finally` so the stream is always closed on exit. Constructor adds `self._current_stream: LogStream | None = None`. **`run()` and `run_once()` stay sync** — no `asyncio.Event`, no `asyncio.wait`, no async refactor. Tray Quit thread calls `orch.stop()` directly; `_stream.close()` is documented thread-safe. | +5 |
| `src/poe2_rpc/cli.py` | Add 3 commands: `tray` (boots tray + orchestrator on background `threading.Thread`), `install-autostart`, `uninstall-autostart`; add `--quiet` flag to `tray`. **(a)** Each command wraps the `from poe2_rpc.infrastructure.{tray,autostart} import ...` line in `try/except ImportError`; on ImportError raise `typer.Exit` with message `"Tray support requires extras: pip install poe2-rpc[tray]"`. **(b)** `tray` command's quit callback calls `orchestrator.stop()` THEN `tray_controller.stop()` — NOT `sys.exit(0)` (which would skip cleanup). **(c)** `install-autostart` resolves the executable as `exe_path = sys.executable if getattr(sys, "frozen", False) else sys.argv[0]` (under PyInstaller `--onefile` `sys.executable` IS the bundled .exe; outside PyInstaller it would be the python interpreter, which is wrong — `sys.argv[0]` is the script). Add inline comment explaining the `frozen` check. | +110 |
| `PathOfExile2DiscordRPC.spec` | **No spec changes for v1.** Tray-mode hides the console at runtime via `subprocess.CREATE_NO_WINDOW` flag when tray subprocess is spawned, instead of building a separate `--noconsole` exe. README documents that a future `tray.spec` (separate `--noconsole` PyInstaller target) is a follow-up if the runtime approach proves insufficient on some Windows versions. | +0 |
| `tests/unit/test_autostart.py` (new) | Mock `pylnk3` write/delete; assert shortcut path = `<startup>\PathOfExile2DiscordRPC.lnk`; assert idempotent install + clean uninstall + `test_install_autostart_uses_frozen_exe_path` parametrized over frozen/non-frozen state. | +110 |
| `tests/unit/test_tray.py` (new) | Mock `pystray.Icon` + `pystray.Menu`; assert menu items present; assert status update reaches mock icon; assert `on_quit` callback wires through `orchestrator.stop()` then `tray.stop()` order. | +75 |
| `tests/unit/test_orchestrator_stop.py` (new) | **3 tests** for the sync close-stream design: (a) `test_orchestrator_stop_closes_stream_within_1s` — spin up `Orchestrator.run_once` in a `threading.Thread` against an in-memory fake stream; call `orch.stop()` from main thread; assert worker joins within 1s. (b) `test_log_stream_close_is_idempotent` — calling `WatchdogLogStream.close()` twice must not raise (tray double-quit). (c) `test_orchestrator_stop_when_no_stream_active_is_noop` — `stop()` called before any `run_once()` is a clean no-op. | +85 |
| `tests/unit/test_extras_missing.py` (new) | `test_tray_command_exits_with_message_when_pystray_missing`: monkeypatch `sys.modules["pystray"] = None` (or use `importlib.import_module` mock), invoke `typer.testing.CliRunner.invoke(app, ["tray"])`, assert exit code != 0 and message contains `"pip install poe2-rpc[tray]"`. Same for `install-autostart` w/ `pylnk3` missing. | +50 |
| `README.md` | Section "Run as background service" with `poe2-rpc install-autostart` instructions; explicit `pip install poe2-rpc[tray]` step BEFORE `poe2-rpc tray`; note about the runtime `CREATE_NO_WINDOW` approach (no separate exe today). | +50 |

#### Symbols

```python
# pyproject.toml — diff at lines 34-44 and 99-101
[project.optional-dependencies]
dev = [...]  # unchanged
tray = [
    "pystray>=0.19",
    "Pillow>=10",
    "pylnk3>=0.4",
]

[[tool.mypy.overrides]]
module = [
    "psutil.*", "pypresence.*", "watchdog.*",
    "pystray.*", "PIL.*", "pylnk3.*",
]
ignore_missing_imports = true
```

```python
# src/poe2_rpc/infrastructure/tray.py
from __future__ import annotations
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Literal

try:
    import pystray
    from PIL import Image
except ImportError as e:
    raise ImportError(
        "Tray support requires extras: pip install poe2-rpc[tray]"
    ) from e

TrayStatus = Literal["waiting", "running", "error"]


class TrayController:
    def __init__(
        self,
        *,
        on_open_log: Callable[[], None],
        on_restart: Callable[[], None],
        on_quit: Callable[[], None],
        icon_path: Path,
    ) -> None:
        self._status: TrayStatus = "waiting"
        self._on_open_log = on_open_log
        self._on_restart = on_restart
        self._on_quit = on_quit
        self._icon_image = Image.open(icon_path)
        self._icon: pystray.Icon | None = None
        self._lock = threading.Lock()

    def set_status(self, status: TrayStatus) -> None:
        with self._lock:
            self._status = status
            if self._icon is not None:
                self._icon.update_menu()

    def _build_menu(self) -> pystray.Menu:
        return pystray.Menu(
            pystray.MenuItem(lambda _i: f"Status: {self._status}", None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Open log file", lambda _i, _it: self._on_open_log()),
            pystray.MenuItem("Restart", lambda _i, _it: self._on_restart()),
            pystray.MenuItem("Quit", lambda _i, _it: self._on_quit()),
        )

    def run(self) -> None:
        self._icon = pystray.Icon(
            "poe2-rpc", self._icon_image, "PoE2 RPC", menu=self._build_menu()
        )
        self._icon.run()

    def stop(self) -> None:
        if self._icon is not None:
            self._icon.stop()
```

```python
# src/poe2_rpc/infrastructure/autostart.py
from __future__ import annotations
import os
from pathlib import Path

try:
    import pylnk3
except ImportError as e:
    raise ImportError(
        "Autostart support requires extras: pip install poe2-rpc[tray]"
    ) from e

_SHORTCUT_NAME = "PathOfExile2DiscordRPC.lnk"


def _startup_dir() -> Path:
    appdata = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    return appdata / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


def install_startup_shortcut(exe_path: Path, target_args: list[str]) -> Path:
    target = _startup_dir() / _SHORTCUT_NAME
    target.parent.mkdir(parents=True, exist_ok=True)
    pylnk3.for_file(
        target_file=str(exe_path),
        lnk_name=str(target),
        arguments=" ".join(target_args),
        description="Path of Exile 2 Discord RPC (background tray)",
    )
    return target


def uninstall_startup_shortcut() -> bool:
    target = _startup_dir() / _SHORTCUT_NAME
    if target.exists():
        target.unlink()
        return True
    return False
```

```python
# src/poe2_rpc/domain/ports.py — additions to LogStream Protocol
@runtime_checkable
class LogStream(Protocol):
    def lines(self) -> Iterator[str]: ...
    def close(self) -> None: ...  # NEW — idempotent, thread-safe
    def is_closed(self) -> bool: ...  # NEW — checked between yields


# src/poe2_rpc/infrastructure/log_stream.py — additions to WatchdogLogStream
class WatchdogLogStream:
    def __init__(self, ...) -> None:
        ...
        self._is_closed: bool = False
        self._close_lock = threading.Lock()  # already imported per file head

    def close(self) -> None:
        """Idempotent, thread-safe close. Safe to call from any thread."""
        with self._close_lock:
            if self._is_closed:
                return
            self._is_closed = True
        self._observer.stop()
        self._observer.join()
        # Wake any pending await on the queue so _SyncLineIterator sees is_closed():
        self._loop.call_soon_threadsafe(self._queue.put_nowait, "")  # sentinel; iterator filters empties

    def is_closed(self) -> bool:
        return self._is_closed


# src/poe2_rpc/application/orchestrator.py — additions (SYNC, closeable-stream)
class Orchestrator:
    def __init__(self, ...) -> None:
        ...
        self._current_stream: LogStream | None = None

    def run_once(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._publisher.connect())
            log_path = self._detector.log_path()
            stream = self._factory(log_path, loop)
            self._current_stream = stream
            try:
                for line in stream.lines():
                    if stream.is_closed():
                        break
                    # ... existing parse + emit logic unchanged ...
            finally:
                stream.close()  # idempotent — safe even if stop() already called
                self._current_stream = None
        except (asyncio.CancelledError, KeyboardInterrupt):
            _log.info("orchestrator_shutdown")
        finally:
            self._publisher.close()
            loop.close()
            asyncio.set_event_loop(None)

    def stop(self) -> None:
        """Thread-safe shutdown signal — called from the tray Quit thread.

        Closes the current stream (if any), which causes the sync
        `for line in stream.lines()` loop to exit cleanly. The orchestrator
        thread then runs the `finally` block (stream.close + publisher.close)
        and run_once returns.
        """
        stream = self._current_stream
        if stream is not None:
            stream.close()
```

```python
# src/poe2_rpc/cli.py — additions
import sys


def _resolve_tray_exe_path() -> Path:
    """In PyInstaller --onefile, sys.executable IS the bundled .exe and is
    correct. In a normal `python -m poe2_rpc` install, sys.executable is
    the python interpreter (wrong — Startup shortcut would launch python.exe
    with no args). Use sys.argv[0] in that case so the shortcut points at
    the actual installed script entrypoint.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable)
    return Path(sys.argv[0])


@app.command()
def tray(
    quiet: bool = typer.Option(False, "--quiet", help="Suppress console output."),
) -> None:
    """Run orchestrator in background; show tray icon for control."""
    try:
        from poe2_rpc.infrastructure.tray import TrayController
    except ImportError as e:
        typer.secho(str(e), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e

    settings = AppSettings()
    configure_logging(settings)
    orch = build_orchestrator(settings)

    import threading
    # orch.run() is SYNC (closeable-stream design — see ADR row "sync orchestrator over async refactor").
    # No asyncio.run wrapper — orch creates its own event loop internally per run_once().
    worker = threading.Thread(target=orch.run, daemon=True)
    worker.start()

    icon_path = _resolve_tray_icon_path()  # bundled via importlib.resources

    def _on_quit() -> None:
        orch.stop()                # signal main loop to wind down cleanly
        tray_controller.stop()     # tear down pystray icon
        # NOTE: do NOT sys.exit — let the worker thread finish cleanup,
        # then the daemon thread + main thread exit naturally.

    tray_controller = TrayController(
        on_open_log=lambda: _open_log_file(),
        on_restart=lambda: _restart_self(),
        on_quit=_on_quit,
        icon_path=icon_path,
    )
    tray_controller.run()


@app.command(name="install-autostart")
def install_autostart() -> None:
    """Create Windows Startup shortcut that boots the tray on login."""
    try:
        from poe2_rpc.infrastructure.autostart import install_startup_shortcut
    except ImportError as e:
        typer.secho(str(e), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e

    exe = _resolve_tray_exe_path()  # frozen-aware path resolution
    target = install_startup_shortcut(exe, target_args=["tray", "--quiet"])
    typer.echo(f"Installed: {target}")


@app.command(name="uninstall-autostart")
def uninstall_autostart() -> None:
    """Remove the Windows Startup shortcut if present."""
    try:
        from poe2_rpc.infrastructure.autostart import uninstall_startup_shortcut
    except ImportError as e:
        typer.secho(str(e), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e

    removed = uninstall_startup_shortcut()
    typer.echo("Removed." if removed else "Nothing to remove.")
```

#### Test stubs

```python
# tests/unit/test_autostart.py
import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from poe2_rpc.infrastructure.autostart import install_startup_shortcut, uninstall_startup_shortcut
from poe2_rpc.cli import _resolve_tray_exe_path


def test_install_creates_shortcut_in_startup_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    exe = Path(r"C:\Tools\PathOfExile2DiscordRPC.exe")
    with patch("poe2_rpc.infrastructure.autostart.pylnk3") as mock_lnk:
        target = install_startup_shortcut(exe, target_args=["tray", "--quiet"])
    assert target.name == "PathOfExile2DiscordRPC.lnk"
    assert target.parent.exists()
    mock_lnk.for_file.assert_called_once()
    args, kwargs = mock_lnk.for_file.call_args
    assert kwargs["target_file"] == str(exe)
    assert kwargs["arguments"] == "tray --quiet"


def test_uninstall_returns_false_when_shortcut_absent(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    assert uninstall_startup_shortcut() is False


def test_uninstall_removes_existing_shortcut(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    startup = tmp_path / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
    startup.mkdir(parents=True)
    (startup / "PathOfExile2DiscordRPC.lnk").write_text("fake")
    assert uninstall_startup_shortcut() is True
    assert not (startup / "PathOfExile2DiscordRPC.lnk").exists()


def test_install_idempotent(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    exe = Path(r"C:\Tools\foo.exe")
    with patch("poe2_rpc.infrastructure.autostart.pylnk3"):
        target1 = install_startup_shortcut(exe, target_args=["tray"])
        target2 = install_startup_shortcut(exe, target_args=["tray"])
    assert target1 == target2


@pytest.mark.parametrize(
    "frozen,executable,argv0,expected",
    [
        # PyInstaller --onefile: sys.executable IS the .exe
        (True, r"C:\Tools\PathOfExile2DiscordRPC.exe", "irrelevant",
         r"C:\Tools\PathOfExile2DiscordRPC.exe"),
        # Pip install: sys.executable is python.exe; sys.argv[0] is the script entrypoint
        (False, r"C:\Python311\python.exe", r"C:\Tools\poe2-rpc.exe",
         r"C:\Tools\poe2-rpc.exe"),
    ],
)
def test_install_autostart_uses_frozen_exe_path(monkeypatch, frozen, executable, argv0, expected):
    if frozen:
        monkeypatch.setattr(sys, "frozen", True, raising=False)
    else:
        monkeypatch.setattr(sys, "frozen", False, raising=False)
    monkeypatch.setattr(sys, "executable", executable)
    monkeypatch.setattr(sys, "argv", [argv0])
    assert _resolve_tray_exe_path() == Path(expected)
```

```python
# tests/unit/test_orchestrator_stop.py — SYNC threading model (Option A)
import threading
import time
import pytest
from poe2_rpc.application.orchestrator import Orchestrator


def test_orchestrator_stop_closes_stream_within_1s():
    """Tray Quit thread calls stop() → stream.close() → sync for-loop exits → thread joins."""
    orch = build_orchestrator_with_in_memory_fakes()  # helper in conftest;
    # the in-memory fake LogStream's lines() yields one line then blocks on a
    # threading.Event until close() is called, mirroring WatchdogLogStream behaviour.
    worker = threading.Thread(target=orch.run_once, daemon=True)
    worker.start()
    time.sleep(0.05)  # let the loop start and pick up _current_stream
    orch.stop()
    worker.join(timeout=1.0)
    assert not worker.is_alive(), "orchestrator.stop() did not terminate run_once within 1s"
    assert orch._current_stream is None, "stream reference must be cleared in finally"


def test_log_stream_close_is_idempotent():
    """Calling close() twice must not raise (tray could double-fire on rapid quit)."""
    from poe2_rpc.infrastructure.log_stream import WatchdogLogStream
    stream = build_watchdog_stream_with_temp_log()  # conftest helper
    stream.close()
    stream.close()  # second call must be a no-op, not raise
    assert stream.is_closed() is True


def test_orchestrator_stop_when_no_stream_active_is_noop():
    """stop() called before run_once() ever assigned _current_stream must not raise."""
    orch = build_orchestrator_with_in_memory_fakes()
    orch.stop()  # _current_stream is None — must be a clean no-op
```

```python
# tests/unit/test_tray.py — quit-order test
def test_quit_callback_invokes_orchestrator_stop_then_tray_stop():
    from unittest.mock import MagicMock, call
    orch = MagicMock()
    icon = MagicMock()
    call_order = []
    orch.stop.side_effect = lambda: call_order.append("orch_stop")
    icon.stop.side_effect = lambda: call_order.append("icon_stop")

    def on_quit() -> None:
        orch.stop()
        icon.stop()

    on_quit()
    assert call_order == ["orch_stop", "icon_stop"]
```

```python
# tests/unit/test_extras_missing.py
import sys
import builtins
import pytest
from typer.testing import CliRunner
from poe2_rpc.cli import app


def test_tray_command_exits_with_helpful_message_when_pystray_missing(monkeypatch):
    """When extras aren't installed, `poe2-rpc tray` must fail with install hint."""
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name.startswith("poe2_rpc.infrastructure.tray"):
            raise ImportError("Tray support requires extras: pip install poe2-rpc[tray]")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    runner = CliRunner()
    result = runner.invoke(app, ["tray"])
    assert result.exit_code == 1
    assert "pip install poe2-rpc[tray]" in result.stderr
```

#### Backport (upstream-pr/background-launcher)

This is the largest backport. Upstream `main.py` minimal-diff:
- Add `pystray` and `Pillow` to upstream `requirements.txt` (yes, this grows their footprint — flag in PR description; offer a separate `requirements-tray.txt` if maintainer prefers).
- Add `--tray` CLI flag (argparse extension if upstream uses argparse, else simple `sys.argv` check).
- When `--tray` is set, run the existing main loop on a background `threading.Thread` and start `pystray.Icon` on the main thread. Use `subprocess.CREATE_NO_WINDOW` (Windows-only flag, available in `subprocess` since 3.7) when spawning subprocess work from the tray to suppress flashing console windows — chosen explicitly over a second PyInstaller `--noconsole` exe build because (a) one .exe artifact stays simpler for the maintainer's release flow and (b) the tray uses the same binary, just a different invocation flag.
- Add `--install-autostart` and `--uninstall-autostart` flags using `pylnk3` (or document the maintainer can omit the autostart commands and ship only `--tray`; ALTERNATIVE PR plan if pystray dep is rejected: keep `--install-autostart` only, run as headless background process).

**Risk (justified — upstream `requirements.txt` is 17 bytes per spec §Constraints):** Maintainer may reject the dep growth. Pre-approved alternative PR shape: split PR-4 into **PR-4a** (autostart shortcut only, ~30 LOC, zero new deps — uses stdlib `subprocess` + Windows `start /min`) and **PR-4b** (tray-only with `pystray`+`Pillow` deps, accepted/declined independently). Choose at PR-open time based on a draft-PR conversation with the maintainer; do not pre-emptively split.

#### Acceptance criteria (testable)

- [ ] `tests/unit/test_autostart.py` 5 tests pass (install, uninstall absent, uninstall present, idempotent, frozen-vs-non-frozen exe path parametrized).
- [ ] `tests/unit/test_tray.py` 4+ tests pass (menu items present, status update reaches icon, quit callback invokes `orchestrator.stop()` THEN `tray.stop()` in that order).
- [ ] `tests/unit/test_orchestrator_stop.py` 3 tests pass — (a) `stop()` causes `run_once()` worker thread to join within 1s, (b) `WatchdogLogStream.close()` is idempotent, (c) `stop()` with no active stream is a clean no-op.
- [ ] `domain/ports.py::LogStream` Protocol gains `close()` and `is_closed()` methods (verified by `mypy --strict` + `lint-imports` still green).
- [ ] `tests/unit/test_extras_missing.py` 2 tests pass — `tray` and `install-autostart` exit with code 1 + `"pip install poe2-rpc[tray]"` in stderr when extras absent.
- [ ] `pystray`, `Pillow`, `pylnk3` declared in `pyproject.toml` `[project.optional-dependencies] tray = [...]` — NOT in `[project] dependencies`.
- [ ] `pyproject.toml` `[[tool.mypy.overrides]]` module list extended to include `pystray.*`, `PIL.*`, `pylnk3.*`.
- [ ] `mypy --strict src/poe2_rpc` passes WITHOUT extras installed (proves the import-gate + override pair works end-to-end).
- [ ] PyInstaller spec unchanged (`PathOfExile2DiscordRPC.spec` stays single-target); README documents the runtime `subprocess.CREATE_NO_WINDOW` approach and notes a separate `tray.spec` is a follow-up if the runtime suppression is insufficient on a target Windows version.
- [ ] `poe2-rpc install-autostart` creates `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\PathOfExile2DiscordRPC.lnk` pointing at the FROZEN .exe path (verified by `test_install_autostart_uses_frozen_exe_path`).
- [ ] Quitting from tray right-click menu causes the `Orchestrator.run()` worker thread to exit cleanly via `stream.close()` (no `sys.exit`, no orphan watchdog observer in process tree, no zombie .exe in Task Manager). Sync close-stream design — verified end-to-end by `test_orchestrator_stop_closes_stream_within_1s` plus the Windows live-smoke screenshot.
- [ ] Windows live-smoke: install autostart → reboot → tray icon appears → right-click menu shows Status/Open log/Restart/Quit. Screenshot in PR.

---

## Sequencing & Dependencies

```
PR-1 (official client)            PR-4 (background launcher)
     │                                 ▲
     │ (independent)                   │
     ▼                                 │
PR-2 (owner detection) ──────────► PR-3 (AFK status)
   │                                   ▲
   │ (PR-3 wants to know whose AFK)    │
   └───────────────────────────────────┘
```

**Strict ordering:** PR-1 → PR-2 → PR-3 → PR-4.

- **PR-1 is independent** — pure detector + settings change. Could ship first or in parallel.
- **PR-2 is the foundation for PR-3.** AFK is meaningless if the system can't tell whose AFK it is in a party (otherwise a party member typing `/afk` would set the local player's presence to AFK).
- **PR-3 depends on PR-2** at the application level: `on_afk_changed` should ideally check `current_state.owner_tracker.should_emit(?)` before mutating presence — but AFK lines have no username field, so we treat ALL AFK events as local-player events (only the local player's chat shows in their own log). This is correct for `Client.txt` (it's a per-client log).
- **PR-4 lands last** — biggest, riskiest dep additions, most upstream-maintainer pushback risk. Don't gate the others on it.

Cross-PR coupling: PR-3's handler reads `current_state` mutated by PR-2's handlers (handler ordering inside the bus matters but is preserved by `application/orchestrator.py::_subscribe_handlers` registration order).

---

## Testable Acceptance Criteria (Master List, refined from spec §Per-PR DoD)

### Cross-cutting (all 4 PRs)

- [ ] `pytest tests -ra` exits 0 (all unit + integration tests).
- [ ] `mypy --strict src/poe2_rpc` exits 0 — including with extras NOT installed (PR-4 import gates + mypy overrides cooperate).
- [ ] `ruff check src tests && ruff format --check src tests` exits 0.
- [ ] `lint-imports` exits 0 (no `application` or `domain` import of `infrastructure`).
- [ ] `tests/unit/test_no_mutable_state.py` AST guard passes (all new domain VOs are frozen pydantic).
- [ ] Windows live-smoke screenshot attached to upstream PR description (per spec AC §"Manual Windows live-smoke").
- [ ] Backport branch has zero test files, zero `src/` layout, only `main.py` (and `requirements.txt` for PR-4) edits: `git diff upstream/main..upstream-pr/<slug> --name-only` matches whitelist.
- [ ] Bd parent issue closed only after upstream PR opened (per `feedback_ci_evidence_acceptance` — CI-evidence acceptance closes remotely, not locally).

### Per-PR pytest test names (master register)

```
tests/unit/test_detection.py::test_detector_resolves_log_path_for_both_clients[PathOfExileSteam.exe-...]
tests/unit/test_detection.py::test_detector_resolves_log_path_for_both_clients[PathOfExile.exe-...]
tests/unit/test_detection.py::test_detector_returns_none_when_no_match
tests/unit/test_detection.py::test_string_process_name_coerced_to_list
tests/unit/test_settings.py::test_process_name_string_env_coerced_to_list
tests/unit/test_owner.py::test_initial_state_is_unknown
tests/unit/test_owner.py::test_local_area_entered_no_override_transitions_to_area_entered
tests/unit/test_owner.py::test_local_area_entered_with_override_pins_immediately
tests/unit/test_owner.py::test_party_join_in_area_window_invalidates
tests/unit/test_owner.py::test_first_level_in_clean_window_pins
tests/unit/test_owner.py::test_should_emit_only_for_pinned_name
tests/unit/test_owner.py::test_invalidated_state_drops_all_emit
tests/unit/test_owner.py::test_party_join_while_pinned_keeps_pin
tests/unit/test_owner.py::test_party_scenarios[<3 cases>]
tests/unit/test_owner.py::test_re_entering_area_resets_invalidated_state
tests/unit/test_log_parser_protocol.py::test_regex_log_parser_satisfies_protocol
tests/unit/test_log_parser_protocol.py::test_incomplete_parser_fails_protocol_check
tests/unit/test_afk.py::test_parse_afk_event_table[<4 cases>]
tests/unit/test_afk.py::test_parse_afk_event_returns_none_for_unrelated_line
tests/unit/test_afk.py::test_presence_kwargs_afk_on_appends_afk_suffix_and_swaps_small_image
tests/unit/test_afk.py::test_presence_kwargs_afk_off_with_restore_override
tests/unit/test_afk.py::test_afk_restore_after_level_during_afk
tests/unit/test_afk.py::test_afk_on_off_with_no_prior_level_info
tests/unit/test_autostart.py::test_install_creates_shortcut_in_startup_dir
tests/unit/test_autostart.py::test_uninstall_returns_false_when_shortcut_absent
tests/unit/test_autostart.py::test_uninstall_removes_existing_shortcut
tests/unit/test_autostart.py::test_install_idempotent
tests/unit/test_autostart.py::test_install_autostart_uses_frozen_exe_path[<2 cases>]
tests/unit/test_tray.py::test_menu_items_built_correctly
tests/unit/test_tray.py::test_status_update_propagates_to_icon
tests/unit/test_tray.py::test_quit_callback_fires
tests/unit/test_tray.py::test_quit_callback_invokes_orchestrator_stop_then_tray_stop
tests/unit/test_orchestrator_stop.py::test_orchestrator_stop_terminates_loop
tests/unit/test_extras_missing.py::test_tray_command_exits_with_helpful_message_when_pystray_missing
tests/unit/test_extras_missing.py::test_install_autostart_command_exits_with_helpful_message_when_pylnk3_missing
```

Total: **34 distinct test functions** (47 with parametrized expansions).

---

## ADR — Architecture Decision Record

### Decision

**Ship four sequential pull requests** to `ezbooz/Path-Of-Exile-2-RPC` for the four open README features, each developed in our hexagonal package (`src/poe2_rpc/`) and **backported as a manually written minimal-diff** against upstream's single-file `main.py`. Recommended order: PR-1 (official client) → PR-2 (owner detection) → PR-3 (AFK) → PR-4 (background launcher).

### Drivers

1. Maintainer is slow (last commit 2025-07-29) — small reviewable PRs raise merge probability vs. one large bundled PR.
2. Upstream is a single 11KB `main.py` with no tests, no mypy, no ruff. We cannot ship our hexagonal modules upstream without a rewrite PR (low merge probability, see Alternatives).
3. Each feature has independent value to end-users — sequential delivery lets the easiest features land first while harder ones iterate.

### Alternatives considered

| Alternative | Pros | Cons | Why rejected / deferred |
|---|---|---|---|
| **Single bundled "all 4 features" PR** | One review thread | Maintainer review burden too high; one feature rejection blocks the rest | Spec §"PR Sequence Plan" explicitly chose 4 sequential. |
| **Upstream-style development (skip hexagonal)** | Trivial backport | Loses our existing `lint-imports` enforcement, `mypy --strict`, AST mutable-state guard | Fork would diverge permanently. |
| **Rewrite PR (port hexagonal to upstream)** | Long-term parity | 11KB → ~3KB+15 modules is a non-starter for an inactive maintainer | Spec §Non-Goals: "Sending a 'rewrite to hexagonal' PR to upstream (low merge probability)." |
| **4 parallel branches submitted simultaneously** | Faster wall-clock | No dependency separation; PR-1 settings change conflicts with PR-2's would complicate rebase | Sequential is safer. |
| **Fork-only (don't pursue upstream)** | No coordination cost | Ecosystem fragmentation | Spec §Non-Goals excludes this. |
| **Draft PRs first to gauge maintainer engagement before full hexagonal investment** | De-risks the 10-month-stale-maintainer assumption; cheap signal in <2 weeks; lets us avoid writing throwaway code if maintainer signals "no thanks" | 1-2 day delay per PR; risk that draft conversation goes silent and we have to pivot back to ready PRs anyway; draft PRs sometimes get less review attention | **Deferred — partial adoption.** We open all 4 as **ready PRs** (not drafts) but flag in PR-1's description footer "more features in this series follow (owner-pin, AFK, tray-launcher) — happy to flag intent so you can signal scope appetite." This costs nothing extra (one paragraph in the PR body), reuses the existing PR review channel, and lets the maintainer signal scope appetite WITHOUT the latency of waiting on draft-PR conversation. If PR-1 gets a fast "love it, send the rest" we proceed; if it sits silently for 4+ weeks, we still have local progress and the next PR is just a `git push`. The pure draft-first variant is rejected because draft PRs from external contributors get demonstrably less attention than ready PRs in many OSS repos, and our maintainer-engagement risk is already mitigated by the per-PR Windows-smoke screenshot evidence trail. |
| **PR-4 async orchestrator refactor (Option B): convert `run_once()` to async, add `alines() -> AsyncIterator[str]` to Protocol, use `asyncio.wait({loop_task, stop_task}, FIRST_COMPLETED)` for cancellation** | Idiomatic asyncio cancellation; the original draft (iteration 2) used this | ~120 LOC + 60 LOC tests vs ~30+25 for sync close-stream; touches every test that builds an Orchestrator (forces `pytest.mark.asyncio` migration); changes the `LogStream` Protocol shape (sync `lines()` callers in `_SyncLineIterator` and any future adapter must dual-implement); the draft snippet at plan L976 mixed sync `Orchestrator.run()` with `asyncio.run(orch.run())` — internally inconsistent and would have shipped a zombie-process bug | **Rejected for PR-4.** Iteration 3 found that the existing `Orchestrator.run_once()` is sync (`for line in stream.lines()`) and the proposed `_stop_event.set()` would never be observed by the sync for-loop — tray Quit would be dead-on-arrival. Chose sync close-stream (Option A): add `LogStream.close()` + `is_closed()` to the Protocol; `Orchestrator.stop()` calls `self._current_stream.close()` and the sync loop exits via `is_closed()` check or queue sentinel. Async refactor remains a future-work option if the orchestrator grows truly concurrent responsibilities, but is not justified by tray Quit alone. |

### Why chosen

- Smallest-blast-radius PRs (one feature each) maximize merge probability with a slow maintainer.
- Dual-track development (hexagonal ours + minimal-diff theirs) preserves our quality gates without imposing them on upstream.
- Sequencing PR-1 first delivers user value (official-client support is most-requested) with least risk (~30 LOC main.py change).
- DELIBERATE-mode pre-mortem on PR-2 (owner detection) caught three failure scenarios (party-join after pin, name collision, portal hop) addressed via `POE2RPC_CHARACTER_NAME` override + log-and-keep pin semantics + README documentation.
- Iteration 2 of this plan closed a dead-code loop in the AFK restore path: the `prior_small_image` field is now THREADED through `publisher.publish(small_image_override=...)` instead of stashed-and-ignored, with `test_afk_restore_after_level_during_afk` enforcing the snapshot semantics.
- Iteration 3 of this plan (this revision) replaced the inconsistent async-Orchestrator-cancel design (`asyncio.wait` + `_stop_event` mixed with a sync `for line in stream.lines()` loop, which would have shipped a zombie-process tray Quit bug) with a sync close-stream design: `LogStream.close()` + `is_closed()` on the Protocol, `Orchestrator.stop()` closes the active stream, the existing sync for-loop exits cleanly. Iteration 3 also added `test_afk_on_off_with_no_prior_level_info` for the architect-flagged `level_info=None` edge.
- PR-4 deps were moved to `[project.optional-dependencies] tray = [...]` so headless/CI installs stay slim and our binary distribution surface stays unchanged.

### Consequences

**Positive:**
- 4 independent merges possible — partial success still ships value.
- Our hexagonal repo continues to enforce strict layering; upstream doesn't have to care.
- All 14 spec ACs covered by named pytest tests + Windows-smoke evidence trail.
- AFK restore is now provably reversible via `test_afk_restore_after_level_during_afk` (regression net for the iteration-1 dead-code bug).
- `poe2-rpc[tray]` extras isolate Pillow + pylnk3 + pystray from headless installs (CI, server-mode, dev loops on machines without graphical desktop).

**Negative:**
- Maintenance burden of 4 backport branches if upstream lands changes between PRs (rebase cost).
- PR-4 grows upstream's `requirements.txt` from 17B to ~80B (pystray + Pillow + pylnk3) — maintainer may reject; PR-4 has fallback split into autostart-only + tray-only.
- Owner detection state machine has documented edge cases (party-join after solo entry → INVALIDATED until next area entry; party-join while PINNED logs warning but keeps pin) that require user education in README.
- `pylnk3` is Windows-specific; macOS/Linux dev-loop won't exercise PR-4's autostart unit tests fully (mocks suffice).
- Adding optional extras means README must document `pip install poe2-rpc[tray]` as a prerequisite for `tray` / `install-autostart` commands; users who install plain `poe2-rpc` and try `tray` get a clear `typer.Exit` with install hint, but it IS one extra step.

### Follow-ups

- [ ] Bd issue for "Detect name collision in owner-pin" (out of scope per spec).
- [ ] Bd issue for "Cross-platform autostart (`launchctl` macOS, systemd-user Linux)" if PR-4 ships and demand surfaces.
- [ ] Bd issue for "Login regex" (`klayveR/poe-log-monitor` includes `Connected to <realm>...` — could feed PR-2's owner detection a stronger anchor in future).
- [ ] After PR-4 ships, deprecate the bare `run` command in favor of `tray` for end-users (keep `run` for headless/CI use).
- [ ] If upstream rejects pystray dep growth, split PR-4 → PR-4a (autostart-only, ~50 LOC, no new deps using `subprocess` + Windows `start /min`) and PR-4b (tray-only, optional install).
- [ ] If runtime `subprocess.CREATE_NO_WINDOW` proves insufficient on some Windows versions, ship a separate `tray.spec` PyInstaller `--noconsole` build target as a follow-up PR.

---

## Bd Task Tree to Create

```
panvex-pr1  Official PoE2 client support (epic)
  ├─ panvex-pr1.1  Settings: process_name list[str] + back-compat coercion
  ├─ panvex-pr1.2  Detector: candidate-list match
  ├─ panvex-pr1.3  Tests: parametrized detection + settings env coerce
  └─ panvex-pr1.4  Backport branch + upstream PR + Windows smoke
                   (PR description footer flags series intent)

panvex-pr2  Owner detection auto-pin (epic) [DELIBERATE]
  ├─ panvex-pr2.1  domain/owner.py state machine + frozen VO
  ├─ panvex-pr2.2  domain/ports.py: extend LogParser Protocol with 2 methods
  ├─ panvex-pr2.3  parsing.py: 3 new regexes + RegexLogParser methods
  ├─ panvex-pr2.4  domain/events.py: LocalAreaEntered + PartyMemberJoined
  ├─ panvex-pr2.5  application: handlers + orchestrator wiring + MutableState owner field
  ├─ panvex-pr2.6  Settings: character_name override
  ├─ panvex-pr2.7  Tests: 10 unit + 3 parametrized party scenarios + 2 Protocol-conformance
  └─ panvex-pr2.8  Backport + upstream PR + 2-player Windows smoke

panvex-pr3  AFK status (epic) — depends on panvex-pr2
  ├─ panvex-pr3.1  parsing.py: regex_afk verbatim + parse_afk_event
  ├─ panvex-pr3.2  domain: AFKStatus VO + AFKStatusChanged event
  ├─ panvex-pr3.3  domain/ports.py: PresencePublisher.publish small_image_override kwarg
  ├─ panvex-pr3.4  presence.py: small_image_override threaded through _build_update_kwargs
  ├─ panvex-pr3.5  handlers: on_afk_changed THREADS prior_small_image into publish() (no dead writes)
  ├─ panvex-pr3.6  Tests: 4 parametrized parse + 2 round-trip presence + test_afk_restore_after_level_during_afk + test_afk_on_off_with_no_prior_level_info (level_info=None edge)
  ├─ panvex-pr3.7  README addendum: Discord asset upload
  └─ panvex-pr3.8  Backport + upstream PR + Windows smoke (/afk on/off + level during AFK)

panvex-pr4  Background launcher (epic) — depends on panvex-pr3
  ├─ panvex-pr4.1  pyproject.toml: pystray + Pillow + pylnk3 → [project.optional-dependencies] tray
  ├─ panvex-pr4.2  pyproject.toml: extend [[tool.mypy.overrides]] module list
  ├─ panvex-pr4.3  infrastructure/tray.py: TrayController + ImportError gate
  ├─ panvex-pr4.4  infrastructure/autostart.py: install/uninstall shortcut + ImportError gate
  ├─ panvex-pr4.5a domain/ports.py: LogStream.close() + is_closed() Protocol methods
  ├─ panvex-pr4.5b infrastructure/log_stream.py: WatchdogLogStream.close() (thread-safe, idempotent) + observer.stop+join
  ├─ panvex-pr4.5c application/orchestrator.py: Orchestrator.stop() calls _current_stream.close() (sync close-stream design — NO async refactor)
  ├─ panvex-pr4.6  cli.py: tray + install-autostart + uninstall-autostart + extras-missing typer.Exit
  ├─ panvex-pr4.7  cli.py: _resolve_tray_exe_path frozen-aware shortcut target
  ├─ panvex-pr4.8  Tests: autostart (5 incl. frozen parametrized) + tray (4 incl. quit-order) + orchestrator_stop (3 incl. idempotent close + no-stream no-op) + extras_missing (2)
  ├─ panvex-pr4.9  README: background service section + pip install poe2-rpc[tray] prereq
  └─ panvex-pr4.10 Backport (with fallback split plan) + upstream PR + reboot smoke (CREATE_NO_WINDOW choice documented)
```

Use `bd dep add panvex-pr3 panvex-pr2 --type blocks` and `bd dep add panvex-pr4 panvex-pr3 --type blocks`. PR-1 has no deps.

---

## Risks Surfaced

1. **PR-4 dep growth rejected by upstream maintainer.** Backup plan documented (split PR-4a + PR-4b).
2. **Owner detection edge case: solo player → party joins → solo player levels.** Mitigated by `POE2RPC_CHARACTER_NAME` override; documented in README.
3. **Owner detection edge case: party joins WHILE pinned.** Mitigated by log-and-keep semantics (`on_party_member_joined` returns self in PINNED state); covered by `test_party_join_while_pinned_keeps_pin`. Operator gets a structlog warning event for diagnosis.
4. **AFK regex assumes Steam-build log format identical to standalone.** Windows smoke must validate against PoE2 standalone client (PR-1 lands first to ensure the standalone path is testable).
5. **AFK restore previously dead-coded** (iteration 1 plan).  Iteration 2 fixed by threading `small_image_override` through `publisher.publish` and adding `test_afk_restore_after_level_during_afk` as a regression net.
6. **Backport drift if upstream lands changes between PRs.** Mitigated by per-feature branching + rebase before each PR opens.
7. **Maintainer inactive 10 months.** Local progress NOT blocked on merge per spec constraint; bd issues for upstream PRs stay open until merged or 90-day-stale, whichever first. Maintainer-engagement risk further mitigated by the PR-1-description "series-intent" footer (cheaper signal than full draft-PR pre-flight; see ADR Alternatives row).
8. **Backport divergence: module-level globals upstream vs. immutable VO ours.** Documented in PR-2 backport section as intentional — do NOT port `OwnerTracker` upstream. State-transition table is the contract; representation differs by branch.
9. **PyInstaller --noconsole vs runtime CREATE_NO_WINDOW.** Chose runtime suppression to keep a single .exe artifact for the maintainer's release flow. If insufficient on some Windows versions, follow-up adds `tray.spec` build target.
10. **Optional extras require README education.** Users installing plain `poe2-rpc` then running `tray` get a clear `typer.Exit` with `pip install poe2-rpc[tray]` hint; README install section calls out the extras in the background-service heading.
