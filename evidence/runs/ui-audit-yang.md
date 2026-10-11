# UI audit M: report only (jrkrishh, Sun 11 Oct ~22:45 IST, main at fb0a12a)

## How this was checked
- `scripts/rehearse.py` on 8791, with fake keys only. One real Team run made real content: hand-offs, a Writer file, an
  approval card that expired, a routine, Board tasks.
- **Automated sweep, every screen:** 19 screens, at 375x812, 1100x760 and 1440x900, in dark and light (114 passes).
  - Screens: Chats, Team chat, DM, New group sheet, Crew Room, bot profile sheet, Build a bot sheet, Board, Jobs,
    Settings home, and all 9 Settings pages.
  - Each pass checked for:
    - sideways page scroll
    - controls off-screen
    - text cut off
    - content cut off vertically
    - tap targets under 28 px on a phone
- **Visual pass:** by eye, on screenshots.
- **Tooling limit, so you can trust each row:** the in-app browser's screenshots crop the right edge of the viewport at
  every emulated size. The DOM showed text ending at 318 of 375 px while the image cut it off. So:
  - Anything about clipping or overflow below comes from **DOM measurement**, not from a picture.
  - Screenshots back up the look-and-feel rows only.
  - Anything that only looked cut off in a screenshot but measured fine was dropped. For example, Board "Done" ends at
    1059 of 1100 px, and the 375 chips end at 363 of 375.
- **Light vs dark:** both themes gave identical sweep results. I found no theme-only layout bug.

## Rows, worst first
| # | Screen | Size | What's wrong | Evidence |
|---|---|---|---|---|
| 1 | Crew Room | 375, 1100 (DOM) and every size (eye) | Bots overlap: Inbox sits in front of Desk, and Desk's name tag lands on Inbox's body. The ring runs off the right edge. At 375, **5 of 6 bot buttons are off-screen** (Web, Scout, Inbox, Writer, and the 🙋 button); at 1100, Writer is. There's no way to reach them except by guessing. The tab's whole point is "tap a bot". | `audit-crew-room-crowded-yang.jpg`; sweep: "control off-screen horizontally: BUTTON Writer" |
| 2 | Team chat | all | Internal plumbing shown to the person: a `schedule_routine` code chip, and `Routine ac0c955d set: "Remind me about…"` with a raw id. Reads like a log, not a team. | `audit-chat-375-internals-yang.jpg` |
| 3 | Team chat, approval card | all | The card shows a full Windows path (`C:\Users\…\AppData\Local\Temp\…\Desktop`) that wraps across 3 lines on a phone. "Desktop\llm-report-1.md" says the same thing. | `audit-chat-375-internals-yang.jpg` |
| 4 | Team chat, expired card | all | The card says **"No answer: not done"**, and the next bubble from Desk says **"You said no, so I left it."** They contradict each other: the person never said no. The rehearsal's scripted Desk may cause this, but `registry._say_how_the_card_ended` exists for exactly this, so please check the wording on a live model. | `audit-chat-375-internals-yang.jpg` |
| 5 | Board | 375 | On a phone it opens on **"Doing 0"**, an empty column, while Blocked 1 and Done 2 exist. The first thing you see is nothing. Opening on the first non-empty column would fix it. | `audit-board-375-empty-tab-yang.jpg`; DOM: selected chip "Doing 0" |
| 6 | Board | all | A step the person **declined** sits in **Blocked** forever ("You said no, so I left it."). Blocked means waiting on something; a no is finished. It belongs in Done (or a "Cancelled" note), or Blocked fills up with dead cards. | `audit-board-blocked-declined-yang.jpg` |
| 7 | Board | 375 | The "Remove task" × is a **15x20 px** tap target. It sits next to the status menu, so a mis-tap removes a task. | sweep: "tap target 15x20 < 28px: Remove task 3" |
| 8 | Board | all | Card titles are the raw step text with a trailing period and a path ("Open Desktop/llm-report-1.md."). It's fine as a log line but reads oddly as a to-do title. | `audit-board-blocked-declined-yang.jpg` |
| 9 | Board | 1100, 1440 | A done card's note is cut off vertically (`.task-note`, 98 px of text in 78 px) with no "more" or expand, so the result's links are hidden. | sweep: "content cut off vertically (98>78px): .task-note" |
| 10 | Settings → Crew's Chrome | all | The Discord row says automating it "could get banned", yet it has the same **Open** button as the safe rows. Either drop the button or make the warning the action. LinkedIn shows `/login` in its address while the others show a bare domain. | `audit-chrome-discord-yang.jpg` |
| 11 | Settings → Routines | all | The schedule shows the raw lowercase text ("every monday at 9am") next to a nicely formatted "next Mon, Oct 12, 09:00 AM". Capitalise it, or show only the friendly form. | eye |
| 12 | Chats list, hand-off rows in chat | 375, 1440 | Hand-off and step rows cut long text with an ellipsis (`Save Desktop/llm-report-1.md with: # Fre…`: 1046 px of text in 207 px), with no way to see the rest. Tap to expand would do. | sweep: "text cut off (1046>207px)" |
| 13 | Board | 375 | "Open chat" link is 83x28 px, at the edge of comfortable. | sweep |

## What looked right
- No sideways page scroll on any screen, at any size, in either theme.
- Settings home and the API keys, Models, Usage, Phone, Allowed, Security and Appearance pages had no clipping in the
  sweep (after your `.page > *` fix).
- Jobs' empty state explains itself.
- Build a bot and the profile sheet fit at 375.
