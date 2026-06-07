import time

from rabbitmq.rabbitmq_setup import (
    DEFAULT_QUEUE,
    get_queue_message_count,
    publish_message,
    purge_queue,
    wait_for_rabbitmq,
)


def test_rabbitmq_connection():
    wait_for_rabbitmq()
    purge_queue(DEFAULT_QUEUE)

    assert get_queue_message_count(DEFAULT_QUEUE) == 0


def test_publish_consume_and_ack():
    wait_for_rabbitmq()
    purge_queue(DEFAULT_QUEUE)

    message = "test message for worker ack"
    publish_message(message, DEFAULT_QUEUE)

    deadline = time.time() + 5
    while time.time() < deadline:
        if get_queue_message_count(DEFAULT_QUEUE) == 0:
            break
        time.sleep(0.2)
    else:
        raise AssertionError("Expected rabbitmq-worker service to ack the message and empty the queue.")
