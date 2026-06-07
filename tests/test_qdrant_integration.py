from vector_db.qdrant_setup import (
    DEFAULT_COLLECTION,
    count_points,
    delete_point,
    get_client,
    insert_sample_points,
    recreate_collection,
    search_points,
    wait_for_qdrant,
)


def test_qdrant_connection():
    wait_for_qdrant()
    client = get_client()
    recreate_collection(client, DEFAULT_COLLECTION)

    collections = client.get_collections()

    assert any(collection.name == DEFAULT_COLLECTION for collection in collections.collections)


def test_insert_and_search():
    wait_for_qdrant()
    client = get_client()
    recreate_collection(client, DEFAULT_COLLECTION)
    insert_sample_points(client, DEFAULT_COLLECTION)

    assert count_points(client, DEFAULT_COLLECTION) == 3

    results = search_points(client, [1.0, 0.0, 0.0, 0.0], DEFAULT_COLLECTION, limit=2)
    result_titles = [result.payload["title"] for result in results]

    assert result_titles[0] == "Action Movie"
    assert "Action Show" in result_titles


def test_delete_point():
    wait_for_qdrant()
    client = get_client()
    recreate_collection(client, DEFAULT_COLLECTION)
    insert_sample_points(client, DEFAULT_COLLECTION)

    delete_point(client, 2, DEFAULT_COLLECTION)

    assert count_points(client, DEFAULT_COLLECTION) == 2

    remaining = search_points(client, [1.0, 0.0, 0.0, 0.0], DEFAULT_COLLECTION, limit=3)
    remaining_ids = [point.id for point in remaining]

    assert 2 not in remaining_ids
