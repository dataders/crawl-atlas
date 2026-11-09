# Finding missed observations in the corpus

The Book 1 reread added 456 observations from 379 paragraphs. The old review queue already included the source paragraph for 282 additions. For 56 of those, the timeline even had a different fact at that source. Conversely, the queue skipped the source paragraph for 174 additions. These counts compare the six Book 1 audits with the saved queue and the timeline at `785eff966`. A queue match tells us a reviewer could have found the passage. We have no record of whether a person actually reviewed it.

The original extractor keeps the chapter text and classifies paragraphs using keywords and bold formatting. Its stat pattern expects a stat name, a colon and digits. Its level pattern expects digits immediately after “level”. Ordinary narrative frequently puts the value, character, item transfer or activation in a neighboring sentence. The timeline builder also contains hand-selected lists of milestones. On a leaderboard, including one character from a row of rankings can leave the other named characters unrecorded. Of the 237 corrections in Book 1, 183 changed which paragraph first establishes a fact.

## Printed leaderboards

Run `uv run python scripts/extract_leaderboard_readings.py`. It parses the numbered place, printed name, race, class, level and prize fields. It compares the character level to the timeline and writes all readings and a deduplicated draft of missing observations under `data/private/`. The proposals retain the printed source and describe what the leaderboard says. Repeated printings, lower values, unresolved names and conflicts remain available to inspect.

In Books 3–5, six leaderboard displays contained 58 matching rows. Of these, 23 listed levels absent for a tracked character. Four repeated an earlier printing, leaving 19 distinct additions. Another 14 entries used names outside the exact roster/alias mapping. One reading was lower than the character's previously established level. The formula works on that particular printed layout. Books without it require other searches.

## Narrative passages

Run `uv run python scripts/find_audit_leads.py --books 2 3 4 5 6 7 8 --limit-per-book 12`. The output is private JSONL with the matching paragraph, up to two neighbors on each side, the reason for selection and existing observations at those sources. The selector rotates through changes in rank, abilities, gear, ownership, rewards and party or life status. It retains paragraphs that already have a recorded fact. Book text stays in the ignored private directory.

Review the full character history for a duplicate. Read farther when a pronoun, item, condition or speaker needs context. Record a disposition and use the actual paragraph establishing the fact. A hypothetical bonus, enemy level or inventory handoff to an unnamed recipient cannot establish a character's numeric stat. Combine reviewed rows into a JSONL file and pass it as `--reviewed PATH` to skip those window keys on a subsequent run. The key changes if the context or observations linked to it change.

The November 9 pilot sampled 12 windows per later book, 84 windows or 420 distinct paragraphs in total, before follow-up context. Reviewers found new information in 51 windows, corrections in four, existing coverage in 11, inapplicable content in 16, and unresolved evidence in two. This measures findings per selected window. It cannot estimate how much of the series remains undiscovered. As a retrospective check on the second half of Book 1, 48 windows selected against the pre-audit timeline covered 240 of 2,179 paragraphs and included the source for 61 of 241 newly found observations. Fourteen of those 61 had been missed by the old candidate queue.

Use exact-format extraction to draft structured records, passage review for narrative findings, and occasional complete chapter reads to discover patterns absent from both. After verifying sources, additions still go through the normal curated audit and spoiler-boundary checks.
