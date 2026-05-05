<img width="800" height="500" alt="2" src="https://github.com/user-attachments/assets/30d06f66-797b-4c52-9895-344c42ecadff" />

**Мови:** [English](README.md) · [Русский](README.ru.md) · Українська

## ⚙️ Встановлення:
1. Встановіть Python 3.11 або новіший.
2. Встановіть пакет разом із dev-залежностями: `pip install -e ".[dev]"`
3. Запустіть застосунок: `poe2-rpc run` (або `python -m poe2_rpc run`).
4. Переконайтеся, що Discord запущено.

Опціональний конфіг: покладіть файл `config.toml` за шляхом
`%APPDATA%\poe2-rpc\config.toml` на Windows (або
`~/.config/poe2-rpc/config.toml` на macOS/Linux для розробки). Без
конфіга застосунок працює зі значеннями за замовчуванням.

CLI-команди: `poe2-rpc run` (безперервний моніторинг),
`poe2-rpc once` (один прохід по лог-файлу),
`poe2-rpc validate-config --no-discord` (перевірити налаштування та
вбудовані ассети без підключення до Discord IPC).

**Для зручності зібрано `.exe` під Windows — він лежить у розділі Releases.
Завантажте останню версію тут:**
👉 https://github.com/ezbooz/Path-Of-Exile-2-RPC/releases

## ✅ Можливості

- Discord Rich Presence для **Path of Exile 2**
- Автоматично розпізнає клас персонажа, асцендансі, зону та рівень
- Показує іконку для кожного класу

---

## 🔧 To-Do

- [x] Підтримка користувацьких зображень (усі класи та асцендансі)
- [ ] Запуск як фонова служба під час старту гри
- [ ] Підтримка офіційного клієнта PoE2
- [ ] Визначення гравця, що запустив скрипт (уникати конфліктів у паті)
- [ ] Показ AFK-статусу

---


## 🙏 Подяки

- 💾 [adainrivers](https://github.com/adainrivers/poe2-data) — дані мап та ресурси
- 💻 [Miksuu](https://github.com/Miksuu) — внесок у код

---

## 📎 Ліцензія

Проєкт поширюється за ліцензією [MIT](LICENSE).
