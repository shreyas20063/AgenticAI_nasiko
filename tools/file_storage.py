"""
File Storage Tool - handles document upload/download for resumes, policies, etc.
Uses local filesystem for demo; pluggable for S3/GCS in production.
"""

import os
import uuid
from pathlib import Path
from tools.base_tool import BaseTool, ToolResult
import structlog

logger = structlog.get_logger()

UPLOAD_DIR = Path("./uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


class FileStorageTool(BaseTool):
    name = "file_storage"
    description = "Upload, download, and manage files (resumes, documents)"

    async def execute(self, parameters: dict, context: dict) -> ToolResult:
        operation = parameters.get("operation", "upload")

        if operation == "upload":
            return await self._upload(parameters, context)
        elif operation == "download":
            return await self._download(parameters, context)
        elif operation == "delete":
            return await self._delete(parameters, context)
        else:
            return ToolResult(success=False, error=f"Unknown operation: {operation}", tool_name=self.name)

    async def _upload(self, params: dict, ctx: dict) -> ToolResult:
        content = params.get("content", "")
        filename = params.get("filename", f"{uuid.uuid4()}.txt")
        tenant_id = ctx.get("tenant_id", "default")

        # Tenant-isolated storage
        tenant_dir = UPLOAD_DIR / tenant_id
        tenant_dir.mkdir(exist_ok=True)

        file_path = tenant_dir / filename

        # Security: prevent path traversal in uploads (e.g., filename="../../etc/passwd")
        resolved = file_path.resolve()
        if not str(resolved).startswith(str(tenant_dir.resolve())):
            return ToolResult(success=False, error="Invalid filename: path traversal detected", tool_name=self.name)

        file_path.write_text(content, encoding="utf-8")

        return ToolResult(
            success=True,
            data={"file_path": str(file_path), "filename": filename},
            tool_name=self.name,
        )

    async def _download(self, params: dict, ctx: dict) -> ToolResult:
        filename = params.get("filename")
        tenant_id = ctx.get("tenant_id", "default")

        file_path = UPLOAD_DIR / tenant_id / filename
        if not file_path.exists():
            return ToolResult(success=False, error="File not found", tool_name=self.name)

        # Security: ensure path doesn't escape tenant dir (path traversal defense)
        resolved = file_path.resolve()
        if not str(resolved).startswith(str((UPLOAD_DIR / tenant_id).resolve())):
            return ToolResult(success=False, error="Access denied", tool_name=self.name)

        content = file_path.read_text(encoding="utf-8")
        return ToolResult(
            success=True,
            data={"content": content, "filename": filename},
            tool_name=self.name,
        )

    async def _delete(self, params: dict, ctx: dict) -> ToolResult:
        filename = params.get("filename")
        tenant_id = ctx.get("tenant_id", "default")

        file_path = UPLOAD_DIR / tenant_id / filename
        resolved = file_path.resolve()
        if not str(resolved).startswith(str((UPLOAD_DIR / tenant_id).resolve())):
            return ToolResult(success=False, error="Access denied", tool_name=self.name)

        if file_path.exists():
            file_path.unlink()
            return ToolResult(success=True, data={"deleted": filename}, tool_name=self.name)

        return ToolResult(success=False, error="File not found", tool_name=self.name)

    def get_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "operation": {"type": "string", "enum": ["upload", "download", "delete"]},
                    "filename": {"type": "string", "description": "Name of the file"},
                    "content": {"type": "string", "description": "File content (for upload)"},
                },
                "required": ["operation"],
            },
        }
