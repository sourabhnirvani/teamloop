# #neatHack post drafts (for a person to post; put the links in hackathon.md afterwards)

All numbers come from files in `evidence/`. Each post fits in 280 characters. Attach the screenshot named under it.

---

**1. Crew vs one bot**
> One bot with every tool vs a crew that hands off: on "research, write a report, open it, remind me Monday", the crew
> finished 4/4, one bot 0/4 (it never set the reminder), at the same or fewer tokens. On a 2-step job one bot wins, and
> we say so. #neatHack

📎 the table from `evidence/runs/before-after-yang.md`

---

**2. Computer use you can see coming**
> Our desktop bot now clicks things by name (accessibility tree, then Windows OCR), moves the real mouse to exact
> pixels, and checks every step. Before it clicks, the approval card shows a red ring on the exact spot. 10/10 live
> tests. #neatHack

📎 `evidence/ui/cu-safety-card-ring-yang.png`

---

**3. It waits for you**
> Move your mouse and TeamLoop's bots pause, then carry on 3 s after you stop. Ctrl+Alt+Q from any app stops every
> chat at once. Tested live on a real laptop, not just in unit tests. #neatHack

📎 `evidence/ui/operator-ctrl-alt-q-balloon-crop-yang.png`

---

**4. We tried to break it**
> We attacked our own phone hub, pairing and approvals: 44 attempts, 7 got through (DNS rebinding, cross-site POSTs,
> an endless stream). All 7 fixed the same morning; re-test: 0. The write-up and the probe script are in the repo.
> #neatHack

📎 `evidence/runs/security-review-yang.md` (screenshot of the table)

---

**5. Honest by design**
> A 7B local model said "saved the file", and the neatlogs trace showed no tool ran. Now TeamLoop adds its own line:
> "Not done: save the file (no tool ran for it)." After the fix: zero fake successes on the same evals. #neatHack

📎 the before/after from `evidence/runs/evals-local-sourabh.md`

---

**6. The real app finds the real bugs**
> Final pass on the real app before the freeze. A model replayed "close without saving" from chat history and clicked
> Don't Save with no approval card. Fixed: every discard click now asks, and old messages are marked as handled.
> #neatHack

📎 `evidence/runs/final-pass-yang.md`
