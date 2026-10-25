# Gerald — launch video (Remotion)

Motion-design launch video, readable without sound (every scene carries a caption), landing DA (`web/src/landing.css`).

```bash
cd video && npm i
npm run dev                      # Remotion Studio → http://localhost:3000/Launch
npx remotion render Launch out/gerald-launch.mp4
```

Structure (`src/Video.tsx`, 1920×1080 · 30 fps · ~89 s): hook → problem (chatbot dumps the answer, next-morning blank page, PISA 474) → thesis → **Gerald** (board: sees, circles, speaks) → any app (fake desktop + Photoshop guided by voice) → TD + board → how it works → proof/trust → CTA. See `STORYBOARD.md`.

## Real footage

Drop screen recordings in `public/footage/` and point the `footage` default props (`src/Root.tsx`) to them; `null` keeps the animated mock:

```ts
footage: { board: "board.mp4", photoshop: "photoshop.mp4", td: "td.mp4" }
```

Each slot is shown with `objectFit: cover` in a 16:9 frame; record at 1920×1080 (or 1680×…) and trim to the scene length (board 12 s, photoshop 11 s, TD 9 s) or set `trimBefore` in `src/footage.tsx`.

## Audio

`public/audio/` — Mixkit tracks (free licence, see `CREDITS.md`). Default: *Driving Ambition* (film score, lifts at ~35 s = the "Meet Gerald" beat). Swap with the `music` prop (`motivating-mornings.mp3` is the brighter corporate alternative). SFX from remotion.media.
