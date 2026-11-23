"""Private input PDFs, distinct from generated LaTeX resume revisions."""

from hashlib import sha256
from typing import Annotated
from urllib.parse import unquote
from uuid import UUID, uuid4

from fastapi import APIRouter, Header, HTTPException, Query, Request, Response
from pydantic import BeforeValidator
from sqlalchemy import delete, func, insert, select, update
from starlette.concurrency import run_in_threadpool

from .candidate import Draft, mutate
from .candidate_contracts import ResumeEdit, Short, Step, Version
from .controls import Key, Result
from .routes import Owner
from .security import seal, tenant, unseal
from .tables import uploaded_resumes as files

resumes_api = APIRouter(prefix="/api/v1/candidate/resumes")
Revision = Annotated[int, Query(ge=0)]
HeaderLabel = Annotated[Short, BeforeValidator(unquote)]
MAX_PDF = 5 * 1024 * 1024


class Uploaded(Version):
    resume_id: UUID


@resumes_api.post(
    "",
    status_code=201,
    response_model=Uploaded,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {"application/pdf": {"schema": {"type": "string", "format": "binary"}}},
        }
    },
)
async def upload(
    request: Request,
    owner: Owner,
    key: Key,
    revision: Revision,
    label: Annotated[HeaderLabel, Header(alias="X-Resume-Label")],
    target_role: Annotated[HeaderLabel | None, Header(alias="X-Resume-Role")] = None,
) -> Result:
    if request.headers.get("content-type", "").split(";")[0].strip() != "application/pdf":
        raise HTTPException(415, "Upload a PDF.")
    data = bytearray()
    async for chunk in request.stream():
        if len(data) + len(chunk) > MAX_PDF:
            raise HTTPException(413, "PDF exceeds 5 MiB.")
        data.extend(chunk)
    if not data.startswith(b"%PDF-") or not data.rstrip().endswith(b"%%EOF"):
        raise HTTPException(422, "Expected a PDF with a header and end marker.")
    inputs = {
        "revision": revision,
        "label": label,
        "target_role": target_role,
        "sha256": sha256(data).hexdigest(),
    }

    def change(draft: Draft) -> Result:
        if draft.conn.execute(select(func.count()).select_from(files)).scalar_one() >= 20:
            raise HTTPException(409, "Remove a resume before adding another (limit 20).")
        rid = uuid4()
        iv, sealed = seal(draft.key, owner, f"candidate-resume:{rid}", bytes(data))
        draft.conn.execute(
            insert(files).values(
                id=rid,
                user_id=owner,
                label=label,
                target_role=target_role,
                byte_size=len(data),
                ciphertext=iv + sealed,
            )
        )
        draft.invalidate(Step.resume)
        return {"resume_id": str(rid)}

    return await run_in_threadpool(
        mutate, request, owner, key, "resume.upload", inputs, revision, change
    )


@resumes_api.get(
    "/{resume_id}",
    response_class=Response,
    responses={
        200: {"content": {"application/pdf": {"schema": {"type": "string", "format": "binary"}}}}
    },
)
def download(resume_id: UUID, request: Request, owner: Owner) -> Response:
    with tenant(request.app.state.db, owner) as conn:
        blob = conn.scalar(
            select(files.c.ciphertext).where(files.c.id == resume_id, files.c.user_id == owner)
        )
        if blob is None:
            raise HTTPException(404, "Resume not found.")
        data = unseal(
            request.app.state.secret_key,
            owner,
            f"candidate-resume:{resume_id}",
            blob[:12],
            blob[12:],
        )
        return Response(
            data,
            media_type="application/pdf",
            headers={
                "Content-Disposition": 'attachment; filename="resume.pdf"',
                "X-Content-Type-Options": "nosniff",
            },
        )


@resumes_api.patch("/{resume_id}", response_model=Version)
def edit_resume(
    resume_id: UUID, payload: ResumeEdit, request: Request, owner: Owner, key: Key
) -> Result:
    def change(draft: Draft) -> None:
        values = payload.model_dump(exclude={"revision"}, exclude_unset=True)
        found = draft.conn.scalar(
            update(files)
            .where(files.c.id == resume_id, files.c.user_id == owner)
            .values(**values)
            .returning(files.c.id)
        )
        if not found:
            raise HTTPException(404, "Resume not found.")
        draft.invalidate(Step.resume)

    return mutate(
        request,
        owner,
        key,
        "resume.edit",
        {"id": str(resume_id), **payload.model_dump(exclude_unset=True)},
        payload.revision,
        change,
    )


@resumes_api.delete("/{resume_id}", response_model=Version)
def remove(resume_id: UUID, revision: Revision, request: Request, owner: Owner, key: Key) -> Result:
    def change(draft: Draft) -> None:
        found = draft.conn.scalar(
            delete(files)
            .where(files.c.id == resume_id, files.c.user_id == owner)
            .returning(files.c.id)
        )
        if not found:
            raise HTTPException(404, "Resume not found.")
        draft.invalidate(Step.resume)

    return mutate(
        request,
        owner,
        key,
        "resume.remove",
        {"id": str(resume_id), "revision": revision},
        revision,
        change,
    )
