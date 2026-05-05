<img width="800" height="500" alt="2" src="https://github.com/user-attachments/assets/30d06f66-797b-4c52-9895-344c42ecadff" />



## ⚙️ Install guide:
1. Install Python 3.11 or higher.
2. Install the package and dev dependencies: `pip install -e ".[dev]"`
3. Run the app: `poe2-rpc run` (or `python -m poe2_rpc run`).
4. Ensure that Discord is running.

Optional config: drop a `config.toml` at `%APPDATA%\poe2-rpc\config.toml` on
Windows (or `~/.config/poe2-rpc/config.toml` on macOS/Linux for dev). Defaults
work without one.

CLI commands: `poe2-rpc run` (continuous monitor), `poe2-rpc once` (single
log-stream pass), `poe2-rpc validate-config --no-discord` (validate settings
+ bundled assets without contacting Discord IPC).

**For convenience, a pre-compiled .exe is available in the releases section.  
Download the latest release here:**  
👉 https://github.com/ezbooz/Path-Of-Exile-2-RPC/releases

## ✅ Features

- Rich Discord presence for **Path of Exile 2**
- Automatically detects character class, ascendancy, zone, and level
- Displays an image for each class

---

## 🔧 To-Do

- [x] Support for custom images (all classes and ascendancies)
- [ ] Launch as background service when game starts
- [ ] Add support for the official PoE2 client
- [ ] Detect the player who started the script (avoid party conflicts)
- [ ] Show AFK status

---


## 🙏 Acknowledgements

- 💾 [adainrivers](https://github.com/adainrivers/poe2-data) — map data and resources  
- 💻 [Miksuu](https://github.com/Miksuu) — code contributions

---

## 📎 License

This project is open-source under the [MIT License](LICENSE).
