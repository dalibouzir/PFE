from typing import List

from pydantic import BaseModel

from app.schemas.cooperative import CooperativeRead
from app.schemas.institution import InstitutionRead


class InstitutionWithCooperativesRead(InstitutionRead):
    cooperatives: List[CooperativeRead]


class HierarchyOverviewRead(BaseModel):
    institutions: List[InstitutionWithCooperativesRead]
    independent_cooperatives: List[CooperativeRead]
