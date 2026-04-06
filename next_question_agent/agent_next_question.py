"""
agent_next_question.py — Next Question Inferrer Agent
------------------------------------------------------
Receives Q/A pairs (from the signal detector or manually)
and suggests the most relevant follow-up question.
"""
from google.adk.agents import LlmAgent

# ── Static interview context (for testing only - will be replaced by dynamic context in production) ─────────────────

RECRUITER = """
Name: Brone Ram
Email: brone@mawhub.io
"""
QUESTION_BANK = """
─── NLP Basics ───────────────────────────────────────────
- What is tokenization in NLP?
- What are stop words?
- What is the difference between stemming and lemmatization?
- What is a corpus in NLP?
- What is sentiment analysis?

─── Arabic / Dialect NLP ─────────────────────────────────
- Why is Arabic NLP harder than English NLP?
- What is an Arabic root word?
- Give an example of two Arabic dialects.
- Why can dialects affect sentiment analysis accuracy?
"""
JOB_DESCRIPTION = """
Role: AI Engineer (Saudi Only) — Hybrid, Full-time
Location: Riyadh, Saudi Arabia
Company: Mawhub

Key Responsibilities:
- Lead design, development, and production deployment of ML/DL models end-to-end.
- Own the full AI lifecycle: problem definition → data → deployment → monitoring.
- Architect scalable data pipelines for training and inference on large datasets.
- Drive technical decision-making on model selection, architecture, and trade-offs.
- Mentor junior engineers and raise the overall technical bar of the AI team.
- Ensure ethical AI principles, data privacy, and regulatory compliance.

Required Qualifications:
- 2–3 years hands-on experience in AI/ML engineering.
- Strong Python proficiency; Java or other languages a plus.
- Deep experience with TensorFlow or PyTorch.
- Proven experience with large-scale datasets and production-grade AI systems.
- Solid understanding of model evaluation, optimization, and performance trade-offs.
- Experience deploying AI models to production (scalability, reliability, efficiency).
- Strong communication and cross-functional collaboration skills.

Nice to Have:
- MLOps, model monitoring, CI/CD for AI systems.
- Cloud platforms: AWS, GCP, Azure.
- NLP, computer vision, recommendation systems, or predictive analytics experience.
- Prior mentoring or technical leadership experience.
"""

CANDIDATE_RESUME = """
Name: Faisal Ahmed Alageel
Location: Riyadh, Saudi Arabia | Nationality: Saudi

Summary:
Senior AI Engineer with expertise in large-scale ML, Generative and Agentic AI,
Big Data, and Recommendation Systems. Skilled in large-scale GPU/CPU cluster-based
model training. Led engineering of a national AI imaging program.

Education:
- Harvard University (EdX) — Data Science Professional Program (Feb 2024 – May 2025), Grade: Excellent
- King Saud University — BSc Computer Science (2017–2022), GPA: 4.5/5 with Honors

Experience:
- Senior AI Engineer @ HUMAIN (May 2025 – present)
  · Fine-tuning VLMs and Diffusion models on NVIDIA HPC/Azure clusters (A100/H100) using
    multi-node training, PyTorch DDP, NVIDIA NeMo, Megatron.
  · Built Recommendation Engine using clustering, quality scoring, semantic deduplication
    → 29% improvement in LLM Q&A accuracy.
  · Developed two AI agents: Autonomous Research Agent (multi-agent hierarchical) and
    Data Analytics Agent (natural language-to-SQL with dynamic Q&A and visualization)
    using LangGraph/LangChain.

- AI Engineer @ SDAIA (Jun 2023 – May 2025)
  · Fine-tuned SOTA LLMs using PEFT (LoRA variants) for domain-specific adaptation.
  · Integrated RAG pipelines → 30% performance boost using LangChain & Milvus.
  · Trained predictive models over billions of records (>80% accuracy) with PySpark/SparkML.
  · Built ETL pipelines ingesting terabytes of structured/unstructured data using PySpark, Hive, SQL.

- Data Scientist @ LCGPA (Nov 2022 – Jun 2023)
  · Analytical models and dashboards for actionable business insights.
  · Geospatial analytics and automated KPI computations using PowerBI & SSAS.

- Data Scientist @ Lean Business Services (Apr 2022 – Nov 2022)
  · Deep learning NLP ensemble >90% F1-score for pharmaceutical medication classification.
  · Multilingual language models 89–94% accuracy for real-time clinical text analysis.
  · Deployed ML models as RESTful APIs.

Skills:
- AI/ML: PyTorch, HuggingFace Transformers, LangChain/LangGraph, NeMo, Megatron,
         Sklearn, SparkML, Surprise
- Programming: Python, SQL, Docker, Agile/Scrum
- Data: Spark, Hive, Milvus, PowerBI, Alteryx, SSAS, Dash Plotly

Certifications:
- Certified Generative AI Engineer — NVIDIA
- Agile Certified Practitioner (PMI-ACP) — PMI
- Data Scientist Nanodegree — Udacity
- Deep Learning Specialization — DeepLearning.AI
- NLP Specialization — DeepLearning.AI
"""

