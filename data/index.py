import json
import os
import time

from elasticsearch import Elasticsearch

BATCH_SIZE = 500

TEXT_FIELDS = [
    "abstract_en",
    "abstract_kk",
    "abstract_fr",
    "description_en",
    "description_kk",
    "description_fr",
]

EMBEDDING_DIM = 768


def create_index(client, index_name):
    properties = {
        "title": {"type": "text"},
        "genres": {"type": "keyword"},
        "year": {"type": "integer"},
    }
    for field in TEXT_FIELDS:
        properties[field] = {"type": "text"}
        properties[f"{field}_embedding"] = {
            "type": "dense_vector",
            "dims": EMBEDDING_DIM,
            "index": True,
            "similarity": "cosine",
        }

    if client.indices.exists(index=index_name):
        client.indices.delete(index=index_name)

    client.indices.create(
        index=index_name,
        body={"mappings": {"properties": properties}},
    )
    print(
        f"Created index '{index_name}' with dense_vector mappings ({EMBEDDING_DIM} dims)"
    )


def make_doc(row):
    try:
        split = row["title"].split("(")
        year = "1900"
        if len(split) == 2:
            year = split[1][:-1]

        doc = {
            "title": row["title"],
            "genres": (
                row["genres"].split("|")
                if row["genres"] != "(no genres listed)"
                else []
            ),
            "year": int(year),
        }
        for field in TEXT_FIELDS:
            doc[field] = row.get(field, "")
            emb_key = f"{field}_embedding"
            if emb_key in row:
                doc[emb_key] = row[emb_key]
        return doc
    except Exception as e:
        print(f"Error processing row: {row.get('title', 'unknown')}: {e}")


def index_batch(client, batch):
    actions = []
    for row in batch:
        actions.append({"index": {"_index": "movies_enriched", "_id": row["movieId"]}})
        actions.append(make_doc(row))
    client.bulk(operations=actions)


def main():
    client = Elasticsearch(
        hosts=[os.getenv("ELASTICSEARCH_URL", "http://localhost:9200")],
        basic_auth=("elastic", "elastic"),
    )

    input_path = os.path.join(
        os.path.dirname(__file__), "..", "data", "movies_enriched_with_embeddings.json"
    )

    create_index(client, "movies_enriched")

    start = time.time()
    batch = []
    count = 0

    with open(input_path, encoding="utf-8") as f:
        movies = json.load(f)

    for row in movies:
        batch.append(row)
        if len(batch) >= BATCH_SIZE:
            index_batch(client, batch)
            count += len(batch)
            print(f"Indexed {count} movies...")
            batch = []

    if batch:
        index_batch(client, batch)
        count += len(batch)

    print(f"Indexed {count} movies in {time.time() - start:.1f}s")

    print(client.search(index="movies_enriched", body={"query": {"match_all": {}}}))


if __name__ == "__main__":
    main()
