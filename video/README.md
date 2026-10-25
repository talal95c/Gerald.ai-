# Gerald — launch video (Remotion)

Motion-design launch video, readable without sound (every scene carries a caption), landing DA (`web/src/landing.css`).

```bash
cd video && npm i
npm run dev                      # Remotion Studio → http://localhost:3000/Launch
npx remotion render Launch out/gerald-launch.mp4
```

Structure (`src/Video.tsx`, 1920×1080 · 30 fps · ~55 s, English): problem (stuck alone → chatbots give the answer) → **Voici Gerald** → real clips of the live site (TD, board + parabola, Photoshop guided) → CTA. Voice-over: OpenAI TTS (`python3 scripts_vo.py ash`, needs `OPENAI_API_KEY`; set `voiceOver: false` to mute). See `STORYBOARD.md`.

## Real footage

`public/footage/clip1..3.mp4` are the real site recordings (1440×900, silent). `footage` default props in `src/Root.tsx` map them to scenes with a start offset in seconds; `null` keeps the animated mock:

```ts
footage: { board: "clip2.mp4", photoshop: "clip3.mp4", td: "clip1.mp4", trim: { board: 9, photoshop: 8, td: 7 } }
```

Clips are shown `objectFit: contain` in a 1360×850 (16:10) frame on the landing gradient stage.

## Audio

`public/audio/` — Mixkit tracks (free licence, see `CREDITS.md`). Default: *Motivating Mornings* (123 BPM, lifts at ~10 s), ducked under the voice-over. Swap with the `music` prop (`driving-ambition.mp3` is the calmer film-score alternative). SFX from remotion.media.
