"""
Portal Router Module

Handles all portal routes including:
- Authentication (login/logout)
- Dashboard and submission management
- File explorer and uploads (stored in database)
- Admin chat interface
"""

import os
import uuid
import hashlib
import base64
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from app.database import db
from .auth import (
    SESSION_COOKIE_NAME,
    authenticate_user,
    create_session,
    get_current_user,
    invalidate_session,
    require_admin,
)

# Router configuration
router = APIRouter(prefix="/portal", tags=["portal"])

# Template setup
PORTAL_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = PORTAL_DIR / "templates"
STATIC_DIR = PORTAL_DIR / "static"

templates = Jinja2Templates(directory=TEMPLATES_DIR)

# Maximum file size (50MB)
MAX_FILE_SIZE = 50 * 1024 * 1024


# =============================================================================
# Request Models
# =============================================================================

class LoginRequest(BaseModel):
    username: str
    password: str


class StatusUpdateRequest(BaseModel):
    status: str
    reviewed_by: Optional[str] = None


class CommentRequest(BaseModel):
    message: str
    is_internal: bool = False


class CreateFolderRequest(BaseModel):
    name: str
    parent_path: str = "/uploads"


class ChatMessageRequest(BaseModel):
    message: str
    recipient_id: Optional[str] = None
    is_broadcast: bool = False


# =============================================================================
# Page Routes (HTML)
# =============================================================================

@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def portal_root(request: Request):
    """Redirect to portal dashboard or login."""
    user = await get_current_user(request)
    if user:
        return RedirectResponse(url="/portal/dashboard", status_code=302)
    return RedirectResponse(url="/portal/login", status_code=302)


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: Optional[str] = None):
    """Render login page."""
    user = await get_current_user(request)
    if user:
        return RedirectResponse(url="/portal/dashboard", status_code=302)
    
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"error": error}
    )


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    """Render main dashboard."""
    user = await get_current_user(request)
    if not user:
        return RedirectResponse(url="/portal/login", status_code=302)
    
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={"user": user}
    )


# =============================================================================
# Authentication API
# =============================================================================

@router.post("/api/login")
async def login(request: Request, login_data: LoginRequest):
    """Authenticate user and create session."""
    user = authenticate_user(login_data.username, login_data.password)
    
    if not user:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"success": False, "error": "Invalid credentials"}
        )
    
    session = create_session(str(user["id"]), request)
    if not session:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"success": False, "error": "Failed to create session"}
        )
    
    response = JSONResponse(content={
        "success": True,
        "user": {
            "id": str(user["id"]),
            "username": user["username"],
            "email": user["email"],
            "full_name": user["full_name"],
            "role": user["role"]
        }
    })
    
    # Set secure cookie
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session["token"],
        httponly=True,
        secure=os.getenv("ENVIRONMENT", "development") == "production",
        samesite="lax",
        max_age=86400 * 7  # 7 days
    )
    
    return response


@router.post("/api/logout")
async def logout(request: Request):
    """Logout and invalidate session."""
    session_token = request.cookies.get(SESSION_COOKIE_NAME)
    if session_token:
        invalidate_session(session_token)
    
    response = JSONResponse(content={"success": True})
    response.delete_cookie(SESSION_COOKIE_NAME)
    return response


@router.get("/api/me")
async def get_me(request: Request):
    """Get current user info."""
    user = await get_current_user(request)
    if not user:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"success": False, "error": "Not authenticated"}
        )
    return {"success": True, "user": user}


# =============================================================================
# Submissions API
# =============================================================================

