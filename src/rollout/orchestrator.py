import hashlib
import json
import logging
import os
import sqlite3
import time
import yaml
from typing import Any, Dict, List, Optional
from src.config.generator import ConfigGenerator
from src.registry import store
from src.registry.key_manager import get_node_url, get_node_master_key
from src.adapters.litellm_adapter import LiteLLMAdapter

logger = logging.getLogger("rollout_orchestrator")

class RolloutOrchestrator:
    def __init__(self, generator: ConfigGenerator):
        self.generator = generator
        self.node_config_paths: Dict[str, str] = {}

    def deploy_config(
        self,
        conn: sqlite3.Connection,
        node_id: str,
        config_filepath: str,
        timeout_sec: float = 10.0,
        poll_interval_sec: float = 1.0,
        mock_adapter: Optional[Any] = None  # Hook for testing verification flow
    ) -> Dict[str, Any]:
        """
        Deploy configuration to a node: generate -> validate -> apply -> verify -> rollback on fail.
        """
        import uuid
        rollout_id = f"roll-{uuid.uuid4().hex[:8]}"

        node = store.get_node(conn, node_id)
        if not node:
            raise ValueError(f"Node {node_id} not found.")

        # 1. Generate Config
        try:
            config_dict = self.generator.generate_config(conn, node_id)
            config_yaml = yaml.safe_dump(config_dict, default_flow_style=False)
        except Exception as e:
            logger.error(f"Config generation failed for node {node_id}: {e}")
            raise RuntimeError(f"Config generation failed: {e}")

        # 2. Validate Config (Verify we can dump it and it is valid YAML)
        try:
            yaml.safe_load(config_yaml)
        except Exception as e:
            logger.error(f"Generated config is not valid YAML: {e}")
            raise RuntimeError(f"Config validation failed: {e}")

        config_version = hashlib.sha256(config_yaml.encode("utf-8")).hexdigest()

        # 3. Create Rollout record as pending
        store.create_rollout(
            conn,
            rollout_id=rollout_id,
            node_id=node_id,
            config_version=config_version,
            status="pending",
            config_content=config_yaml
        )

        # Backup current config file if it exists to support local restore on immediate write fail
        backup_content: Optional[str] = None
        if os.path.exists(config_filepath):
            try:
                with open(config_filepath, "r", encoding="utf-8") as f:
                    backup_content = f.read()
            except Exception:
                pass

        # 4. Apply (Write new config to disk)
        try:
            self.node_config_paths[node_id] = config_filepath
            store.update_rollout_status(conn, rollout_id, "applying")
            os.makedirs(os.path.dirname(os.path.abspath(config_filepath)), exist_ok=True)
            with open(config_filepath, "w", encoding="utf-8") as f:
                f.write(config_yaml)
        except Exception as e:
            store.update_rollout_status(conn, rollout_id, "failed", f"File write error: {e}")
            raise RuntimeError(f"Failed to write config file to disk: {e}")

        # 5. Verify (Poll proxy health readiness)
        url = get_node_url(node.host, node.port)
        master_key = get_node_master_key(node.id)
        adapter = mock_adapter or LiteLLMAdapter(url, master_key)

        start_time = time.time()
        verified = False
        while time.time() - start_time < timeout_sec:
            if adapter.check_health():
                verified = True
                break
            time.sleep(poll_interval_sec)

        if verified:
            logger.info(f"Rollout {rollout_id} successfully verified for node {node_id}.")
            store.update_rollout_status(conn, rollout_id, "success")
            return {
                "rollout_id": rollout_id,
                "status": "success",
                "config_version": config_version
            }
        else:
            logger.warning(f"Rollout {rollout_id} verification failed. Initiating rollback.")
            store.update_rollout_status(conn, rollout_id, "failed", "Verification timed out.")
            
            # 6. Rollback
            rollback_id = f"roll-back-{uuid.uuid4().hex[:8]}"
            prev_success = store.get_latest_success_rollout(conn, node_id)
            
            if prev_success:
                logger.info(f"Restoring previous successful config version {prev_success.config_version}.")
                try:
                    with open(config_filepath, "w", encoding="utf-8") as f:
                        f.write(prev_success.config_content)
                    
                    store.create_rollout(
                        conn,
                        rollout_id=rollback_id,
                        node_id=node_id,
                        config_version=prev_success.config_version,
                        status="rolled_back",
                        config_content=prev_success.config_content,
                        error_message=f"Rolled back from failed rollout {rollout_id}"
                    )
                except Exception as rollback_err:
                    logger.critical(f"Failed to restore previous config file: {rollback_err}")
            else:
                # No previous success, restore from file backup if possible, otherwise leave empty/delete
                logger.info("No previous successful rollout found in database to roll back to.")
                if backup_content is not None:
                    try:
                        with open(config_filepath, "w", encoding="utf-8") as f:
                            f.write(backup_content)
                    except Exception:
                        pass

            raise RuntimeError(f"Rollout verification failed. Node rolled back to previous state.")

    def detect_drift(
        self,
        conn: sqlite3.Connection,
        node_id: str,
        config_filepath: str
    ) -> Dict[str, Any]:
        """
        Compare active disk configuration and sync keys against the desired control plane state.
        """
        node = store.get_node(conn, node_id)
        if not node:
            raise ValueError(f"Node {node_id} not found.")

        stale_config = False
        reason = None

        # 1. Config file check
        if not os.path.exists(config_filepath):
            stale_config = True
            reason = "Config file does not exist on disk."
            config_dict_disk = {}
        else:
            try:
                with open(config_filepath, "r", encoding="utf-8") as f:
                    config_dict_disk = yaml.safe_load(f) or {}
                
                # Generate desired config
                desired_config = self.generator.generate_config(conn, node_id)
                
                # Check for semantic equality (ignore ordering)
                if json.dumps(config_dict_disk, sort_keys=True) != json.dumps(desired_config, sort_keys=True):
                    stale_config = True
                    reason = "Disk config contents do not match database desired state."
            except Exception as e:
                stale_config = True
                reason = f"Failed to read/parse disk config: {e}"
                config_dict_disk = {}

        # 2. Virtual keys check
        db_keys = store.list_consumer_keys(conn)
        node_keys = [k for k in db_keys if k.node_id == node_id]

        active_consumers = [c for c in store.list_consumers(conn) if c.status == "active"]
        active_consumer_ids = {c.id for c in active_consumers}

        missing_keys = []
        orphaned_keys = []

        # Check for missing keys (active consumers without a key on this node)
        node_consumer_ids = {k.consumer_id for k in node_keys if k.status == "active"}
        for cid in active_consumer_ids:
            if cid not in node_consumer_ids:
                missing_keys.append(cid)

        # Check for orphaned keys (keys on this node for inactive/deleted consumers)
        for key in node_keys:
            if key.consumer_id not in active_consumer_ids:
                orphaned_keys.append(key.consumer_id)

        has_key_drift = len(missing_keys) > 0 or len(orphaned_keys) > 0

        return {
            "node_id": node_id,
            "config_drift": stale_config,
            "config_drift_reason": reason,
            "key_drift": has_key_drift,
            "missing_keys": missing_keys,
            "orphaned_keys": orphaned_keys,
            "drift_detected": stale_config or has_key_drift
        }

    def reconcile_node(
        self,
        conn: sqlite3.Connection,
        node_id: str,
        config_filepath: Optional[str] = None,
        timeout_sec: float = 10.0,
        mock_adapter: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Detect config and key drift for a node, and automatically re-align it
        with the desired control plane state.
        """
        path = config_filepath or self.node_config_paths.get(node_id)
        if not path:
            return {"reconciled": False, "reason": "No config path registered for this node yet."}

        drift = self.detect_drift(conn, node_id, path)
        if not drift["drift_detected"]:
            return {"reconciled": False, "reason": "No drift detected"}

        logger.info(f"Drift detected on node {node_id}. Initiating auto-reconciliation. Drift details: {drift}")

        # Increment Prometheus metric
        try:
            from src.metrics.pipeline import DRIFT_DETECTION_TOTAL
            DRIFT_DETECTION_TOTAL.labels(node_id=node_id).inc()
        except Exception as me:
            logger.error(f"Failed to record drift detection metric: {me}")

        # Audit drift event
        store.log_audit(
            conn,
            actor="reconcile-worker",
            action="drift_detected",
            target_type="node",
            target_id=node_id,
            changes=drift,
            reason="Periodic drift detection check"
        )

        reconciled_config = False
        reconciled_keys = False

        # 1. Resolve Config Drift
        if drift["config_drift"]:
            try:
                logger.info(f"Reconciling config drift for node {node_id}...")
                self.deploy_config(conn, node_id, config_filepath, timeout_sec=timeout_sec, mock_adapter=mock_adapter)
                reconciled_config = True
            except Exception as e:
                logger.error(f"Failed to reconcile config drift for node {node_id}: {e}")

        # 2. Resolve Key Drift
        if drift["key_drift"]:
            try:
                from src.registry import key_manager
                from src.registry.key_manager import _PENDING_KEY_PREFIX
                
                # Sync missing keys
                for cid in drift["missing_keys"]:
                    logger.info(f"Reconciling missing key for consumer {cid} on node {node_id}...")
                    key_manager.sync_consumer_to_all_nodes(conn, cid)
                
                # Revoke and delete orphaned keys
                for cid in drift["orphaned_keys"]:
                    logger.info(f"Reconciling orphaned key for consumer {cid} on node {node_id}...")
                    key = store.get_consumer_key(conn, cid, node_id)
                    if key:
                        is_placeholder = key.virtual_key.startswith(_PENDING_KEY_PREFIX) or key.status == "pending-sync"
                        if not is_placeholder:
                            node = store.get_node(conn, node_id)
                            if node:
                                master_key = get_node_master_key(node.id)
                                url = get_node_url(node.host, node.port)
                                adapter = LiteLLMAdapter(url, master_key)
                                try:
                                    adapter.delete_key(key.virtual_key)
                                except Exception as err:
                                    logger.warning(f"Failed to revoke orphaned key {key.virtual_key} on node {node_id}: {err}")
                        store.delete_consumer_key(conn, cid, node_id, actor="reconcile-worker", reason="orphaned key cleanup")
                reconciled_keys = True
            except Exception as e:
                logger.error(f"Failed to reconcile key drift for node {node_id}: {e}")

        return {
            "reconciled": True,
            "reconciled_config": reconciled_config,
            "reconciled_keys": reconciled_keys,
            "drift_details": drift
        }
