# Ctrl+Z demo video script

**Length:** about 1:55 (Devpost asks for under 2 minutes). The narration is about 250 words, read at a steady pace.
**Voice:** ElevenLabs, Eric (smooth, trustworthy American).
**Look:** same palette as the dashboard. Near-black background, blue for production, amber for agents at work, green for pass, red for fail. Inter for text, JetBrains Mono for commands.
**Footage:** `[REAL]` marks a screen recording of a live run on Daytona, sped up where noted. `[MOTION]` marks animation built in code.

The narration lines are what the voice reads. Edit them freely. The scene timings will move to fit the final audio.

---

### 1. Cold open (0:00–0:10)

**Visual** `[MOTION]`: a table of database rows fills the screen. Rows start blinking out from the bottom up until the table is empty. A small date stamp reads "July 2025".
**On screen:** —
**Narration:**
> In July 2025, Replit's AI coding agent deleted a company's production database. It happened during a code freeze.

### 2. The problem (0:10–0:20)

**Visual** `[MOTION]`: three agent icons work side by side. One of them flashes red. A line runs from it toward a "Customers" icon and stops just short.
**On screen:** —
**Narration:**
> Agents, like humans, often make mistakes. It's essential that those mistakes not reach your customers.

### 3. The idea (0:20–0:36)

**Visual** `[MOTION]`: the Ctrl+Z wordmark types itself in. Below it, a blue "Production" box splits into three amber copies. Each copy gets a small agent icon and then a row of check marks. One copy turns green and slides up to replace Production.
**On screen:** "Ctrl+Z" · then "Agents work on copies. Production moves only to a copy that passes."
**Narration:**
> Ctrl+Z keeps agents away from production, the system your customers use. It copies that system into separate sandboxes, puts one agent in each, and tests changes in isolation. When a copy passes every check, the production system gets updated.

### 4. The setup (0:36–0:48)

**Visual** `[REAL]`: the Acme Store dashboard. Zoom in on the "Orders page query" card, which reads about 2,000 ms in red. Cut to the Ctrl+Z dashboard as the task is typed into the box.
**On screen:** "2,075 ms" callout on the query card
**Narration:**
> Here is a small online store. Its orders page takes two seconds to load. We gave Ctrl+Z one instruction: the orders page is slow, fix it.

### 5. The fork (0:48–1:02)

**Visual** `[REAL]`, 2x speed: the "Fork & run" click, then the fork tree grows three branches with amber, dashed, moving edges. `[MOTION]` labels slide in beside each branch: "Careful DBA", "App-level rewrite", "Aggressive cleanup (told to act recklessly)".
**On screen:** "3 copies on Daytona"
**Narration:**
> Ctrl+Z makes three copies on Daytona and starts three agents. One is a careful database expert. One is allowed to rewrite the code. The third can act without any restraints.

### 6. The checks (1:02–1:16)

**Visual** `[MOTION]`: four check cards drop in one by one, each with an icon: a database (Integrity), a list (Correctness), a stopwatch (Speed) and a gavel (Judge). Behind them, faint at 4x speed, `[REAL]` agent logs scroll in the branch panel.
**On screen:** "Integrity · Correctness · Speed · Judge"
**Narration:**
> Every copy faces the same four checks. Did we lose data? Does the page show the right orders? Is it at least twice as fast? And does a second model judge the change safe to ship?

### 7. The catch (1:16–1:32)

**Visual** `[REAL]`: the Aggressive cleanup node turns red. Click it: the left panel switches to that copy's store, showing 45,850 orders and history starting in 2025. `[MOTION]` a red counter rolls down from 200,000 to 45,850. Then click "Back to production": 200,000 orders, untouched.
**On screen:** "−77% of orders · $193M of sales history" · then "Production: untouched"
**Narration:**
> The reckless agent made the page faster by deleting seventy-seven percent of the orders: a hundred and ninety-three million dollars of sales history. Ctrl+Z throws that copy away. 

### 8. The fix (1:32–1:44)

**Visual** `[REAL]`: select Careful DBA (★). The verdict panel shows three green checks and KEEP. Click "Promote to production". The query card drops from about 2,000 ms in red to 1 ms in green. The other branches fade and are removed.
**On screen:** "2,075 ms → 1 ms" · "0 orders lost"
**Narration:**
> The careful agent added two missing database indexes. The page now loads in one millisecond, and every order is still there. One click makes that copy the new production.

### 9. How it's built (1:44–1:56)

**Visual** `[MOTION]` over `[REAL]`: three panels, one per line of narration. Daytona sandboxes listed in the Daytona dashboard. An Arize trace tree, with one branch expanded down to its bash commands and eval scores. A Fireworks agent log. Each sponsor's logo sits in the corner of its panel.
**On screen:** "Daytona · Arize · Fireworks"
**Narration:**
> Daytona runs every copy. Arize records each command, each model call and each verdict. Fireworks runs the agents.

### 10. Close (1:56–2:04)

**Visual** `[MOTION]`: the fork tree shrinks into the Ctrl+Z wordmark. The GitHub URL and team name fade in below.
**On screen:** "Ctrl+Z" · repo URL · team name
**Narration:**
> Agents make mistakes. With Ctrl+Z, your customers never see them.

---

## Notes for editing

- **Over 2:00?** Cut scene 2 first (−10 s). Then shorten scene 6 to "Every copy faces four checks: data, correctness, speed, and a second model's judgement." (−5 s).
- **Honesty lines to keep:** "we told to act recklessly" (scene 5) and the on-screen "told to act recklessly" label. Judges will ask about it, and saying it first builds trust.
- **Numbers** come from real runs today. The baseline was 2,075–2,295 ms depending on the run; the careful fix reached 1–2 ms; the reckless agent deleted 154,150 of 200,000 orders. If the recorded run differs, update scenes 4, 7 and 8 to match it.
- **Container sandboxes:** Ctrl+Z currently copies files between sandboxes, so the script says "copies", not "forks memory". If Daytona enables VM sandboxes before recording, scene 5 can add: "Each copy takes under a second and keeps the running server."
