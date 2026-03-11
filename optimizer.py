# optimizer.py
import re
import json
from datetime import datetime

from config import client, MODEL, MAX_TOKENS_BRONZE, MAX_TOKENS_SILVER, TASK, TEST_INPUT, CRITERIA, PROMPT_VARIANTS
from scoring import calculate_final_score


def run_prompt(variant: dict, task: str, input_text: str) -> str:
    """
    Runs a prompt and returns the response.
    Used to generate the test outputs
    """

    user_message = variant["template"].format(task=task, input=input_text)

    response = client.chat.completions.create(
        model=MODEL,
        max_tokens=MAX_TOKENS_BRONZE,
        messages=[
            {"role": "system", "content": variant["system"]},
            {"role": "user", "content": user_message}
        ]
    )

    return response.choices[0].message.content


def get_manual_scores() -> dict:
    """Asks the user to score each category individually."""

    categories = ["Empathy", "Professionalism", "Concreteness"]
    scores = {}

    for category in categories:
        while True:
            raw = input(f"  {category} (1-10): ").strip()
            try:
                value = int(raw)
                if 1 <= value <= 10:
                    scores[category.lower()] = value
                    break
                else:
                    print("  Please enter a number between 1 and 10.")
            except ValueError:
                print("  Please enter a number between 1 and 10.")

    return scores

def evaluate_output_with_llm(output: str) -> dict:
    """
    Uses the LLM to score a customer service response.
    Returns the same 3 keys as get_manual_scores(): empathy, professionalism, concreteness.
    Word count is NOT evaluated here — it's measured programmatically in the main loop.
    """

    eval_prompt = f"""Rate this customer service response on three categories, each from 1 to 10.

    ANSWER TO BE RATED:
    \"\"\"
    {output}
    \"\"\"
    
    CATEGORIES:
    - empathy: Shows understanding of the customer's frustration
    - professionalism: Appropriate tone — not too casual, not too stiff
    - concreteness: Mentions specific next steps to resolve the issue
    
    Respond in this exact JSON format, nothing else:
    {{
        "empathy": <integer 1-10>,
        "professionalism": <integer 1-10>,
        "concreteness": <integer 1-10>,
        "reasoning": "<1-2 sentences explaining the scores>"
    }}
    
    """

    response = client.chat.completions.create(
        model=MODEL,
        max_tokens=MAX_TOKENS_SILVER, # should be adjusted for short response, just JSON
        messages=[
            {"role": "user", "content": eval_prompt}
        ]
    )

    text = response.choices[0].message.content  # extract response text

    # Go through JSON response and extract
    json_match = re.search(r'\{.*\}', text, re.DOTALL) # find JSON block in response

    if json_match:
        try:
            parsed = json.loads(json_match.group())
            return {
                "empathy": int(parsed.get("empathy", 5)),
                "professionalism": int(parsed.get("professionalism", 5)),
                "concreteness": int(parsed.get("concreteness", 5)),
                "reasoning": parsed.get("reasoning", "")
            }
        except (json.JSONDecodeError, ValueError):
            pass

    # Fallback: if parsing fails, return neutral scores
    print("  ⚠ Warning: Could not parse LLM evaluation, using defaults scores")
    return {"empathy": 5, "professionalism": 5, "concreteness": 5, "reasoning": "Parse error"}


def run_automated_experiment(variants: list, task: str, test_input: str, num_runs: int = 1) -> list:
    """
    Runs all variants and scores them via LLM.
    num_runs > 1 = multiple runs per variant for statistical significance.
    Uses the same scoring pipeline as Bronze (calculate_final_score).
    """

    all_results = []

    for run_num in range(num_runs):
        print(f"\n{'=' * 60}")
        print(f"RUN {run_num + 1}/{num_runs}")
        print(f"{'=' * 60}")

        for idx, variant in enumerate(variants, 1):
            print(f"\n  [{idx}/{len(variants)}] Testing: {variant['name']}...", end=" ")

            # 1. Generate output -> same as Bronze
            output = run_prompt(variant, task, test_input)
            word_count = len(output.split())

            # 2. Call LLM for scoring the 3 categories
            evaluation = evaluate_output_with_llm(output)

            # 3. Calculate final score (identical to Bronze pipeline)
            scores = calculate_final_score(
                evaluation["empathy"],
                evaluation["professionalism"],
                evaluation["concreteness"],
                word_count
            )

            result = {
                "run": run_num + 1,
                "variant": variant["name"],
                "system_prompt": variant["system"],
                "template": variant["template"],
                "output": output,
                **scores,  # same keys as Bronze results
                "reasoning": evaluation["reasoning"],  # LLM's explanation
                "timestamp": datetime.now().isoformat()
            }

            all_results.append(result)
            print(f"Score: {scores['total_score']}/10 "
                  f"(E:{scores['empathy']} P:{scores['professionalism']} "
                  f"C:{scores['concreteness']}) Words:{word_count}")

    return all_results



