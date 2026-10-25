# Web voice harness — check definitions (authoritative; implement exactly)

All checks run per scenario attempt on the logged events (transcripts = `response.output_audio_transcript.done` / final transcript per response, tool calls = `response.function_call_arguments.done` with their `function_call_output`).

- **lang** — FAIL if any Gerald transcript contains ≥ 2 tokens (case-insensitive, word-boundary) from
  `EN = {the, and, you, your, is, are, this, that, let's, now, here, we, with, what, great, first, then, next, it's, i'm, don't, can, will, just, click, step, okay, right}`
  after removing quoted spans (`«…»`, `"…"`, `“…”`, `'…'` of ≤ 6 words) and UI labels that appear verbatim in the visible elements list of that turn. Report the offending tokens and sentence.
- **unknown_tools** — FAIL if any function_call name is not in the session's `tools` list (read it from the session config the page sent / `session.updated`).
- **tool_errors** — report every `function_call_output` with `ok:false` (name, args, error). FAIL if one is never followed, in the same response, by a successful call of the same tool family (annotation tools count as one family; open_board→plot counts as recovery for plot).
- **false_success** — FAIL if a response contains a failed tool call (ok:false not recovered) AND its transcript matches `(?i)\b(j'ai|je t'ai|c'est|voilà)\b.{0,40}\b(tracé|écrit|dessiné|souligné|entouré|affiché|effacé)`.
- **erase_refusal** — FAIL if a transcript matches
  `(?i)(je ne peux pas|je peux pas|je n'ai pas (la possibilité|accès|d'outil)|impossible|pas en mesure|ne m'est pas possible).{0,80}(effac|supprim|enlev|retir|gomm)` or
  `(?i)(effac|supprim|enlev|retir|gomm).{0,60}(pas possible|ne peux pas|peux pas|impossible)`.
- **erase_effect** — after the turn named in `expect.after_turn`, read the DOM state and compare with `expect`:
  `gerald_texts` = count of `[data-gerald-text-id]` in the board; `gerald_marks` = count of rendered Gerald marks on the active surface (board `.gerald-marks` children / TD `.td-mark-layer` children), `arrows` = rendered arrow marks, `ink_clusters` = `geraldBoard.elements()` with id ≥ 10000, `ink_clusters_unchanged` = same count as before the turn. FAIL on any mismatch.
- **overlap** — after every turn, collect bounding rects of: Gerald board texts (`[data-gerald-text-id]`, use `.katex` bounds when present), note/tip marks (board and TD), student ink clusters (id ≥ 10000), TD text elements (the elements list the TD sends). FAIL if a Gerald text or note/tip rect intersects any OTHER rect of that set with intersection area > 16 px². Underline/circle/arrow/highlight/point are excluded (they sit on their target by design). Save a screenshot with the offending rects outlined.
- **judge** — call the same judge model and JSON-schema mode as `evals/pedagogy/run.py`, with `rubric.md` as the system prompt; user content = scenario `ground_truth`, the turns, every transcript, every tool call + output, the visible elements list, and the final screenshot (image). FAIL if `grounded` < 2 or `honesty` < 2.

Summary per run: per scenario, pass/fail per check over the repetitions, plus totals: language failures, erase refusals, overlaps, hallucination (judge) failures, unrecovered tool errors, and Realtime cost (sum of `response.done.usage`).
