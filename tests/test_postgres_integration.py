import psycopg

from postgresql.postgres_setup import (
    DEFAULT_TABLE,
    DEFAULT_DB,
    DEFAULT_HOST,
    DEFAULT_PORT,
    DEFAULT_USER,
    count_rows,
    create_table,
    delete_item,
    fetch_all_items,
    get_connection,
    insert_user_content,
    insert_item,
    reset_table,
    update_item_name,
    wait_for_postgres,
)


def setup_function():
    wait_for_postgres()
    with get_connection() as connection:
        reset_table(connection, DEFAULT_TABLE)
        create_table(connection, DEFAULT_TABLE)


def teardown_function():
    with get_connection() as connection:
        reset_table(connection, DEFAULT_TABLE)


def test_postgres_connection():
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_database() AS database_name")
            result = cursor.fetchone()

    assert result["database_name"]


def test_insert_and_update():
    with get_connection() as connection:
        create_table(connection, DEFAULT_TABLE)
        item_id = insert_item(connection, "first item", DEFAULT_TABLE)
        update_item_name(connection, item_id, "updated item", DEFAULT_TABLE)
        rows = fetch_all_items(connection, DEFAULT_TABLE)
        total = count_rows(connection, DEFAULT_TABLE)

    assert total == 1
    assert rows[0]["name"] == "updated item"


def test_delete_item():
    with get_connection() as connection:
        create_table(connection, DEFAULT_TABLE)
        item_id = insert_item(connection, "temporary item", DEFAULT_TABLE)
        delete_item(connection, item_id, DEFAULT_TABLE)
        rows = fetch_all_items(connection, DEFAULT_TABLE)
        total = count_rows(connection, DEFAULT_TABLE)

    assert total == 0
    assert rows == []


def test_postgres_rejects_wrong_password():
    try:
        psycopg.connect(
            dbname=DEFAULT_DB,
            user=DEFAULT_USER,
            password="wrong-password",
            host=DEFAULT_HOST,
            port=DEFAULT_PORT,
        )
    except psycopg.OperationalError:
        return

    raise AssertionError("Expected PostgreSQL to reject the wrong password")


def test_insert_user_content_is_idempotent():
    table_name = "user_content_test"
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
            cursor.execute(
                f"""
                CREATE TABLE {table_name} (
                    user_id BIGINT NOT NULL,
                    show_id BIGINT NOT NULL,
                    PRIMARY KEY (user_id, show_id)
                )
                """
            )
        connection.commit()
        insert_user_content(connection, user_id=1001, show_id=45418, table_name=table_name)
        insert_user_content(connection, user_id=1001, show_id=45418, table_name=table_name)
        total = count_rows(connection, table_name)
        with connection.cursor() as cursor:
            cursor.execute(
                f"SELECT user_id, show_id FROM {table_name} WHERE user_id = %s",
                (1001,),
            )
            rows = cursor.fetchall()
            cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
        connection.commit()

    assert total == 1
    assert rows == [{"user_id": 1001, "show_id": 45418}]
