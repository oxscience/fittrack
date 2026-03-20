# FitTrack

**Fitness tracking app with email-first trainer/trainee workflows.**

Trainers create workout plans and send them via email. Trainees reply with their results. The system parses the replies automatically and logs the workouts.

## Features

- **Trainer/Trainee Roles**: Trainers manage clients, create routines, review workouts
- **Email-First Workflow**: Training plans sent via SMTP, replies parsed via IMAP — no app install needed for trainees
- **Workout Parser**: Regex-based parser handles German formats (`3x10`, `je 12`, `wie geplant`, etc.)
- **Auto-Reminders**: Morning plans (7:00) and evening nudges (20:00) via APScheduler cron jobs
- **Inbox Polling**: Automatic IMAP polling every 5 minutes for trainee replies
- **Exercise Library**: Pre-seeded exercise database with categories (Brust, Rücken, Beine, etc.)
- **Workout History**: Detailed logs with charts and progress tracking
- **Routine Builder**: Create and duplicate workout routines with sets/reps/weight
- **Setup Wizard**: 4-step onboarding (Account, Email, Branding, Summary)

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python, Flask 3.1 |
| Frontend | HTMX, Vanilla JS/CSS, Chart.js |
| Database | SQLite |
| Scheduler | Flask-APScheduler |
| Email | SMTP (send), IMAP (receive), email-reply-parser |

## Quick Start

```bash
git clone https://github.com/oxscience/fittrack.git
cd fittrack
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open `http://localhost:5003` — the setup wizard will guide you through account and email configuration.

## How the Email Workflow Works

```
Trainer creates routine → sends plan via email (SMTP)
                                    ↓
Trainee receives email → replies with results ("3x10 Bankdrücken, 80kg")
                                    ↓
IMAP polls inbox → workout_parser.py extracts sets/reps/weight → logs workout
                                    ↓
Trainer reviews parsed workout → approves or adjusts
```

## License

MIT
