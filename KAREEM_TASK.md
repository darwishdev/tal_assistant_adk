### 1. Context
We are extending the Interview Assistant with **signal-based question mapping** and **dynamic next question extension**. You will implement new agents and modify existing ones, ensuring Redis channels, caching, and request/response contracts are respected.

### 2. Prerequisites – Pull the ADK Project
Before starting, pull the ADK project and switch to the `ats-polish` branch to see the **interview find endpoint** (via API Dog).

```bash
git pull origin ats-polish
git checkout ats-polish
```

Review the endpoint to understand how question banks are retrieved and passed as initial prompts.

---

### 3. Task 1 – Create `signaling_agent_mapper`

**Purpose:**  
Maps incoming signals (from `signaling_agent`) to a specific question ID from the personalized question bank.

**Initial Prompt:**  
Receives the **personalized question bank** (JSON array of question objects, each with `id` and `question_text`).

**Input (from Redis channel):**  
Listens for signals on a designated Redis channel. Signal format is a string stream from the signaling agent starting with `Q:` or `A:`.

**Output (response model):**  
Returns either a successful mapping with question ID or a not found error.

**Caching / Redis:**  
- Cache the question bank in Redis with an appropriate TTL, keyed by session ID.  
- Use session ID to retrieve the correct bank.

**Behavior:**  
- Only responds to signals starting with `Q:` (ignore `A:` for mapping).  
- Define and document your matching strategy.  
- Log unmapped signals for debugging.

---

### 4. Task 2 – Edit `signaling_agent`

**Changes required:**  
1. Accept **personalized question bank** as initial prompt (same format as above).  
2. Ensure it returns a **string stream** where each line starts with `Q:` or `A:`.

**Redis channel to publish:** Define and document the channel name.

**No caching needed** – just stream formatting.

---

### 5. Task 3 – Bridge `signaling_agent` → `signaling_agent_mapper`

- Ensure `signaling_agent` publishes to the appropriate Redis channel.  
- `signaling_agent_mapper` subscribes to that same channel.  
- After mapping, `signaling_agent_mapper` publishes to another designated channel.  

**Message broker:** Redis Pub/Sub.

**Provide the channel names you choose.**

---

### 6. Task 4 – Create `next_question_extender`

**Purpose:**  
Runs **only** when `next_question_agent` returns a **change question strategy** (`C:`).  
Takes the raw question string and extends it to match the **question entity JSON model**.

**Input (Redis channel):** Define the channel name and input JSON structure (must include session ID, question string, and strategy type).

**Output (Redis channel):** Define the channel name and output JSON model for the full question entity (must include id, question_text, type, difficulty, expected_keywords, source).

**Caching:**  
- Cache generated question entities with an appropriate TTL.  
- If same question string appears again, return cached version.

**Behavior:**  
- Only triggered on `C:` (change question) or `F:` (follow-up) from `next_question_agent`.  
- If `None` received, do nothing.

---

### 7. Task 5 – Edit `next_question_agent`

**Changes required:**  
1. Accept **personalized question bank** as initial prompt.  
2. Return a **string** starting with:  
   - `C:` → change question (triggers extender)  
   - `F:` → follow-up question (triggers extender)  
   - `None` → move to next question in list without any command.

**Redis channel to publish:** Define and document the channel name.

**No caching needed** – stateless decision.

---

### 8. Task 6 – Document Redis Channels & Caching

**Provide a summary table including:**

| Agent | Subscribes to (channel) | Publishes to (channel) | Cache key pattern | TTL |
|-------|------------------------|------------------------|-------------------|-----|
| signaling_agent | | | | |
| signaling_agent_mapper | | | | |
| next_question_agent | | | | |
| next_question_extender | | | | |

---

### 9. Task 7 – Provide Request/Response Models

**For each of the following, provide the exact JSON structure you will use:**

- Personalized question bank (initial prompt for signaling_agent and next_question_agent)
- Signal mapper output (success and error cases)
- Next question extender input
- Next question extender output (full question entity)

---

### 10. Final Checklist for Kareem

- [ ] Pull `ats-polish` branch and review interview find endpoint (API Dog).  
- [ ] Implement `signaling_agent_mapper` with Redis caching of question bank.  
- [ ] Modify `signaling_agent` to output `Q:` / `A:` streams.  
- [ ] Bridge both agents via Redis Pub/Sub with documented channels.  
- [ ] Implement `next_question_extender` with JSON entity generation.  
- [ ] Modify `next_question_agent` to return `C:` / `F:` / `None`.  
- [ ] Ensure `next_question_extender` only runs on `C:` or `F:`.  
- [ ] Document all Redis channels, cache keys, and request/response models.  
- [ ] Provide all examples as requested in Tasks 6, 7, and 8.  
- [ ] Test with sample question banks and signals.



