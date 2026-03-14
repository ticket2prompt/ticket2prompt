import pathlib

import pytest
import yaml

PROJECT_ROOT = pathlib.Path(__file__).parent.parent
COMPOSE_FILE = PROJECT_ROOT / "docker-compose.yml"


@pytest.fixture
def compose_data():
    with open(COMPOSE_FILE) as f:
        return yaml.safe_load(f)


def test_docker_compose_file_exists():
    assert COMPOSE_FILE.exists(), f"docker-compose.yml not found at {COMPOSE_FILE}"


def test_docker_compose_valid_yaml(compose_data):
    assert isinstance(compose_data, dict), "docker-compose.yml did not parse as a dict"


def test_docker_compose_has_services(compose_data):
    assert "services" in compose_data, "docker-compose.yml missing 'services' key"
    assert isinstance(compose_data["services"], dict), "'services' is not a dict"


def test_all_five_services_present(compose_data):
    services = compose_data["services"]
    expected = {"postgres", "redis", "qdrant", "app", "celery-worker", "frontend"}
    actual = set(services.keys())
    assert actual == expected, (
        f"Expected exactly services {expected}, got {actual}"
    )


def test_postgres_service_defined(compose_data):
    services = compose_data["services"]
    assert "postgres" in services, "No 'postgres' service defined"

    postgres = services["postgres"]

    assert "image" in postgres, "postgres service missing 'image'"
    assert postgres["image"].startswith("postgres:"), (
        f"postgres image '{postgres['image']}' does not start with 'postgres:'"
    )

    assert "environment" in postgres, "postgres service missing 'environment'"
    env = postgres["environment"]
    if isinstance(env, dict):
        env_keys = set(env.keys())
    else:
        env_keys = {item.partition("=")[0] for item in env}
    for var in ("POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB"):
        assert var in env_keys, f"postgres environment missing '{var}'"

    assert "ports" in postgres, "postgres service missing 'ports'"
    assert any("5432" in str(p) for p in postgres["ports"]), (
        "postgres ports do not expose 5432"
    )


def test_redis_service_defined(compose_data):
    services = compose_data["services"]
    assert "redis" in services, "No 'redis' service defined"

    redis = services["redis"]

    assert "image" in redis, "redis service missing 'image'"
    assert redis["image"].startswith("redis:"), (
        f"redis image '{redis['image']}' does not start with 'redis:'"
    )

    assert "ports" in redis, "redis service missing 'ports'"
    assert any("6379" in str(p) for p in redis["ports"]), (
        "redis ports do not expose 6379"
    )


def test_qdrant_service_defined(compose_data):
    services = compose_data["services"]
    assert "qdrant" in services, "No 'qdrant' service defined"

    qdrant = services["qdrant"]

    assert "image" in qdrant, "qdrant service missing 'image'"
    assert "qdrant" in qdrant["image"], (
        f"qdrant image '{qdrant['image']}' does not contain 'qdrant'"
    )

    assert "ports" in qdrant, "qdrant service missing 'ports'"
    assert any("6333" in str(p) for p in qdrant["ports"]), (
        "qdrant ports do not expose 6333"
    )


def test_infra_services_have_healthchecks(compose_data):
    services = compose_data["services"]
    infra_services = ["postgres", "redis", "qdrant"]
    for name in infra_services:
        svc = services[name]
        assert "healthcheck" in svc, f"{name} service is missing a healthcheck"
        assert "test" in svc["healthcheck"], f"{name} healthcheck is missing 'test'"


def test_app_service_defined(compose_data):
    services = compose_data["services"]
    assert "app" in services, "No 'app' service defined"

    app = services["app"]

    assert "build" in app, "app service missing 'build'"
    assert "ports" in app, "app service missing 'ports'"
    assert any("8000" in str(p) for p in app["ports"]), (
        "app ports do not expose 8000"
    )


def test_celery_worker_service_defined(compose_data):
    services = compose_data["services"]
    assert "celery-worker" in services, "No 'celery-worker' service defined"

    worker = services["celery-worker"]

    assert "build" in worker, "celery-worker service missing 'build'"
    command = worker.get("command", "")
    assert "celery" in str(command), (
        f"celery-worker command '{command}' does not invoke celery"
    )
    assert "workers.celery_app" in str(command), (
        f"celery-worker command '{command}' does not reference workers.celery_app"
    )


def test_app_and_worker_depend_on_infra_with_health_condition(compose_data):
    services = compose_data["services"]
    for svc_name in ["app", "celery-worker"]:
        svc = services[svc_name]
        assert "depends_on" in svc, f"{svc_name} missing 'depends_on'"
        depends_on = svc["depends_on"]
        for infra in ["postgres", "redis", "qdrant"]:
            assert infra in depends_on, (
                f"{svc_name} depends_on does not include '{infra}'"
            )
            condition = depends_on[infra].get("condition")
            assert condition == "service_healthy", (
                f"{svc_name} depends_on {infra} condition is '{condition}', "
                f"expected 'service_healthy'"
            )


def test_postgres_mounts_schema_sql(compose_data):
    services = compose_data["services"]
    postgres = services["postgres"]
    assert "volumes" in postgres, "postgres service missing 'volumes'"
    volumes = postgres["volumes"]
    schema_mounted = any("schema.sql" in str(v) for v in volumes)
    assert schema_mounted, (
        "postgres volumes do not mount schema.sql"
    )


def test_app_and_worker_have_required_env_vars(compose_data):
    services = compose_data["services"]
    required_vars = [
        "POSTGRES_URL",
        "REDIS_URL",
        "QDRANT_URL",
        "CELERY_BROKER_URL",
        "CELERY_RESULT_BACKEND",
    ]
    for svc_name in ["app", "celery-worker"]:
        svc = services[svc_name]
        assert "environment" in svc, f"{svc_name} missing 'environment'"
        env = svc["environment"]
        if isinstance(env, dict):
            env_keys = set(env.keys())
        else:
            env_keys = {item.partition("=")[0] for item in env}
        for var in required_vars:
            assert var in env_keys, (
                f"{svc_name} environment missing required variable '{var}'"
            )
