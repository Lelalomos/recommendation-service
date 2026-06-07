from pathlib import Path

import pytest
from openpyxl import Workbook

from postgresql.postgres_setup import (
    DEFAULT_CONTENT_TABLE,
    DEFAULT_MOVIE_METADATA_TABLE,
    DEFAULT_TV_METADATA_TABLE,
    DEFAULT_USER_ACCOUNT_TABLE,
    DEFAULT_USER_CONTENT_TABLE,
)
from postgresql.scripts.verify_postgres_import import load_expected_counts, verify_counts


def create_user_workbook(path: Path) -> None:
    workbook = Workbook()
    user_content = workbook.active
    user_content.title = "user_content"
    user_content.append(["user_id", "show_id"])
    user_content.append([1, 100])
    user_content.append([1, 100])
    user_content.append([2, 200])

    user_account = workbook.create_sheet("user_account")
    user_account.append(["user_id", "username", "password"])
    user_account.append([1, "alice", "hash1"])
    user_account.append([1, "alice", "hash1"])
    user_account.append([2, "bob", "hash2"])
    workbook.save(path)


def test_load_expected_counts_uses_unique_source_rows(tmp_path):
    movies_path = tmp_path / "movies.csv"
    tv_path = tmp_path / "tv.csv"
    user_xlsx_path = tmp_path / "user_data.xlsx"

    movies_path.write_text(
        "show_id,director,cast,genres,description,title\n"
        "1,Dir A,Actor A,Drama,Movie A,Title A\n"
        "2,Dir B,Actor B,Action,Movie B,Title B\n",
        encoding="utf-8",
    )
    tv_path.write_text(
        "show_id,director,cast,genres,description,title\n"
        "2,Dir C,Actor C,Comedy,Show C,Title C\n"
        "3,Dir D,Actor D,News,Show D,Title D\n",
        encoding="utf-8",
    )
    create_user_workbook(user_xlsx_path)

    counts = load_expected_counts(tv_path, movies_path, user_xlsx_path)

    assert counts == {
        DEFAULT_CONTENT_TABLE: 3,
        DEFAULT_TV_METADATA_TABLE: 2,
        DEFAULT_MOVIE_METADATA_TABLE: 2,
        DEFAULT_USER_CONTENT_TABLE: 2,
        DEFAULT_USER_ACCOUNT_TABLE: 2,
    }


def test_verify_counts_raises_when_counts_do_not_match():
    expected = {
        DEFAULT_CONTENT_TABLE: 3,
        DEFAULT_TV_METADATA_TABLE: 2,
        DEFAULT_MOVIE_METADATA_TABLE: 2,
        DEFAULT_USER_CONTENT_TABLE: 2,
        DEFAULT_USER_ACCOUNT_TABLE: 2,
    }
    actual = {
        DEFAULT_CONTENT_TABLE: 3,
        DEFAULT_TV_METADATA_TABLE: 2,
        DEFAULT_MOVIE_METADATA_TABLE: 1,
        DEFAULT_USER_CONTENT_TABLE: 2,
        DEFAULT_USER_ACCOUNT_TABLE: 2,
    }

    with pytest.raises(ValueError, match="movie_metadata: expected=2 actual=1"):
        verify_counts(expected, actual)
