"""Read-only catalog for the repository's versioned JSON Schema contracts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ContractDescriptor:
    contract_id: str
    contract_version: str
    path: Path


class ContractCatalog:
    """Loads schema identity/version metadata and rejects ambiguous catalogs.

    This catalog is routing metadata, not a partial JSON Schema validator.
    Callers must not send a payload to a privileged boundary merely because its
    contract ID and version were found here.
    """

    def __init__(self, contracts_root: Path) -> None:
        root = contracts_root.resolve()
        if not root.is_dir():
            raise ValueError("contracts root does not exist")
        descriptors: dict[str, ContractDescriptor] = {}
        for path in sorted(root.rglob("*.schema.json")):
            schema = json.loads(path.read_text(encoding="utf-8"))
            contract_id = schema.get("$id")
            version = schema.get("properties", {}).get(
                "contract_version", {}
            ).get("const")
            if not isinstance(contract_id, str) or not contract_id:
                raise ValueError(f"contract has no stable $id: {path}")
            if not isinstance(version, str) or not version:
                raise ValueError(f"contract has no fixed version: {path}")
            if contract_id in descriptors:
                raise ValueError(f"duplicate contract ID: {contract_id}")
            descriptors[contract_id] = ContractDescriptor(
                contract_id=contract_id,
                contract_version=version,
                path=path.relative_to(root),
            )
        if not descriptors:
            raise ValueError("contract catalog is empty")
        self._descriptors = descriptors

    @property
    def count(self) -> int:
        return len(self._descriptors)

    @property
    def contract_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._descriptors))

    def get(self, contract_id: str) -> ContractDescriptor | None:
        return self._descriptors.get(contract_id)
