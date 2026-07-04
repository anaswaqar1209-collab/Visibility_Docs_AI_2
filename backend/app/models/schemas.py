from pydantic import BaseModel, Field
from typing import Optional, Any
from datetime import datetime
from enum import Enum


class DocumentType(str, Enum):
    INVOICE = "invoice"
    PURCHASE_ORDER = "purchase_order"
    CONTRACT = "contract"
    QUOTATION = "quotation"
    HR_DOCUMENT = "hr_document"
    AUDIT_REPORT = "audit_report"
    QUALITY_REPORT = "quality_report"
    CERTIFICATE = "certificate"
    MAINTENANCE_REPORT = "maintenance_report"
    FINANCIAL_STATEMENT = "financial_statement"
    ENGINEERING_DRAWING = "engineering_drawing"
    SOP = "sop"
    OTHER = "other"


class DocumentStatus(str, Enum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    OCR_DONE = "ocr_done"
    CLASSIFIED = "classified"
    EXTRACTED = "extracted"
    PROCESSED = "processed"
    FAILED = "failed"


class DocumentResponse(BaseModel):
    id: str
    organization_id: str
    title: str
    document_type: Optional[str] = None
    status: DocumentStatus = DocumentStatus.UPLOADED
    file_url: Optional[str] = None
    file_hash: Optional[str] = None
    page_count: Optional[int] = None
    language: Optional[str] = None
    file_size: Optional[int] = None
    raw_text: Optional[str] = None
    error_message: Optional[str] = None
    created_at: str
    updated_at: str


class DocumentListResponse(BaseModel):
    documents: list[DocumentResponse]
    total: int


class UploadResponse(BaseModel):
    id: str
    title: str
    status: str
    message: str


class ClassificationResponse(BaseModel):
    document_id: str = ""
    document_type: DocumentType = DocumentType.OTHER
    agent_type: Optional[str] = None
    confidence: float = 0.0
    reasoning: str = ""
    language: Optional[str] = None
    estimated_quality: Optional[str] = None


class ExtractionResponse(BaseModel):
    document_id: str
    document_type: DocumentType
    extracted_data: dict[str, Any]
    confidence: float


class SearchRequest(BaseModel):
    query: str
    organization_id: str
    document_type: Optional[str] = None
    limit: int = 10
    offset: int = 0


class SearchResult(BaseModel):
    document_id: str
    document_title: str
    document_type: Optional[str] = None
    chunk_text: str
    page_number: Optional[int] = None
    score: float
    metadata: Optional[dict] = None


class SearchResponse(BaseModel):
    results: list[SearchResult]
    total: int
    query: str


class ChatRequest(BaseModel):
    document_id: str
    organization_id: str
    question: str
    chat_history: Optional[list[dict]] = None
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    answer: str
    sources: list[dict]
    document_id: str
    history: list[dict] = []


class ProcessRequest(BaseModel):
    organization_id: str


class ProcessResponse(BaseModel):
    document_id: str
    status: str
    classification: Optional[ClassificationResponse] = None
    extraction: Optional[ExtractionResponse] = None
