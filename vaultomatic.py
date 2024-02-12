import time
import logging
import hvac
import enum

from typing import Annotated, Any
from pydantic import Field, ValidationInfo, BeforeValidator
from pydantic_settings import BaseSettings, SettingsConfigDict
import requests.exceptions


def maybe_split_str(v, info: ValidationInfo):
    if isinstance(v, str):
        return v.split()
    return v


# via https://github.com/pydantic/pydantic/issues/1458#issuecomment-789051576
StringList = Annotated[str | list[str], BeforeValidator(maybe_split_str)]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="VOM_")

    vault_addrs: StringList = Field([], alias="VAULT_ADDRS")
    secret_shares: int = 5
    secret_threshold: int = 3


SETTINGS = Settings()
LOG = logging.getLogger(__name__)


class VaultManager:
    def __init__(self, settings):
        self.settings = settings
        self.initialized = False
        self.nodes = {}
        self.keys = {}

        self.create_clients()

    def create_clients(self):
        for addr in self.settings.vault_addrs:
            self.nodes[addr] = hvac.Client(addr)

    def init_vault(self):
        leader = next(iter(self.nodes))
        node = self.nodes[leader]
        self.keys = node.sys.initialize(
            secret_shares=self.settings.secret_shares,
            secret_threshold=self.settings.secret_threshold,
        )
        self.unseal_node(leader)

        for node in self.nodes:
            if node != leader:
                for tries in range(3):
                    try:
                        self.nodes[node].sys.join_raft_cluster(leader_api_addr=leader)
                        break
                    except hvac.exceptions.InternalServerError as err:
                        LOG.error(
                            f"node {node} failed to join cluster (will retry): {err}"
                        )
                        time.sleep(2)
                else:
                    LOG.error(f"node {node} failed to join cluster; giving up")

    def unseal_node(self, node):
        LOG.warning(f"unsealing node {node}")
        keys = self.keys["keys"][: self.settings.secret_threshold]
        self.nodes[node].sys.submit_unseal_keys(keys)

    def monitor(self):
        if not self.nodes:
            raise ValueError("no nodes")

        while True:
            try:
                initialized = [
                    k for k in self.nodes if self.nodes[k].seal_status["initialized"]
                ]
                break
            except Exception:
                pass

            time.sleep(1)

        if len(initialized) not in [0, len(self.nodes)]:
            raise ValueError("unexpected cluster state")

        if not initialized:
            self.init_vault()

        while True:
            for node in self.nodes:
                try:
                    if self.nodes[node].seal_status["sealed"]:
                        if not self.keys:
                            LOG.info(f"node {node} is sealed; no keys available")
                            continue

                        self.unseal_node(node)
                except requests.exceptions.ConnectionError as err:
                    LOG.error(f"unable to determine seal status of node {node}: {err}")

            time.sleep(5)


logging.basicConfig(level=logging.INFO)
settings = Settings()
vm = VaultManager(settings)
vm.monitor()
