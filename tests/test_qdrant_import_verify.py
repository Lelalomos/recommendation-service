from types import SimpleNamespace

import pytest

from vector_db.scripts.verify_qdrant_import import verify_dataset_counts, verify_show_id_exists


def test_verify_dataset_counts_raises_when_counts_do_not_match():
    with pytest.raises(ValueError, match="expected=10 actual=8"):
        verify_dataset_counts(10, 8)


def test_verify_show_id_exists_raises_when_show_id_is_missing():
    client = SimpleNamespace(
        scroll=lambda **kwargs: ([], None)
    )

    with pytest.raises(ValueError, match="missing show_id 32415"):
        verify_show_id_exists(client, "dataset", "32415")
