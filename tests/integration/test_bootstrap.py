import os
import tempfile
import pytest
from src.config.db import get_db
from src.config.bootstrap import bootstrap_from_file
from src.registry import store

def test_bootstrap_from_inventory_yaml():
    # Setup temporary database
    fd, db_path = tempfile.mkstemp()
    os.close(fd)

    config_path = os.path.join("examples", "inventory.yaml")

    try:
        # Run bootstrap
        bootstrap_from_file(config_path, db_path=db_path, actor="bootstrap-test")

        # Verify the contents in the database
        with get_db(db_path) as conn:
            nodes = store.list_nodes(conn)
            providers = store.list_providers(conn)
            models = store.list_models(conn)
            accounts = store.list_accounts(conn)
            endpoints = store.list_endpoints(conn)

            assert len(nodes) == 3
            assert len(providers) == 3
            assert len(models) == 3
            assert len(accounts) == 3
            assert len(endpoints) == 3

            # Verify specific node
            kr_node = store.get_node(conn, "node-kr-1")
            assert kr_node is not None
            assert kr_node.region == "ap-northeast-2"
            assert kr_node.role == "proxy"

            # Verify specific endpoint routing properties
            ep_llama3 = store.get_endpoint(conn, "ep-kr-llama3")
            assert ep_llama3 is not None
            assert ep_llama3.priority == 2
            assert ep_llama3.weight == 50

            # Verify audit logs
            logs = store.list_audit_logs(conn)
            assert len(logs) > 0
            actors = {log["actor"] for log in logs}
            assert "bootstrap-test" in actors

        # Re-run bootstrap to ensure idempotency / graceful skips
        bootstrap_from_file(config_path, db_path=db_path, actor="bootstrap-test-again")

        with get_db(db_path) as conn:
            # Counts should remain the same
            assert len(store.list_nodes(conn)) == 3
            assert len(store.list_endpoints(conn)) == 3

    finally:
        # Clean up
        try:
            os.remove(db_path)
        except OSError:
            pass
