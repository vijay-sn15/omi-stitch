"""
Portal Authentication Module

Handles admin authentication with secure session management.
Uses bcrypt for password hashing and secure session tokens.
"""

import os
import secrets
from datetime import datetime, timedelta
from typing import Optional

import bcrypt
from fastapi import Cookie, HTTPException, Request, status

from app.database import db


# Session configuration
SESSION_EXPIRY_HOURS = int(os.getenv("PORTAL_SESSION_HOURS", "24"))
SESSION_COOKIE_NAME = "portal_session"


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against its hash."""
    try:
        return bcrypt.checkpw(
            password.encode('utf-8'), 
            password_hash.encode('utf-8')
        )
    except Exception:
        return False


def generate_session_token() -> str:
    """Generate a secure session token."""
    return secrets.token_urlsafe(64)


def create_session(user_id: str, request: Request) -> Optional[dict]:
    """
    Create a new session for a user.
    
    Args:
        user_id: The user's UUID
        request: FastAPI request object for IP/user-agent
        
    Returns:
        Session dict with token and expiry, or None on failure
    """
    try:
        token = generate_session_token()
        expires_at = datetime.utcnow() + timedelta(hours=SESSION_EXPIRY_HOURS)
        
        # Get client info
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent", "")[:500]
        
        result = db.fetch_one(
            """
            INSERT INTO portal_sessions (
                user_id, session_token, ip_address, user_agent, expires_at
            ) VALUES (%s, %s, %s, %s, %s)
            RETURNING id, session_token, expires_at
            """,
            (user_id, token, ip_address, user_agent, expires_at)
        )
        
        if result:
            # Update last login
            db.execute(
                """
                UPDATE portal_users 
                SET last_login_at = %s, updated_at = %s
                WHERE id = %s
                """,
                (datetime.utcnow(), datetime.utcnow(), user_id)
            )
            return {
                "token": result["session_token"],
                "expires_at": result["expires_at"]
            }
        return None
    except Exception as e:
        print(f"Failed to create session: {e}")
        return None


def verify_session(session_token: str) -> Optional[dict]:
    """
    Verify a session token and return user info.
    
    Args:
        session_token: The session token from cookie
        
    Returns:
        User dict if valid, None otherwise
    """
    if not session_token:
        return None
        
    try:
        result = db.fetch_one(
            """
            SELECT 
                u.id, u.username, u.email, u.full_name, u.role, u.is_active,
                s.expires_at
            FROM portal_sessions s
            JOIN portal_users u ON s.user_id = u.id
            WHERE s.session_token = %s
            AND s.expires_at > NOW()
            AND u.is_active = true
            """,
            (session_token,)
        )
        return result
    except Exception as e:
        print(f"Failed to verify session: {e}")
        return None


def invalidate_session(session_token: str) -> bool:
    """Invalidate a session (logout)."""
    try:
        db.execute(
            "DELETE FROM portal_sessions WHERE session_token = %s",
            (session_token,)
        )
        return True
    except Exception:
        return False


def invalidate_all_user_sessions(user_id: str) -> bool:
    """Invalidate all sessions for a user."""
    try:
        db.execute(
            "DELETE FROM portal_sessions WHERE user_id = %s",
            (user_id,)
        )
        return True
    except Exception:
        return False


def cleanup_expired_sessions() -> int:
    """Remove expired sessions. Returns count of deleted sessions."""
    try:
        result = db.fetch_one(
            """
            WITH deleted AS (
                DELETE FROM portal_sessions 
                WHERE expires_at < NOW()
                RETURNING id
            )
            SELECT COUNT(*) as count FROM deleted
            """
        )
        return result["count"] if result else 0
    except Exception:
        return 0


def authenticate_user(username: str, password: str) -> Optional[dict]:
    """
    Authenticate a user by username/email and password.
    
    Args:
        username: Username or email
        password: Plain text password
        
    Returns:
        User dict if valid, None otherwise
    """
    try:
        # Try to find by username or email
        user = db.fetch_one(
            """
            SELECT id, username, email, password_hash, full_name, role, is_active
            FROM portal_users
            WHERE (username = %s OR email = %s) AND is_active = true
            """,
            (username, username)
        )
        
        if user and verify_password(password, user["password_hash"]):
            # Don't return password hash
            del user["password_hash"]
            return user
        return None
    except Exception as e:
        print(f"Authentication error: {e}")
        return None


async def get_current_user(request: Request) -> Optional[dict]:
    """
    Dependency to get current authenticated user from request.
    
    Args:
        request: FastAPI request object
        
    Returns:
        User dict if authenticated, None otherwise
    """
    session_token = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_token:
        return None
    return verify_session(session_token)


async def require_auth(request: Request) -> dict:
    """
    Dependency that requires authentication.
    Raises HTTPException if not authenticated.
    """
    user = await get_current_user(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    return user


async def require_admin(request: Request) -> dict:
    """
    Dependency that requires admin role.
    """
    user = await require_auth(request)
    if user["role"] not in ["admin", "superadmin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return user


async def require_superadmin(request: Request) -> dict:
    """
    Dependency that requires superadmin role.
    """
    user = await require_auth(request)
    if user["role"] != "superadmin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superadmin access required"
        )
    return user
