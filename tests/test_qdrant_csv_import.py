import pandas as pd
import pytest

from vector_db.qdrant_setup import (
    DATASET_COLLECTION,
    DATASET_COLUMNS,
    DATASET_VECTOR_SIZE,
    build_text_vectors,
    build_weighted_text,
    combine_text_fields,
    count_dataset_rows,
    count_points,
    ensure_dataset_imported,
    get_repeat_counts,
    get_client,
    import_csvs_to_qdrant,
    load_dataset_rows,
    load_field_weights,
    should_recreate_dataset,
    wait_for_qdrant,
)


def test_load_dataset_rows_selects_only_requested_columns(tmp_path):
    movies_path = tmp_path / "movies.csv"
    tv_path = tmp_path / "tv.csv"

    pd.DataFrame(
        [
            {
                "show_id": "m1",
                "director": "Dir One",
                "cast": "Actor A",
                "genres": "Drama",
                "description": "Movie text",
                "title": "Ignored",
            }
        ]
    ).to_csv(movies_path, index=False)

    pd.DataFrame(
        [
            {
                "show_id": "t1",
                "director": "Dir Two",
                "cast": "Actor B",
                "genres": "Action",
                "description": "Show text",
                "rating": "TV-14",
            }
        ]
    ).to_csv(tv_path, index=False)

    df = load_dataset_rows(str(movies_path), str(tv_path))

    assert list(df.columns) == DATASET_COLUMNS + ["combined_text"]
    assert df["show_id"].tolist() == ["m1", "t1"]


def test_load_field_weights_requires_total_of_one_hundred(tmp_path):
    config_path = tmp_path / "weights.json"
    config_path.write_text(
        '{"director": 10, "cast": 30, "genres": 30, "description": 10}',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="sum to 100"):
        load_field_weights(config_path)


def test_load_field_weights_accepts_valid_percentages(tmp_path):
    config_path = tmp_path / "weights.json"
    config_path.write_text(
        '{"director": 10, "cast": 30, "genres": 40, "description": 20}',
        encoding="utf-8",
    )

    assert load_field_weights(config_path) == {
        "director": 10,
        "cast": 30,
        "genres": 40,
        "description": 20,
    }


def test_get_repeat_counts_reduces_percentages_by_common_divisor():
    repeat_counts = get_repeat_counts(
        {"director": 10, "cast": 30, "genres": 40, "description": 20}
    )

    assert repeat_counts == {
        "director": 1,
        "cast": 3,
        "genres": 4,
        "description": 2,
    }


def test_build_weighted_text_respects_percentages():
    text = build_weighted_text(
        {
            "director": "Director A",
            "cast": "Actor A",
            "genres": "Sci-Fi",
            "description": "Dream world",
        },
        {"director": 10, "cast": 30, "genres": 40, "description": 20},
    )

    assert text == "Director A Actor A Actor A Actor A Sci-Fi Sci-Fi Sci-Fi Sci-Fi Dream world Dream world"


def test_combine_text_fields_uses_loaded_weights():
    text = combine_text_fields(
        pd.Series(
            {
                "director": "Director A",
                "cast": "Actor A",
                "genres": "Sci-Fi",
                "description": "Dream world",
            }
        ),
        weights={"director": 25, "cast": 25, "genres": 25, "description": 25},
    )

    assert text == "Director A Actor A Sci-Fi Dream world"


def test_build_text_vectors_uses_expected_size():
    vectors = build_text_vectors(["alpha beta", "gamma delta"])

    assert len(vectors) == 2
    assert len(vectors[0]) == DATASET_VECTOR_SIZE


def test_count_dataset_rows_sums_all_csvs(tmp_path):
    movies_path = tmp_path / "movies.csv"
    tv_path = tmp_path / "tv.csv"

    pd.DataFrame([{"show_id": "m1"}, {"show_id": "m2"}]).to_csv(movies_path, index=False)
    pd.DataFrame([{"show_id": "t1"}]).to_csv(tv_path, index=False)

    assert count_dataset_rows(str(movies_path), str(tv_path)) == 3


