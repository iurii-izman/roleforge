# Bootstrap: Access and Secrets

This doc covers fixing GitHub CLI auth (project scope), Linear token/API path, and the RoleForge keyring.

## Keyring: `roleforge`

The project uses a keyring named **roleforge**. All local secrets are stored under the namespace `service=roleforge` via `scripts/roleforge-keyring.sh`.

- **Keyring name**: create or use a keyring called **roleforge** in your system keyring (e.g. GNOME Secrets / Seahorse, or KDE Wallet). If you only have one keyring, naming it `roleforge` keeps project secrets clearly separated.
- **Storage**: the helper script stores items with attributes `service=roleforge`, `domain=<domain>`, `key=<key>`. Use the script for get/set so naming stays consistent.

### Keyring domain contract (MVP)

Canonical domains under `service=roleforge`:

| Domain      | Purpose                         | Typical keys (examples)     |
|------------|----------------------------------|-----------------------------|
| `google`   | Gmail API / OAuth                | `client_id`, `client_secret`, `refresh_token` |
| `telegram` | Telegram Bot API                | `bot_token`                 |
| `openai`   | OpenAI API (if chosen for MVP)   | `api_key`                   |
| `anthropic`| Anthropic API (if chosen for MVP)| `api_key`                   |
| `db`       | Postgres connection             | `url`, `password`           |
| `app`      | Application / runtime secrets    | per-app keys                |
| `linear`   | Linear GraphQL API              | `api_key`                   |

Use only these domains for MVP so scripts and docs stay aligned. Store and read secrets via `scripts/roleforge-keyring.sh`; do not hardcode or commit secrets.

### Exact key paths and set commands (MVP, now → end of MVP)

All keys live under **service=roleforge**. Path = `domain` + `key`. Ниже — куда зайти в браузере, что создать/скопировать, какой командой положить в keyring.

---

**1. Linear — `linear` / `api_key`**

- **Куда зайти:** твой workspace в Linear → **Settings** (шестерёнка внизу слева) → **API** → в блоке *Member API keys* ссылка **"security & access settings"**, или напрямую: `https://linear.app/settings/api` (если открывается твой workspace).
- **Что сделать:** Create **Personal API key** → скопировать ключ (показывается один раз).
- **Ввести в keyring:**  
  `scripts/roleforge-keyring.sh set linear api_key`  
  Вставить ключ по запросу, Enter.

---

**2–4. Google (Gmail OAuth) — `google` / `client_id`, `client_secret`, `refresh_token`**