@router.get("/api/submissions")
async def get_submissions(
    request: Request,
    status_filter: Optional[str] = Query(None, alias="status"),
    search: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
):
    """Get all submissions with optional filtering."""
    user = await get_current_user(request)
    if not user:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"success": False, "error": "Not authenticated"}
        )
    
    try:
        # Build query with filters
        where_clauses = []
        params = []
        
        if status_filter:
            where_clauses.append("status = %s")
            params.append(status_filter)
        
        if search:
            where_clauses.append(
                "(title ILIKE %s OR contact_name ILIKE %s OR contact_email ILIKE %s)"
            )
            search_term = f"%{search}%"
            params.extend([search_term, search_term, search_term])
        
        where_sql = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""
        
        # Get submissions
        query = f"""
            SELECT 
                id, title, contact_name, contact_email, contact_phone,
                logline, synopsis, budget, languages, status,
                created_at, updated_at, reviewed_at, reviewed_by,
                tracking_token
            FROM project_submissions
            {where_sql}
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
        """
        params.extend([limit, offset])
        
        submissions = db.fetch_all(query, tuple(params))
        
        # Get total count
        count_query = f"SELECT COUNT(*) as total FROM project_submissions {where_sql}"
        count_params = params[:-2] if params else ()
        count_result = db.fetch_one(count_query, count_params if count_params else None)
        total = count_result["total"] if count_result else 0
        
        # Get unread comment counts for each submission
        for sub in submissions:
            comment_result = db.fetch_one(
                """
                SELECT COUNT(*) as unread 
                FROM submission_comments 
                WHERE submission_id = %s AND author_type = 'user' AND is_read = false
                """,
                (sub["id"],)
            )
            sub["unread_comments"] = comment_result["unread"] if comment_result else 0
        
        return {
            "success": True,
            "submissions": submissions,
            "pagination": {"total": total, "limit": limit, "offset": offset}
        }
    except Exception as e:
        print(f"Error fetching submissions: {e}")
        return {"success": False, "error": str(e), "submissions": []}


@router.get("/api/submissions/{submission_id}")
async def get_submission(request: Request, submission_id: str):
    """Get a single submission with details."""
    user = await get_current_user(request)
    if not user:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"success": False, "error": "Not authenticated"}
        )
    
    try:
        submission = db.fetch_one(
            """
            SELECT *
            FROM project_submissions
            WHERE id = %s
            """,
            (submission_id,)
        )
        
        if not submission:
            return {"success": False, "error": "Submission not found"}
        
        # Get comments
        comments = db.fetch_all(
            """
            SELECT id, author_type, author_name, message, is_internal, is_read, created_at
            FROM submission_comments
            WHERE submission_id = %s
            ORDER BY created_at ASC
            """,
            (submission_id,)
        )
        
        return {
            "success": True,
            "submission": submission,
            "comments": comments or []
        }
    except Exception as e:
        print(f"Error fetching submission: {e}")
        return {"success": False, "error": str(e)}


@router.patch("/api/submissions/{submission_id}/status")
async def update_submission_status(
    request: Request,
    submission_id: str,
    status_update: StatusUpdateRequest
):
    """Update submission status."""
    user = await get_current_user(request)
    if not user:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"success": False, "error": "Not authenticated"}
        )
    
    valid_statuses = ["pending", "reviewed", "callback", "meeting", "approved", "rejected"]
    if status_update.status not in valid_statuses:
        return {"success": False, "error": f"Invalid status. Must be one of: {valid_statuses}"}
    
    try:
        reviewer = status_update.reviewed_by or user.get("full_name") or user.get("username")
        
        result = db.fetch_one(
            """
            UPDATE project_submissions
            SET status = %s, updated_at = %s, reviewed_at = %s, reviewed_by = %s
            WHERE id = %s
            RETURNING id
            """,
            (status_update.status, datetime.utcnow(), datetime.utcnow(), reviewer, submission_id)
        )
        
        if result:
            return {"success": True, "message": f"Status updated to {status_update.status}"}
        return {"success": False, "error": "Submission not found"}
    except Exception as e:
        print(f"Error updating status: {e}")
        return {"success": False, "error": str(e)}


