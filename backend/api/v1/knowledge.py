from __future__ import annotations

from typing import List, Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...models.knowledge_models import KnowledgeDocument
from ...schemas.knowledge_schemas import (
    DocumentCreate,
    DocumentRead,
    KnowledgeQueryRequest,
    KnowledgeQueryResult,
)
from ...services import auth_service, rag_service

router = APIRouter(
    prefix="/api/v1/knowledge",
    tags=["knowledge"],
    dependencies=[Depends(auth_service.get_current_user)],
)


@router.post("/upload", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    current_user=Depends(auth_service.get_current_user),
    db: Session = Depends(get_db),
):
    """
    Upload and ingest a document file (txt, md, json, etc.).
    Extracts text, splits into chunks, computes embeddings, and stores in tenant vector collection.
    """
    content_bytes = await file.read()
    if not content_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty",
        )

    doc_title = (title or "").strip() or file.filename or "Uploaded Document"
    text_content = rag_service.extract_text_from_file(
        content_bytes, filename=file.filename, content_type=file.content_type
    )

    if not text_content.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No readable text could be extracted from the uploaded file",
        )

    try:
        doc = await rag_service.ingest_document(
            db=db,
            user_id=current_user.id,
            title=doc_title,
            content=text_content,
            filename=file.filename,
            content_type=file.content_type,
            doc_metadata={"source": "file_upload", "original_filename": file.filename},
        )
        return doc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Document ingestion failed: {exc}",
        ) from exc


@router.post("/documents", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
async def create_document(
    payload: DocumentCreate,
    current_user=Depends(auth_service.get_current_user),
    db: Session = Depends(get_db),
):
    """
    Ingest a new text document into the tenant knowledge base.
    """
    try:
        doc = await rag_service.ingest_document(
            db=db,
            user_id=current_user.id,
            title=payload.title,
            content=payload.content,
            doc_metadata=payload.metadata or {},
        )
        return doc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Document ingestion failed: {exc}",
        ) from exc


@router.get("/documents", response_model=List[DocumentRead])
async def list_documents(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user=Depends(auth_service.get_current_user),
    db: Session = Depends(get_db),
):
    """
    List all knowledge base documents owned by the authenticated tenant.
    """
    docs = (
        db.query(KnowledgeDocument)
        .filter(KnowledgeDocument.user_id == current_user.id)
        .order_by(KnowledgeDocument.updated_at.desc(), KnowledgeDocument.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return docs


@router.get("/documents/{document_id}", response_model=DocumentRead)
async def get_document(
    document_id: int,
    current_user=Depends(auth_service.get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retrieve document details for the authenticated tenant.
    """
    doc = (
        db.query(KnowledgeDocument)
        .filter(
            KnowledgeDocument.id == document_id,
            KnowledgeDocument.user_id == current_user.id,
        )
        .first()
    )
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    return doc


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: int,
    current_user=Depends(auth_service.get_current_user),
    db: Session = Depends(get_db),
):
    """
    Delete a document and purge its vectors from Chroma.
    """
    deleted = await rag_service.delete_document(
        db=db, user_id=current_user.id, document_id=document_id
    )
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/query", response_model=List[KnowledgeQueryResult])
async def query_knowledge(
    payload: KnowledgeQueryRequest,
    current_user=Depends(auth_service.get_current_user),
):
    """
    Query the authenticated tenant's knowledge base using semantic vector search.
    """
    try:
        results = await rag_service.retrieve_knowledge(
            user_id=current_user.id,
            query=payload.query,
            top_k=payload.top_k,
            document_id=payload.document_id,
        )
        return results
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Semantic query failed: {exc}",
        ) from exc
