import argparse
import json
import os
import yaml
from src.config.db import get_db, init_db, DB_PATH
from src.registry import store
from src.registry.models import (
    NodeCreate, ProviderCreate, ModelCreate, AccountCreate, EndpointCreate
)

def bootstrap_from_file(config_path: str, db_path: str = DB_PATH, actor: str = "bootstrap"):
    """Reads a JSON or YAML inventory file and populates the database."""
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found: {config_path}")

    # Determine parser based on extension
    _, ext = os.path.splitext(config_path.lower())
    with open(config_path, "r", encoding="utf-8") as f:
        if ext in (".yaml", ".yml"):
            data = yaml.safe_load(f)
        else:
            data = json.load(f)

    if not data:
        print("Warning: Config file is empty. Nothing to bootstrap.")
        return

    # Ensure DB is initialized
    init_db(db_path)

    print(f"Bootstrapping database '{db_path}' from '{config_path}'...")

    with get_db(db_path) as conn:
        # 1. Providers
        providers = data.get("providers", [])
        for p in providers:
            p_model = ProviderCreate(**p)
            if store.get_provider(conn, p_model.id) is None:
                store.create_provider(conn, p_model, actor=actor, reason="bootstrap")
                print(f"  [+] Created Provider: {p_model.id}")
            else:
                print(f"  [~] Provider already exists, skipping: {p_model.id}")

        # 2. Nodes
        nodes = data.get("nodes", [])
        for n in nodes:
            n_model = NodeCreate(**n)
            if store.get_node(conn, n_model.id) is None:
                store.create_node(conn, n_model, actor=actor, reason="bootstrap")
                print(f"  [+] Created Node: {n_model.id}")
            else:
                print(f"  [~] Node already exists, skipping: {n_model.id}")

        # 3. Models
        models = data.get("models", [])
        for m in models:
            m_model = ModelCreate(**m)
            if store.get_model(conn, m_model.id) is None:
                store.create_model(conn, m_model, actor=actor, reason="bootstrap")
                print(f"  [+] Created Model: {m_model.id}")
            else:
                print(f"  [~] Model already exists, skipping: {m_model.id}")

        # 4. Accounts
        accounts = data.get("accounts", [])
        for a in accounts:
            a_model = AccountCreate(**a)
            if store.get_account(conn, a_model.id) is None:
                store.create_account(conn, a_model, actor=actor, reason="bootstrap")
                print(f"  [+] Created Account: {a_model.id}")
            else:
                print(f"  [~] Account already exists, skipping: {a_model.id}")

        # 5. Endpoints
        endpoints = data.get("endpoints", [])
        for e in endpoints:
            e_model = EndpointCreate(**e)
            if store.get_endpoint(conn, e_model.id) is None:
                store.create_endpoint(conn, e_model, actor=actor, reason="bootstrap")
                print(f"  [+] Created Endpoint: {e_model.id}")
            else:
                print(f"  [~] Endpoint already exists, skipping: {e_model.id}")

    print("Bootstrap completed successfully!")

def main():
    parser = argparse.ArgumentParser(description="Bootstrap LiteLLM Control Plane topology database.")
    parser.add_argument("--config", required=True, help="Path to JSON or YAML inventory config file.")
    parser.add_argument("--db", default=DB_PATH, help=f"Path to SQLite database file. Default: {DB_PATH}")
    args = parser.parse_args()

    bootstrap_from_file(args.config, args.db)

if __name__ == "__main__":
    main()
