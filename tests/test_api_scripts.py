from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent


def test_combined_api_client_script_exists_and_supports_all_routes():
    script_path = ROOT_DIR / "api-service/scripts/api_client.py"
    contents = script_path.read_text(encoding="utf-8")

    assert script_path.is_file()
    assert 'ACTION = os.getenv("API_ACTION", "health")' in contents
    assert 'API_AUTO_LOGIN_FOR_RECOMMENDATIONS' in contents
    assert "def call_health()" in contents
    assert "def call_register()" in contents
    assert "def call_login()" in contents
    assert "def call_recommendations()" in contents
    assert '/health' in contents
    assert '/api/v1/auth/register' in contents
    assert '/api/v1/auth/token' in contents
    assert '/api/v1/recommendations' in contents


def test_login_wrapper_script_uses_combined_api_client():
    script_path = ROOT_DIR / "api-service/scripts/test_login_api.sh"
    contents = script_path.read_text(encoding="utf-8")

    assert 'API_ACTION=login' in contents
    assert 'api_client.py' in contents
