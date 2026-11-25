import time
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient

import src.database as db_module
from src.analyzer import analyze_python_code
from src.github_client import parse_github_url
from src.main import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    test_db = str(tmp_path / "test_repolens.db")
    monkeypatch.setattr(db_module, "DB_PATH", test_db)
    db_module.init_db(test_db)
    with TestClient(app) as test_client:
        yield test_client


def test_t01_cyclomatic_complexity_calculation():
    code = "def evaluate(x, y):\n    if x > 0 and y > 0:\n        for i in range(x):\n            print(i)\n    return x\n"
    result = analyze_python_code(code, "math_ops.py")
    assert result["function_count"] == 1
    assert result["functions"][0]["complexity"] == 4


def test_t02_hardcoded_secret_detection():
    code = 'API_KEY = "sk-secret-token-12345"\nUSER_LABEL = "Enter password"\n'
    result = analyze_python_code(code, "secrets_test.py")
    assert len(result["warnings"]) == 1
    assert result["warnings"][0]["variable"] == "API_KEY"


def test_t03_database_persistence_and_delete_integration(client):
    post_resp = client.post("/api/analyze", json={"filename": "service.py", "source_code": "def ping():\n    return 'pong'\n"})
    assert post_resp.status_code == 200
    scan_id = post_resp.json()["scan_id"]
    assert client.delete(f"/api/scans/{scan_id}").status_code == 200


def test_t04_boundary_whitespace_and_syntax_error(client):
    assert client.post("/api/analyze", json={"filename": "empty.py", "source_code": "   \n\t  "}).status_code == 422
    assert client.post("/api/analyze", json={"filename": "broken.py", "source_code": "def broken(:\n    pass"}).status_code == 422


def test_t05_github_url_parser_and_endpoint(client):
    assert parse_github_url("https://github.com/octocat/Hello-World/blob/main/app.py") == ("octocat", "Hello-World", "main", "app.py")
    mock_files = [{"filename": "octocat/Hello-World/app.py", "source_code": "def run():\n    if True:\n        return 1\n"}]
    with patch("src.main.fetch_python_files_from_github", return_value=mock_files):
        resp = client.post("/api/analyze-github", json={"repo_url": "https://github.com/octocat/Hello-World"})
        assert resp.status_code == 200
        assert resp.json()["reports"][0]["max_complexity"] == 2


def test_t06_performance_1000_lines_under_threshold():
    large_code = "\n".join([f"def func_{i}(x):\n    return x + {i}\n" for i in range(500)])
    start = time.perf_counter()
    result = analyze_python_code(large_code, "large_module.py")
    assert result["function_count"] == 500
    assert (time.perf_counter() - start) < 1.5
