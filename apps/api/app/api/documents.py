import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext, require_permission
from app.core.permissions import Permission
from app.db.session import get_db
from app.models.enterprise import Document, DocumentChunk
from app.schemas.documents import DocumentCreate, DocumentOut
from app.services.audit import record_event
from app.services.chunking import chunk_text
from app.services.embeddings import embed

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("", response_model=DocumentOut, status_code=201)
async def ingest_document(
    payload: DocumentCreate,
    auth: AuthContext = Depends(require_permission(Permission.DOCUMENT_WRITE)),
    db: AsyncSession = Depends(get_db),
) -> Document:
    document = Document(
        organization_id=auth.organization_id,
        customer_id=payload.customer_id,
        title=payload.title,
        source=payload.source,
        content=payload.content,
    )
    db.add(document)
    await db.flush()

    for index, chunk in enumerate(chunk_text(document.content)):
        db.add(
            DocumentChunk(
                organization_id=auth.organization_id,
                document_id=document.id,
                chunk_index=index,
                content=chunk,
                embedding=embed(chunk),
            )
        )

    await db.commit()
    await db.refresh(document)

    await record_event(
        db,
        organization_id=auth.organization_id,
        user_id=auth.user_id,
        action="document.ingest",
        resource=f"document:{document.id}",
    )
    return document


@router.get("", response_model=list[DocumentOut])
async def list_documents(
    auth: AuthContext = Depends(require_permission(Permission.DOCUMENT_READ)),
    db: AsyncSession = Depends(get_db),
) -> list[Document]:
    result = await db.execute(
        select(Document).where(Document.organization_id == auth.organization_id)
    )
    return list(result.scalars().all())


@router.get("/{document_id}", response_model=DocumentOut)
async def get_document(
    document_id: uuid.UUID,
    auth: AuthContext = Depends(require_permission(Permission.DOCUMENT_READ)),
    db: AsyncSession = Depends(get_db),
) -> Document:
    result = await db.execute(
        select(Document).where(
            Document.id == document_id, Document.organization_id == auth.organization_id
        )
    )
    document = result.scalar_one_or_none()
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="document not found")
    return document