@router.post("/api/submissions/{submission_id}/comments")
async def add_comment(request: Request, submission_id: str, comment: CommentRequest):
    """Add an admin comment to a submission."""
    user = await get_current_user(request)
    if not user:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"success": False, "error": "Not authenticated"}
        )
    
    try:
        author_name = user.get("full_name") or user.get("username") or "OMI Team"
        
        result = db.fetch_one(
            """
            INSERT INTO submission_comments (
                submission_id, author_type, author_name, author_email,
                message, is_internal, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                submission_id,
                "admin",
                author_name,
                user.get("email"),
                comment.message,
                comment.is_internal,
                datetime.utcnow()
            )
        )
        
        if result:
            return {"success": True, "comment_id": str(result["id"])}
        return {"success": False, "error": "Failed to add comment"}
    except Exception as e:
        print(f"Error adding comment: {e}")
        return {"success": False, "error": str(e)}


@router.patch("/api/submissions/{submission_id}/comments/mark-read")
async def mark_comments_read(request: Request, submission_id: str):
    """Mark all user comments on a submission as read."""
    user = await get_current_user(request)
    if not user:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"success": False, "error": "Not authenticated"}
        )
    
    try:
        db.execute(
            """
            UPDATE submission_comments
            SET is_read = true, read_at = %s
            WHERE submission_id = %s AND author_type = 'user' AND is_read = false
            """,
            (datetime.utcnow(), submission_id)
        )
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


# =============================================================================
# File Explorer API
# =============================================================================

@router.get("/api/files")
async def list_files(
    request: Request,
    path: str = "/uploads"
):
    """List files and folders at a given path."""
    user = await get_current_user(request)
    if not user:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"success": False, "error": "Not authenticated"}
        )
    
    try:
        # Get folder by path
        parent = db.fetch_one(
            "SELECT id FROM portal_files WHERE path = %s AND is_folder = true",
            (path,)
        )
        
        if not parent:
            # If it's the root, still list root-level files
            if path == "/uploads":
                files = db.fetch_all(
                    """
                    SELECT id, name, path, mime_type, size_bytes, is_folder, created_at
                    FROM portal_files
                    WHERE parent_id IS NULL OR path = '/uploads'
                    ORDER BY is_folder DESC, name ASC
                    """
                )
            else:
                return {"success": True, "files": [], "path": path}
        else:
            files = db.fetch_all(
                """
                SELECT id, name, path, mime_type, size_bytes, is_folder, created_at
                FROM portal_files
                WHERE parent_id = %s
                ORDER BY is_folder DESC, name ASC
                """,
                (parent["id"],)
            )
        
        return {"success": True, "files": files or [], "path": path}
    except Exception as e:
        print(f"Error listing files: {e}")
        return {"success": False, "error": str(e), "files": []}


@router.post("/api/files/upload")
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    path: str = Form("/uploads"),
    description: str = Form(None)
):
    """Upload a file and store it directly in the database."""
    user = await get_current_user(request)
    if not user:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"success": False, "error": "Not authenticated"}
        )
    
    try:
        # Read file content
        content = await file.read()
        file_size = len(content)
        
        # Check file size limit
        if file_size > MAX_FILE_SIZE:
            return JSONResponse(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                content={"success": False, "error": f"File too large. Maximum size is {MAX_FILE_SIZE // (1024*1024)}MB"}
            )
        
        # Get file metadata
        original_name = file.filename or "unnamed"
        extension = Path(original_name).suffix.lstrip('.').lower() if '.' in original_name else ''
        mime_type = file.content_type or 'application/octet-stream'
        
        # Calculate checksums for integrity
        checksum_md5 = hashlib.md5(content).hexdigest()
        checksum_sha256 = hashlib.sha256(content).hexdigest()
        
        # Get parent folder
        parent = db.fetch_one(
            "SELECT id FROM portal_files WHERE path = %s AND is_folder = true",
            (path,)
        )
        parent_id = parent["id"] if parent else None
        
        # Calculate new path
        new_path = f"{path}/{original_name}" if path != "/" else f"/{original_name}"
        
        # Check if file with same path already exists
        existing = db.fetch_one(
            "SELECT id FROM portal_files WHERE path = %s",
            (new_path,)
        )
        if existing:
            # Add timestamp to make unique
            timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            name_parts = original_name.rsplit('.', 1)
            if len(name_parts) > 1:
                original_name = f"{name_parts[0]}_{timestamp}.{name_parts[1]}"
            else:
                original_name = f"{original_name}_{timestamp}"
            new_path = f"{path}/{original_name}"
        
        # Prepare metadata JSON
        metadata = {
            "content_type": mime_type,
            "uploaded_from": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent", "")[:200]
        }
        
        # Store file content directly in database
        result = db.fetch_one(
            """
            INSERT INTO portal_files (
                name, path, mime_type, size_bytes, is_folder,
                parent_id, uploaded_by, original_filename, extension,
                checksum_md5, checksum_sha256, description,
                file_content, metadata, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                original_name,
                new_path,
                mime_type,
                file_size,
                False,
                parent_id,
                user["id"],
                file.filename,
                extension,
                checksum_md5,
                checksum_sha256,
                description,
                content,  # Binary content stored in database
                str(metadata).replace("'", '"'),  # Convert to JSON-like string
                datetime.utcnow()
            )
        )
        
        if result:
            return {
                "success": True,
                "file": {
                    "id": str(result["id"]),
                    "name": original_name,
                    "path": new_path,
                    "size": file_size,
                    "mime_type": mime_type,
                    "checksum_md5": checksum_md5
                }
            }
        return {"success": False, "error": "Failed to save file"}
    except Exception as e:
        print(f"Error uploading file: {e}")
        return {"success": False, "error": str(e)}


