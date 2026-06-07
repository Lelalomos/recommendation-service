from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent


def test_service_dockerfiles_use_standard_name():
    for service_name in ["api-service", "postgresql", "vector_db", "rabbitmq"]:
        assert (ROOT_DIR / service_name / "Dockerfile").is_file()
        assert not (ROOT_DIR / service_name / "Dockerfile.tests").exists()


def test_compose_files_reference_standard_dockerfile():
    compose_paths = [
        ROOT_DIR / "api-service/docker-compose.yml",
        ROOT_DIR / "postgresql/docker-compose.yml",
        ROOT_DIR / "vector_db/docker-compose.yml",
        ROOT_DIR / "rabbitmq/docker-compose.yml",
    ]
    for compose_path in compose_paths:
        contents = compose_path.read_text(encoding="utf-8")
        assert "Dockerfile.tests" not in contents
        assert "Dockerfile" in contents


def test_api_stack_uses_postgresql_folder_configuration():
    api_compose = (ROOT_DIR / "api-service/docker-compose.yml").read_text(encoding="utf-8")
    api_env = (ROOT_DIR / "api-service/.env").read_text(encoding="utf-8")

    assert "\n  postgres:\n" not in api_compose
    assert "\n  postgres-import:\n" not in api_compose
    assert "POSTGRES_ENV_FILE" in api_compose
    assert "POSTGRES_ENV_FILE=../postgresql/.env" in api_env


def test_build_and_start_scripts_exist_for_all_services():
    expected_scripts = [
        ROOT_DIR / "api-service/scripts/build_api_docker.sh",
        ROOT_DIR / "api-service/scripts/start_api_compose.sh",
        ROOT_DIR / "api-service/scripts/api_client.py",
        ROOT_DIR / "api-service/scripts/run_api_unit_tests.sh",
        ROOT_DIR / "api-service/scripts/run_api_tests.sh",
        ROOT_DIR / "api-service/scripts/test_login_api.sh",
        ROOT_DIR / "postgresql/scripts/build_postgres_docker.sh",
        ROOT_DIR / "postgresql/scripts/start_postgres_compose.sh",
        ROOT_DIR / "postgresql/scripts/run_postgres_tests.sh",
        ROOT_DIR / "postgresql/scripts/verify_postgres_import.py",
        ROOT_DIR / "vector_db/scripts/build_qdrant_docker.sh",
        ROOT_DIR / "vector_db/scripts/start_qdrant_compose.sh",
        ROOT_DIR / "vector_db/scripts/run_qdrant_tests.sh",
        ROOT_DIR / "vector_db/scripts/verify_qdrant_import.py",
        ROOT_DIR / "rabbitmq/scripts/build_rabbitmq_docker.sh",
        ROOT_DIR / "rabbitmq/scripts/start_rabbitmq_compose.sh",
        ROOT_DIR / "rabbitmq/scripts/run_rabbitmq_tests.sh",
        ROOT_DIR / "scripts/verify_all_imports.sh",
    ]
    for script_path in expected_scripts:
        assert script_path.is_file()


def test_qdrant_import_service_stays_alive_after_import():
    compose_path = ROOT_DIR / "vector_db/docker-compose.yml"
    contents = compose_path.read_text(encoding="utf-8")

    assert "/tmp/qdrant-import.done" in contents
    assert "tail -f /dev/null" in contents
    assert "qdrant-import:\n        condition: service_healthy" in contents


def test_test_scripts_cleanup_after_execution():
    script_paths = [
        ROOT_DIR / "api-service/scripts/run_api_unit_tests.sh",
        ROOT_DIR / "api-service/scripts/run_api_tests.sh",
        ROOT_DIR / "postgresql/scripts/run_postgres_tests.sh",
        ROOT_DIR / "postgresql/scripts/test_startup_import.sh",
        ROOT_DIR / "vector_db/scripts/run_qdrant_tests.sh",
        ROOT_DIR / "rabbitmq/scripts/run_rabbitmq_tests.sh",
    ]
    for script_path in script_paths:
        contents = script_path.read_text(encoding="utf-8")
        assert "trap cleanup EXIT" in contents
        assert "down -v" in contents


