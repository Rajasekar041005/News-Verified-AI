from fastapi import APIRouter, UploadFile, File, HTTPException, Body
from fastapi.responses import Response
from typing import Dict, Any

from services.verification_engine import VerificationEngine

router = APIRouter()

engine = VerificationEngine()


# ----------------------------
# Verify Text
# ----------------------------
@router.post("/verify/text")
async def verify_text(payload: Dict[str, Any]):
    try:
        result = await engine.verify_text(payload)
        return result

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# ----------------------------
# Verify URL
# ----------------------------
@router.post("/verify/url")
async def verify_url(payload: Dict[str, Any]):
    try:
        result = await engine.verify_url(payload)
        return result

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# ----------------------------
# Verify Image
# ----------------------------
@router.post("/verify/image")
async def verify_image(file: UploadFile = File(...)):
    try:
        content = await file.read()

        result = await engine.verify_image(
            content,
            file.filename
        )

        return result

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# ----------------------------
# Verify Video
# ----------------------------
@router.post("/verify/video")
async def verify_video(file: UploadFile = File(...)):
    try:
        content = await file.read()

        result = await engine.verify_video(
            content,
            file.filename
        )

        return result

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# ----------------------------
# Download PDF Report
# ----------------------------
@router.post("/verify/report")
async def verify_report(payload: Dict[str, Any] = Body(...)):
    try:
        pdf_bytes = engine.generate_pdf_report(payload)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": 'attachment; filename="verification_report.pdf"'}
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )
