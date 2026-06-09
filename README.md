# nightguard

![nightguard banner](banner.png)

**Your late-night self is smart. Nightguard is smarter.**

A digital discipline system for [Claude Code](https://docs.anthropic.com/en/docs/claude-code) that enforces bedtime curfews, keeps your screen-time blockers alive, and catches you when you try to cheat the clock.

> *"I'll just fix one more thing..."* — You, at 2 AM, every night.

Nightguard makes the disciplined choice the default — and the undisciplined choice harder than just going to bed.

## Features

**Curfew Guard** — Blocks Claude Code during the hours you choose. Set different schedules for weekdays vs weekends, or disable specific days entirely.

**Clock Protection** — Verifies time against NTP servers. Changed your system clock to 2 PM? Nightguard knows it's actually midnight. Nice try.

**App Watchdog** — Closed your screen-time blocker from the system tray? It's back in 2 minutes. Supports any Windows app — Store apps and regular `.exe` programs.

**Fully Configurable** — One YAML file controls everything: timezone, curfew hours, per-day schedules, which apps to protect, custom block messages, and more.

## Setup

1. Clone this repo
2. Open it in [Claude Code](https://docs.anthropic.com/en/docs/claude-code)
3. Say: **"Set up nightguard for me"**

Claude walks you through everything — timezone, schedule, apps, preferences — and installs it for you. No config files to edit by hand.

### Manual setup

```powershell
# 1. Copy and edit the config
mkdir ~/.claude/nightguard
cp config.example.yaml ~/.claude/nightguard/config.yaml
# Edit config.yaml with your preferences

# 2. Install hooks (no admin needed)
powershell -File scripts/setup.ps1 -SkipScheduledTask

# 3. Install app watchdog (admin PowerShell, one-time)
powershell -File scripts/setup.ps1
```

## Configuration

All settings live in `~/.claude/nightguard/config.yaml`. See [`config.example.yaml`](config.example.yaml) for the full annotated reference.

### Basics

```yaml
timezone: America/New_York

curfew:
  enabled: true
  start: "22:00"
  end: "07:00"
```

### Per-day schedules

Stay up later on weekends. Disable curfew on specific days.

```yaml
curfew:
  start: "21:30"
  end: "06:00"

  schedule:
    friday:
      start: "23:00"
      end: "08:00"
    saturday:
      start: "23:00"
      end: "08:00"
    sunday: off
```

### Custom messages

Set the tone. Gentle reminder, strict parent, sarcastic friend — whatever keeps you honest.

```yaml
curfew:
  message: "Go to bed. You have a 9 AM meeting tomorrow."
  tamper_message: "Caught you changing the clock. Go to sleep."
  offline_message: "Can't check the time, so you're blocked. Goodnight."
```

Use `{start}` and `{end}` as placeholders:
```yaml
  message: "Curfew started at {start}. See you at {end}."
```

### App watchdog

Keep screen-time blockers (or any app) running. Works with Microsoft Store and regular apps.

```yaml
watchdog:
  enabled: true
  check_interval_minutes: 2
  apps:
    - name: Cold Turkey Blocker
      type: exe
      path: "C:\\Program Files\\Cold Turkey\\Cold Turkey Blocker.exe"
      process_name: ColdTurkey
```

## How it works

Nightguard installs as a [Claude Code hook](https://docs.anthropic.com/en/docs/claude-code/hooks) — a script that runs before every prompt. During curfew, it blocks the prompt and tells you to go to bed.

The time check queries independent HTTPS time APIs (`timeapi.io`, `worldclockapi.com`) to get the real time, falling back to NTP via `w32tm` only as a last resort. HTTPS is preferred because some managed networks (universities, corporate VPNs) transparently intercept NTP traffic and return the local system clock as "authoritative", defeating tamper detection. HTTPS uses TLS cert validation, which fails when the clock is significantly wrong — making it much harder to spoof. If your system clock is off by more than 5 minutes from any reachable source, it flags tampering. If all sources are unreachable, it blocks by default.

The app watchdog runs as a Windows Scheduled Task, checking every 2 minutes if your configured apps are still alive.

## Requirements

- Windows 10/11
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code)
- PowerShell 5.1+ (included with Windows)
- Internet connection (for NTP verification)
- Admin privileges (one-time, for the watchdog scheduled task)

## Philosophy

Willpower is a depletable resource. At midnight, after a long day, you will talk yourself into "just five more minutes" every time. Nightguard removes that negotiation entirely.

It's designed to be **hard to bypass when you're tired** and **easy to configure when you're thinking clearly**. Your morning self sets the rules. Your night self follows them.

## License

MIT
