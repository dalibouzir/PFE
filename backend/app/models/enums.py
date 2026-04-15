from enum import Enum


class UserRole(str, Enum):
    ADMIN = "admin"
    MANAGER = "manager"


class UserStatus(str, Enum):
    ACTIVE = "active"
    DISABLED = "disabled"


class CooperativeStatus(str, Enum):
    ACTIVE = "active"
    ONBOARDING = "onboarding"
    SUSPENDED = "suspended"


class MemberStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SEASONAL = "seasonal"


class InputStatus(str, Enum):
    PENDING = "pending"
    QUALITY_CONTROL = "quality_control"
    VALIDATED = "validated"


class BatchStatus(str, Enum):
    CREATED = "created"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class ProcessStepStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FLAGGED = "flagged"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
