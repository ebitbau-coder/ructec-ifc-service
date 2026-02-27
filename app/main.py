import os
import subprocess
import tempfile
from uuid import uuid4

import ifcopenshell
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse

from app.db import SessionLocal, init_db, Project, ModelRecord
from app.schemas import CreateProjectRequest
from app.storage import (
    put_bytes,
    put_json,
    get_bytes,
    presigned_get_url,
    original_ifc_key,
    summary_json_key,
    export_glb_key,
)

app = FastAPI(title="RUCTEC IFC Service")


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/tools")
def tools():
    data = {
        "ifcopenshell_version": getattr(ifcopenshell, "version", "unknown"),
        "ifcconvert_available": False,
    }
    try:
        result = subprocess.run(
            ["IfcConvert", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        data["ifcconvert_available"] = result.returncode == 0
        data["ifcconvert_version"] = (result.stdout or result.stderr).strip()
    except Exception as e:
        data["ifcconvert_error"] = str(e)
    return data


@app.post("/projects")
def create_project(payload: CreateProjectRequest):
    db = SessionLocal()
    try:
        project = Project(
            id=str(uuid4()),
            tenant_id=payload.tenant_id,
            name=payload.name,
        )
        db.add(project)
        db.commit()
        return {
            "project_id": project.id,
            "tenant_id": project.tenant_id,
            "name": project.name,
        }
    finally:
        db.close()


@app.get("/projects/{project_id}")
def get_project(project_id: str, tenant_id: str):
    db = SessionLocal()
    try:
        project = (
            db.query(Project)
            .filter(Project.id == project_id, Project.tenant_id == tenant_id)
            .first()
        )
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        return {
            "project_id": project.id,
            "tenant_id": project.tenant_id,
            "name": project.name,
        }
    finally:
        db.close()


@app.post("/projects/{project_id}/models")
async def upload_model(
    project_id: str,
    tenant_id: str = Form(...),
    file: UploadFile = File(...),
):
    if not file.filename.lower().endswith(".ifc"):
        raise HTTPException(status_code=400, detail="Only .ifc files are allowed")

    db = SessionLocal()
    try:
        project = (
            db.query(Project)
            .filter(Project.id == project_id, Project.tenant_id == tenant_id)
            .first()
        )
        if not project:
            raise HTTPException(status_code=404, detail="Project not found for tenant")

        model_id = str(uuid4())
        model = ModelRecord(
            id=model_id,
            tenant_id=tenant_id,
            project_id=project_id,
            filename=file.filename,
            status="uploaded",
        )
        db.add(model)
        db.commit()

        content = await file.read()
        put_bytes(
            original_ifc_key(tenant_id, project_id, model_id),
            content,
            "application/octet-stream",
        )

        return {
            "model_id": model_id,
            "project_id": project_id,
            "tenant_id": tenant_id,
            "status": "uploaded",
        }
    finally:
        db.close()


@app.post("/projects/{project_id}/models/{model_id}/process")
def process_model(project_id: str, model_id: str, tenant_id: str):
    db = SessionLocal()
    try:
        record = (
            db.query(ModelRecord)
            .filter(
                ModelRecord.id == model_id,
                ModelRecord.project_id == project_id,
                ModelRecord.tenant_id == tenant_id,
            )
            .first()
        )
        if not record:
            raise HTTPException(status_code=404, detail="Model not found")

        ifc_bytes = get_bytes(original_ifc_key(tenant_id, project_id, model_id))

        with tempfile.TemporaryDirectory() as tmpdir:
            in_path = os.path.join(tmpdir, "input.ifc")
            out_path = os.path.join(tmpdir, "output.glb")

            with open(in_path, "wb") as f:
                f.write(ifc_bytes)

            model = ifcopenshell.open(in_path)

            summary = {
                "schema": model.schema,
                "counts": {
                    "IfcProject": len(model.by_type("IfcProject")),
                    "IfcSite": len(model.by_type("IfcSite")),
                    "IfcBuilding": len(model.by_type("IfcBuilding")),
                    "IfcBuildingStorey": len(model.by_type("IfcBuildingStorey")),
                    "IfcSpace": len(model.by_type("IfcSpace")),
                    "IfcWall": len(model.by_type("IfcWall")),
                    "IfcSlab": len(model.by_type("IfcSlab")),
                    "IfcDoor": len(model.by_type("IfcDoor")),
                    "IfcWindow": len(model.by_type("IfcWindow")),
                },
            }
            put_json(summary_json_key(tenant_id, project_id, model_id), summary)

            result = subprocess.run(
                ["IfcConvert", in_path, out_path],
                capture_output=True,
                text=True,
                timeout=600,
            )

            if result.returncode != 0:
                record.status = "failed"
                db.commit()
                return JSONResponse(
                    status_code=500,
                    content={
                        "error": result.stderr or result.stdout,
                        "model_id": model_id,
                        "status": "failed",
                    },
                )

            with open(out_path, "rb") as f:
                put_bytes(
                    export_glb_key(tenant_id, project_id, model_id),
                    f.read(),
                    "model/gltf-binary",
                )

        record.status = "processed"
        db.commit()

        return {
            "model_id": model_id,
            "project_id": project_id,
            "tenant_id": tenant_id,
            "status": "processed",
        }
    finally:
        db.close()


@app.get("/projects/{project_id}/models/{model_id}")
def get_model(project_id: str, model_id: str, tenant_id: str):
    db = SessionLocal()
    try:
        record = (
            db.query(ModelRecord)
            .filter(
                ModelRecord.id == model_id,
                ModelRecord.project_id == project_id,
                ModelRecord.tenant_id == tenant_id,
            )
            .first()
        )
        if not record:
            raise HTTPException(status_code=404, detail="Model not found")

        return {
            "model_id": record.id,
            "project_id": record.project_id,
            "tenant_id": record.tenant_id,
            "filename": record.filename,
            "status": record.status,
        }
    finally:
        db.close()


@app.get("/projects/{project_id}/models/{model_id}/viewer-url")
def get_viewer_url(project_id: str, model_id: str, tenant_id: str):
    db = SessionLocal()
    try:
        record = (
            db.query(ModelRecord)
            .filter(
                ModelRecord.id == model_id,
                ModelRecord.project_id == project_id,
                ModelRecord.tenant_id == tenant_id,
            )
            .first()
        )
        if not record:
            raise HTTPException(status_code=404, detail="Model not found")

        if record.status != "processed":
            raise HTTPException(status_code=400, detail="Model not processed yet")

        return {
            "model_id": model_id,
            "glb_url": presigned_get_url(export_glb_key(tenant_id, project_id, model_id)),
            "summary_url": presigned_get_url(summary_json_key(tenant_id, project_id, model_id)),
        }
    finally:
        db.close()
