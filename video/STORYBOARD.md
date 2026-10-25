# Storyboard — Gerald launch video (~88 s)

Readable without sound: a black caption pill carries the message of every scene. Every sentence on screen comes from the pitch deck (`pitch/index.html`), the landing (`web/src/landing.tsx`) or a measured result in the repo — nothing invented.

| # | t (s) | Scene | What you see | On-screen text | Source |
|---|------|-------|--------------|----------------|--------|
| 1 | 0–6.5 | Problem (dark) | Headline reveals word by word, blue underline on "nobody next to you" | "Learning alone in front of a screen means learning with nobody next to you." | Deck · slide 3 title |
| 2 | 6–13 | 01 · AI gives the answer | Chat window: the student asks, a chatbot streams the full solution; the window greys out | "AI gives the answer. Chatbots solve the exercise for you." → "You copy it. You don't understand it." | Deck · slide 3 point 01 |
| 3 | 12.5–18.5 | 02 · It can't see your screen | Headline | "Screenshots, copy-paste, re-explaining context on every question." / "The learning flow breaks." | Deck · slide 3 point 02 |
| 4 | 18–24.5 | The number (dark) | Counter 495 → **474**, "−21 pts" | "Average maths score, down 21 points since 2018 — a historic drop. Source: OECD, PISA 2022 results (Dec. 2023)" | Deck · slide 3 stat (OECD PISA 2022: France maths 474, 2018: 495) |
| 5 | 24–30 | 03 · A real tutor is rare | Centered headline | "A tutor points, draws, makes you think. But not at 11 pm, and not for everyone." | Deck · slide 3 point 03 |
| 6 | 29.5–35.5 | Meet Gerald | Brand mark, badge, hero claim, Ctrl + Shift keycaps press | "Voice tutor for students · Beta" / "You write on the board. Gerald corrects you." / "Hold Ctrl + Shift and speak" | Landing hero · README shortcuts |
| 7 | 35–47.5 | The board | Landing hero board replayed: handwriting, Gerald's cursor glides to "+ 24", violet circle, bubble "Careful: it's minus 4ac. 4 × 1 × 6 = 24.", correction, tick, "Bravo! Both roots are right." **Footage slot `board`** | "Work your exercise by hand on Gerald's board. It follows every line." → "It circles the mistake and explains it out loud." → "You still find the answer." | Landing hero lead + HeroBoard copy |
| 8 | 47–58.5 | Any app · Windows first | Fake desktop + Photoshop-like window: Gerald points the shape tool, the user draws, points the colour, fill. **Footage slot `photoshop`** | "Hold Ctrl + Shift from any app. Gerald sees what you see." → "It points at what matters. You do the clicking." → "One step at a time, then "your turn". It only acts if you allow it." | Landing How-step 2 + Feature 01 title · Deck slide 4 "It guides" |
| 9 | 58–66.5 | Your courses · the board | TD left, board right; Gerald underlines Δ = b² − 4ac, plots the parabola with roots 2 and 3. **Footage slot `td`** | "Drop your courses. Gerald reads the exercise you have open." → "When a drawing helps, it opens a board and plots the exact curve." | Landing How-step 1 + Features 01/02 |
| 10 | 66–75 | Under the hood | 5 nodes (Trigger · Perception · Brain · Tools · Render) lit by a travelling pulse | Deck node texts verbatim; caption "Trust order: UIA element → OCR word → visual grounder → never the model's raw coordinate." | Deck · slides 6 and 8 |
| 11 | 74.5–81.5 | Trust & privacy | 3 cards: 77 → **92 %**, Vision on demand, Real consent | "A tutor on your screen, not a spy." / harness: 17 scenarios, gpt-5.5 judge, 8 criteria, 77 % → 91–93 % | Deck · slides 7 and 9 · `evals/pedagogy/scenarios.json` (17) |
| 12 | 81–88 | CTA | Brand, claim, keycaps, buttons Try the demo / Learn live, GitHub | "Doesn't give you the answer. Helps you find it." / "Any app · Windows first · open source (MIT)" | Deck · slides 1, 4 and 12 · landing CTAs |

The Photoshop bubbles ("A rectangle? Start with the shape tool." …) describe the live demo scenario being recorded by the main session; they are replaced by the real recording.

## Footage to record (16:9, 1920×1080, no audio needed)

- `board.mp4` (≥ 12 s): board with x² − 5x + 6 = 0; student writes the wrong Δ (25 + 24), Gerald circles/underlines it, bubble, correction, roots, "Bravo".
- `photoshop.mp4` (≥ 11 s): the fake desktop → Photoshop; voice ask "draw a blue rectangle"; Gerald points the rectangle tool, user drags, Gerald points the colour, fill.
- `td.mp4` (≥ 9 s): TD open, Gerald underlines the Δ formula, board opens, parabola plotted with roots.

Record the UI only (no browser chrome); the video frames each clip in the landing gradient stage.
