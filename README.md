# Serial Auto Uploader Bot

A production-ready Python Telegram bot built with **PyroBlack** that automatically monitors TV serial episode platforms (such as `https://desiserials.com.co/`), parses new releases, uploads media to a primary Telegram channel, and executes a zero-data-loss 12-hour archival lifecycle to a permanent File Archive channel and searchable History index channel.

---

## 🌟 Architecture Overview

```text
serial-auto-uploader/
├── app/
│   ├── main.py               # Main application lifecycle manager
│   ├── config.py             # Pydantic environment configuration
│   ├── logging.py            # Structured logging setup
│   ├── database/             # MongoDB async layer (Motor)
│   │   ├── mongodb.py        # Connection & indexes
│   │   ├── models.py         # Episode & Show data models
│   │   └── repositories.py   # Atomic DB repository operations
│   ├── scraper/              # Site scraper & resilient HTML parser
│   │   ├── client.py         # Async HTTP client with backoff retries
│   │   ├── parser.py         # Isolated BeautifulSoup HTML selectors
│   │   ├── models.py         # Scraped episode data structures
│   │   └── service.py        # Automated scanning pipeline
│   ├── media/                # Streaming downloader & temp file storage
│   │   ├── downloader.py     # Chunked 1MB stream downloader
│   │   ├── validator.py      # Filename & path traversal security
│   │   ├── metadata.py       # File size & metadata extraction
│   │   └── cleanup.py        # Temp storage cleaner
│   ├── telegram/             # Telegram Bot Implementation (PyroBlack)
│   │   ├── client.py         # PyroBlack Client initialization
│   │   ├── uploader.py       # Channel media posters & messaging
│   │   ├── handlers.py       # User callbacks & Admin commands
│   │   ├── filters.py        # Admin permission filter
│   │   ├── keyboards.py      # Dynamic Inline Keyboards
│   │   └── messages.py       # Caption templates
│   ├── scheduler/            # APScheduler async background jobs
│   │   ├── manager.py        # Scheduler lifecycle manager
│   │   └── jobs.py           # Periodic scrape, archive, retry jobs
│   └── services/             # Core Business Logic Services
│       ├── episode_service.py # Scrape -> Upload workflow
│       ├── archive_service.py # 12-Hour Archive -> Delete workflow
│       └── retry_service.py   # Automated failure retry engine
├── tests/                    # Unit tests for scraper & lifecycle
├── Dockerfile                # Container deployment definition
├── requirements.txt          # Python dependencies
└── run.py                    # Application launcher
```

---

## 🚀 Features

- **Automated Scraping**: Periodically scans latest episode listings (configurable interval).
- **Duplicate Detection**: Uses canonical URL and composite unique identifier indexes (`show_name:episode_number:episode_date`).
- **PyroBlack Telegram Integration**: Isolated Telegram layer utilizing `pyroblack`.
- **12-Hour Archival Safety**:
  1. Post initial episode to **MAIN Channel**.
  2. Wait 12 hours (configurable via `DELETE_AFTER_HOURS`).
  3. Copy media permanently to **FILE Channel**.
  4. Create history entry in **HISTORY Channel** with interactive `📥 GET FILE` button.
  5. Delete original message from MAIN channel **only after file & history posts are verified**.
- **User Episode Retrieval**: Users click `📥 GET FILE` in the history channel to receive the episode directly in private chat without re-downloading media.
- **Admin Security**: Strict middleware restricting administrative bot commands (`/status`, `/scan`, `/recheck`, `/pause`, `/resume`, `/retry`, `/cleanup`, `/stats`, `/search`) to configured `ADMIN_IDS`.
- **Restart Safety**: State recovery on startup for stuck uploads or interrupted schedules using MongoDB as the single source of truth.

---

## 🛠 Setup & Installation

### Prerequisites
- Python 3.11+
- MongoDB instance (Local or MongoDB Atlas)
- Telegram Bot Token & API Credentials from [my.telegram.org](https://my.telegram.org)

### Local Environment Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/MrAbhi2k3/vidlink-decryptor.git
   cd vidlink-decryptor
   ```

2. **Create and activate Python virtual environment:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure Environment Variables:**
   Copy `.env.example` to `.env` and fill in your details:
   ```bash
   cp .env.example .env
   ```

---

## ⚙️ Configuration (.env)

| Variable | Description | Default |
| :--- | :--- | :--- |
| `API_ID` | Telegram API ID from my.telegram.org | *Required* |
| `API_HASH` | Telegram API Hash from my.telegram.org | *Required* |
| `BOT_TOKEN` | Bot Token from @BotFather | *Required* |
| `MONGO_URI` | MongoDB Connection URI | `mongodb://localhost:27017` |
| `MONGO_DB_NAME` | Database name | `serial_bot` |
| `MAIN_CHANNEL_ID` | ID of Main temporary channel (e.g. `-100...`) | *Required* |
| `FILE_CHANNEL_ID` | ID of Archive file channel (e.g. `-100...`) | *Required* |
| `HISTORY_CHANNEL_ID` | ID of History index channel (e.g. `-100...`) | *Required* |
| `LOG_CHANNEL_ID` | Optional channel ID for bot event notifications | *Optional* |
| `ADMIN_IDS` | Comma-separated Telegram User IDs for admins | *Required* |
| `SOURCE_URL` | Site URL to scrape | `https://desiserials.com.co/` |
| `SCRAPE_INTERVAL` | Polling interval in seconds | `300` |
| `DELETE_AFTER_HOURS` | Retention time in main channel before archive | `12` |
| `DOWNLOAD_DIR` | Temporary download folder | `downloads` |
| `DOWNLOAD_TIMEOUT` | Max download stream timeout in seconds | `1800` |

---

## 🤖 Telegram Channel Permissions

The bot must be added as an **Administrator** in all 3 configured channels with the following permissions:

1. **MAIN CHANNEL**:
   - Post Messages
   - Delete Messages
2. **FILE / ARCHIVE CHANNEL**:
   - Post Messages
3. **HISTORY CHANNEL**:
   - Post Messages

---

## 🏃 Running the Application

### Direct Run
```bash
python run.py
```

### Docker Deployment

1. **Build Docker Image:**
   ```bash
   docker build -t serial-auto-uploader .
   ```

2. **Run Container:**
   ```bash
   docker run -d --name serial_uploader --env-file .env serial-auto-uploader
   ```

---

## 🧪 Running Unit Tests

Run the pytest test suite covering HTML parsing, canonical normalization, and archival math:
```bash
pytest
```
