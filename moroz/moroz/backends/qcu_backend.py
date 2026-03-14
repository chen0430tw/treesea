# qcu_backend.py
from __future__ import annotations
from moroz.contracts.request import CollapseRequest
from moroz.contracts.result import CollapseResult
from moroz.adapters.request_mapper import map_request
from moroz.adapters.result_adapter import adapt_runtime_result
from .base import CollapseBackend
from qcu.runtime.qcu_runner import run_qcu

class QCUBackend(CollapseBackend):
    def submit(self, req: CollapseRequest) -> CollapseResult:
        runtime_cfg = map_request(req)
        runtime_result = run_qcu(runtime_cfg)
        return adapt_runtime_result(req.request_id, runtime_result)
