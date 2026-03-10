# 🔬 Prompt Optimizer Agent

> **Learning Project**: An autonomous prompt optimization agent that systematically tests, evaluates, and improves prompts — inspired by Karpathy's [AutoResearch](https://github.com/karpathy/autoresearch) project, where an AI agent experiments with LLM training code overnight without human intervention.

This project applies the same principle to **prompts instead of code**: generate variants, test them, evaluate the outputs, keep or discard, repeat.

---

## 🎯 What This Is

A systematic prompt optimization pipeline:

**Define task → Generate prompt variants → Test each variant → Score outputs → Find the winner → Iterate**

The core loop mirrors AutoResearch:

| AutoResearch | Prompt Optimizer |
|---|---|
| `train.py` — code that gets modified | The prompt that gets modified |
| `val_bpb` — the metric (lower = better) | `total_score` — output quality (higher = better) |
| `program.md` — instructions for the agent | `instructions.md` for the optimizer agent |
| 5 min training per experiment | 1 API call per experiment |
| git commit / git reset | Keep best prompt / discard |

Built as a self-directed project for the KI & Python module at Morphos GmbH.

---

## 🏆 Challenge Status

| Level | What | Status |
|---|---|---|
| 🥉 Bronze | Test 5 fixed prompt variants with manual scoring, find winner | ✅ Done |
| 🥈 Silver | Replace manual scoring with LLM-as-judge, automated evaluation loop | ✅ Done |
| 🥇 Gold | Agent generates NEW variants based on learnings, iterative optimization | 🔄 In Progress |
| 💎 Diamond | Meta-optimization — agent optimizes its own evaluator prompt | ⬜ Planned |

---

## 🗂️ Project Structure

```
auto-prompt-optimizer/
├── config.py              # Constants, API client, prompt variants
├── scoring.py             # word_count_factor (Gaussian), calculate_final_score
├── optimizer.py           # Main workflow — Bronze & Silver via mode parameter
├── prompts/
│   └── variants.json      # (Gold) Agent-editable prompt variants
├── instructions.md        # (Gold) Instructions for the optimizer agent
├── results/
│   ├── results_bronze.json
│   ├── results_silver.json
│   └── results_gold.json
└── .env                   # OPENAI_API_KEY
```

---

## ⚙️ Scoring System

The scoring pipeline is the same for Bronze (manual) and Silver (LLM-as-judge):

```
empathy:           1-10   (human or LLM)
professionalism:   1-10   (human or LLM)
concreteness:      1-10   (human or LLM)
content_score:     average of the three above
word_count:        measured programmatically
word_count_weight: 0–1 multiplier from Gaussian curve (k=3, target=150 words)
total_score:       content_score × word_count_weight  ← the one number to optimize
```

Word count is never evaluated by the LLM — it's measured and penalized deterministically via a Gaussian function. This keeps the metric reproducible regardless of scoring mode.

---

## 🚀 Getting Started

### Prerequisites

- Python 3.10+
- OpenAI API Key

### Installation

```bash
git clone https://github.com/yourusername/auto-prompt-optimizer.git
cd auto-prompt-optimizer

python -m venv .venv
source .venv/bin/activate       # macOS/Linux
.venv\Scripts\activate          # Windows

pip install -r requirements.txt
```

### Environment Setup

```bash
cp .env.example .env
```

`.env.example`:
```
OPENAI_API_KEY=sk-...
```

---

## ▶️ Usage

```bash
# Silver — automated LLM scoring (default)
python optimizer.py

# Bronze — manual human scoring
# Change mode in optimizer.py: main(mode="manual")
```

Results are saved to `results/results_bronze.json` or `results/results_silver.json`.

---

## 🔗 Reference

This project is inspired by Karpathy's [AutoResearch](https://github.com/karpathy/autoresearch) — an experiment where an AI agent autonomously modifies LLM training code, trains for 5 minutes, evaluates the result, and iterates. The same hypothesis → test → evaluate → keep/discard loop is applied here to prompt engineering.

---

## 🛠️ Tech Stack

| Technology | Purpose |
|---|---|
| **OpenAI API** | Output generation + LLM-as-judge evaluation |
| **gpt-4o-mini** | Model for both generation and scoring |
| **Python** | Core language |

---

## ✏️ Author

**Dennis Feyerabend**
KI & Python Modul — Morphos GmbH — March 2026

---

## 📝 License

Created as part of an AI & Python training program at Morphos GmbH. Learning project for educational purposes.
