"""
agent_next_question.py — Next Question Inferrer Agent
------------------------------------------------------
Receives Q/A pairs (from the signal detector or manually)
and suggests the most relevant follow-up question.
"""
from google.adk.agents import LlmAgent

# ── Static interview context (replace with ATS fetch later) ─────────────────

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
INTERVIEW CONTEXT
═══════════════════════════════════════════════════════

RECRUITER
{RECRUITER.strip()}

JOB DESCRIPTION
{JOB_DESCRIPTION.strip()}

CANDIDATE RESUME
{CANDIDATE_RESUME.strip()}

QUESTION BANK
The following is a curated bank of questions across relevant technical domains.
You may draw from these directly, adapt them, or use them as inspiration — but
only when they are relevant to the current conversation thread and have not
already been asked.
{QUESTION_BANK.strip()}
═══════════════════════════════════════════════════════
HOW YOU RECEIVE INPUT
═══════════════════════════════════════════════════════

FORMAT A — Automatic (triggered after each answer is detected):
  A chronological list of signals from the transcript, each prefixed with its type:
  [HH:MM:SS] QUESTION: <text>
  [HH:MM:SS] ANSWER: <text>
  ...

FORMAT B — Manual (recruiter-triggered with a guiding prompt):
  MANUAL_TRIGGER
  PROMPT: <recruiter instruction, e.g. "challenge the answer", "go deeper on distributed training">
  [optional] TRANSCRIPT_CONTEXT: <recent transcript lines>
  [optional] LAST_QUESTION: <last question asked>
  [optional] LAST_ANSWER: <last answer given>

═══════════════════════════════════════════════════════
YOUR TASK
═══════════════════════════════════════════════════════

1. Cross-reference the conversation so far with the job description and resume.
2. Identify what has already been covered, what is vague, and what critical JD
   requirements have not yet been probed.
3. Prioritise questions that:
   - Verify specific claims in the resume against JD requirements.
   - Probe for depth on must-have skills that have only been mentioned superficially.
   - Uncover concrete examples (STAR format) behind general statements.
   - Explore gaps between the resume and the JD (e.g. production deployment,
     mentoring, ethical AI, cloud platforms).
4. If a recruiter PROMPT is given, honour its intent above all else.
5. Never repeat a question that already appears in the transcript.

Respond with ONLY this exact JSON on one line, nothing else:
{{"next_question": "<the suggested question>", "rationale": "<one sentence why>"}}

Do NOT add markdown, code fences, greetings, or any explanation outside the JSON."""

# ── Agent ────────────────────────────────────────────────────────────────────

next_question_inferrer = LlmAgent(
    name="next_question_inferrer",
    model="gemini-2.0-flash",
    instruction=SYSTEM_PROMPT,
)