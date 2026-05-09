# Local/Online Music Player Server

## Overview

Flask + Socket.IO web app that lets users search for music, queue tracks, and control playback from a browser UI. Features:

- User accounts (login/register), admin tools, and profile updates.
- Local song playback via `pygame.mixer`.
- Online search with YouTube Music results and on-demand download.
- Real-time UI updates (queue, current song, volume, pause state) over WebSockets.

## Key Pages

- `/` — Main player UI (guest/user/admin view)
- `/login` — Login page
- `/register` — Sign-up page
- `/profile` — Profile settings (username/password)
- `/admin` — Admin panel (delete users/songs, refresh data)
- `/consolepage` — Console page (control/monitor playback)

## Backend Highlights (Server.py)

- SQLite DB (`app_database.db`) with tables: `users`, `songs`, `favorites`.
- YouTube search via `uyts` and downloads via `pytube`.
- Audio playback via `pygame.mixer`.
- WebSocket events: `search`, `add_to_playlist`, `remove_from_playlist`, `pause`, `resume`, `stop`, `clear`, `volume`, `favourite`, `adminrefresh`, `deleteusers`, `deletesongs`.

## Requirements

Python 3.9+ recommended.

### Python packages (pip)

- `flask`
- `flask-cors`
- `flask-socketio`
- `flask-login`
- `sqlalchemy`
- `werkzeug`
- `pygame`
- `pytube`
- `uyts`
- `pyserial`

### System tools

- **ffmpeg** (required to convert downloaded audio)

## Setup

1. Create and activate a virtual environment
2. Install dependencies
3. Ensure `ffmpeg` is installed and available on PATH

## Run

From the project root:

- `python Server.py`

Then open:

- `http://localhost:5000`

## Notes

- Audio files are stored under `Song files/Audio`. Ensure the folders exist and are writeable.
- The current `ffmpeg` path in `Server.py` is a Windows path. On macOS, update the command to just `ffmpeg` (available on PATH) or adjust the path accordingly.
- Serial/Arduino support is optional if attaching a hardware jukebox unit; the code attempts to connect to COM ports and `/dev/ttyACM0`. If not present, it safely fails.

## Project Structure

- `Server.py` — Flask + Socket.IO backend
- `templates/` — HTML templates (index, admin_page, Login, Sign_up, profile, console)
- `static/` — CSS/JS assets
- `app_database.db` — SQLite database (created at runtime)