@router.post("/api/files/folder")
async def create_folder(request: Request, folder: CreateFolderRequest):
    """Create a new folder."""
    user = await get_current_user(request)
    if not user:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"success": False, "error": "Not authenticated"}
        )
    
    try:
        # Sanitize folder name
        folder_name = folder.name.strip().replace("/", "-").replace("\\", "-")
        if not folder_name:
            return {"success": False, "error": "Invalid folder name"}
        
        # Get parent folder
        parent = db.fetch_one(
            "SELECT id FROM portal_files WHERE path = %s AND is_folder = true",
            (folder.parent_path,)
        )
        parent_id = parent["id"] if parent else None
        
        # Calculate new path
        new_path = f"{folder.parent_path}/{folder_name}"
        
        # Check if folder already exists
        existing = db.fetch_one(
            "SELECT id FROM portal_files WHERE path = %s",
            (new_path,)
        )
        if existing:
            return {"success": False, "error": "Folder already exists"}
        
        # Create folder record
        result = db.fetch_one(
            """
            INSERT INTO portal_files (
                name, path, is_folder, parent_id, uploaded_by, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (folder_name, new_path, True, parent_id, user["id"], datetime.utcnow())
        )
        
        if result:
            return {
                "success": True,
                "folder": {
                    "id": str(result["id"]),
                    "name": folder_name,
                    "path": new_path
                }
            }
        return {"success": False, "error": "Failed to create folder"}
    except Exception as e:
        print(f"Error creating folder: {e}")
        return {"success": False, "error": str(e)}


@router.delete("/api/files/{file_id}")
async def delete_file(request: Request, file_id: str):
    """Delete a file or folder from database."""
    user = await get_current_user(request)
    if not user:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"success": False, "error": "Not authenticated"}
        )
    
    try:
        # Get file info
        file_info = db.fetch_one(
            "SELECT id, name, is_folder FROM portal_files WHERE id = %s",
            (file_id,)
        )
        
        if not file_info:
            return {"success": False, "error": "File not found"}
        
        # Delete from database (CASCADE will handle children)
        db.execute(
            "DELETE FROM portal_files WHERE id = %s",
            (file_id,)
        )
        
        return {"success": True, "message": f"{'Folder' if file_info['is_folder'] else 'File'} deleted"}
    except Exception as e:
        print(f"Error deleting file: {e}")
        return {"success": False, "error": str(e)}


@router.get("/api/files/download/{file_id}")
async def download_file(request: Request, file_id: str):
    """Download a file from database storage."""
    user = await get_current_user(request)
    if not user:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"success": False, "error": "Not authenticated"}
        )
    
    try:
        file_info = db.fetch_one(
            """
            SELECT name, mime_type, file_content, size_bytes, original_filename
            FROM portal_files 
            WHERE id = %s AND is_folder = false
            """,
            (file_id,)
        )
        
        if not file_info or not file_info["file_content"]:
            raise HTTPException(status_code=404, detail="File not found")
        
        # Return file content from database
        filename = file_info["original_filename"] or file_info["name"]
        return Response(
            content=bytes(file_info["file_content"]),
            media_type=file_info["mime_type"] or "application/octet-stream",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Length": str(file_info["size_bytes"])
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error downloading file: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/files/{file_id}/info")
async def get_file_info(request: Request, file_id: str):
    """Get detailed file metadata without content."""
    user = await get_current_user(request)
    if not user:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"success": False, "error": "Not authenticated"}
        )
    
    try:
        file_info = db.fetch_one(
            """
            SELECT 
                id, name, path, mime_type, size_bytes, is_folder,
                original_filename, extension, checksum_md5, checksum_sha256,
                description, tags, width, height, duration_seconds,
                created_at, updated_at
            FROM portal_files 
            WHERE id = %s
            """,
            (file_id,)
        )
        
        if not file_info:
            return {"success": False, "error": "File not found"}
        
        # Get uploader info
        if file_info.get("uploaded_by"):
            uploader = db.fetch_one(
                "SELECT username, full_name FROM portal_users WHERE id = %s",
                (file_info["uploaded_by"],)
            )
            file_info["uploader"] = uploader
        
        return {"success": True, "file": file_info}
    except Exception as e:
        print(f"Error getting file info: {e}")
        return {"success": False, "error": str(e)}


# =============================================================================
# Stats API
# =============================================================================

@router.get("/api/stats")
async def get_stats(request: Request):
    """Get dashboard statistics."""
    user = await get_current_user(request)
    if not user:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"success": False, "error": "Not authenticated"}
        )
    
    try:
        # Get submission counts by status
        stats = db.fetch_one(
            """
            SELECT
                COUNT(*) FILTER (WHERE status = 'pending') as pending,
                COUNT(*) FILTER (WHERE status = 'reviewed') as reviewed,
                COUNT(*) FILTER (WHERE status = 'callback') as callback,
                COUNT(*) FILTER (WHERE status = 'meeting') as meeting,
                COUNT(*) FILTER (WHERE status = 'approved') as approved,
                COUNT(*) FILTER (WHERE status = 'rejected') as rejected,
                COUNT(*) as total
            FROM project_submissions
            """
        )
        
        # Get unread comments count
        unread = db.fetch_one(
            """
            SELECT COUNT(*) as count
            FROM submission_comments
            WHERE author_type = 'user' AND is_read = false
            """
        )
        
        # Get file count
        files = db.fetch_one(
            "SELECT COUNT(*) as count FROM portal_files WHERE is_folder = false"
        )
        
        # Get unread chat messages count
        chat_unread = db.fetch_one(
            """
            SELECT COUNT(*) as count
            FROM portal_chat_messages
            WHERE (recipient_id = %s OR is_broadcast = true) AND is_read = false
            """,
            (user["id"],)
        )
        
        return {
            "success": True,
            "stats": {
                "submissions": stats or {},
                "unread_messages": unread["count"] if unread else 0,
                "files": files["count"] if files else 0,
                "unread_chat": chat_unread["count"] if chat_unread else 0
            }
        }
    except Exception as e:
        print(f"Error fetching stats: {e}")
        return {"success": False, "error": str(e)}


# =============================================================================
# Chat API
# =============================================================================

@router.get("/api/chat/messages")
async def get_chat_messages(
    request: Request,
    limit: int = 50,
    before_id: Optional[str] = None
):
    """Get chat messages for the current user."""
    user = await get_current_user(request)
    if not user:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"success": False, "error": "Not authenticated"}
        )
    
    try:
        # Build query
        params = [user["id"], user["id"]]
        where_clause = "(sender_id = %s OR recipient_id = %s OR is_broadcast = true)"
        
        if before_id:
            where_clause += " AND id < %s"
            params.append(before_id)
        
        params.append(limit)
        
        messages = db.fetch_all(
            f"""
            SELECT 
                m.id, m.sender_id, m.recipient_id, m.message, m.message_type,
                m.file_id, m.is_read, m.is_broadcast, m.created_at,
                s.username as sender_username, s.full_name as sender_name,
                r.username as recipient_username, r.full_name as recipient_name
            FROM portal_chat_messages m
            LEFT JOIN portal_users s ON m.sender_id = s.id
            LEFT JOIN portal_users r ON m.recipient_id = r.id
            WHERE {where_clause}
            ORDER BY m.created_at DESC
            LIMIT %s
            """,
            tuple(params)
        )
        
        return {"success": True, "messages": messages or []}
    except Exception as e:
        print(f"Error fetching chat messages: {e}")
        return {"success": False, "error": str(e), "messages": []}


@router.post("/api/chat/messages")
async def send_chat_message(request: Request, chat_msg: ChatMessageRequest):
    """Send a chat message."""
    user = await get_current_user(request)
    if not user:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"success": False, "error": "Not authenticated"}
        )
    
    try:
        if not chat_msg.message.strip():
            return {"success": False, "error": "Message cannot be empty"}
        
        result = db.fetch_one(
            """
            INSERT INTO portal_chat_messages (
                sender_id, recipient_id, message, message_type, is_broadcast, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id, created_at
            """,
            (
                user["id"],
                chat_msg.recipient_id if not chat_msg.is_broadcast else None,
                chat_msg.message,
                "text",
                chat_msg.is_broadcast,
                datetime.utcnow()
            )
        )
        
        if result:
            return {
                "success": True,
                "message": {
                    "id": str(result["id"]),
                    "sender_id": str(user["id"]),
                    "sender_name": user.get("full_name") or user.get("username"),
                    "message": chat_msg.message,
                    "created_at": result["created_at"].isoformat() if result["created_at"] else None
                }
            }
        return {"success": False, "error": "Failed to send message"}
    except Exception as e:
        print(f"Error sending chat message: {e}")
        return {"success": False, "error": str(e)}


@router.patch("/api/chat/messages/mark-read")
async def mark_chat_messages_read(request: Request):
    """Mark all chat messages as read for the current user."""
    user = await get_current_user(request)
    if not user:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"success": False, "error": "Not authenticated"}
        )
    
    try:
        db.execute(
            """
            UPDATE portal_chat_messages
            SET is_read = true, read_at = %s
            WHERE (recipient_id = %s OR is_broadcast = true) AND is_read = false
            """,
            (datetime.utcnow(), user["id"])
        )
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/api/chat/users")
async def get_chat_users(request: Request):
    """Get list of users available for chat."""
    user = await get_current_user(request)
    if not user:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"success": False, "error": "Not authenticated"}
        )
    
    try:
        users = db.fetch_all(
            """
            SELECT id, username, full_name, role, last_login_at
            FROM portal_users
            WHERE is_active = true AND id != %s
            ORDER BY full_name, username
            """,
            (user["id"],)
        )
        return {"success": True, "users": users or []}
    except Exception as e:
        print(f"Error fetching chat users: {e}")
        return {"success": False, "error": str(e), "users": []}