def main(mode="manual"):
    """
    Tests all prompt variants and collects results.
    mode="manual": human scores each output (Bronze)
    mode="llm": LLM scores each output (Silver)
    """

    # Choose label and save path based on mode
    tier = "BRONZE (Manual)" if mode == "manual" else "SILVER (Automated)"
    save_path = "results/results_bronze.json" if mode == "manual" else "results/results_silver.json"

    results = []

    print("=" * 70)
    print(f"PROMPT OPTIMIZER — {tier}")
    print("=" * 70)
    print(f"\nTASK: {TASK}")
    print(f"Test Input: {TEST_INPUT[:50]}...")
    print("\n" + "=" * 70)

    for idx, variant in enumerate(PROMPT_VARIANTS, 1):

        print(f"\n[{idx}/{len(PROMPT_VARIANTS)}] Testing: {variant['name']}")
        print("-" * 50)

        output = run_prompt(variant, TASK, TEST_INPUT)
        word_count = len(output.split())

        # Display output and metadata
        print(f"\nRole: {variant['system'][:60]}...")
        print(f"\nOutput:\n{output}")
        print(f"\nWord count: {word_count} (Target: <=150)")

        # === Switches modes based on mode parameter ===

        if mode == "manual":
            print(f"\n{CRITERIA}")
            scores_raw = get_manual_scores()
            reasoning = "Manual scoring" # Reasoning was added with LLM (LLM reason for score)
        else:
            scores_raw = evaluate_output_with_llm(output)
            reasoning = scores_raw["reasoning"]
            print(f"\n  LLM reasoning: {reasoning}")

        # Calculate_final_score returns a dict with all scoring components
        scores = calculate_final_score(
            scores_raw["empathy"], scores_raw["professionalism"],
            scores_raw["concreteness"], word_count
        )

        results.append({
            "variant": variant["name"],
            "system_prompt": variant["system"],
            "template": variant["template"],
            "output": output,
            **scores,  # unpacks: empathy, professionalism, concreteness, content_score, word_count, word_count_weight, total_score
            "reasoning": reasoning,
            "scoring_mode": mode,
            "timestamp": datetime.now().isoformat()
        })

        print(f"✓ Saved: {variant['name']} = {scores['total_score']}/10 "
              f"(E:{scores['empathy']} P:{scores['professionalism']} C:{scores['concreteness']})")

    # Sort by total score, highest first
    results.sort(key=lambda x: x["total_score"], reverse=True)
    winner = results[0]

    print("\n" + "=" * 70)
    print("RESULTS")
    print("=" * 70)

    # Print results as visual bar chart
    for r in results:
        bar_len = int(round(r["total_score"]))
        total_score = int(round(r["total_score"]))
        bar = "█" * bar_len + "░" * (10 - total_score)
        print(f"  {r['variant']:15} [{bar}] {r['total_score']}/10  "
              f"(E:{r['empathy']} P:{r['professionalism']} C:{r['concreteness']}) "
              f"Words:{r['word_count']}, WC Weight:{r['word_count_weight']}")

    print(f"\n🏆 WINNER: {winner['variant']} with {winner['total_score']}/10")

    # Save results
    with open(save_path, "w") as f:
        json.dump({
            "task": TASK,
            "test_input": TEST_INPUT,
            "experiments": results,
            "winner": winner["variant"],
            "scoring_mode": mode,
            "timestamp": datetime.now().isoformat()
        }, f, indent=2, ensure_ascii=False)

    print(f"\n✓ Results saved to {save_path}")

    return results


if __name__ == "__main__":
    # mode="manuel" = BRONZE, mode="llm" = SILVER
    main(mode="llm")