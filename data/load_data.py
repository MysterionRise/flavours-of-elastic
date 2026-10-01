#!/usr/bin/env python3
"""Load the checked-in movie data into Elasticsearch or OpenSearch.

    python data/load_data.py --dataset movies --size small
    python data/load_data.py --dataset movies --size full
    python data/load_data.py --dataset movies --embeddings hash

The implementation lives in search/loader.py (run `--help` for every option);
this script keeps the path the course and the docs use.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from search.loader import (  # noqa: E402,F401 - re-exported for older imports
    DATASETS,
    MOVIES_MAPPING,
    main,
    normalize_movie,
    parse_year,
    read_ids,
    read_movies,
    split_genres,
    strip_year,
)

if __name__ == "__main__":
    sys.exit(main())
