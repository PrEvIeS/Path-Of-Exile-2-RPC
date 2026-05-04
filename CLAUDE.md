# CLAUDE.md — Path-Of-Exile-2-RPC

Project-level guidance for Claude Code working in this repository. Pair with the hierarchical `AGENTS.md` files for directory-specific detail.

## Project at a glance
- **What it is:** A Discord Rich Presence integration for Path of Exile 2. Tails the game's `Client.txt`, parses level-up and area-generation events, and pushes presence updates via `pypresence`.
- **Shape:** Single-script Python app. The runtime entrypoint is `main.py`; everything else (`locations.json`, `requirements.txt`, GitHub config) supports it.
- **Distribution:** End users grab a prebuilt Windows `.exe` from GitHub Releases. The `.exe` is produced by `.github/workflows/build.yml` via PyInstaller `--onefile` whenever `main.py` changes on `main`.

## Build & Test

```bash
pip install -r requirements.txt
python main.py
```

Discord must be running. The script polls `psutil` for `PathOfExileSteam.exe` and only proceeds once the game is running — it will block on `Waiting for the game start..` otherwise.

There is no automated test suite. Verification is manual: run the game, run the script, watch Discord for the expected presence, then kill/relaunch Discord to exercise `rpc_connect`'s 5-retry exponential-backoff loop.

## Architecture Overview

`main.py` is the whole app. Top to bottom:

1. **Enums** (`CharacterClass`, `ClassAscendency`) — mappings between in-game class strings and ascendancies. The enum value is what appears in the log.
2. **`find_game_log()`** — `psutil.process_iter` loop hunting for `PathOfExileSteam.exe`; returns `<game_dir>/logs/Client.txt`.
3. **`load_locations()`** — reads `locations.json` from disk if present, otherwise downloads it from this repo's `main` branch and caches it.
4. **`determine_location()`** — turns an internal area code (e.g. `G1_4_BrambleghastSlain`) into a display name; map areas (`Map*`) get prefix-stripped and underscore-split before lookup.
5. **Parsers** — `find_last_level_up()` and `find_instance()` apply two precompiled regexes to log lines.
6. **`rpc_connect()`** — 5-attempt connect loop with `time.sleep(2 ** retries)` backoff against the Discord IPC socket (app ID `1315800372207419504`).
7. **`update_rpc()`** — formats presence details and sets `small_image = ascension_class.lower().replace(" ", "_")`.
8. **`monitor_log()`** — opens the log, seeks to EOF, then loops `readlines()` + `time.sleep(5)`, dispatching to `update_rpc()` whenever the parsed level or zone changes.

## Conventions & Patterns

- **Keep it one file.** CI's path-filter (`paths: ['main.py']`) and the PyInstaller call assume a single entrypoint. Splitting modules requires updating both in the same change.
- **Type hints + `logging`.** 4-space indent, type hints on signatures, `logging.info/error/warning` instead of `print`.
- **`pathlib.Path` + explicit `encoding="utf-8"`** for all file I/O.
- **Optional return shape:** parsers return `Optional[Dict[str, str]]`; the caller does the `if level_info:` check.
- **Exponential backoff** for retry loops (`time.sleep(2 ** retries)`), matching `rpc_connect`.

## Adding a new ascendancy

1. Add the enum member to `ClassAscendency` — value must match the in-game string verbatim (e.g. `"Smith of Kitava"`).
2. Add the mapping in `ClassAscendency.get_class()`.
3. Append it to the right list in `CharacterClass.get_ascendencies()`.
4. Upload the matching Discord asset using the **lowercase + underscore** key, since `update_rpc` derives `small_image` as `ascension_class.lower().replace(" ", "_")` (commit `5ae14e6` enforced this).

Reference commit: `fe9c494` ("Add new character classes: Smith of Kitava, Lich, and Tactician").

## Adding/updating zones

- Edit `locations.json` (the in-repo copy is the source of truth) and ship it in the same commit.
- Schema: `{"areas": {"<internal_code>": "<display name>"}}`. Internal codes look like `G1_1`, `G1_4_Brambleghast`, etc.
- `determine_location()` strips a leading `Map` prefix and splits on `_` for map-tier areas, so map-name lookups bypass `locations.json`.
- Existing installs auto-fetch `locations.json` from GitHub `main` only when the local file is **missing**. The upgrade path for cached installs is a new `.exe` release.

## Regex contracts

Don't break these without checking a real `Client.txt` sample:

- `regex_level`: `r": (\w+) \(([\w\s]+)\) is now level (\d+)"` → `(username, base_or_ascendancy_class, level)`.
- `regex_instance`: `r'Generating level (\d+) area "([^"]+)" with seed (\d+)'` → `(level, area_code, seed)`.

Both target the Steam-build log format.

## CI / Release flow

- Push to `main` touching `main.py` → `.github/workflows/build.yml` runs on `windows-latest`.
- A timestamp tag (`vYYYYMMDD-HHMMSS`) is created and pushed; the release job uploads `PathOfExile2DiscordRPC.exe` as a GitHub Release asset.

## Open work (from README)

- [ ] Launch as a background service when the game starts.
- [ ] Support the official PoE2 client (currently Steam-only via the hardcoded `PathOfExileSteam.exe` process name).
- [ ] Detect which player started the script (avoid party-conflict mis-detection).
- [ ] Show AFK status.

## See also

- `AGENTS.md` — hierarchical directory guide.
- `.github/AGENTS.md`, `.github/workflows/AGENTS.md`, `.github/ISSUE_TEMPLATE/AGENTS.md` — directory-specific notes.
- `README.md` — end-user instructions.

<!-- BEGIN BEADS INTEGRATION v:1 profile:minimal hash:ca08a54f -->
## Beads Issue Tracker

This project uses **bd (beads)** for issue tracking. Run `bd prime` to see full workflow context and commands.

### Quick Reference

```bash
bd ready              # Find available work
bd show <id>          # View issue details
bd update <id> --claim  # Claim work
bd close <id>         # Complete work
```

### Rules

- Use `bd` for ALL task tracking — do NOT use TodoWrite, TaskCreate, or markdown TODO lists
- Run `bd prime` for detailed command reference and session close protocol
- Use `bd remember` for persistent knowledge — do NOT use MEMORY.md files

## Session Completion

**When ending a work session**, you MUST complete ALL steps below. Work is NOT complete until `git push` succeeds.

**MANDATORY WORKFLOW:**

1. **File issues for remaining work** - Create issues for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **PUSH TO REMOTE** - This is MANDATORY:
   ```bash
   git pull --rebase
   bd dolt push
   git push
   git status  # MUST show "up to date with origin"
   ```
5. **Clean up** - Clear stashes, prune remote branches
6. **Verify** - All changes committed AND pushed
7. **Hand off** - Provide context for next session

**CRITICAL RULES:**
- Work is NOT complete until `git push` succeeds
- NEVER stop before pushing - that leaves work stranded locally
- NEVER say "ready to push when you are" - YOU must push
- If push fails, resolve and retry until it succeeds
<!-- END BEADS INTEGRATION -->
