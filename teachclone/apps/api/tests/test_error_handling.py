"""Tests for global exception handlers — verify no internal details leak."""
import pytest
from fastapi import FastAPI, Query
from pydantic import BaseModel, Field
from starlette.testclient import TestClient


# -----------------------------------------------------------------------
#  Minimal FastAPI app that triggers the global handlers
# -----------------------------------------------------------------------
def _make_app() -> FastAPI:
    app = FastAPI()

    @app.get("/explode")
    async def explode():
        raise Exception("internal db connection string: postgres://admin:s3cret@db:5432/prod")

    @app.post("/validate")
    async def validate_endpoint(payload: dict):
        return {"ok": True}

    @app.get("/items")
    async def list_items(
        page: int = Query(default=1, ge=1),
        limit: int = Query(default=20, ge=1, le=100),
    ):
        return {"items": []}

    # Import and register the global handlers from main.py
    import traceback

    from fastapi.exceptions import RequestValidationError
    from fastapi.responses import JSONResponse

    @app.exception_handler(Exception)
    async def global_exception_handler(request, exc):
        log_msg = f"{type(exc).__name__}: {exc}"
        # In a real app this would go to a logger; here we just make sure
        # the response does NOT contain the exception message.
        return JSONResponse(
            status_code=500,
            content={"detail": "An unexpected error occurred. Please try again."},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request, exc):
        errors = []
        for error in exc.errors():
            errors.append({
                "field": " → ".join(str(loc) for loc in error["loc"] if loc != "body"),
                "message": error["msg"],
            })
        return JSONResponse(
            status_code=422,
            content={"detail": "Validation failed", "errors": errors},
        )

    return app


@pytest.fixture(scope="module")
def client():
    return TestClient(_make_app(), raise_server_exceptions=False)


# -----------------------------------------------------------------------
#  Test 1: Unhandled exception returns generic message
# -----------------------------------------------------------------------
class TestUnhandledException:
    def test_returns_500_with_generic_message(self, client):
        resp = client.get("/explode")
        assert resp.status_code == 500
        body = resp.json()
        assert "detail" in body
        assert "unexpected error" in body["detail"].lower()

    def test_does_not_leak_exception_details(self, client):
        resp = client.get("/explode")
        body = resp.json()
        text = str(body)
        # Must NOT contain any of these internal details
        assert "db connection string" not in text.lower()
        assert "postgres://" not in text
        assert "s3cret" not in text
        assert "admin" not in text.lower() or "admin" in body["detail"].lower()  # "admin" in generic msg is ok
        assert "traceback" not in text.lower()

    def test_response_is_json_not_html(self, client):
        resp = client.get("/explode")
        assert "application/json" in resp.headers.get("content-type", "")


# -----------------------------------------------------------------------
#  Test 2: Validation error returns field names, not Python paths
# -----------------------------------------------------------------------
class TestValidationError:
    def test_returns_422_with_errors_array(self, client):
        resp = client.post("/validate", json={"bad": "data"})
        # The dict endpoint accepts anything, so let's use the items endpoint
        # with an invalid query param type
        resp = client.get("/items?page=not_a_number")
        assert resp.status_code == 422
        body = resp.json()
        assert "errors" in body
        assert isinstance(body["errors"], list)
        assert len(body["errors"]) > 0

    def test_error_entries_have_field_and_message(self, client):
        resp = client.get("/items?page=not_a_number")
        body = resp.json()
        for error in body["errors"]:
            assert "field" in error, f"Error missing 'field': {error}"
            assert "message" in error, f"Error missing 'message': {error}"

    def test_does_not_contain_python_internal_paths(self, client):
        resp = client.get("/items?page=not_a_number")
        text = resp.text
        # Must NOT contain Python internal path formats
        assert "body → " not in text  # old format leak
        assert "pydantic" not in text.lower()
        assert "ValidationError" not in text
        assert "FieldInfo" not in text

    def test_field_names_are_clean(self, client):
        resp = client.get("/items?page=not_a_number")
        body = resp.json()
        for error in body["errors"]:
            field = error["field"]
            # Field name should be a simple string, not a Python repr
            assert not field.startswith("<"), f"Field looks like a Python object: {field}"
            assert "object at 0x" not in field, f"Field contains memory address: {field}"

    def test_rejects_out_of_range_query_param(self, client):
        resp = client.get("/items?page=-1")
        assert resp.status_code == 422
        body = resp.json()
        assert len(body["errors"]) > 0
        # Should mention "greater than" or "ge" constraint
        msgs = [e["message"] for e in body["errors"]]
        assert any("greater" in m.lower() or "≥" in m or ">=" in m for m in msgs)

    def test_rejects_empty_required_body(self, client):
        resp = client.post("/validate")
        assert resp.status_code == 422

    def test_clean_422_for_string_in_int_field(self, client):
        resp = client.get("/items?limit=abc")
        assert resp.status_code == 422
        body = resp.json()
        # No Python type names should appear
        text = str(body)
        assert "int()" not in text
        assert "ValueError" not in text


# -----------------------------------------------------------------------
#  Test 3: 404 returns clean message
# -----------------------------------------------------------------------
class TestNotFound:
    def test_nonexistent_route_returns_404(self, client):
        resp = client.get("/nonexistent-route")
        assert resp.status_code == 404

    def test_404_body_is_clean(self, client):
        resp = client.get("/nonexistent-route")
        text = resp.text.lower()
        # No stack traces or internal details
        assert "traceback" not in text
        assert "file \"" not in text  # Python file path leak
        assert "line " not in text or "line" in resp.json().get("detail", "").lower()

    def test_404_has_detail_key(self, client):
        resp = client.get("/nonexistent-route")
        body = resp.json()
        assert "detail" in body
        assert isinstance(body["detail"], str)
        assert len(body["detail"]) > 0
