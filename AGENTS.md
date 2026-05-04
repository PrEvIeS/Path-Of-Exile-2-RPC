<!-- Generated: 2026-05-04 | Updated: 2026-05-04 -->

# Path-Of-Exile-2-RPC

## Purpose
A small, single-script Python utility that provides Discord Rich Presence integration for Path of Exile 2. The tool locates the running `PathOfExileSteam.exe` process, tails its `Client.txt` log, parses level-up and zone-generation events, and pushes a live presence update (character/class/ascendancy/zone) to Discord via `pypresence`.

The whole runtime is intentionally one file (`main.py`) so it can be packaged into a single Windows `.exe` via PyInstaller in CI.

## Key Files
| File | Description |
|------|-------------|
| `main.py` | Entire application: log discovery, regex parsing, RPC connect, monitor loop. Discord app ID `1315800372207419504`. |
| `locations.json` | Mapping of internal area codes (e.g. `G1_1`) to player-facing zone names (e.g. `The Riverbank`). Loaded from disk if present, otherwise fetched from the GitHub `main` branch on first run. |
| `requirements.txt` | Runtime dependencies: `psutil` (process discovery), `pypresence` (Discord IPC). |
| `README.md` | User-facing install/run instructions. |
| `LICENSE` | MIT license. |
| `.gitignore` | Ignores `.idea/` and `__pycache__/`. |

## Subdirectories
| Directory | Purpose |
|-----------|---------|
| `.github/` | CI workflow + issue templates (see `.github/AGENTS.md`) |

## For AI Agents

### Working In This Directory
- Keep the runtime to `main.py`. The CI build (`.github/workflows/build.yml`) only triggers on changes to `main.py`, and PyInstaller is invoked as `pyinstaller --onefile --name PathOfExile2DiscordRPC main.py`. Splitting code into modules requires updating both the path filter and the PyInstaller call in lockstep.
- The `regex_level` pattern is `: (\w+) \(([\w\s]+)\) is now level (\d+)` and `regex_instance` is `Generating level (\d+) area "([^"]+)" with seed (\d+)`. Both target the literal log format produced by the Steam build of PoE2; verify against a real `Client.txt` sample before changing them.
- When adding a new ascendancy: extend `ClassAscendency` enum (value must match the in-game string exactly), add the entry to `ClassAscendency.get_class()`, and add it to the parent `CharacterClass.get_ascendencies()` list. Reference commit: `fe9c494` ("Add new character classes: Smith of Kitava, Lich, and Tactician").
- The `small_image` field is derived as `ascension_class.lower().replace(" ", "_")`. Discord asset keys must therefore be lowercase + underscores (commit `5ae14e6` enforced this). Asset names that don't match this convention silently fall back to no image.
- `locations.json` is fetched from `https://raw.githubusercontent.com/ezbooz/Path-Of-Exile-2-RPC/refs/heads/main/locations.json` only when the local file is missing. If you change the schema, ship the updated `locations.json` in the same commit so existing installs upgrade on next launch.
- `monitor_log()` calls `log_file.readlines()` after `seek(0, 2)` and sleeps 5s — a deliberate append-only poll. The cadence matches how PoE2 buffers its log; preserve this approach.
- Process discovery hardcodes `PathOfExileSteam.exe`. Adding support for the official client (see README) means another explicit process-name check, not a regex.

### Testing Requirements
- No automated test suite. Manual verification: launch the game, run `python main.py`, confirm Discord shows the expected presence; kill/relaunch Discord to exercise `rpc_connect` (5 retries with `time.sleep(2 ** retries)` backoff).
- No linter/formatter is enforced. Match existing style: 4-space indent, type hints on signatures, `logging` over `print`.

### Common Patterns
- Log parsers return `Optional[Dict[str, str]]`; callers check truthiness.
- Module-level `logging` (configured at import) is used everywhere instead of `print`.
- File I/O uses `pathlib.Path` and explicit `encoding="utf-8"`.
- Retry loops use exponential backoff `time.sleep(2 ** retries)` (see `rpc_connect`).

## Dependencies

### External
- `psutil` — iterating processes to find `PathOfExileSteam.exe` and resolve its install directory.
- `pypresence` — Discord IPC client for the Rich Presence API.
- Stdlib: `datetime`, `json`, `logging`, `os`, `re`, `time`, `random`, `pathlib`, `enum`, `urllib.request`.

### Runtime
- Discord desktop client must be running and authorized for app ID `1315800372207419504`.
- Path of Exile 2 (Steam build) must be installed and running.

## Non-Interactive Shell Commands

**ALWAYS use non-interactive flags** with file operations to avoid hanging on confirmation prompts.

Shell commands like `cp`, `mv`, and `rm` may be aliased to include `-i` (interactive) mode on some systems, causing the agent to hang indefinitely waiting for y/n input.

**Use these forms instead:**
```bash
# Force overwrite without prompting
cp -f source dest           # NOT: cp source dest
mv -f source dest           # NOT: mv source dest
rm -f file                  # NOT: rm file

# For recursive operations
rm -rf directory            # NOT: rm -r directory
cp -rf source dest          # NOT: cp -r source dest
```

**Other commands that may prompt:**
- `scp` - use `-o BatchMode=yes` for non-interactive
- `ssh` - use `-o BatchMode=yes` to fail instead of prompting
- `apt-get` - use `-y` flag
- `brew` - use `HOMEBREW_NO_AUTO_UPDATE=1` env var

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

<!-- MANUAL: Manually added notes below this line are preserved on regeneration -->