def test_rabbitmq_compose_has_worker_and_manual_ack_test_service():
    compose_path = ROOT_DIR / "rabbitmq/docker-compose.yml"
    contents = compose_path.read_text(encoding="utf-8")

    assert "\n  rabbitmq-worker:\n" in contents
    assert 'profiles: ["worker", "test"]' in contents
    assert "tests/test_rabbitmq_integration.py" in contents
    assert "RABBITMQ_WORKER_MODE" in contents


def test_runtime_services_use_unless_stopped_restart_policy():
    expected_restart_entries = {
        ROOT_DIR / "rabbitmq/docker-compose.yml": [
            "  rabbitmq:\n",
            "    restart: unless-stopped",
            "  rabbitmq-worker:\n",
        ],
        ROOT_DIR / "postgresql/docker-compose.yml": [
            "  postgres:\n",
            "  adminer:\n",
            "  postgres-import:\n",
            "    restart: unless-stopped",
        ],
        ROOT_DIR / "api-service/docker-compose.yml": [
            "  api:\n",
            "    restart: unless-stopped",
        ],
        ROOT_DIR / "vector_db/docker-compose.yml": [
            "  qdrant:\n",
            "  qdrant-import:\n",
            "    restart: unless-stopped",
        ],
    }

    for compose_path, required_snippets in expected_restart_entries.items():
        contents = compose_path.read_text(encoding="utf-8")
        for snippet in required_snippets:
            assert snippet in contents

    rabbitmq_contents = (ROOT_DIR / "rabbitmq/docker-compose.yml").read_text(encoding="utf-8")
    assert 'restart: "no"' not in rabbitmq_contents


def test_manual_login_script_checks_running_services():
    script_path = ROOT_DIR / "api-service/scripts/test_login_api.sh"
    contents = script_path.read_text(encoding="utf-8")

    assert 'API_ACTION=login' in contents
    assert 'api_client.sh' in contents


def test_combined_api_client_script_covers_all_routes():
    script_path = ROOT_DIR / "api-service/scripts/api_client.py"
    contents = script_path.read_text(encoding="utf-8")

    assert 'subprocess.run' in contents
    assert 'service_name' in contents
    assert '/health' in contents
    assert '/api/v1/auth/register' in contents
    assert '/api/v1/auth/token' in contents
    assert '/api/v1/recommendations' in contents
    assert 'API_ACTION' in contents


def test_compose_files_use_docker_log_rotation():
    compose_paths = [
        ROOT_DIR / "api-service/docker-compose.yml",
        ROOT_DIR / "postgresql/docker-compose.yml",
        ROOT_DIR / "vector_db/docker-compose.yml",
        ROOT_DIR / "rabbitmq/docker-compose.yml",
        ROOT_DIR / "worker/docker-compose.yml",
    ]
    for compose_path in compose_paths:
        contents = compose_path.read_text(encoding="utf-8")
        assert 'driver: json-file' in contents
        assert 'max-size: "10m"' in contents
        assert 'max-file: "3"' in contents


def test_native_service_logging_is_enabled():
    postgres_compose = (ROOT_DIR / "postgresql/docker-compose.yml").read_text(encoding="utf-8")
    rabbitmq_compose = (ROOT_DIR / "rabbitmq/docker-compose.yml").read_text(encoding="utf-8")
    qdrant_compose = (ROOT_DIR / "vector_db/docker-compose.yml").read_text(encoding="utf-8")

    assert "log_connections=on" in postgres_compose
    assert "log_disconnections=on" in postgres_compose
    assert 'RABBITMQ_LOGS: "-"' in rabbitmq_compose
    assert "RUST_LOG: info" in qdrant_compose


def test_verify_all_imports_script_checks_service_status():
    script_contents = (ROOT_DIR / "scripts/verify_all_imports.sh").read_text(encoding="utf-8")

    assert 'docker inspect --format' in script_contents
    assert '[[ "$status" == "running" ]]' in script_contents
    assert 'POSTGRES_CONTAINER_NAME' in script_contents
    assert 'QDRANT_CONTAINER_NAME' in script_contents
    assert 'rg -q' not in script_contents
    assert 'verify_postgres_import.py' in script_contents
    assert 'verify_qdrant_import.py' in script_contents
