# Contributing to skool-kb

Thanks for helping out! This is a small, pragmatic project — contributions that keep it
simple and honest are very welcome.

## Ways to contribute
- **Bug reports** — especially "Skool changed something and scraping broke." Include the
  error output and (roughly) what page it happened on. Never paste your `cookies.txt`.
- **New video hosts** — add patterns to `VIDEO_PATTERNS` in `skool_dump.py`.
- **Better native-video handling** — the Mux/HLS signed-token case is the biggest open gap.
- **Docs** — clearer onboarding, Windows notes, more caption languages, translations.
- **Agent ergonomics** — improvements to `AGENTS.md` that make agent-driven setup smoother.

## Dev setup
```bash
git clone https://github.com/iantinney/skool-kb.git
cd skool-kb
./bootstrap.sh
```

## Ground rules
1. **Never commit secrets or scraped content.** Double-check `git status` — `cookies.txt`,
   `.env`, `communities.txt`, `audio/`, and `kb/posts|transcripts` are gitignored; keep it so.
2. **Keep it dependency-light.** The whole point is "boring and simple." Justify any new dep.
3. **Match the existing style** — small standard-library-first Python, clear comments where a
   choice is non-obvious.
4. **Verify external claims.** If you change a documented external step (an extension name, a
   yt-dlp flag, an API detail), confirm it against current upstream docs and link the source.
5. **Be honest about limits** in docs. Don't turn a "sometimes works" into a promise.

## Pull requests
- Keep PRs focused and describe what you changed and why.
- If you touched a script, show a quick before/after or sample output in the PR.
- The CI runs a lint + import smoke test; make sure it's green.

By contributing, you agree your contributions are licensed under the [MIT License](LICENSE).
