#!/usr/bin/env python3
"""
Generate multilingual abstract and description columns for movies.csv using OpenRouter LLM API.

Reads ml-32m/movies.csv (movieId, title, genres) and produces
data/movies_enriched.csv with 6 extra columns:
  abstract_en, abstract_kk, abstract_fr, description_en, description_kk, description_fr

Supports resuming from where it left off if interrupted.

Usage:
    export OPENROUTER_API_KEY="sk-or-..."
    python data/generate_descriptions.py [OPTIONS]

Options:
    --input         Input CSV path        (default: ml-32m/movies.csv)
    --output        Output CSV path       (default: data/movies_enriched.csv)
    --model         OpenRouter model ID   (default: google/gemini-2.0-flash-001)
    --concurrency   Parallel requests     (default: 20)
    --limit         Max movies to process (default: all)
    --batch-size    Save every N movies   (default: 100)
"""

import argparse
import asyncio
import csv
import json
import os
import sys
import time
from pathlib import Path

try:
    import aiohttp
except ImportError:
    print("Error: aiohttp required. Install with: pip install aiohttp")
    sys.exit(1)


OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

FIELDS = [
    "abstract_en",
    "abstract_kk",
    "abstract_fr",
    "description_en",
    "description_kk",
    "description_fr",
]

SYSTEM_PROMPT = """\
You are a movie encyclopedia. Given a movie title and its genres, generate \
an abstract and description in three languages: English, Kazakh, and French.

For each language produce:
- "abstract_XX": 1-2 concise sentences describing what the movie is about.
- "description_XX": A detailed one-paragraph description (~100-150 words) covering \
the plot, themes, and notable aspects of the movie.

Language codes: en = English, kk = Kazakh (use Cyrillic script), fr = French.

If you don't recognize the movie, write plausible descriptions based on the title and genres.

Respond ONLY with valid JSON containing exactly these 6 keys:
{"abstract_en": "...", "abstract_kk": "...", "abstract_fr": "...", \
"description_en": "...", "description_kk": "...", "description_fr": "..."}
No markdown, no code fences, no extra text."""


def parse_args():
    parser = argparse.ArgumentParser(description="Generate movie descriptions via LLM")
    parser.add_argument(
        "--input",
        default="ml-32m/movies.csv",
        help="Input CSV path (default: ml-32m/movies.csv)",
    )
    parser.add_argument(
        "--output",
        default="data/movies_enriched.csv",
        help="Output CSV path (default: data/movies_enriched.csv)",
    )
    parser.add_argument(
        "--model",
        default="google/gemini-2.0-flash-001",
        help="OpenRouter model ID (default: google/gemini-2.0-flash-001)",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=20,
        help="Number of parallel requests (default: 20)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Max movies to process, 0=all (default: 0)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Save progress every N movies (default: 100)",
    )
    return parser.parse_args()


def read_input(path):
    """Read the input movies CSV."""
    movies = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            movies.append(row)
    return movies


def read_existing_output(path):
    """Read already-processed movie IDs from output CSV for resume support."""
    done = {}
    if not Path(path).exists():
        return done
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            done[row["movieId"]] = row
    return done


def write_output(path, rows):
    """Write all rows to the output CSV."""
    if not rows:
        return
    fieldnames = ["movieId", "title", "genres"] + FIELDS
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def parse_llm_response(text):
    """Parse JSON from LLM response, handling common formatting issues."""
    text = text.strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        if text.endswith("```"):
            text = text[: -len("```")]
        text = text.strip()
    try:
        data = json.loads(text)
        result = {f: data.get(f, "") for f in FIELDS}
        if all(result.values()):
            return result
        return None
    except json.JSONDecodeError:
        return None


async def call_llm(session, semaphore, movie, model, api_key, retries=3):
    """Call OpenRouter API for a single movie."""
    title = movie["title"]
    genres = movie.get("genres", "").replace("|", ", ")
    user_msg = f"Title: {title}\nGenres: {genres}"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        "temperature": 0.3,
        "max_tokens": 1536,
    }

    for attempt in range(retries):
        async with semaphore:
            try:
                async with session.post(
                    OPENROUTER_URL, headers=headers, json=payload, timeout=30
                ) as resp:
                    if resp.status == 429:
                        wait = 2 ** (attempt + 1)
                        await asyncio.sleep(wait)
                        continue
                    resp_data = await resp.json()
                    if resp.status != 200:
                        err = resp_data.get("error", {}).get("message", resp.status)
                        print(f"  API error for '{title}': {err}")
                        await asyncio.sleep(1)
                        continue
                    content = resp_data["choices"][0]["message"]["content"]
                    result = parse_llm_response(content)
                    if result:
                        return result
                    continue
            except (asyncio.TimeoutError, aiohttp.ClientError) as e:
                if attempt < retries - 1:
                    await asyncio.sleep(2 ** (attempt + 1))
                else:
                    print(f"  Failed after {retries} attempts for '{title}': {e}")

    return {f: "" for f in FIELDS}


async def process_batch(movies, model, api_key, concurrency):
    """Process a batch of movies concurrently."""
    semaphore = asyncio.Semaphore(concurrency)
    async with aiohttp.ClientSession() as session:
        tasks = [call_llm(session, semaphore, m, model, api_key) for m in movies]
        return await asyncio.gather(*tasks)


async def main():
    args = parse_args()

    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        print("Error: Set OPENROUTER_API_KEY environment variable")
        sys.exit(1)

    # Read input
    print(f"Reading {args.input}...")
    all_movies = read_input(args.input)
    print(f"  Total movies in input: {len(all_movies)}")

    # Read existing progress
    done = read_existing_output(args.output)
    if done:
        print(f"  Already processed: {len(done)} (will resume)")

    # Filter to remaining movies
    remaining = [m for m in all_movies if m["movieId"] not in done]
    if args.limit:
        remaining = remaining[: args.limit]
    print(f"  To process: {len(remaining)}")

    if not remaining:
        print("Nothing to do!")
        return

    # Collect all results (start with existing)
    all_results = {mid: row for mid, row in done.items()}

    # Process in batches
    total = len(remaining)
    start_time = time.time()
    processed = 0

    for i in range(0, total, args.batch_size):
        batch = remaining[i : i + args.batch_size]
        results = await process_batch(batch, args.model, api_key, args.concurrency)

        for movie, result in zip(batch, results):
            row = {
                "movieId": movie["movieId"],
                "title": movie["title"],
                "genres": movie.get("genres", ""),
            }
            row.update(result)
            all_results[movie["movieId"]] = row

        processed += len(batch)
        elapsed = time.time() - start_time
        rate = processed / elapsed if elapsed > 0 else 0
        eta = (total - processed) / rate if rate > 0 else 0
        pct = processed / total * 100

        failed = sum(
            1 for m in batch if not all_results[m["movieId"]].get("abstract_en")
        )

        print(
            f"  [{processed}/{total}] {pct:.0f}% | "
            f"{rate:.1f} movies/s | ETA {eta:.0f}s | "
            f"batch failures: {failed}"
        )

        # Save progress — preserve input order
        ordered = []
        for m in all_movies:
            if m["movieId"] in all_results:
                ordered.append(all_results[m["movieId"]])
        write_output(args.output, ordered)

    elapsed = time.time() - start_time
    total_done = sum(1 for r in all_results.values() if r.get("abstract_en"))
    print(f"\nDone! {total_done} movies enriched in {elapsed:.0f}s")
    print(f"Output: {args.output}")


if __name__ == "__main__":
    asyncio.run(main())
