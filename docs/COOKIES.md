# Cookies: giving the tool your logged-in session

The scraper reads content **as you** — it needs your logged-in browser cookies. There's no
way around this (Skool has no export/API), and it's the only genuinely manual step.

> **Safety:** your `cookies.txt` grants access to your accounts. It's gitignored by default.
> Never commit it, paste it into an issue, or send it to anyone. See [SECURITY.md](../SECURITY.md).

## 1. Install the cookie-export extension

- **Chrome / Edge / Brave:** install **"Get cookies.txt LOCALLY"** from the Chrome Web Store.
  It processes cookies entirely on your machine.
  ⚠️ **Do not** install the older **"Get cookies.txt"** (without *LOCALLY*) — it was removed
  from the store as malware. If you have it, uninstall it.
- **Firefox:** install the add-on named **"cookies.txt"** (the *LOCALLY* one is Chromium-only).

## 2. Export Skool cookies

1. Go to **https://www.skool.com** and make sure you're **logged in**.
2. Click the extension → **Export** (Netscape / `cookies.txt` format).
3. Save/move the file into the project folder as **`cookies.txt`**.

If you're setting this up on a **different machine than your browser** (e.g. a server), open
the exported file in a text editor, copy everything, and either `scp` it over or paste it to
your agent to write into `cookies.txt`. The format is **tab-delimited** — if pasting mangles
the tabs, the tool/agent will re-normalize them.

## 3. (Recommended) Also export YouTube cookies

Communities often embed lots of YouTube videos, and YouTube bot-checks unauthenticated
requests. Adding your YouTube cookies makes caption/audio downloads far more reliable.

yt-dlp's recommended, most-durable method for YouTube specifically:

1. Open a **private / incognito** window and log into **youtube.com**.
2. In that same tab, visit `https://www.youtube.com/robots.txt` (keeps the session from
   rotating on you).
3. Export cookies for **youtube.com** with the extension.
4. **Close the incognito window without logging out** — this "pins" the session so YouTube
   doesn't invalidate the cookies later.

You can keep Skool and YouTube cookies in **one `cookies.txt`** — a Netscape cookie file
holds multiple domains, and yt-dlp/requests each send only the cookies matching their domain.
Just append the YouTube lines to the existing file (below the Skool lines).

## 4. When cookies go stale

Cookies expire. Signs:
- Scraping warns `no __NEXT_DATA__ (login wall? bad cookies?)`
- YouTube returns `Sign in to confirm you're not a bot`

Fix: re-export and replace `cookies.txt`. Nothing else to change.

## Why not `--cookies-from-browser`?

yt-dlp can read cookies directly from your browser with `--cookies-from-browser`, and for
many sites that's easiest. But for **YouTube** it tends to grab your live, rotating session
(which YouTube then invalidates), so a manually exported file from a **closed incognito
session** is more reliable. This project uses the exported-file approach for that reason.
