import os
import json
import math
from openai import OpenAI
from datetime import datetime
from dotenv import load_dotenv

# Helper function to calculate word count score
def word_count_factor(word_count: int, target: int = 150) -> float:
    """
    Returns a multiplier between 0 and 1.
    At target words: score = 1.0 (no penalty).
    Deviation gets penalized exponentially (Gaussian curve).

    Examples with k=3:
      150 words → 1.00  (perfect)
      120 words → 0.96  (minimal penalty)
      180 words → 0.96  (minimal penalty)
      225 words → 0.78  (noticeable penalty, 50% over)
       75 words → 0.78  (noticeable penalty, 50% under)
      300 words → 0.37  (heavy penalty, 100% over)
    """
    k = 3                                          # controls penalty steepness, not too strict for now
    relative_deviation = (word_count - target) / target   # e.g. 0.2 = 20% off
    factor = math.exp(-k * relative_deviation ** 2)       # Gaussian: symmetric, smooth
    return round(factor, 4)

# Load .env
load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# The task we're optimizing
TASK = "Write a professional customer service response to a complaint."
TEST_INPUT = "My package hasn't arrived in 2 weeks and nobody is responding to my emails. This is unacceptable!"

# Evaluation criteria (for manual scoring in Bronze)
CRITERIA = """
Rate each category from 1-10:
- Empathy: Shows understanding of the customer's frustration
- Professionalism: Not too casual, not too stiff
- Concreteness: Mentions specific next steps
(Word count is tracked separately — target is under 150 words)
"""

# Different prompt variants to test
PROMPT_VARIANTS = [
    # Variant 1: Minimal
    {
        "name": "minimal",
        "system": "You are a customer service representative.",
        "template": "{task}\n\nCustomer inquiry: {input}"
    },

    # Variant 2: Detailed
    {
        "name": "detailed",
        "system": "You are an experienced customer service representative at an e-commerce company. You always respond professionally, empathetically, and solution-oriented.",
        "template": "Task: {task}\n\nCustomer inquiry:\n{input}\n\nWrite a response that acknowledges the problem and outlines concrete next steps."
    },

    # Variant 3: Persona
    {
        "name": "persona",
        "system": "You are Sarah, Senior Customer Success Manager with 10 years of experience. You are known for calming down even the most frustrated customers.",
        "template": "{task}\n\nThe customer writes:\n\"{input}\"\n\nRespond as Sarah."
    },

    # Variant 4: Structured
    {
        "name": "structured",
        "system": "You are a customer service representative. Always structure your responses like this: 1) Show empathy, 2) Acknowledge the problem, 3) Solution/next steps, 4) Closing.",
        "template": "{task}\n\nInput: {input}"
    },

    # Variant 5: Chain of Thought
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

def run_prompt(variant: dict, task: str, input_text: str) -> str:
    """
    Runs a prompt and return the response
    """

    user_message = variant["template"].format(task=task, input=input_text)

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=500,
        messages=[
            {"role": "system", "content": variant["system"]},
            {"role": "user", "content": user_message}
        ]
    )

    return response.choices[0].message.content

# Create a custom function to get user scores
def get_manual_scores() -> dict:
    """
    Asks the user to score each category individually. Returns dict with scores and average.
    """

    categories = ["Empathy", "Professionalism", "Concreteness"]
    scores = {}

    for category in categories:
        while True: # loop until broken with break -> so loops until valid input is given
            raw = input(f"  {category} (1-10): ").strip()
            try:
                value = int(raw)
                if 1 <= value <= 10: # Ensure valid range
                    scores[category.lower()] = value
                    break
                else:
                    print("  Please enter a number between 1 and 10.")
            except ValueError:
                print("  Please enter a number between 1 and 10.")

    return scores


def main():
    """
    Tests all prompt variants and collects results.
    Flow: run each variant → collect manual scores → calculate final score → find winner
    """

    results = []

    print("=" * 70)
    print("PROMPT OPTIMIZER — BRONZE")
    print("=" * 70)
    print(f"\nTASK: {TASK}")
    print(f"Test Input: {TEST_INPUT[:50]}...")
    print("\n" + "=" * 70)

    for idx, variant in enumerate(PROMPT_VARIANTS, 1):

        print(f"\n[{idx}/{len(PROMPT_VARIANTS)}] Testing: {variant['name']}")
        print("-" * 50)

        # Run the prompt
        output = run_prompt(variant, TASK, TEST_INPUT)
        word_count = len(output.split())

        # Display output and metadata
        print(f"\nRole: {variant['system'][:60]}...")
        print(f"\nOutput:\n{output}")
        print(f"\nWords count: {word_count} (Target: <=150)")

        # Manual scoring for Bronze
        print(f"\n{CRITERIA}")
        scores = get_manual_scores()

        # Calculate total score
        # final_score = content quality * length compliance
        # word_count_weight is 1.0 at 150 words, drops toward 0 for large deviations
        content_score = (scores["empathy"] + scores["professionalism"] + scores["concreteness"]) / 3
        word_count_weight = word_count_factor(word_count)
        final_score = round(content_score * word_count_weight, 2)

        results.append({
            "variant": variant["name"],
            "system_prompt": variant["system"],
            "template": variant["template"],
            "output": output,
            "word_count": word_count,
            "word_count_weight": round(word_count_weight, 2),
            "empathy_score": scores["empathy"],
            "professionalism_score": scores["professionalism"],
            "concreteness_score": scores["concreteness"],
            "total_score": final_score, # content avg * word_count_weight
            "timestamp": datetime.now().isoformat()
        })

        print(f"✓ Saved: {variant['name']} = {final_score}/10 "
              f"(E:{scores['empathy']} P:{scores['professionalism']} C:{scores['concreteness']})")

    # Sort by average score, highest first
    results.sort(key=lambda x: x["total_score"], reverse=True)
    winner = results[0] # assign winner to highest score

    print("\n" + "=" * 70)
    print("RESULTS")
    print("=" * 70)

    # Print results as visual bar chart
    for r in results:
        bar_len = int(round(r["total_score"]))  # round for visual bar
        total_score = int(round(r["total_score"]))
        bar = "█" * bar_len + "░" * (10 - total_score)
        print(f"  {r['variant']:15} [{bar}] {total_score}/10  "
              f"(E:{r['empathy_score']} P:{r['professionalism_score']} C:{r['concreteness_score']}) "
              f"Words:{r['word_count']}, Word Count Weight:{r['word_count_weight']}")

    print(f"\n🏆 WINNER: {winner['variant']} with {winner['total_score']}/10")

    # Save results
    with open("results.json", "w") as f:
        json.dump({
            "task": TASK,
            "test_input": TEST_INPUT,
            "experiments": results,
            "winner": winner["variant"],
            "timestamp": datetime.now().isoformat()
        }, f, indent=2, ensure_ascii=False)

    print(f"\n✓ Results saved to results.json")

    return results


if __name__ == "__main__":
    main()