from __future__ import annotations

import argparse
from pathlib import Path

from neoforge_agent.semantic_coverage import write_stability_semantic_report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Refresh semantic coverage from an existing real-LLM stability report without provider calls."
    )
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--cases", default=Path("examples/real_llm_stability_cases.json"), type=Path)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()

    json_path, markdown_path = write_stability_semantic_report(
        args.report,
        args.cases,
        output_dir=args.output_dir,
    )
    print(f"Semantic coverage JSON: {json_path}")
    print(f"Semantic coverage Markdown: {markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
