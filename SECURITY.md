# Security

## How this tool handles your secrets

`skool-kb` runs entirely on your machine. Two sensitive things live in the project
directory:

- **`cookies.txt`** — your logged-in browser session for Skool (and optionally YouTube).
  Anyone with this file can act as you on those sites. It is **gitignored** and never
  transmitted anywhere except to Skool/YouTube by `yt-dlp`/`requests` as normal requests.
- **`.env`** — holds `GROQ_API_KEY` if you use Groq. Also gitignored.

**Best practices:**
- Keep `cookies.txt` and `.env` out of version control (the default `.gitignore` does this).
- Don't paste their contents into issues, PRs, screenshots, or chat with third-party services.
- On a **shared machine**, remember these files grant access to your accounts. Delete them
  when you're done (`rm cookies.txt .env`) and re-export next time.
- Cookies expire — re-export when scrapes start failing. That's normal, not a breach.
- Prefer exporting YouTube cookies from a **private/incognito** window you then close
  without logging out (see [docs/COOKIES.md](docs/COOKIES.md)) — it limits session rotation.

## Scope

This project does not run a server, collect telemetry, or phone home. The only network
calls are: Skool (scraping), the video hosts (yt-dlp), Groq (only if you set a key), and
package registries / Deno's installer during setup.

## Reporting a vulnerability

Found a security issue in the code (e.g. a way secrets could leak)? Please open a
[GitHub Security Advisory](https://github.com/iantinney/skool-kb/security/advisories/new)
or a private report rather than a public issue. We'll respond as fast as we can.
