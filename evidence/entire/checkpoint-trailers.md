# Commits that carry an Entire checkpoint

Every commit made from a Claude Code session with Entire's hook carries an `Entire-Checkpoint: <id>` trailer. The
trailer links the commit to the checkpoint that holds the agent session behind it.

Count them yourself:

    git log --all --format='%(trailers:key=Entire-Checkpoint,valueonly)' | grep -c .

| When | Commits with a trailer | By author |
|---|---|---|
| Mon 12 Oct, 19:45 IST | **88** | JrKrishh 11, sourabh 77 |
| Mon 12 Oct, before the demo video was cut | 86 by 19:27 IST (`git log --all --until="2026-10-12 19:27 +0530" ...`) | |

The demo video says "76 commits carry a checkpoint". That count came from a clone that hadn't pulled the latest
commits, so it's an **undercount**: the real number at the time was 86.

See one trailer:

    git log -1 --format='%h %an %s%n%(trailers)' e784dc7

(Any commit hash from `git log` works.) 
