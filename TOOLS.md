# TOOLS.md - Local Notes

Skills define _how_ tools work. This file is for _your_ specifics — the stuff that's unique to your setup.

## What Goes Here

Things like:

- Camera names and locations
- SSH hosts and aliases
- Preferred voices for TTS
- Speaker/room names
- Device nicknames
- Anything environment-specific

## Examples

```markdown
### Cameras

- living-room → Main area, 180° wide angle
- front-door → Entrance, motion-triggered

### SSH

- home-server → 192.168.1.100, user: admin

### TTS

- Preferred voice: "Nova" (warm, slightly British)
- Default speaker: Kitchen HomePod
```

## Why Separate?

Skills are shared. Your setup is yours. Keeping them apart means you can update skills without losing your notes, and share skills without leaking your infrastructure.

---

Add whatever helps you do your job. This is your cheat sheet.

---

## Calendar Event Rules (gog)

When creating events via `gog calendar create`:

1. **Always add Google Meet by default** — use `--with-meet` flag
2. **Send confirmation email afterward** — email jmuller3140@gmail.com with event details
3. **Default account for calendar operations:** alfredclaw3140@gmail.com
4. **Alfred's calendar:** jmuller3140@gmail.com (shared with me)

### Confirmation Email Template

Subject: Calendar Event Created — [Event Title]

Body should include:
- Event title
- Date/time
- Attendees
- Google Meet link
- Calendar link
