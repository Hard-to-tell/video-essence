---
name: video-essence
description: Summarize Bilibili or Douyin video links, watch-later lists, or local media using this bundled subtitle, transcription and visual pipeline. Use for video essence requests, including bare links in an established summarization chat. Not for ordinary browsing or downloading unrelated media.
---

# Video essence

Resolve the runtime root as the directory containing this SKILL.md; never assume a personal drive path. Read [README.md](README.md) for installation or missing dependencies. Use the root `.venv/Scripts/python.exe` on Windows or the configured `VIDEO_ESSENCE_PYTHON`.

## Single video → inline answer

Run `bili.py "URL-or-BV"` for Bilibili, `douyin.py "https://www.douyin.com/video/ID"` for Douyin, or `bili.py --file "absolute media path"`. Set the working directory to this root. Pass URLs as a single quoted argument. Wait on the same process; do not launch duplicate jobs while it transcribes.

The last stdout line is a transcript path. Read its adjacent `content.json`, including all segments (read long transcripts in parts). If mode is visual or speech-and-frames, inspect the listed storyboard images before summarizing. Visual sampling is limited to at most 24 frames, not exhaustive viewing. If a transcript clearly conflicts with the video topic, rerun Bilibili with `--force-asr`; do not summarize unrelated captions.

Answer directly in the chat, normally in Chinese. Keep useful conclusions, explanations, examples and limitations proportional to the content. Distinguish the speaker's claims from established evidence. Do not invent value in filler content. Use timestamps when useful. Do not create summary files unless requested; required media/transcript caches stay inside this root.

## Watch-later or UI workflow

Use the bundled app for persisted batches. Start `app/server.py --no-open` only if the local service is not already running. Check `/api/status` returns `application: bili-summary`; do not send requests to another service occupying the port. See [references/api.md](references/api.md) for submission and polling. Default Douyin batches to 5 and never exceed 9; process serially. Return actual completed summaries, not just a queued status. The app uses a separately installed and authenticated Codex CLI for model summaries; direct single-video chat summarization does not need that nested model call.

Login cookies belong only on the user's machine. Use the app settings import/QR flow or locally supplied Netscape files; never print or upload credentials. An interface rejection or incomplete media is a failure, not permission to substitute the description. Stop on login/CAPTCHA/access errors and report the concrete blocker. No repeated automatic access retries.