- **Куда зайти:** [Google Cloud Console](https://console.cloud.google.com/) → выбрать проект (или создать) → **APIs & Services** → **Credentials** (`https://console.cloud.google.com/apis/credentials`).
- **client_id и client_secret:**  
  **Create credentials** → **OAuth client ID** → тип приложения **Desktop app**.  
  В нашем случае (локальные скрипты, один раз consent со своей машины, ключи в keyring) Desktop подходит лучше: не нужен публичный redirect URL и веб-сервер; достаточно один раз открыть браузер, войти в Google и получить refresh_token. Web application имеет смысл только если у тебя уже есть развёрнутое приложение с HTTPS-URL для callback. После создания клиента — в карточке скопировать **Client ID** и **Client secret**.  
  - `scripts/roleforge-keyring.sh set google client_id` → вставить Client ID.  
  - `scripts/roleforge-keyring.sh set google client_secret` → вставить Client secret.
- **refresh_token:**  
  После того как `client_id` и `client_secret` лежат в keyring, один раз запусти скрипт — откроется браузер, войди в Google и разреши доступ; скрипт сам сохранит refresh_token в keyring:
  ```bash
  pip install -r requirements.txt   # если ещё не ставил
  python scripts/google_oauth_refresh_token.py
  ```
  В браузере выбери аккаунт, который будет получать job alerts; после редиректа на localhost скрипт запишет `google` / `refresh_token` и завершится. Если refresh_token не выдаётся (уже давал consent раньше), в [Google Account → Security → Third-party access](https://myaccount.google.com/permissions) отзови доступ приложения и запусти скрипт снова.  
  Gmail API должен быть включён в проекте: **APIs & Services** → **Library** → поиск "Gmail API" → Enable.

---

**5. Telegram — `telegram` / `bot_token`**

- **Куда зайти:** в Telegram найти [@BotFather](https://t.me/BotFather) → команда `/newbot` (или для существующего бота — `/mybots` → выбрать бота → **API Token**).
- **Что сделать:** по шагам BotFather дать имя и username бота → получить строку вида `123456:ABC-Def1234ghIkl-zyx57W2v1u123ew11`.
- **Ввести в keyring:**  
  `scripts/roleforge-keyring.sh set telegram bot_token`  
  Вставить токен целиком, Enter.

---

**6. OpenAI — `openai` / `api_key`** (если выбран OpenAI для MVP)

- **Куда зайти:** [OpenAI API keys](https://platform.openai.com/api-keys) (логин при необходимости).
- **Что сделать:** **Create new secret key** → скопировать ключ (начинается с `sk-...`, показывается один раз).
- **Ввести в keyring:**  
  `scripts/roleforge-keyring.sh set openai api_key`  
  Вставить ключ, Enter.

---

**7. Anthropic — `anthropic` / `api_key`** (если выбран Anthropic для MVP)

- **Куда зайти:** [Anthropic Console — API Keys](https://console.anthropic.com/settings/keys) (логин при необходимости).
- **Что сделать:** **Create Key** → скопировать ключ (показывается один раз).
- **Ввести в keyring:**  
  `scripts/roleforge-keyring.sh set anthropic api_key`  
  Вставить ключ, Enter.

---

**8–9. Postgres — `db` / `url`, `db` / `password`** (когда будет БД)

Локально на Fedora Atomic удобно поднять Postgres через **Podman** (встроен, rootless, без отдельного демона). Ниже — пошагово.

1. **Запустить контейнер Postgres 16** (образ совместим с нашим schema, Postgres 13+):
   ```bash
   podman run -d \
     --name roleforge-pg \
     -e POSTGRES_USER=roleforge \
     -e POSTGRES_PASSWORD=roleforge \
     -e POSTGRES_DB=roleforge \
     -p 5432:5432 \
     -v roleforge-pgdata:/var/lib/postgresql/data \
     docker.io/library/postgres:16
   ```
   Том `roleforge-pgdata` сохраняет данные при пересоздании контейнера. Проверка: `podman ps` — контейнер `roleforge-pg` в статусе Up.

2. **Применить схему** (один раз после первого запуска):
   ```bash
   podman exec -i roleforge-pg psql -U roleforge -d roleforge < schema/001_initial_mvp.sql
   ```
   Вывод без ошибок — таблицы созданы.

3. **Собрать URL и положить в keyring:**
   - URL: `postgresql://roleforge:roleforge@localhost:5432/roleforge`
   - Ввести в keyring:
     ```bash
     scripts/roleforge-keyring.sh set db url
     # вставить: postgresql://roleforge:roleforge@localhost:5432/roleforge
     ```
   Пароль уже в URL; отдельно `db` / `password` не обязателен. Если захочешь хранить пароль отдельно — поменяй URL на `postgresql://roleforge@localhost:5432/roleforge` (без пароля в строке) и `scripts/roleforge-keyring.sh set db password` → ввести `roleforge`.

4. **Перезапуск после перезагрузки:** контейнер не стартует сам. Запустить снова:
   ```bash
   podman start roleforge-pg
   ```

**Альтернативы:** Docker (если уже используешь) — те же шаги, заменить `podman` на `docker`. Системный Postgres (пакет из репозитория) — создать БД и пользователя вручную, применить schema, URL вида `postgresql://user:pass@localhost:5432/roleforge`.

---

**Сводка команд (все ключи):**

| Domain     | Key             | Команда |
|------------|-----------------|--------|
| `linear`   | `api_key`       | `scripts/roleforge-keyring.sh set linear api_key` |
| `google`   | `client_id`     | `scripts/roleforge-keyring.sh set google client_id` |
| `google`   | `client_secret` | `scripts/roleforge-keyring.sh set google client_secret` |
| `google`   | `refresh_token` | `scripts/roleforge-keyring.sh set google refresh_token` |
| `telegram` | `bot_token`     | `scripts/roleforge-keyring.sh set telegram bot_token` |
| `openai`   | `api_key`       | `scripts/roleforge-keyring.sh set openai api_key` |
| `anthropic`| `api_key`       | `scripts/roleforge-keyring.sh set anthropic api_key` |
| `db`       | `url`           | `scripts/roleforge-keyring.sh set db url` |
| `db`       | `password`      | `scripts/roleforge-keyring.sh set db password` |

**Lookup в коде:**  
`secret-tool lookup service roleforge domain <domain> key <key>`

### Текущий статус ключей и доступов

*(Проверка: `scripts/roleforge-keyring.sh exists <domain> <key>` — выводит `yes` или `no`.)*

**Уже в keyring (проверено):**

| Domain     | Key             | Статус  |
|------------|-----------------|---------|
| `linear`   | `api_key`       | есть    |
| `google`   | `client_id`     | есть    |
| `google`   | `client_secret` | есть    |
| `telegram` | `bot_token`     | есть    |
| `openai`   | `api_key`       | есть    |
| `anthropic`| `api_key`       | есть    |
| `db`      | `url`           | есть (локальный Postgres в Podman: `podman start roleforge-pg` при необходимости) |

**Нет в keyring (нужно внести):**

| Domain   | Key             | Что сделать |
|----------|-----------------|-------------|
| `db`     | `password`      | Не обязателен: пароль уже в `db`/`url`. По необходимости — если хранишь URL без пароля. |

**Ожидает твоего решения или авторизации (не ключ в keyring):**

| Что | Действие |
|-----|----------|
| **GitHub** | Один раз: `gh auth refresh -s project`. Проверка: `gh auth status` — в scope должен быть `project`. Локально уже настроено. |
| **Gmail OAuth (консент‑экран)** | Конфигурация пройдена: приложение `Roleforge` переведено в нужный режим, текущий Gmail добавлен в аудиторию (Test users / External). При необходимости менять список пользователей и режим In production/Back to testing — делать это в разделе **Audience** консоли Google Cloud. |
| **Gmail label для intake** | Выбрать один лейбл Gmail для писем с вакансиями (TASK-015). Задать в конфиге/переменной окружения. |

**Decisions you need to make (no keyring, just config/choice):**

- **GitHub:** run `gh auth refresh -s project` once; no key in roleforge keyring.
- **AI provider:** choose exactly one for MVP — OpenAI **or** Anthropic. Store only that provider’s key (row 6 or 7).
- **Gmail label/mailbox:** which Gmail label to use for intake (TASK-015); config/env, not keyring.
- **Postgres:** when you have a DB, add `db` `url` (and optionally `db` `password`).

### Keys present in keyring by default

The project assumes that the keys listed above are present in the keyring when the corresponding feature is used (Linear for sync, Google for Gmail intake, telegram for digest/bot, openai/anthropic for AI, db for runtime). **No automated verification step is required** — scripts and docs treat keyring as the source of truth; if a key is missing, the call that needs it will fail at runtime.

**Entry label and description (for manual edits in keyring GUI):**
- **Linear API key**: label `RoleForge linear api_key` (or keep `roleforge-linear` if you prefer). Description/note: *Personal API key for Linear GraphQL API (api.linear.app). Used for backlog sync and API access.*  
  For scripts to find it, the secret must be stored via `scripts/roleforge-keyring.sh set linear api_key` so attributes `domain=linear`, `key=api_key` are set; otherwise add the same attributes in your keyring app if it allows editing them.

```bash
scripts/roleforge-keyring.sh set <domain> <key>   # prompts for secret value
scripts/roleforge-keyring.sh get <domain> <key>
scripts/roleforge-keyring.sh exists <domain> <key>
```

## GitHub CLI: `gh` auth and project scope

To use GitHub Projects (e.g. for `scripts/seed_github_backlog.py`), the token must include the **project** scope.

1. Add the scope:
   ```bash
   gh auth refresh -s project
   ```
2. Verify:
   ```bash
   gh auth status
   ```
   Ensure `project` appears in the token scopes.

If you use a non-default host or need to re-login from scratch:

```bash
gh auth login
# then add project scope:
gh auth refresh -s project
```

## Linear: token and API path

- **API endpoint**: `https://api.linear.app/graphql` (GraphQL).
- **Auth**: Personal API key in the `Authorization` header (value is the key as-is, or `Bearer <key>` depending on client).

**Where to create the key (best option):**  
On the workspace **Settings → API** page (the one with OAuth, Webhooks, Member API keys), use the link **"security & access settings"** in the *Member API keys* section. There you create a **Personal API key** for your user. No need to create an OAuth application or a webhook for backlog/API access — a single Personal API key is enough.

- **Keyring**: store the token under the **roleforge** keyring with domain `linear`, key `api_key`:
  ```bash
  scripts/roleforge-keyring.sh set linear api_key
  # paste the Linear API key when prompted
  ```
- **Usage**: apps read the token with `scripts/roleforge-keyring.sh get linear api_key` (or equivalent secret-tool lookup with `service=roleforge` `domain=linear` `key=api_key`).

| Item        | Value                              |
|------------|-------------------------------------|
| API base   | `https://api.linear.app/graphql`    |
| Keyring domain | `linear`                        |
| Keyring key    | `api_key`                        |

## Bootstrap sequence (MVP)

Complete these steps in order. After each secret is stored in the keyring, **delete any plaintext copy** (file, clipboard, env export); do not commit or leave secrets in repo or shell history.

1. **GitHub**  
   Run `gh auth refresh -s project` and confirm `gh auth status` shows `project` scope. No keyring entry needed (gh uses its own credential store).

2. **Linear**  
   Create a Personal API key in Linear (Settings → API → security & access settings). Store: `scripts/roleforge-keyring.sh set linear api_key`. Remove any file or note containing the raw key.

3. **Google Cloud project and Gmail OAuth**  
   Create a Google Cloud project, enable Gmail API, create OAuth 2.0 credentials (desktop or web client). Complete the OAuth consent flow and obtain a refresh token. Store in keyring:  
   - `scripts/roleforge-keyring.sh set google client_id`  
   - `scripts/roleforge-keyring.sh set google client_secret`  
   - `scripts/roleforge-keyring.sh set google refresh_token`  
   After each: remove plaintext. Do not commit credentials or leave them in `.env` long-term.

4. **Telegram bot**  
   Create a bot via BotFather, copy the token. Store: `scripts/roleforge-keyring.sh set telegram bot_token`. Delete the message or file with the token.

5. **Primary AI provider (one for MVP)**  
   Choose either OpenAI or Anthropic. Store the API key:  
   - OpenAI: `scripts/roleforge-keyring.sh set openai api_key`  
   - Anthropic: `scripts/roleforge-keyring.sh set anthropic api_key`  
   Remove any plaintext copy and document the chosen provider in repo (e.g. `docs/architecture.md` or product brief).

6. **Postgres (when ready for runtime)**  
   When you have a DB URL or password: `scripts/roleforge-keyring.sh set db url` and/or `set db password`. Do not commit connection strings.

**Plaintext cleanup**: Treat keyring as the only durable store. After `roleforge-keyring.sh set`, ensure no copy of the secret remains in downloads, temp files, `.env`, or git-tracked files.

## Summary

| System    | Fix / path |
|----------|------------|
| Keyring  | Use keyring named **roleforge**; store secrets via `scripts/roleforge-keyring.sh` with `service=roleforge`. |
| GitHub   | `gh auth refresh -s project` then `gh auth status`. |
| Linear   | Token in keyring: domain `linear`, key `api_key`. API: `https://api.linear.app/graphql`. |
