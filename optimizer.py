# optimizer.py
import re
import os
import json
from datetime import datetime

from config import client, MODEL, MAX_TOKENS_BRONZE, MAX_TOKENS_SILVER, MAX_TOKENS_GOLD, TASK, TEST_INPUT, CRITERIA, PROMPT_VARIANTS
from scoring import calculate_final_score


def run_prompt(variant: dict, task: str, input_text: str) -> str:
    """
    Runs a prompt and returns the response.
    Uses .replace() instead of .format() — safe for LLM-generated templates
    Used to generate the test outputs
    """

    user_message = variant["template"].replace("{task}", task).replace("{input}", input_text)

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

# =============================================================================
# GOLD LEVEL CODE
# =============================================================================

def generate_new_variants(previous_results: list, num_variants: int = 3) -> list:
    """
    Analyzes previous results and generates new prompt variants.
    This is the "mutation" step — like modifying train.py in AutoResearch.
    """

    # Format results so the LLM can see what worked and what didn't
    results_summary = ""
    for r in previous_results:
        results_summary += f"""
        Variant: {r['variant']}
        System Prompt: {r.get('system_prompt', 'N/A')[:100]}...
        Total Score: {r['total_score']}/10 (E:{r['empathy']} P:{r['professionalism']} C:{r['concreteness']})
        Word Count: {r['word_count']} (Weight: {r['word_count_weight']})
        Reasoning: {r.get('reasoning', 'N/A')}
        ---
        """

    generation_prompt = f"""You are a prompt engineering expert. Analyze these experiment results and generate {num_variants} NEW, improved prompt variants.
    
    PREVIOUS RESULTS:
    {results_summary}
    
    TASK BEING OPTIMIZED:
    {TASK}
    
    SCORING: Each output is scored on empathy (1-10), professionalism (1-10), concreteness (1-10). The average is multiplied by a word count penalty (target: 150 words, Gaussian curve). Optimize for all three categories while keeping word count near 150.
    
    Based on the results:
    1. What patterns work well?
    2. What performs poorly?
    3. What new approaches could score higher?
    
    Generate {num_variants} new variants in this exact JSON format, nothing else:
    [
        {{
            "name": "variant_name",
            "hypothesis": "Why this variant might score higher",
            "system": "The system prompt",
            "template": "The template with {{task}} and {{input}} placeholders"
        }}
    ]
    """

    response = client.chat.completions.create(
        model=MODEL,
        max_tokens=MAX_TOKENS_GOLD,
        messages=[
            {"role": "user", "content": generation_prompt}
        ]
    )

    text = response.choices[0].message.content

    # Extract JSON array from response
    json_match = re.search(r'\[.*\]', text, re.DOTALL)
    if json_match:
        try:
            variants = json.loads(json_match.group())
            # Validate: each variant must have name, system, template
            valid = [v for v in variants
                     if all(k in v for k in ["name", "system", "template"])]
            if valid:
                return valid
        except json.JSONDecodeError:
            pass

    print("  ⚠ Warning: Could not parse new variants from LLM response")
    return []


def iterative_optimization(initial_variants: list, num_iterations: int = 3, variants_file: str = "prompts/variants.json") -> dict:
    """
    Runs multiple iteration rounds.
    Each round: load variants → test → analyze → generate new → save to file → repeat
    Like AutoResearch: the agent only modifies the variants file, nothing else.
    """

    all_history = []
    best_ever = {"total_score": 0, "variant": None}

    # Write initial variants to the editable file (clean state)
    os.makedirs(os.path.dirname(variants_file), exist_ok=True)
    with open(variants_file, "w") as f:
        json.dump(initial_variants, f, indent=2)
    print(f"✓ Initial variants written to {variants_file}")

    for iteration in range(num_iterations):
        print(f"\n{'#' * 70}")
        print(f"ITERATION {iteration + 1}/{num_iterations}")
        print(f"{'#' * 70}")

        # Load current variants from file (the "editable" file)
        with open(variants_file, "r") as f:
            current_variants = json.load(f)
        print(f"Loaded {len(current_variants)} variants from {variants_file}")

        # Test all variants using existing Silver pipeline
        results = run_automated_experiment(
            current_variants, TASK, TEST_INPUT, num_runs=1
        )

        all_history.extend(results)

        # Find best in this iteration
        best_this_round = max(results, key=lambda x: x["total_score"])
        print(f"\nBest this round: {best_this_round['variant']} = "
              f"{best_this_round['total_score']}/10")

        # Update best ever
        if best_this_round["total_score"] > best_ever["total_score"]:
            best_ever = {
                "total_score": best_this_round["total_score"],
                "variant": best_this_round["variant"],
                "iteration": iteration + 1,
                "output": best_this_round["output"],
                "system_prompt": best_this_round.get("system_prompt", ""),
                "empathy": best_this_round["empathy"],
                "professionalism": best_this_round["professionalism"],
                "concreteness": best_this_round["concreteness"],
            }
            print(f"🆕 New best ever!")

        # Generate new variants for next iteration (except last)
        if iteration < num_iterations - 1:
            print(f"\nGenerating new variants based on learnings...")
            new_variants = generate_new_variants(results, num_variants=3)

            if new_variants:
                # Write new variants to file — this is the ONLY file the LLM changes
                with open(variants_file, "w") as f:
                    json.dump(new_variants, f, indent=2)
                print(f"✓ {len(new_variants)} new variants written to {variants_file}")
                for v in new_variants:
                    print(f"  - {v['name']}: {v.get('hypothesis', '')[:60]}...")
            else:
                print("No new variants generated, keeping current file")

    return {
        "best_ever": best_ever,
        "total_experiments": len(all_history),
        "iterations": num_iterations,
        "history": all_history
    }

def main_gold():
    """Iterative optimization loop — the Gold challenge."""
    # Timestamped output so multiple runs don't overwrite each other
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    save_path = f"results/{timestamp}_gold.json"
    variants_file = f"prompts/{timestamp}_variants.json"

    print("=" * 70)
    print("PROMPT OPTIMIZER — GOLD (Iterative)")
    print("=" * 70)

    result = iterative_optimization(
        PROMPT_VARIANTS,  # start fresh from config.py defaults
        num_iterations=3,
        variants_file=variants_file
    )

    # Display final results
    print(f"\n{'=' * 70}")
    print("FINAL RESULTS")
    print(f"{'=' * 70}")
    print(f"Total Experiments: {result['total_experiments']}")
    print(f"Iterations: {result['iterations']}")
    print(f"\n🏆 BEST PROMPT EVER:")
    print(f"   Variant: {result['best_ever']['variant']}")
    print(f"   Score: {result['best_ever']['total_score']}/10")
    print(f"   Found in iteration: {result['best_ever']['iteration']}")
    print(f"   (E:{result['best_ever']['empathy']} "
          f"P:{result['best_ever']['professionalism']} "
          f"C:{result['best_ever']['concreteness']})")
    print(f"\n   System Prompt:")
    print(f"   {result['best_ever'].get('system_prompt', 'N/A')}")

    # Save everything
    os.makedirs("results", exist_ok=True)
    with open(save_path, "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"\n✓ Results saved to {save_path}")
    print(f"✓ Final variants in {variants_file}")

    return result



# =============================================================================
# RUN CODE
# =============================================================================

if __name__ == "__main__":
    # mode="manuel" = BRONZE, mode="llm" = SILVER
    #main(mode="llm")
    main_gold()