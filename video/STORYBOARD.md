# Storyboard — Gerald launch video (~55 s, hackathon submission) — copy and voice-over in English (Talal: « en anglais »); the table below keeps the French wording of the previous cut, see `scripts_vo.py` for the current lines

Lisible sans le son (une capsule de texte par scène) + voix off française (OpenAI gpt-4o-mini-tts, voix `ash`, script dans `scripts_vo.py`, normalisée à −16 LUFS). Musique Mixkit *Motivating Mornings* (0.3, ducking ×0.45 sous la voix). DA landing, accents violet #7C3AED. Les trois clips réels du site live (1440×900, muets, bulles de Gerald à l'écran) sont dans `public/footage/` et cadrés en 16:10 dans la scène gradient.

| # | Scène | Visuel | Capsule(s) | Voix off |
|---|-------|--------|------------|----------|
| 1 | Problème (fond noir) | « 23 h. Un exercice. Bloqué. Seul. » mot à mot, équation qui clignote, « Ça s'arrête aujourd'hui. » | — | 23 heures. Un exercice. Bloqué. Seul. Ça s'arrête aujourd'hui. |
| 2 | Chatbot | Fenêtre de chat : la solution complète arrive d'un coup, puis se grise | « Les chatbots donnent la réponse. On n'apprend rien. » → « Maths au plus bas (PISA 2022 : 474). Les profs particuliers coûtent une fortune. » | Les chatbots donnent la réponse. On n'apprend rien. Et les profs particuliers coûtent une fortune. |
| 3 | Solution · Voici Gerald | Logo, badge « Le prof particulier qui vit sur votre écran », « Il voit. Il parle. Il dessine. Vous apprenez enfin. », Ctrl + Shift | — | Voici Gerald. Le prof particulier qui vit sur votre écran. |
| 4 | Vos cours (**clip1**, à partir de 7 s) | Bureau → Notes → TD « Polynômes du second degré », Gerald pointe et souligne l'exercice | « Déposez vos cours. Gerald les connaît. » → « Il lit votre TD avec vous et pointe ce qui compte. » | Déposez vos cours. Gerald les connaît, et lit votre TD avec vous. |
| 5 | Le tableau (**clip2**, à partir de 9 s) | Tableau, parabole tracée, racines marquées | « Vous écrivez au tableau. Gerald suit chaque ligne. » → « Il trace la courbe exacte — et c'est vous qui trouvez. » | Vous écrivez au tableau. Gerald suit chaque ligne, explique à voix haute, trace la courbe exacte. Et c'est vous qui trouvez. |
| 6 | N'importe quelle appli (**clip3**, 3 coupes : 6–9 s Formes, 20.5–23 s Color picker rouge, 31.5–36 s carré rouge) | Photoshop : Gerald guide Formes → Rectangle → couleur #ff0000 → le carré rouge est dessiné par l'utilisateur (Gerald ne clique jamais) | « Une touche. N'importe quelle appli. Gerald voit ce que vous voyez. » → « Il vous guide jusqu'au carré rouge. C'est vous qui cliquez. » | Une touche, n'importe quelle appli. Gerald vous guide pas à pas, jusqu'au carré rouge. Et c'est vous qui cliquez. |
| 7 | CTA | Logo, « Ne restez plus jamais bloqué. », « Il ne donne pas la réponse. Il vous aide à la trouver. », boutons Essayer la démo / Apprendre en live, GitHub | — | Gerald. Il ne donne pas la réponse, il vous aide à la trouver. |

Durées de scène = durée de la voix off + 1 s (jamais sous le minimum visuel) ; pour changer le texte : éditer `LINES` dans `scripts_vo.py`, lancer `python3 scripts_vo.py <voice>` avec `OPENAI_API_KEY`, normaliser (loudnorm) et régénérer `src/vo.ts` (voir README).

## Footage to record (16:9, 1920×1080, no audio needed)

- `board.mp4` (≥ 12 s): board with x² − 5x + 6 = 0; student writes the wrong Δ (25 + 24), Gerald circles/underlines it, bubble, correction, roots, "Bravo".
- `photoshop.mp4` (≥ 11 s): the fake desktop → Photoshop; voice ask "draw a blue rectangle"; Gerald points the rectangle tool, user drags, Gerald points the colour, fill.
- `td.mp4` (≥ 9 s): TD open, Gerald underlines the Δ formula, board opens, parabola plotted with roots.

Record the UI only (no browser chrome); the video frames each clip in the landing gradient stage.
