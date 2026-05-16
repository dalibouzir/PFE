from enum import Enum


class UserRole(str, Enum):
    SUPER_ADMIN = "super_admin"
    INSTITUTION_ADMIN = "institution_admin"
    ADMIN = "admin"
    OWNER = "owner"
    MANAGER = "manager"
    VIEWER = "viewer"


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


class FarmerAdvanceStatus(str, Enum):
    ACTIVE = "active"
    CANCELLED = "cancelled"


class TreasuryTransactionType(str, Enum):
    INCOME = "income"
    EXPENSE = "expense"


class TreasuryTransactionStatus(str, Enum):
    NON_ENREGISTRE = "non_enregistre"
    ENREGISTRE_SANS_JUSTIFICATIF = "enregistre_sans_justificatif"
    ENREGISTRE_COMPLET = "enregistre_complet"
    CANCELLED = "cancelled"
    RECORDED = "RECORDED"


class BatchStatus(str, Enum):
    CREATED = "created"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class ProcessStepStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FLAGGED = "flagged"


class PreHarvestStepStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class CommercialCatalogStatus(str, Enum):
    ACTIVE = "active"
    HIDDEN = "hidden"


class CommercialOrderStatus(str, Enum):
    RECEIVED = "received"
    CONFIRMED = "confirmed"
    PREPARING = "preparing"
    READY = "ready"
    DELIVERED = "delivered"
    PAID = "paid"
    REFUSED = "refused"


class InvoiceStatus(str, Enum):
    PENDING = "pending"
    PAID = "paid"
