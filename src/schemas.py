"""Pydantic models for the Construction Inventory Bot."""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any

from pydantic import BaseModel, Field


class UserRole(str, Enum):
    """User roles in the system."""
    ADMIN = "admin"
    STAFF = "staff"
    VIEWER = "viewer"


class MovementType(str, Enum):
    """Types of stock movements."""
    IN = "In"
    OUT = "Out"
    ADJUST = "Adjust"


class MovementStatus(str, Enum):
    """Status of stock movements."""
    POSTED = "Posted"
    REQUESTED = "Requested"
    VOIDED = "Voided"
    APPROVED = "Approved"
    PENDING_APPROVAL = "Pending Approval"  # New status for items awaiting approval
    REJECTED = "Rejected"  # New status for rejected items


class BatchFormat(str, Enum):
    """Format types for batch input."""
    SINGLE = "single"
    NEWLINE = "newline"
    SEMICOLON = "semicolon"
    COMMA_SEPARATED = "comma_separated"
    MIXED = "mixed"


class BatchErrorType(str, Enum):
    """Types of batch processing errors."""
    VALIDATION = "validation"
    DATABASE = "database"
    ROLLBACK = "rollback"
    PARSING = "parsing"


class Unit(BaseModel):
    """Unit of measurement."""
    name: str
    conversion_factor: float = Field(gt=0, description="Conversion factor to base unit")


class Item(BaseModel):
    """Inventory item."""
    name: str = Field(..., description="Item name")
    sku: Optional[str] = None  # Optional SKU for future use
    description: Optional[str] = None  # Aliases field
    # base_unit field has been removed from Airtable
    unit_size: float = Field(default=1.0, gt=0, description="Size of each unit (e.g., 20 for 20ltr cans)")
    unit_type: str = Field(default="piece", description="Type of unit (e.g., 'ltrs', 'kg', 'm', 'piece')")
    total_volume: Optional[float] = Field(default=None, description="Auto-calculated total volume (unit_size × quantity)")
    units: List[Unit]
    on_hand: float = 0.0
    threshold: Optional[float] = None  # Reorder Level field
    location: Optional[str] = None  # Preferred Location field
    category: Optional[str] = None  # Category field
    large_qty_threshold: Optional[float] = None  # Large Qty Threshold field
    is_active: Optional[bool] = True  # Is Active field
    last_stocktake_date: Optional[str] = None  # Last Stocktake Date field
    last_stocktake_by: Optional[str] = None  # Last Stocktake By field
    
    def get_total_volume(self) -> float:
        """Calculate total volume as unit_size × on_hand quantity."""
        return self.unit_size * self.on_hand


class StockMovement(BaseModel):
    """Stock movement record."""
    id: Optional[str] = None
    item_name: str  # Changed from sku to item_name
    movement_type: MovementType
    quantity: float
    unit: str
    signed_base_quantity: float
    unit_size: Optional[float] = Field(default=None, description="Size of each unit for enhanced items")
    unit_type: Optional[str] = Field(default=None, description="Type of unit for enhanced items")
    location: Optional[str] = None
    note: Optional[str] = None
    status: MovementStatus = MovementStatus.POSTED
    user_id: str
    user_name: str
    timestamp: datetime = Field(default_factory=datetime.now)
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    reason: Optional[str] = None  # Reason field
    source: str = "Telegram"  # Source field
    driver_name: Optional[str] = None  # Driver's Name field
    from_location: Optional[str] = None  # From/To Location field (source for IN, destination for OUT)
    to_location: Optional[str] = None  # To Location field (destination for OUT/ADJUST)
    project: Optional[str] = None  # Project field
    batch_id: Optional[str] = None  # New field to track which batch this movement belongs to
    category: Optional[str] = None  # Category field for stock movements


class BatchParseResult(BaseModel):
    """Result of parsing a batch of stock movements."""
    format: BatchFormat
    movements: List[StockMovement]
    total_entries: int
    valid_entries: int
    errors: List[str] = []
    is_valid: bool = True
    global_parameters: Dict[str, str] = Field(default_factory=dict)


class BatchError(BaseModel):
    """Detailed error information for batch processing."""
    error_type: BatchErrorType
    message: str
    entry_index: Optional[int] = None
    entry_details: Optional[str] = None
    suggestion: Optional[str] = None
    severity: str = "ERROR"  # WARNING, ERROR, CRITICAL


class BatchResult(BaseModel):
    """Result of processing a batch of stock movements."""
    total_entries: int
    successful_entries: int
    failed_entries: int
    success_rate: float
    movements_created: List[str] = []  # List of created movement IDs
    errors: List[BatchError] = []
    rollback_performed: bool = False
    processing_time_seconds: Optional[float] = None
    summary_message: str
    global_parameters: Dict[str, str] = Field(default_factory=dict)  # Global parameters used in the batch


class BatchApproval(BaseModel):
    """Batch approval request."""
    batch_id: str  # Unique identifier for this batch
    movements: List[StockMovement]  # List of movements in this batch
    user_id: str
    user_name: str
    timestamp: datetime = Field(default_factory=datetime.now)
    chat_id: int
    status: str = "Pending"  # Pending, Approved, Rejected
    before_levels: Dict[str, float] = Field(default_factory=dict)  # Stock levels before batch processing
    after_levels: Dict[str, float] = Field(default_factory=dict)   # Stock levels after batch processing
    failed_entries: List[Dict[str, Any]] = Field(default_factory=list)  # Entries that failed processing
    message_id: Optional[int] = None  # Telegram message ID of the approval request for updating


class Command(BaseModel):
    """Parsed Telegram command."""
    command: str
    args: List[str] = []
    chat_id: int
    user_id: int
    user_name: str
    message_id: int
    update_id: int


class TelegramUser(BaseModel):
    """Telegram user information."""
    user_id: int
    username: Optional[str] = None
    first_name: str
    last_name: Optional[str] = None
    role: UserRole = UserRole.VIEWER
    is_active: bool = True
    allowed_chats: Optional[str] = None  # Allowed Chats field


class ApprovalRequest(BaseModel):
    """Approval request for large movements."""
    movement_id: str
    sku: str
    quantity: float
    unit: str
    user_name: str
    timestamp: datetime
    chat_id: int
    message_id: int


class DailyReport(BaseModel):
    """Daily inventory report."""
    date: str
    total_in: float
    total_out: float
    movements_count: int
    low_stock_items: List[str]
    pending_approvals: int


class Response(BaseModel):
    """Generic API response."""
    success: bool
    message: str
    data: Optional[dict] = None


class StocktakeAuditRecord(BaseModel):
    """Audit record for a single inventory item change."""
    batch_id: str
    date: str  # ISO date string
    logged_by: str  # Comma-separated names
    item_name: str
    counted_qty: float
    previous_on_hand: float
    new_on_hand: float
    applied_at: datetime
    applied_by: str
    item: Optional[str] = None  # Item record link
    notes: Optional[str] = None  # Notes field
    discrepancy: Optional[float] = None  # Discrepancy field