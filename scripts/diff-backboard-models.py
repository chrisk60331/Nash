#!/usr/bin/env python3
"""
Fetches all providers and chat models from the Backboard API,
writes them to backboard-models.txt, then diffs against librechat.yaml.

Usage:
    python scripts/diff-backboard-models.py [--output PATH] [--yaml PATH]
"""
import argparse
import asyncio
import os
import re
import sys
from pathlib import Path

from backboard import BackboardClient


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = REPO_ROOT / "backboard-models.txt"
DEFAULT_YAML = REPO_ROOT / "librechat.yaml"


PAGE_SIZE = 500


async def fetch_provider_models(client: BackboardClient, provider_id: str) -> list[str]:
    """Paginate through all models for a single provider."""
    results: list[str] = []
    skip = 0
    while True:
        resp = await client.list_models(provider=provider_id, skip=skip, limit=PAGE_SIZE)
        for m in resp.models:
            results.append(f"{m.provider}/{m.name}")
        skip += len(resp.models)
        if skip >= resp.total:
            break
    return results


async def fetch_all_models(client: BackboardClient) -> list[str]:
    """Return sorted list of 'provider/model_name' for all LLM models."""
    resp = await client.list_providers()
    providers: list[str] = resp.providers

    results: list[str] = []
    for provider_id in providers:
        # peek at total first so we can log it
        peek = await client.list_models(provider=provider_id, skip=0, limit=1)
        total = peek.total
        print(f"  {provider_id}: {total} models", flush=True)
        models = await fetch_provider_models(client, provider_id)
        results.extend(models)

    return sorted(results)


def extract_yaml_models(yaml_path: Path) -> set[str]:
    """Extract all 'provider/model' entries from librechat.yaml default model lists."""
    # Matches lines like:  - 'provider/model-name'  or  - "provider/model-name"
    pattern = re.compile(r"""^\s+-\s+['"]([^/'"]+/[^'"]+)['"]\s*$""")
    models: set[str] = set()
    with open(yaml_path) as f:
        for line in f:
            m = pattern.match(line)
            if m:
                models.add(m.group(1))
    return models


def diff_models(backboard_models: list[str], yaml_models: set[str]) -> None:
    backboard_set = set(backboard_models)

    in_backboard_not_yaml = sorted(backboard_set - yaml_models)
    in_yaml_not_backboard = sorted(yaml_models - backboard_set)

    print(f"\n{'='*60}")
    print(f"Backboard total:   {len(backboard_set):>5} models")
    print(f"librechat.yaml:    {len(yaml_models):>5} models")
    print(f"{'='*60}")

    if in_backboard_not_yaml:
        print(f"\n[+] In Backboard but MISSING from librechat.yaml ({len(in_backboard_not_yaml)}):")
        for m in in_backboard_not_yaml:
            print(f"    + {m}")
    else:
        print("\n[+] No models missing from librechat.yaml — fully in sync!")

    if in_yaml_not_backboard:
        print(f"\n[-] In librechat.yaml but NOT in Backboard ({len(in_yaml_not_backboard)}):")
        for m in in_yaml_not_backboard:
            print(f"    - {m}")
    else:
        print("\n[-] No stale models in librechat.yaml — all entries are valid!")


async def main(output_path: Path, yaml_path: Path) -> None:
    api_key = os.getenv("BACKBOARD_API_KEY")
    if not api_key:
        sys.exit("ERROR: BACKBOARD_API_KEY is not set")

    client = BackboardClient(api_key=api_key)

    print("Fetching providers and models from Backboard…")
    models = await fetch_all_models(client)
    print(f"  Found {len(models)} chat models across all providers")

    output_path.write_text("\n".join(models) + "\n")
    print(f"  Written to {output_path}")

    print(f"\nParsing {yaml_path}…")
    yaml_models = extract_yaml_models(yaml_path)
    print(f"  Found {len(yaml_models)} model entries in librechat.yaml")

    diff_models(models, yaml_models)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=DEFAULT_OUTPUT, type=Path, help="Where to write backboard-models.txt")
    parser.add_argument("--yaml", default=DEFAULT_YAML, type=Path, help="Path to librechat.yaml")
    args = parser.parse_args()

    asyncio.run(main(args.output, args.yaml))
