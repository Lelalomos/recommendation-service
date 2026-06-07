import os

from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse


def test_qdrant_requires_api_key():
    client = QdrantClient(url=os.environ["QDRANT_URL"])

    try:
        client.get_collections()
    except UnexpectedResponse as exc:
        assert exc.status_code == 401
    else:
        raise AssertionError("Expected Qdrant to reject requests without API key")


def test_qdrant_accepts_api_key():
    client = QdrantClient(
        url=os.environ["QDRANT_URL"],
        api_key=os.environ["QDRANT_API_KEY"],
    )

    collections = client.get_collections()

    assert collections is not None
