import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# API setup
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL = "gpt-4o-mini"
MAX_TOKENS_BRONZE = 500
MAX_TOKENS_SILVER = 200
MAX_TOKENS_GOLD = 2000

# The task we're optimizing
TASK = "Write a professional customer service response to a complaint."
TEST_INPUT = "My package hasn't arrived in 2 weeks and nobody is responding to my emails. This is unacceptable!"

# Evaluation criteria
CRITERIA = """
Rate each category from 1-10:
- Empathy: Shows understanding of the customer's frustration
- Professionalism: Not too casual, not too stiff
- Concreteness: Mentions specific next steps
(Word count is tracked separately — target is under 150 words)
"""

# Different prompt variants to test
PROMPT_VARIANTS = [
    {
        "name": "minimal",
        "system": "You are a customer service representative.",
        "template": "{task}\n\nCustomer inquiry: {input}"
    },
    {
        "name": "detailed",
        "system": "You are an experienced customer service representative at an e-commerce company. You always respond professionally, empathetically, and solution-oriented.",
        "template": "Task: {task}\n\nCustomer inquiry:\n{input}\n\nWrite a response that acknowledges the problem and outlines concrete next steps."
    },
    {
        "name": "persona",
        "system": "You are Sarah, Senior Customer Success Manager with 10 years of experience. You are known for calming down even the most frustrated customers.",
        "template": "{task}\n\nThe customer writes:\n\"{input}\"\n\nRespond as Sarah."
    },
    {
        "name": "structured",
        "system": "You are a customer service representative. Always structure your responses like this: 1) Show empathy, 2) Acknowledge the problem, 3) Solution/next steps, 4) Closing.",
        "template": "{task}\n\nInput: {input}"
    },
    {
        "name": "cot",
        "system": "You are a customer service representative.",
        "template": """{task}

Customer inquiry: {input}

Before you respond, consider:
1. What is the customer's core problem?
2. What emotion is the customer showing?
3. What would be the best next step?

Then write your response (without showing your reasoning)."""
    },
]