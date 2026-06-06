"""AutoMark AI — CLI entry point for campaign generation."""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


def main() -> None:
    """Parse CLI arguments, run the pipeline, and save the campaign bundle."""
    parser = argparse.ArgumentParser(
        description="AutoMark AI — Generate a Meta ad campaign bundle from a product image."
    )
    parser.add_argument("--image", required=True, help="Path to product image")
    parser.add_argument(
        "--budget", required=True, type=float, help="Total campaign budget in USD"
    )
    parser.add_argument("--goal", required=True, help="Campaign goal description")
    args = parser.parse_args()

    if not Path(args.image).exists():
        print(f"ERROR: Image not found: {args.image}", file=sys.stderr)
        sys.exit(1)

    from graph import get_graph  # deferred so dotenv loads before graph imports llm_client

    graph = get_graph()

    initial_state = {
        "image_path": args.image,
        "budget": args.budget,
        "goal": args.goal,
        "errors": [],
        "llm_used": {},
    }

    print("Running AutoMark AI pipeline…")
    result = graph.invoke(initial_state)

    # Orchestrator failure means nothing else ran — exit with error
    if not result.get("campaign_bundle") and result.get("errors"):
        print(f"FATAL: Pipeline failed — {result['errors']}", file=sys.stderr)
        sys.exit(1)

    bundle = result["campaign_bundle"]

    # --- Print summary ---
    print("\n" + "=" * 60)
    print("CAMPAIGN BUNDLE SUMMARY")
    print("=" * 60)

    product = bundle.get("product", {})
    print(f"Product : {product.get('type', 'N/A')}")
    print(f"Platform: {bundle.get('campaign', {}).get('platform', 'N/A')}")
    print(f"Objective: {bundle.get('campaign', {}).get('objective', 'N/A')}")

    creative = bundle.get("creative", {})
    print("\n--- Ad Copies ---")
    for i, copy in enumerate(creative.get("copies", []), 1):
        print(f"  {i}. {copy}")

    print("\n--- Headlines ---")
    for i, headline in enumerate(creative.get("headlines", []), 1):
        print(f"  {i}. {headline}")

    print(f"\nCTA: {creative.get('cta', 'N/A')}")

    media = bundle.get("media", {})
    print(f"\n--- Budget Split ---")
    for platform, share in media.get("budget_split", {}).items():
        print(f"  {platform}: {share:.0%}")
    print(f"Daily budget: ${media.get('daily_budget_usd', 0):.2f}")

    audience = media.get("audience", {})
    print(f"\n--- Audience ---")
    print(f"  Age: {audience.get('age_min', 'N/A')}–{audience.get('age_max', 'N/A')}")
    print(f"  Interests: {', '.join(audience.get('interests', []))}")

    if result.get("errors"):
        print(f"\nWarnings: {result['errors']}")

    # --- Save output ---
    output_dir = Path("./output")
    output_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = output_dir / f"campaign_bundle_{timestamp}.json"

    with open(output_path, "w") as f:
        json.dump(bundle, f, indent=2)

    print(f"\nCampaign bundle saved to: {output_path}")


if __name__ == "__main__":
    main()
