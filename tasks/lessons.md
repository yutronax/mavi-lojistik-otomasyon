## Mavi Lojistik Otomasyon - Lessons Learned

### Human Behavior Simulation for WHAPI
- **API Ban Prevention Strategy**: Replaced continuous, fixed-interval API polling (e.g. `sleep(60)`) with a non-deterministic simulation of human behavior to introduce entropy and reduce ban rates.
- **Statistical Modeling**:
  - Utilized a **Log-Normal** distribution to calculate the time between checking WhatsApp (intervals). This accurately simulates human habits where most intervals are short/average with occasional long delays.
  - Utilized a **Weibull** distribution to calculate how long a given WhatsApp session lasts (duration).
  - Utilized a **Gamma** distribution to introduce micro-jitters during message processing (simulating read/processing time).
- **Behavioral Skips**:
  - Implemented logic where a session might pull *zero* target groups (18% probability) or randomly click on a non-target chat to create noise (33% probability).
  - Inside a chat, human behavior skips over consecutive messages from the same sender or occasionally doesn't scroll all the way to the newest message.
- **Tools**: Used `numpy.random` components (`np.random.lognormal`, `np.random.weibull`, `np.random.gamma`) to enforce distributions within specified min/max bounds.
- **Null Sessions**: Artificially injected 2-5 "Null Sessions" per day where the system hits the API (enters WhatsApp) but doesn't read any groups, exiting after 15-35 seconds.
- **Coverage vs. Entropy Trade-off**: When replacing batch processing with probabilistic group sampling (e.g. 1-3 groups per session), it is critical NOT to use random subset selection (`np.random.choice`), which would cause some groups to be excluded for hours due to the Coupon Collector's problem. Instead, maintain a shuffled **Rotation Queue** (pop `N` groups per session and reload/reshuffle when empty). This guarantees 100% group coverage over time while perfectly mimicking randomized, low-count human behavior during any given session.

### 22. WhatsApp API changes (@lid) and UI Display Overwrites
- **Context:** Group names were displaying as IDs (`12036...` ) and sender names as 15-digit sequences (`18564157...`) in the desktop UI.
- **Problem:**
  1. `masaustu_uygulama.py` was unconditionally trying to fetch the group name from an offline cache `chat_groups_map` using the ID. Even if the message parser correctly fetched and embedded the real `chat_name`, the UI discarded it if it wasn't in the offline map.
  2. WHAPI now uses `@lid` (Linked Device) for hidden participant numbers (e.g. in Communities), which look like 15-digit numbers (`185641572794458@lid`). Since no name is provided, splitting by `@` exposed this raw string to the user.
- **Solution:** 
  1. Updated UI parsing to prioritize `mi.get('chat_name')` before falling back to local maps or just IDs.
  2. Added logic to detect `@lid` suffixes or 14+ digit sender "names". If detected, standardizes the display to `Gizli Numara` (Hidden Number), improving UX immensely.
