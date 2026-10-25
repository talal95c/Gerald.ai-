# Gerald — launch video (Remotion)

Motion-design launch video, readable without sound (every scene carries a caption), landing DA (`web/src/landing.css`).

```bash
cd video && npm i
npm run dev                      # Remotion Studio → http://localhost:3000/Launch
npx remotion render Launch out/gerald-launch.mp4
```

Structure (`src/Video.tsx`, 1920×1080 · 30 fps · ~65 s): hook → chatbot gives the answer → PISA 474 → **Meet Gerald** → board (sees, circles, speaks) → any app (fake desktop + Photoshop) → your courses + board → not a chatbot (92 %) → CTA. Voice-over: OpenAI TTS (`scripts_vo.py`, needs `OPENAI_API_KEY`; set `voiceOver: false` to mute). See `STORYBOARD.md`.

## Real footage

Drop screen recordings in `public/footage/` and point the `footage` default props (`src/Root.tsx`) to them; `null` keeps the animated mock:

```ts
footage: { board: "board.mp4", photoshop: "photoshop.mp4", td: "td.mp4" }
```

Each slot is shown with `objectFit: cover` in a 16:9 frame; record at 1920×1080 (or 1680×…) and trim to the scene length (board 12 s, photoshop 11 s, TD 9 s) or set `trimBefore` in `src/footage.tsx`.

## Audio

`public/audio/` — Mixkit tracks (free licence, see `CREDITS.md`). Default: *Motivating Mornings* (123 BPM, lifts at ~10 s), ducked under the voice-over. Swap with the `music` prop (`driving-ambition.mp3` is the calmer film-score alternative). SFX from remotion.media.
