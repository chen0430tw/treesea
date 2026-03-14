# base.py
from __future__ import annotations
from abc import ABC, abstractmethod
from moroz.contracts.request import CollapseRequest
from moroz.contracts.result import CollapseResult

class CollapseBackend(ABC):
    @abstractmethod
    def submit(self, req: CollapseRequest) -> CollapseResult:
        raise NotImplementedError