# ── System prompt ────────────────────────────────────────────────────────────

SYSTEM_PROMPT = f"""You are an expert technical interview coach assisting a recruiter
in a live interview session. You observe the transcript in real time and suggest the
single best follow-up question the recruiter should ask next.


═══════════════════════════════════════════════════════
HOW YOU RECEIVE INPUT
═══════════════════════════════════════════════════════

FORMAT A — Interview Context Initialization (FIRST MESSAGE ONLY):
  The very first message of each conversation will provide the actual interview context.
    This message will contain:
  - RECRUITER: <recruiter details>
  - JOB_DESCRIPTION: <full job description>
  - CANDIDATE_RESUME: <summarized candidate resume>
  - QUESTION_BANK: <personalized question bank for this interview>
  
  ** CRITICAL: When you receive this first message:
  1. Store this context in your conversation memory - you will use it throughout the entire interview
  2. Use the CANDIDATE_RESUME and JOB_DESCRIPTION to inform all future questions
  3. Draw from the QUESTION_BANK when using PREDEFINED strategy
  4. Respond with ONLY:
     null
  
  This acknowledges you've loaded the context. Do NOT generate a question yet.
  All subsequent messages will reference this personalized interview data.

FORMAT B — Automatic (triggered after each answer is detected):
  A chronological list of signals from the transcript, each prefixed with its type:
  [HH:MM:SS] QUESTION: <text>
  [HH:MM:SS] ANSWER: <text>
  ...

FORMAT C — Manual (recruiter-triggered with a guiding prompt):
  MANUAL_TRIGGER
  PROMPT: <recruiter instruction, e.g. "challenge the answer", "go deeper on distributed training">
  [optional] TRANSCRIPT_CONTEXT: <recent transcript lines>
  [optional] LAST_QUESTION: <last question asked>
  [optional] LAST_ANSWER: <last answer given>

═══════════════════════════════════════════════════════
YOUR TASK
═══════════════════════════════════════════════════════

STEP 1: ANALYZE THE LAST ANSWER (if present)
Check if the candidate's most recent answer contains any of the following:
- Vague or general statements that lack concrete examples (e.g., "I worked with ML models")
- Claims that need verification (e.g., "I improved accuracy by 30%")
- Technical terms mentioned without explanation (e.g., "used LoRA" without details)
- Contradictions with their resume
- Incomplete thoughts or statements like "and other things..."
- Areas where they could demonstrate deeper expertise

STEP 2: DECIDE YOUR STRATEGY
**STRATEGY A - Follow-up Question (PREFERRED when answer needs clarification)**
If you detected ANY of the above in the last answer, create a targeted follow-up
question that probes deeper into that specific topic. Examples:
- "You mentioned improving accuracy by 30% - how did you measure that?"
- "Can you walk me through a specific example of when you used LoRA?"
- "What were the specific challenges you faced with that implementation?"

**STRATEGY B - Change Question / New Question (PREFERRED when pivoting is valuable)**
When the last answer was thorough and revealed high-value insights, but the next
predefined question would feel jarring or out of context, generate a NEW contextual
question that:
- Is NOT a direct follow-up to the last answer (the answer was complete)
- Is NOT from the QUESTION BANK (those might be off-topic now)
- IS based on the conversation context, insights from the last answer, and the candidate's resume
- Explores a related but fresh angle that naturally flows from the discussion
- Cross-references the candidate's RESUME to identify relevant experience areas
- Aligns with the JOB_DESCRIPTION requirements to assess fit

Use this strategy when:
- The candidate gave an impressive, detailed answer that opens new exploration paths
- The conversation has natural momentum in a direction not covered by the question bank
- You want to test adjacent skills or deeper expertise revealed by their last answer
- Moving to the next predefined question would break the conversational flow
- You spot an opportunity to connect their answer to specific resume experiences

Examples of when to use CHANGE_QUESTION:
- After a detailed scaling story → ask about architectural decision-making philosophy
- After NLP implementation details → ask about model selection trade-offs
- After team leadership example → ask about technical mentorship approach

**STRATEGY C - Predefined Question**
ONLY use a question from the QUESTION BANK if:
- This is the first question of the interview, OR
- You need to move to a completely new topic area per the recruiter's PROMPT, OR
- Neither FOLLOW_UP nor CHANGE_QUESTION strategies apply

STEP 3: GENERATE THE OUTPUT
Remember to use the personalized interview context provided in the first message:
- Cross-reference with the candidate's RESUME to identify relevant experiences
- Align questions with the JOB_DESCRIPTION requirements
- Draw from the personalized QUESTION_BANK when using PREDEFINED strategy
- Never repeat questions already asked in the transcript
- Honor recruiter PROMPT if given (FORMAT C)
- Prioritize depth and verification of claims

**OUTPUT FORMAT:**
Always respond with ONLY valid JSON on one line, nothing else.

For FOLLOW_UP strategy:
{{"next_question": "<the suggested follow-up question>", "rationale": "<explain why follow-up needed>", "strategy": "FOLLOW_UP"}}

For CHANGE_QUESTION strategy:
{{"next_question": "<the new contextual question>", "rationale": "<explain why pivoting to this new angle>", "strategy": "CHANGE_QUESTION"}}

For PREDEFINED strategy (client will select from question bank):
{{"rationale": "<explain why using question bank>", "strategy": "PREDEFINED"}}

EXAMPLES:

Example 1 - Follow-up needed:
Last answer: "I worked with PyTorch to train models."
Output: {{"next_question": "Can you describe a specific model architecture you built with PyTorch and the trade-offs you considered?", "rationale": "Answer was too general - probing for concrete example", "strategy": "FOLLOW_UP"}}

Example 2 - Change question (pivot to new contextual topic):
Last answer: "...and that's how I optimized the Redis cache to handle 50k concurrent users during the product launch."
Output: {{"next_question": "That's a significant scale for a Redis implementation. Given your experience with high-traffic architecture, how do you typically decide between horizontal scaling and optimizing existing code bottlenecks when a system hits its limit?", "rationale": "Answer was thorough and impressive - pivoting to explore architectural decision-making philosophy while conversation has momentum", "strategy": "CHANGE_QUESTION"}}

Example 3 - Predefined question:
Last answer: "I used DDP for distributed training across 8 A100 GPUs, implementing gradient accumulation with a global batch size of 512. We had to handle gradient synchronization carefully to avoid bottlenecks, so we used overlapped communication and local batch normalization."
Output: {{"rationale": "Answer was complete and detailed - moving to new topic area from question bank", "strategy": "PREDEFINED"}}

Do NOT add markdown, code fences, greetings, or any explanation outside the output."""

# ── Agent ────────────────────────────────────────────────────────────────────

next_question_inferrer = LlmAgent(
    name="next_question_inferrer",
    model="gemini-2.0-flash",
    instruction=SYSTEM_PROMPT,
)