def test_import_csvs_to_qdrant_inserts_rows(tmp_path):
    movies_path = tmp_path / "movies.csv"
    tv_path = tmp_path / "tv.csv"

    pd.DataFrame(
        [
            {
                "show_id": "m1",
                "director": "Dir One",
                "cast": "Actor A",
                "genres": "Drama",
                "description": "Movie text",
            }
        ]
    ).to_csv(movies_path, index=False)

    pd.DataFrame(
        [
            {
                "show_id": "t1",
                "director": "Dir Two",
                "cast": "Actor B",
                "genres": "Action",
                "description": "Show text",
            }
        ]
    ).to_csv(tv_path, index=False)

    wait_for_qdrant()
    client = get_client()
    inserted = import_csvs_to_qdrant(
        client=client,
        collection_name=DATASET_COLLECTION,
        csv_paths=[str(movies_path), str(tv_path)],
        recreate=True,
        batch_size=1,
    )

    assert inserted == 2
    assert count_points(client, DATASET_COLLECTION) == 2

    results = client.search(
        collection_name=DATASET_COLLECTION,
        query_vector=build_text_vectors(["Dir One Actor A Drama Movie text"])[0],
        limit=1,
        with_payload=True,
    )

    assert results[0].payload["show_id"] == "m1"


def test_should_recreate_dataset_respects_existing_data(tmp_path):
    movies_path = tmp_path / "movies.csv"
    tv_path = tmp_path / "tv.csv"

    pd.DataFrame(
        [
            {
                "show_id": "m1",
                "director": "Dir One",
                "cast": "Actor A",
                "genres": "Drama",
                "description": "Movie text",
            }
        ]
    ).to_csv(movies_path, index=False)

    pd.DataFrame(
        [
            {
                "show_id": "t1",
                "director": "Dir Two",
                "cast": "Actor B",
                "genres": "Action",
                "description": "Show text",
            }
        ]
    ).to_csv(tv_path, index=False)

    wait_for_qdrant()
    client = get_client()
    first_inserted = import_csvs_to_qdrant(
        client=client,
        collection_name=DATASET_COLLECTION,
        csv_paths=[str(movies_path), str(tv_path)],
        recreate=True,
        batch_size=1,
    )
    inserted, imported = ensure_dataset_imported(
        client=client,
        collection_name=DATASET_COLLECTION,
        csv_paths=[str(movies_path), str(tv_path)],
        import_mode="missing",
        batch_size=1,
    )

    assert first_inserted == 2
    assert imported is False
    assert inserted == 2
    assert should_recreate_dataset(
        client,
        DATASET_COLLECTION,
        "missing",
        csv_paths=[str(movies_path), str(tv_path)],
    ) is False


def test_should_recreate_dataset_when_existing_collection_is_incomplete(tmp_path):
    movies_path = tmp_path / "movies.csv"
    tv_path = tmp_path / "tv.csv"

    pd.DataFrame(
        [
            {
                "show_id": "m1",
                "director": "Dir One",
                "cast": "Actor A",
                "genres": "Drama",
                "description": "Movie text",
            }
        ]
    ).to_csv(movies_path, index=False)

    pd.DataFrame(
        [
            {
                "show_id": "t1",
                "director": "Dir Two",
                "cast": "Actor B",
                "genres": "Action",
                "description": "Show text",
            },
            {
                "show_id": "t2",
                "director": "Dir Three",
                "cast": "Actor C",
                "genres": "Comedy",
                "description": "Second show text",
            },
        ]
    ).to_csv(tv_path, index=False)

    wait_for_qdrant()
    client = get_client()
    import_csvs_to_qdrant(
        client=client,
        collection_name=DATASET_COLLECTION,
        csv_paths=[str(movies_path)],
        recreate=True,
        batch_size=1,
    )

    assert should_recreate_dataset(
        client,
        DATASET_COLLECTION,
        "missing",
        csv_paths=[str(movies_path), str(tv_path)],
    ) is True
