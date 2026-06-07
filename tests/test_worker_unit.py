import json
import logging
from types import SimpleNamespace

import pytest

from worker.worker_service import (
    RecommendationResult,
    WorkerTask,
    build_completion_message,
    build_error_message,
    build_similarity_text,
    parse_task_message,
    process_task,
    rank_recommendations,
    run_once,
    search_similar_show_ids,
)


def test_parse_task_message_reads_username_and_movie():
    task = parse_task_message(json.dumps({"username": "lelalomos", "movie": "Inception"}))

    assert task == WorkerTask(username="lelalomos", movie="Inception")


def test_parse_task_message_rejects_missing_fields():
    with pytest.raises(ValueError):
        parse_task_message(json.dumps({"username": "lelalomos"}))


def test_build_similarity_text_uses_requested_fields_only(monkeypatch):
    monkeypatch.setattr(
        "worker.worker_service.load_field_weights",
        lambda: {"director": 25, "cast": 25, "genres": 25, "description": 25},
    )
    text = build_similarity_text(
        {
            "cast": "Actor A, Actor B",
            "description": "Dream inside a dream",
            "director": "Christopher Nolan",
            "genres": "Sci-Fi",
            "ignored": "value",
        }
    )

    assert text == "Christopher Nolan Actor A, Actor B Sci-Fi Dream inside a dream"


def test_rank_recommendations_prioritizes_language_then_type():
    ranked = rank_recommendations(
        [
            RecommendationResult("1", "Same Both", "Movie", "en", 0.70),
            RecommendationResult("2", "Same Language", "TV Show", "en", 0.99),
            RecommendationResult("3", "Same Type", "Movie", "fr", 0.95),
        ],
        input_language="en",
        input_type="Movie",
    )

    assert [item.show_id for item in ranked] == ["1", "2", "3"]


def test_search_similar_show_ids_skips_input_show_id():
    client = SimpleNamespace(
        search=lambda **kwargs: [
            SimpleNamespace(payload={"show_id": "100"}, score=0.99),
            SimpleNamespace(payload={"show_id": "101"}, score=0.88),
            SimpleNamespace(payload={"show_id": "102"}, score=0.77),
        ]
    )

    rows = search_similar_show_ids(
        client=client,
        query_text="alpha beta",
        excluded_show_id="100",
        limit=2,
        fetch_limit=3,
    )

    assert rows == [("101", 0.88), ("102", 0.77)]


def test_build_completion_message_has_done_status():
    message = json.loads(
        build_completion_message(
            WorkerTask(username="lelalomos", movie="Inception"),
            [RecommendationResult("1", "Title", "Movie", "en", 0.9)],
        )
    )

    assert message == {
        "status": "done",
        "username": "lelalomos",
        "movie": "Inception",
        "result_count": 1,
        "recommendations": [
            {
                "show_id": "1",
                "title": "Title",
                "content_type": "Movie",
                "language": "en",
                "score": 0.9,
            }
        ],
    }


def test_build_error_message_has_error_status():
    message = json.loads(build_error_message(WorkerTask(username="lelalomos", movie="Inception"), "bad request"))

    assert message == {
        "status": "error",
        "error": "bad request",
        "username": "lelalomos",
        "movie": "Inception",
    }


def test_process_task_returns_ranked_recommendations(monkeypatch):
    saved_user_content = []

    monkeypatch.setattr(
        "worker.worker_service.find_user_account_by_username",
        lambda connection, username: {"user_id": 1, "username": username},
    )
    monkeypatch.setattr(
        "worker.worker_service.insert_user_content",
        lambda connection, user_id, show_id: saved_user_content.append((user_id, show_id)),
    )
    monkeypatch.setattr(
        "worker.worker_service.find_content_by_title",
        lambda connection, title: {
            "show_id": "100",
            "title": title,
            "type": "Movie",
            "language": "en",
        },
    )
    monkeypatch.setattr(
        "worker.worker_service.get_qdrant_payload_by_show_id",
        lambda client, show_id: {
            "cast": "Actor A",
            "description": "Dream world",
            "director": "Director A",
            "genres": "Sci-Fi",
        },
    )
    monkeypatch.setattr(
        "worker.worker_service.search_similar_show_ids",
        lambda client, query_text, excluded_show_id: [("101", 0.91), ("102", 0.95)],
    )
    monkeypatch.setattr(
        "worker.worker_service.fetch_content_details_by_show_ids",
        lambda connection, show_ids: [
            {"show_id": "101", "title": "English Movie", "type": "Movie", "language": "en"},
            {"show_id": "102", "title": "French Show", "type": "TV Show", "language": "fr"},
        ],
    )

    results = process_task(
        task=WorkerTask(username="lelalomos", movie="Inception"),
        postgres_connection=object(),
        qdrant_client=object(),
    )

    assert [item.show_id for item in results] == ["101", "102"]
    assert saved_user_content == [(1, "100")]


def test_run_once_publishes_ack_message_and_acks(monkeypatch):
    published = []
    acked = []

    class FakeChannel:
        def basic_publish(self, **kwargs):
            published.append(kwargs)

        def basic_ack(self, delivery_tag):
            acked.append(delivery_tag)

        def queue_declare(self, **kwargs):
            return None

    delivery = SimpleNamespace(delivery_tag=77)
    monkeypatch.setattr(
        "worker.worker_service.process_task",
        lambda task, postgres_connection, qdrant_client: [
            RecommendationResult("10", "Example", "Movie", "en", 0.95)
        ],
    )

    recommendations = run_once(
        channel=FakeChannel(),
        delivery=delivery,
        properties=SimpleNamespace(reply_to="reply-queue", correlation_id="corr-1"),
        body=json.dumps({"username": "lelalomos", "movie": "Inception"}).encode("utf-8"),
        postgres_connection=object(),
        qdrant_client=object(),
    )

    assert recommendations[0].show_id == "10"
    assert acked == [77]
    assert published
    payload = json.loads(published[0]["body"].decode("utf-8"))
    assert payload["status"] == "done"
    assert published[0]["routing_key"] == "reply-queue"
    assert published[0]["properties"].correlation_id == "corr-1"


def test_run_once_logs_failure(monkeypatch, caplog):
    class FakeChannel:
        def basic_publish(self, **kwargs):
            return None

        def basic_ack(self, delivery_tag):
            return None

        def queue_declare(self, **kwargs):
            return None

    monkeypatch.setattr(
        "worker.worker_service.process_task",
        lambda task, postgres_connection, qdrant_client: (_ for _ in ()).throw(LookupError("missing content")),
    )

    with pytest.raises(LookupError):
        with caplog.at_level(logging.WARNING):
            run_once(
                channel=FakeChannel(),
                delivery=SimpleNamespace(delivery_tag=77),
                properties=SimpleNamespace(reply_to="reply-queue", correlation_id="corr-1"),
                body=json.dumps({"username": "lelalomos", "movie": "Inception"}).encode("utf-8"),
                postgres_connection=object(),
                qdrant_client=object(),
            )

    assert "worker_task_failed username=lelalomos movie=Inception error=missing content" in caplog.text
