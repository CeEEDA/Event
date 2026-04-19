from fastapi import FastAPI, APIRouter, HTTPException, Depends, UploadFile, File as FastAPIFile, Form, Query, Request, BackgroundTasks
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import StreamingResponse, FileResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorGridFSBucket
import os
import logging
from pathlib import Path
STATIC_DIR = str(Path(__file__).resolve().parent / "static")
from pydantic import BaseModel, Field, ConfigDict, EmailStr
from typing import List, Optional, Dict
import uuid
from datetime import datetime, timezone, timedelta
import jwt
import bcrypt
from bson import ObjectId
import io
import zipfile
from email_service import send_password_reset_email, send_admin_reset_email

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]
fs = AsyncIOMotorGridFSBucket(db)

# JWT Configuration
JWT_SECRET = os.environ.get('JWT_SECRET', 'eventenergie-fileshare-secret-key-2024')
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

# Create the main app
app = FastAPI(title="FileShare Portal API")

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Security
security = HTTPBearer()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============== Models ==============

class UserRole:
    ADMIN = "admin"
    KUNDE = "kunde"
    MITARBEITER = "mitarbeiter"

class FilesharingPermissions(BaseModel):
    enabled: bool = False
    max_upload_size_mb: int = 100
    can_write: bool = False  # False = nur lesen, True = auch schreiben
    can_delete: bool = False

class UserApps(BaseModel):
    filesharing: FilesharingPermissions = FilesharingPermissions()

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    name: str
    role: str = UserRole.KUNDE

class UserUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    apps: Optional[Dict] = None
    access_type: Optional[str] = None
    access_start: Optional[str] = None
    access_end: Optional[str] = None
    permissions: Optional[Dict] = None

class PasswordResetRequest(BaseModel):
    email: EmailStr
    frontend_url: Optional[str] = ""

class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str

class AdminSetPassword(BaseModel):
    user_id: str
    new_password: str

class UserResponseWithPassword(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    email: str
    name: str
    role: str
    is_active: bool
    created_at: str
    apps: Dict = {}
    password_plain: Optional[str] = None  # Only for admin view

class UserResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    email: str
    name: str
    role: str
    is_active: bool
    created_at: str
    apps: Dict = {}
    access_type: Optional[str] = "permanent"
    access_start: Optional[str] = None
    access_end: Optional[str] = None
    permissions: Dict = {}

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class LoginResponse(BaseModel):
    token: str
    user: UserResponse

class FileMetadata(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    filename: str
    original_filename: str
    size: int
    content_type: str
    owner_id: str
    owner_name: str
    folder_path: str
    storage_area: str = "personal"  # personal, shared, or user_id for admin viewing
    created_at: str
    is_shared: bool = False

class FolderCreate(BaseModel):
    name: str
    parent_path: str = "/"
    storage_area: str = "personal"  # personal or shared

class FolderResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    name: str
    path: str
    owner_id: str
    storage_area: str
    created_at: str

class ShareLinkCreate(BaseModel):
    file_id: Optional[str] = None
    folder_id: Optional[str] = None
    share_type: str = "file"  # file or folder
    expires_in_days: int = 7
    password: Optional[str] = None
    allow_download: bool = True
    allow_upload: bool = False
    allow_edit: bool = False  # kann Dateien bearbeiten/löschen

class ShareLinkResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    file_id: Optional[str] = None
    folder_id: Optional[str] = None
    share_type: str
    token: str
    created_by: str
    expires_at: str
    password_protected: bool
    allow_download: bool
    allow_upload: bool
    allow_edit: bool
    access_count: int
    created_at: str

class ShareAccessRequest(BaseModel):
    password: Optional[str] = None

class FileMoveRequest(BaseModel):
    target_folder_path: str = "/"
    target_storage_area: Optional[str] = None

# ============== Helper Functions ==============

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def create_jwt_token(user_id: str, email: str, role: str) -> str:
    payload = {
        "user_id": user_id,
        "email": email,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def decode_jwt_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token abgelaufen")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Ungültiger Token")

def get_default_apps():
    return {
        "filesharing": {
            "enabled": False,
            "max_upload_size_mb": 100,
            "can_write": False,
            "can_delete": False
        },
        "energy_monitoring": {
            "enabled": False,
            "access_all": False,
            "device_ids": []
        }
    }

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    payload = decode_jwt_token(credentials.credentials)
    user = await db.users.find_one({"id": payload["user_id"]}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="Benutzer nicht gefunden")
    if not user.get("is_active", True):
        raise HTTPException(status_code=403, detail="Konto deaktiviert")
    # Ensure apps field exists
    if "apps" not in user:
        user["apps"] = get_default_apps()
    return user

async def get_user_from_token_param(token: str) -> dict:
    """Auth via query parameter token - for direct download URLs in iframes"""
    payload = decode_jwt_token(token)
    user = await db.users.find_one({"id": payload["user_id"]}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="Benutzer nicht gefunden")
    if not user.get("is_active", True):
        raise HTTPException(status_code=403, detail="Konto deaktiviert")
    if "apps" not in user:
        user["apps"] = get_default_apps()
    return user

async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user["role"] != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin-Berechtigung erforderlich")
    return user

async def require_filesharing(user: dict = Depends(get_current_user)) -> dict:
    # Admins always have access
    if user["role"] == UserRole.ADMIN:
        return user
    # Check if filesharing is enabled for user
    apps = user.get("apps", {})
    filesharing = apps.get("filesharing", {})
    if not filesharing.get("enabled", False):
        raise HTTPException(status_code=403, detail="FileShare nicht freigeschaltet")
    return user

def can_user_write(user: dict) -> bool:
    if user["role"] == UserRole.ADMIN:
        return True
    apps = user.get("apps", {})
    filesharing = apps.get("filesharing", {})
    return filesharing.get("can_write", False)

def can_user_delete(user: dict) -> bool:
    if user["role"] == UserRole.ADMIN:
        return True
    apps = user.get("apps", {})
    filesharing = apps.get("filesharing", {})
    return filesharing.get("can_delete", False)

def get_user_upload_limit(user: dict) -> int:
    if user["role"] == UserRole.ADMIN:
        return 10000  # 10 GB for admin
    apps = user.get("apps", {})
    filesharing = apps.get("filesharing", {})
    return filesharing.get("max_upload_size_mb", 100)

# ============== Auth Endpoints ==============

@api_router.post("/auth/register", response_model=LoginResponse)
async def register(data: UserCreate):
    existing = await db.users.find_one({"email": data.email})
    if existing:
        raise HTTPException(status_code=400, detail="E-Mail bereits registriert")
    
    user_count = await db.users.count_documents({})
    role = UserRole.ADMIN if user_count == 0 else data.role
    
    # Set default apps - admin gets all enabled
    apps = get_default_apps()
    if role == UserRole.ADMIN:
        apps["filesharing"]["enabled"] = True
        apps["filesharing"]["can_write"] = True
        apps["filesharing"]["can_delete"] = True
    
    user_id = str(uuid.uuid4())
    user_doc = {
        "id": user_id,
        "email": data.email,
        "name": data.name,
        "password_hash": hash_password(data.password),
        "role": role,
        "is_active": True,
        "apps": apps,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.users.insert_one(user_doc)
    
    token = create_jwt_token(user_id, data.email, role)
    
    user_response = UserResponse(
        id=user_id,
        email=data.email,
        name=data.name,
        role=role,
        is_active=True,
        created_at=user_doc["created_at"],
        apps=apps
    )
    
    return LoginResponse(token=token, user=user_response)

@api_router.post("/auth/login", response_model=LoginResponse)
async def login(data: LoginRequest, request: Request):
    user = await db.users.find_one({"email": data.email}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="Ungültige Anmeldedaten")
    
    if not verify_password(data.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Ungültige Anmeldedaten")
    
    if not user.get("is_active", True):
        raise HTTPException(status_code=403, detail="Konto deaktiviert")
    
    # Check account-level time-based access for Kunden
    if user["role"] == "kunde" and user.get("access_type") == "temporary":
        now = datetime.now(timezone.utc)
        access_end = user.get("access_end")
        if access_end:
            try:
                end = datetime.fromisoformat(access_end)
                if now > end:
                    raise HTTPException(status_code=403, detail="Kontozugang abgelaufen. Bitte kontaktieren Sie den Administrator.")
            except (ValueError, TypeError):
                pass
    
    # Ensure apps field exists
    if "apps" not in user:
        user["apps"] = get_default_apps()
        await db.users.update_one({"id": user["id"]}, {"$set": {"apps": user["apps"]}})
    
    token = create_jwt_token(user["id"], user["email"], user["role"])
    
    # Track login event
    client_ip = request.headers.get("x-forwarded-for", request.headers.get("x-real-ip", request.client.host if request.client else ""))
    if client_ip and "," in client_ip:
        client_ip = client_ip.split(",")[0].strip()
    await db.login_history.insert_one({
        "user_id": user["id"],
        "email": user["email"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ip": client_ip,
    })
    
    user_response = UserResponse(
        id=user["id"],
        email=user["email"],
        name=user["name"],
        role=user["role"],
        is_active=user.get("is_active", True),
        created_at=user["created_at"],
        apps=user.get("apps", get_default_apps()),
        access_type=user.get("access_type", "permanent"),
        access_start=user.get("access_start"),
        access_end=user.get("access_end")
    )
    
    return LoginResponse(token=token, user=user_response)

@api_router.get("/auth/me", response_model=UserResponse)
async def get_me(user: dict = Depends(get_current_user)):
    return UserResponse(
        id=user["id"],
        email=user["email"],
        name=user["name"],
        role=user["role"],
        is_active=user.get("is_active", True),
        created_at=user["created_at"],
        apps=user.get("apps", get_default_apps()),
        access_type=user.get("access_type", "permanent"),
        access_start=user.get("access_start"),
        access_end=user.get("access_end"),
        permissions=user.get("permissions", {})
    )

# ============== Password Reset ==============

@api_router.post("/auth/request-password-reset")
async def request_password_reset(data: PasswordResetRequest):
    """Request a password reset - creates a reset token and sends email"""
    user = await db.users.find_one({"email": data.email}, {"_id": 0})
    if not user:
        # Don't reveal if email exists
        return {"message": "Falls die E-Mail existiert, wurde ein Link gesendet"}
    
    # Create reset token
    reset_token = str(uuid.uuid4()).replace("-", "")[:32]
    expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
    
    # Store reset token
    await db.password_resets.delete_many({"user_id": user["id"]})  # Remove old tokens
    await db.password_resets.insert_one({
        "user_id": user["id"],
        "token": reset_token,
        "expires_at": expires_at.isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat()
    })
    
    # Build reset link and send email
    frontend_url = data.frontend_url.rstrip("/") if hasattr(data, "frontend_url") and data.frontend_url else ""
    reset_link = f"{frontend_url}/reset-password/{reset_token}" if frontend_url else f"/reset-password/{reset_token}"
    
    email_sent = send_password_reset_email(user["email"], user["name"], reset_link)
    logger.info(f"Password reset requested for {data.email}, email_sent={email_sent}")
    
    return {"message": "Falls die E-Mail existiert, wurde ein Link gesendet", "email_sent": email_sent}

@api_router.post("/auth/reset-password")
async def reset_password(data: PasswordResetConfirm):
    """Reset password using a reset token"""
    reset_doc = await db.password_resets.find_one({"token": data.token}, {"_id": 0})
    if not reset_doc:
        raise HTTPException(status_code=400, detail="Ungültiger oder abgelaufener Link")
    
    expires_at = datetime.fromisoformat(reset_doc["expires_at"])
    if datetime.now(timezone.utc) > expires_at:
        await db.password_resets.delete_one({"token": data.token})
        raise HTTPException(status_code=400, detail="Link abgelaufen")
    
    if len(data.new_password) < 6:
        raise HTTPException(status_code=400, detail="Passwort muss mindestens 6 Zeichen haben")
    
    # Update password
    await db.users.update_one(
        {"id": reset_doc["user_id"]},
        {"$set": {
            "password_hash": hash_password(data.new_password),
            "password_changed_at": datetime.now(timezone.utc).isoformat(),
        }}
    )
    
    # Delete used token
    await db.password_resets.delete_one({"token": data.token})
    
    return {"message": "Passwort erfolgreich geändert"}

@api_router.get("/auth/verify-reset-token/{token}")
async def verify_reset_token(token: str):
    """Verify if a reset token is valid"""
    reset_doc = await db.password_resets.find_one({"token": token}, {"_id": 0})
    if not reset_doc:
        raise HTTPException(status_code=400, detail="Ungültiger Link")
    
    expires_at = datetime.fromisoformat(reset_doc["expires_at"])
    if datetime.now(timezone.utc) > expires_at:
        raise HTTPException(status_code=400, detail="Link abgelaufen")
    
    return {"valid": True}

# ============== User Management (Admin) ==============

@api_router.get("/users", response_model=List[UserResponse])
async def list_users(admin: dict = Depends(require_admin)):
    users = await db.users.find({}, {"_id": 0, "password_hash": 0}).to_list(1000)
    return [UserResponse(
        id=u["id"],
        email=u["email"],
        name=u["name"],
        role=u["role"],
        is_active=u.get("is_active", True),
        created_at=u["created_at"],
        apps=u.get("apps", get_default_apps()),
        access_type=u.get("access_type", "permanent"),
        access_start=u.get("access_start"),
        access_end=u.get("access_end"),
        permissions=u.get("permissions", {})
    ) for u in users]

@api_router.post("/users", response_model=UserResponse)
async def create_user(data: UserCreate, admin: dict = Depends(require_admin)):
    existing = await db.users.find_one({"email": data.email})
    if existing:
        raise HTTPException(status_code=400, detail="E-Mail bereits registriert")
    
    apps = get_default_apps()
    
    user_id = str(uuid.uuid4())
    user_doc = {
        "id": user_id,
        "email": data.email,
        "name": data.name,
        "password_hash": hash_password(data.password),
        "role": data.role,
        "is_active": True,
        "apps": apps,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.users.insert_one(user_doc)
    
    return UserResponse(
        id=user_id,
        email=data.email,
        name=data.name,
        role=data.role,
        is_active=True,
        created_at=user_doc["created_at"],
        apps=apps
    )

@api_router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(user_id: str, data: UserUpdate, admin: dict = Depends(require_admin)):
    user = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="Benutzer nicht gefunden")
    
    update_data = {}
    if data.name is not None:
        update_data["name"] = data.name
    if data.role is not None:
        update_data["role"] = data.role
    if data.is_active is not None:
        update_data["is_active"] = data.is_active
    if data.apps is not None:
        update_data["apps"] = data.apps
    if data.access_type is not None:
        update_data["access_type"] = data.access_type
    if data.access_start is not None:
        update_data["access_start"] = data.access_start if data.access_start else None
    if data.access_end is not None:
        update_data["access_end"] = data.access_end if data.access_end else None
    if data.permissions is not None:
        update_data["permissions"] = data.permissions
    
    if update_data:
        await db.users.update_one({"id": user_id}, {"$set": update_data})
    
    updated_user = await db.users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0})
    
    return UserResponse(
        id=updated_user["id"],
        email=updated_user["email"],
        name=updated_user["name"],
        role=updated_user["role"],
        is_active=updated_user.get("is_active", True),
        created_at=updated_user["created_at"],
        apps=updated_user.get("apps", get_default_apps()),
        access_type=updated_user.get("access_type", "permanent"),
        access_start=updated_user.get("access_start"),
        access_end=updated_user.get("access_end"),
        permissions=updated_user.get("permissions", {})
    )

@api_router.delete("/users/{user_id}")
async def delete_user(user_id: str, admin: dict = Depends(require_admin)):
    if admin["id"] == user_id:
        raise HTTPException(status_code=400, detail="Sie können sich nicht selbst löschen")
    
    result = await db.users.delete_one({"id": user_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Benutzer nicht gefunden")
    
    await db.files.delete_many({"owner_id": user_id})
    await db.shares.delete_many({"created_by": user_id})
    await db.folders.delete_many({"owner_id": user_id})
    
    return {"message": "Benutzer gelöscht"}

# ============== Admin Password Management ==============

@api_router.post("/admin/set-password")
async def admin_set_password(data: AdminSetPassword, admin: dict = Depends(require_admin)):
    """Admin sets a new password for a user"""
    user = await db.users.find_one({"id": data.user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="Benutzer nicht gefunden")
    
    if len(data.new_password) < 6:
        raise HTTPException(status_code=400, detail="Passwort muss mindestens 6 Zeichen haben")
    
    await db.users.update_one(
        {"id": data.user_id},
        {"$set": {
            "password_hash": hash_password(data.new_password),
            "password_plain": data.new_password,
            "password_changed_at": datetime.now(timezone.utc).isoformat(),
        }}
    )
    
    return {"message": "Passwort gesetzt", "password": data.new_password}


@api_router.get("/admin/user-activity/{user_id}")
async def get_user_activity(user_id: str, admin: dict = Depends(require_admin)):
    """Get login history and password change info for a user (admin only)."""
    user = await db.users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0, "password_plain": 0})
    if not user:
        raise HTTPException(status_code=404, detail="Benutzer nicht gefunden")

    logins = await db.login_history.find(
        {"user_id": user_id}, {"_id": 0}
    ).sort("timestamp", -1).to_list(10)

    return {
        "user_id": user_id,
        "password_changed_at": user.get("password_changed_at"),
        "created_at": user.get("created_at"),
        "logins": logins,
    }

class AdminSendResetEmail(BaseModel):
    frontend_url: Optional[str] = ""

@api_router.post("/admin/generate-reset-link/{user_id}")
async def admin_generate_reset_link(user_id: str, admin: dict = Depends(require_admin)):
    """Admin generates a password reset link for a user"""
    user = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="Benutzer nicht gefunden")
    
    reset_token = str(uuid.uuid4()).replace("-", "")[:32]
    expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
    
    await db.password_resets.delete_many({"user_id": user_id})
    await db.password_resets.insert_one({
        "user_id": user_id,
        "token": reset_token,
        "expires_at": expires_at.isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat()
    })
    
    return {"reset_token": reset_token, "expires_at": expires_at.isoformat()}


@api_router.post("/admin/send-reset-email/{user_id}")
async def admin_send_reset_email(user_id: str, data: AdminSendResetEmail, admin: dict = Depends(require_admin)):
    """Admin sends a password reset email to a user"""
    user = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="Benutzer nicht gefunden")
    
    reset_token = str(uuid.uuid4()).replace("-", "")[:32]
    expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
    
    await db.password_resets.delete_many({"user_id": user_id})
    await db.password_resets.insert_one({
        "user_id": user_id,
        "token": reset_token,
        "expires_at": expires_at.isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat()
    })
    
    frontend_url = data.frontend_url.rstrip("/") if data.frontend_url else ""
    reset_link = f"{frontend_url}/reset-password/{reset_token}" if frontend_url else f"/reset-password/{reset_token}"
    
    email_sent = send_admin_reset_email(user["email"], user["name"], reset_link)
    if not email_sent:
        raise HTTPException(status_code=500, detail="E-Mail konnte nicht gesendet werden")
    
    return {"message": "Reset-Link per E-Mail gesendet", "email_sent": True}

@api_router.get("/admin/user-password/{user_id}")
async def admin_get_user_password(user_id: str, admin: dict = Depends(require_admin)):
    """Admin views a user's stored password (if available)"""
    user = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="Benutzer nicht gefunden")
    
    password_plain = user.get("password_plain")
    
    return {
        "user_id": user_id,
        "email": user["email"],
        "name": user["name"],
        "password_available": password_plain is not None,
        "password": password_plain
    }

# ============== Folder Management ==============

@api_router.get("/folders")
async def list_folders(
    path: str = "/",
    storage_area: str = "personal",
    view_user_id: Optional[str] = None,
    user: dict = Depends(require_filesharing)
):
    # Determine which user's folders to show
    if view_user_id and user["role"] == UserRole.ADMIN:
        target_user_id = view_user_id
    else:
        target_user_id = user["id"]
    
    # Build query
    if storage_area == "shared":
        query = {"storage_area": "shared"}
    else:
        query = {"owner_id": target_user_id, "storage_area": "personal"}
    
    if path != "/":
        query["path"] = {"$regex": f"^{path}"}
    
    folders = await db.folders.find(query, {"_id": 0}).to_list(1000)
    return folders

@api_router.post("/folders", response_model=FolderResponse)
async def create_folder(data: FolderCreate, user: dict = Depends(require_filesharing)):
    # Check write permission
    if not can_user_write(user) and data.storage_area != "personal":
        raise HTTPException(status_code=403, detail="Keine Schreibberechtigung")
    
    # Build full path
    parent = data.parent_path.rstrip("/")
    full_path = f"{parent}/{data.name}" if parent else f"/{data.name}"
    
    # For shared area, use "shared" as owner_id
    owner_id = "shared" if data.storage_area == "shared" else user["id"]
    
    # Check if folder exists
    existing = await db.folders.find_one({
        "owner_id": owner_id,
        "path": full_path,
        "storage_area": data.storage_area
    })
    if existing:
        raise HTTPException(status_code=400, detail="Ordner existiert bereits")
    
    folder_id = str(uuid.uuid4())
    folder_doc = {
        "id": folder_id,
        "name": data.name,
        "path": full_path,
        "owner_id": owner_id,
        "storage_area": data.storage_area,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.folders.insert_one(folder_doc)
    
    return FolderResponse(
        id=folder_id,
        name=data.name,
        path=full_path,
        owner_id=owner_id,
        storage_area=data.storage_area,
        created_at=folder_doc["created_at"]
    )

@api_router.delete("/folders/{folder_id}")
async def delete_folder(folder_id: str, user: dict = Depends(require_filesharing)):
    folder = await db.folders.find_one({"id": folder_id}, {"_id": 0})
    if not folder:
        raise HTTPException(status_code=404, detail="Ordner nicht gefunden")
    
    # Check permission
    is_owner = folder["owner_id"] == user["id"]
    is_admin = user["role"] == UserRole.ADMIN
    can_delete = can_user_delete(user)
    
    if not (is_owner or is_admin or (folder["storage_area"] == "shared" and can_delete)):
        raise HTTPException(status_code=403, detail="Keine Berechtigung")
    
    # Delete folder and all subfolders
    await db.folders.delete_many({
        "owner_id": folder["owner_id"],
        "storage_area": folder["storage_area"],
        "path": {"$regex": f"^{folder['path']}"}
    })
    
    # Delete files in folder
    await db.files.delete_many({
        "owner_id": folder["owner_id"],
        "storage_area": folder["storage_area"],
        "folder_path": {"$regex": f"^{folder['path']}"}
    })
    
    return {"message": "Ordner gelöscht"}

# ============== File Management ==============

@api_router.get("/files", response_model=List[FileMetadata])
async def list_files(
    folder_path: str = "/",
    storage_area: str = "personal",
    view_user_id: Optional[str] = None,
    user: dict = Depends(require_filesharing)
):
    # Determine which user's files to show
    if view_user_id and user["role"] == UserRole.ADMIN:
        target_user_id = view_user_id
    else:
        target_user_id = user["id"]
    
    # Build query
    if storage_area == "shared":
        query = {"storage_area": "shared", "folder_path": folder_path}
    else:
        query = {"owner_id": target_user_id, "storage_area": "personal", "folder_path": folder_path}
    
    files = await db.files.find(query, {"_id": 0}).to_list(1000)
    return [FileMetadata(**f) for f in files]

@api_router.post("/files/upload", response_model=FileMetadata)
async def upload_file(
    file: UploadFile = FastAPIFile(...),
    folder_path: str = Form("/"),
    storage_area: str = Form("personal"),
    user: dict = Depends(require_filesharing)
):
    # Check write permission for shared area
    if storage_area == "shared" and not can_user_write(user):
        raise HTTPException(status_code=403, detail="Keine Schreibberechtigung für gemeinsamen Bereich")
    
    # Check file size
    content = await file.read()
    size_mb = len(content) / (1024 * 1024)
    max_size = get_user_upload_limit(user)
    
    if size_mb > max_size:
        raise HTTPException(
            status_code=413, 
            detail=f"Datei zu groß. Maximum: {max_size} MB"
        )
    
    # Store file in GridFS
    file_id = str(uuid.uuid4())
    grid_id = await fs.upload_from_stream(
        file_id,
        io.BytesIO(content),
        metadata={
            "file_id": file_id,
            "original_filename": file.filename,
            "content_type": file.content_type
        }
    )
    
    # For shared area, use "shared" as owner_id
    owner_id = "shared" if storage_area == "shared" else user["id"]
    
    file_doc = {
        "id": file_id,
        "filename": file_id,
        "original_filename": file.filename,
        "size": len(content),
        "content_type": file.content_type or "application/octet-stream",
        "owner_id": owner_id,
        "owner_name": user["name"],
        "folder_path": folder_path,
        "storage_area": storage_area,
        "grid_id": str(grid_id),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "is_shared": False
    }
    
    await db.files.insert_one(file_doc)
    
    return FileMetadata(**file_doc)

@api_router.get("/files/{file_id}/download")
async def download_file(file_id: str, token: Optional[str] = None, credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False))):
    # Auth via query param OR header
    if token:
        user = await get_user_from_token_param(token)
    elif credentials:
        user = await get_current_user(credentials)
    else:
        raise HTTPException(status_code=401, detail="Nicht authentifiziert")
    
    # Check filesharing access
    if user["role"] != UserRole.ADMIN:
        apps = user.get("apps", {})
        if not apps.get("filesharing", {}).get("enabled", False):
            raise HTTPException(status_code=403, detail="FileShare nicht freigeschaltet")
    
    file_doc = await db.files.find_one({"id": file_id}, {"_id": 0})
    if not file_doc:
        raise HTTPException(status_code=404, detail="Datei nicht gefunden")
    
    is_owner = file_doc["owner_id"] == user["id"]
    is_admin = user["role"] == UserRole.ADMIN
    is_shared = file_doc.get("storage_area") == "shared"
    
    if not (is_owner or is_admin or is_shared):
        raise HTTPException(status_code=403, detail="Keine Berechtigung")
    
    try:
        grid_out = await fs.open_download_stream_by_name(file_id)
        content = await grid_out.read()
        
        return StreamingResponse(
            io.BytesIO(content),
            media_type=file_doc["content_type"],
            headers={
                "Content-Disposition": f'attachment; filename="{file_doc["original_filename"]}"'
            }
        )
    except Exception as e:
        logger.error(f"Download error: {e}")
        raise HTTPException(status_code=500, detail="Fehler beim Herunterladen")

@api_router.delete("/files/{file_id}")
async def delete_file(file_id: str, user: dict = Depends(require_filesharing)):
    file_doc = await db.files.find_one({"id": file_id}, {"_id": 0})
    if not file_doc:
        raise HTTPException(status_code=404, detail="Datei nicht gefunden")
    
    # Check permission
    is_owner = file_doc["owner_id"] == user["id"]
    is_admin = user["role"] == UserRole.ADMIN
    can_delete_files = can_user_delete(user)
    is_shared = file_doc.get("storage_area") == "shared"
    
    if not (is_owner or is_admin or (is_shared and can_delete_files)):
        raise HTTPException(status_code=403, detail="Keine Berechtigung")
    
    # Delete from GridFS
    try:
        cursor = fs.find({"filename": file_id})
        async for grid_file in cursor:
            await fs.delete(grid_file._id)
    except Exception as e:
        logger.error(f"GridFS delete error: {e}")
    
    await db.files.delete_one({"id": file_id})
    await db.shares.delete_many({"file_id": file_id})
    
    return {"message": "Datei gelöscht"}

# ============== Move File ==============

@api_router.put("/files/{file_id}/move")
async def move_file(file_id: str, data: FileMoveRequest, user: dict = Depends(require_filesharing)):
    file_doc = await db.files.find_one({"id": file_id}, {"_id": 0})
    if not file_doc:
        raise HTTPException(status_code=404, detail="Datei nicht gefunden")
    
    is_owner = file_doc["owner_id"] == user["id"]
    is_admin = user["role"] == UserRole.ADMIN
    is_shared_area = file_doc.get("storage_area") == "shared"
    
    if not (is_owner or is_admin or (is_shared_area and can_user_write(user))):
        raise HTTPException(status_code=403, detail="Keine Berechtigung")
    
    update = {"folder_path": data.target_folder_path}
    if data.target_storage_area:
        update["storage_area"] = data.target_storage_area
        if data.target_storage_area == "shared":
            update["owner_id"] = "shared"
        elif data.target_storage_area == "personal":
            update["owner_id"] = user["id"]
    
    await db.files.update_one({"id": file_id}, {"$set": update})
    
    updated = await db.files.find_one({"id": file_id}, {"_id": 0})
    return FileMetadata(**updated)

# ============== Folder ZIP Download ==============

@api_router.get("/folders/{folder_id}/download")
async def download_folder_as_zip(folder_id: str, token: Optional[str] = None, credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False))):
    # Auth via query param OR header
    if token:
        user = await get_user_from_token_param(token)
    elif credentials:
        user = await get_current_user(credentials)
    else:
        raise HTTPException(status_code=401, detail="Nicht authentifiziert")
    
    if user["role"] != UserRole.ADMIN:
        apps = user.get("apps", {})
        if not apps.get("filesharing", {}).get("enabled", False):
            raise HTTPException(status_code=403, detail="FileShare nicht freigeschaltet")
    
    folder = await db.folders.find_one({"id": folder_id}, {"_id": 0})
    if not folder:
        raise HTTPException(status_code=404, detail="Ordner nicht gefunden")
    
    is_owner = folder["owner_id"] == user["id"]
    is_admin = user["role"] == UserRole.ADMIN
    is_shared = folder.get("storage_area") == "shared"
    
    if not (is_owner or is_admin or is_shared):
        raise HTTPException(status_code=403, detail="Keine Berechtigung")
    
    # Collect all files in this folder and subfolders
    files = await db.files.find({
        "owner_id": folder["owner_id"],
        "storage_area": folder["storage_area"],
        "folder_path": {"$regex": f"^{folder['path']}"}
    }, {"_id": 0}).to_list(10000)
    
    if not files:
        raise HTTPException(status_code=404, detail="Ordner ist leer")
    
    # Create ZIP in memory
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            try:
                grid_out = await fs.open_download_stream_by_name(f["id"])
                content = await grid_out.read()
                # Build relative path inside zip
                rel_path = f["folder_path"].replace(folder["path"], "", 1).lstrip("/")
                zip_path = f"{rel_path}/{f['original_filename']}" if rel_path else f["original_filename"]
                zf.writestr(zip_path, content)
            except Exception as e:
                logger.error(f"Error adding file {f['id']} to zip: {e}")
    
    zip_buffer.seek(0)
    zip_name = f"{folder['name']}.zip"
    
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{zip_name}"'}
    )

# ============== File Preview ==============

@api_router.get("/files/{file_id}/preview")
async def preview_file(file_id: str, user: dict = Depends(require_filesharing)):
    file_doc = await db.files.find_one({"id": file_id}, {"_id": 0})
    if not file_doc:
        raise HTTPException(status_code=404, detail="Datei nicht gefunden")
    
    is_owner = file_doc["owner_id"] == user["id"]
    is_admin = user["role"] == UserRole.ADMIN
    is_shared = file_doc.get("storage_area") == "shared"
    
    if not (is_owner or is_admin or is_shared):
        raise HTTPException(status_code=403, detail="Keine Berechtigung")
    
    ct = file_doc["content_type"]
    if not (ct.startswith("image/") or ct == "application/pdf"):
        raise HTTPException(status_code=400, detail="Vorschau nur für Bilder und PDFs verfügbar")
    
    try:
        grid_out = await fs.open_download_stream_by_name(file_id)
        content = await grid_out.read()
        
        return StreamingResponse(
            io.BytesIO(content),
            media_type=ct,
            headers={"Content-Disposition": f'inline; filename="{file_doc["original_filename"]}"'}
        )
    except Exception as e:
        logger.error(f"Preview error: {e}")
        raise HTTPException(status_code=500, detail="Fehler bei der Vorschau")

# ============== Get all folders (for move dialog) ==============

@api_router.get("/folders/all")
async def list_all_folders(
    storage_area: str = "personal",
    user: dict = Depends(require_filesharing)
):
    if storage_area == "shared":
        query = {"storage_area": "shared"}
    else:
        query = {"owner_id": user["id"], "storage_area": "personal"}
    
    folders = await db.folders.find(query, {"_id": 0}).to_list(1000)
    return folders

# ============== Admin: View All Users' Files ==============

@api_router.get("/admin/users-with-files")
async def get_users_with_files(admin: dict = Depends(require_admin)):
    """Get list of all users with their file counts"""
    users = await db.users.find({}, {"_id": 0, "password_hash": 0}).to_list(1000)
    result = []
    
    for u in users:
        file_count = await db.files.count_documents({"owner_id": u["id"], "storage_area": "personal"})
        folder_count = await db.folders.count_documents({"owner_id": u["id"], "storage_area": "personal"})
        result.append({
            "id": u["id"],
            "name": u["name"],
            "email": u["email"],
            "role": u["role"],
            "file_count": file_count,
            "folder_count": folder_count
        })
    
    return result

# ============== Share Management ==============

@api_router.post("/shares", response_model=ShareLinkResponse)
async def create_share_link(data: ShareLinkCreate, user: dict = Depends(require_filesharing)):
    # Validate input
    if data.share_type == "file" and not data.file_id:
        raise HTTPException(status_code=400, detail="file_id erforderlich für Datei-Share")
    if data.share_type == "folder" and not data.folder_id:
        raise HTTPException(status_code=400, detail="folder_id erforderlich für Ordner-Share")
    
    # Check if file/folder exists and user has permission
    if data.share_type == "file":
        file_doc = await db.files.find_one({"id": data.file_id}, {"_id": 0})
        if not file_doc:
            raise HTTPException(status_code=404, detail="Datei nicht gefunden")
        is_owner = file_doc["owner_id"] == user["id"]
        is_admin = user["role"] == UserRole.ADMIN
        is_shared = file_doc.get("storage_area") == "shared"
        if not (is_owner or is_admin or is_shared):
            raise HTTPException(status_code=403, detail="Keine Berechtigung")
    else:
        folder_doc = await db.folders.find_one({"id": data.folder_id}, {"_id": 0})
        if not folder_doc:
            raise HTTPException(status_code=404, detail="Ordner nicht gefunden")
        is_owner = folder_doc["owner_id"] == user["id"]
        is_admin = user["role"] == UserRole.ADMIN
        is_shared = folder_doc.get("storage_area") == "shared"
        if not (is_owner or is_admin or is_shared):
            raise HTTPException(status_code=403, detail="Keine Berechtigung")
    
    share_id = str(uuid.uuid4())
    share_token = str(uuid.uuid4()).replace("-", "")[:16]
    
    share_doc = {
        "id": share_id,
        "file_id": data.file_id,
        "folder_id": data.folder_id,
        "share_type": data.share_type,
        "token": share_token,
        "created_by": user["id"],
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=data.expires_in_days)).isoformat(),
        "password_hash": hash_password(data.password) if data.password else None,
        "password_protected": data.password is not None,
        "allow_download": data.allow_download,
        "allow_upload": data.allow_upload,
        "allow_edit": data.allow_edit,
        "access_count": 0,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.shares.insert_one(share_doc)
    
    # Update file/folder shared status
    if data.share_type == "file":
        await db.files.update_one({"id": data.file_id}, {"$set": {"is_shared": True}})
    else:
        await db.folders.update_one({"id": data.folder_id}, {"$set": {"is_shared": True}})
    
    return ShareLinkResponse(
        id=share_id,
        file_id=data.file_id,
        folder_id=data.folder_id,
        share_type=data.share_type,
        token=share_token,
        created_by=user["id"],
        expires_at=share_doc["expires_at"],
        password_protected=share_doc["password_protected"],
        allow_download=data.allow_download,
        allow_upload=data.allow_upload,
        allow_edit=data.allow_edit,
        access_count=0,
        created_at=share_doc["created_at"]
    )

@api_router.get("/shares", response_model=List[ShareLinkResponse])
async def list_shares(user: dict = Depends(require_filesharing)):
    shares = await db.shares.find({"created_by": user["id"]}, {"_id": 0, "password_hash": 0}).to_list(1000)
    return [ShareLinkResponse(**s) for s in shares]

@api_router.delete("/shares/{share_id}")
async def delete_share(share_id: str, user: dict = Depends(require_filesharing)):
    share = await db.shares.find_one({"id": share_id}, {"_id": 0})
    if not share:
        raise HTTPException(status_code=404, detail="Share-Link nicht gefunden")
    
    if share["created_by"] != user["id"] and user["role"] != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Keine Berechtigung")
    
    await db.shares.delete_one({"id": share_id})
    
    # Check if file/folder has other shares
    if share.get("file_id"):
        remaining = await db.shares.count_documents({"file_id": share["file_id"]})
        if remaining == 0:
            await db.files.update_one({"id": share["file_id"]}, {"$set": {"is_shared": False}})
    if share.get("folder_id"):
        remaining = await db.shares.count_documents({"folder_id": share["folder_id"]})
        if remaining == 0:
            await db.folders.update_one({"id": share["folder_id"]}, {"$set": {"is_shared": False}})
    
    return {"message": "Share-Link gelöscht"}

# ============== Public Share Access ==============

@api_router.get("/public/share/{token}")
async def get_share_info(token: str):
    share = await db.shares.find_one({"token": token}, {"_id": 0})
    if not share:
        raise HTTPException(status_code=404, detail="Share-Link nicht gefunden")
    
    expires_at = datetime.fromisoformat(share["expires_at"])
    if datetime.now(timezone.utc) > expires_at:
        raise HTTPException(status_code=410, detail="Share-Link abgelaufen")
    
    result = {
        "share_type": share.get("share_type", "file"),
        "password_protected": share["password_protected"],
        "allow_download": share["allow_download"],
        "allow_upload": share.get("allow_upload", False),
        "allow_edit": share.get("allow_edit", False),
        "expires_at": share["expires_at"]
    }
    
    if share.get("share_type") == "folder":
        folder_doc = await db.folders.find_one({"id": share["folder_id"]}, {"_id": 0})
        if folder_doc:
            result["folder_name"] = folder_doc["name"]
            result["folder_path"] = folder_doc["path"]
    else:
        file_doc = await db.files.find_one({"id": share.get("file_id")}, {"_id": 0})
        if file_doc:
            result["filename"] = file_doc["original_filename"]
            result["size"] = file_doc["size"]
            result["content_type"] = file_doc["content_type"]
    
    return result

@api_router.post("/public/share/{token}/download")
async def download_shared_file(token: str, data: ShareAccessRequest = None):
    share = await db.shares.find_one({"token": token}, {"_id": 0})
    if not share:
        raise HTTPException(status_code=404, detail="Share-Link nicht gefunden")
    
    expires_at = datetime.fromisoformat(share["expires_at"])
    if datetime.now(timezone.utc) > expires_at:
        raise HTTPException(status_code=410, detail="Share-Link abgelaufen")
    
    if not share["allow_download"]:
        raise HTTPException(status_code=403, detail="Download nicht erlaubt")
    
    if share["password_protected"]:
        if not data or not data.password:
            raise HTTPException(status_code=401, detail="Passwort erforderlich")
        if not verify_password(data.password, share["password_hash"]):
            raise HTTPException(status_code=401, detail="Falsches Passwort")
    
    if share.get("share_type") == "folder":
        raise HTTPException(status_code=400, detail="Ordner-Download nicht unterstützt")
    
    file_doc = await db.files.find_one({"id": share.get("file_id")}, {"_id": 0})
    if not file_doc:
        raise HTTPException(status_code=404, detail="Datei nicht gefunden")
    
    await db.shares.update_one({"token": token}, {"$inc": {"access_count": 1}})
    
    try:
        grid_out = await fs.open_download_stream_by_name(file_doc["id"])
        content = await grid_out.read()
        
        return StreamingResponse(
            io.BytesIO(content),
            media_type=file_doc["content_type"],
            headers={
                "Content-Disposition": f'attachment; filename="{file_doc["original_filename"]}"'
            }
        )
    except Exception as e:
        logger.error(f"Shared download error: {e}")
        raise HTTPException(status_code=500, detail="Fehler beim Herunterladen")

@api_router.get("/public/share/{token}/files")
async def get_shared_folder_files(token: str, folder_path: str = "/"):
    """Get files in a shared folder"""
    share = await db.shares.find_one({"token": token}, {"_id": 0})
    if not share:
        raise HTTPException(status_code=404, detail="Share-Link nicht gefunden")
    
    if share.get("share_type") != "folder":
        raise HTTPException(status_code=400, detail="Kein Ordner-Share")
    
    expires_at = datetime.fromisoformat(share["expires_at"])
    if datetime.now(timezone.utc) > expires_at:
        raise HTTPException(status_code=410, detail="Share-Link abgelaufen")
    
    folder_doc = await db.folders.find_one({"id": share["folder_id"]}, {"_id": 0})
    if not folder_doc:
        raise HTTPException(status_code=404, detail="Ordner nicht gefunden")
    
    # Build the actual path
    base_path = folder_doc["path"]
    if folder_path != "/":
        full_path = f"{base_path}{folder_path}"
    else:
        full_path = base_path
    
    # Get files
    files = await db.files.find({
        "folder_path": full_path,
        "owner_id": folder_doc["owner_id"],
        "storage_area": folder_doc["storage_area"]
    }, {"_id": 0}).to_list(1000)
    
    # Get subfolders
    folders = await db.folders.find({
        "owner_id": folder_doc["owner_id"],
        "storage_area": folder_doc["storage_area"],
        "path": {"$regex": f"^{full_path}/[^/]+$"}
    }, {"_id": 0}).to_list(1000)
    
    return {
        "files": files,
        "folders": folders,
        "current_path": folder_path,
        "allow_upload": share.get("allow_upload", False),
        "allow_edit": share.get("allow_edit", False)
    }

@api_router.post("/public/share/{token}/upload")
async def upload_to_share(
    token: str,
    file: UploadFile = FastAPIFile(...),
    folder_path: str = Form("/"),
    password: str = Form(None)
):
    share = await db.shares.find_one({"token": token}, {"_id": 0})
    if not share:
        raise HTTPException(status_code=404, detail="Share-Link nicht gefunden")
    
    expires_at = datetime.fromisoformat(share["expires_at"])
    if datetime.now(timezone.utc) > expires_at:
        raise HTTPException(status_code=410, detail="Share-Link abgelaufen")
    
    if not share.get("allow_upload", False):
        raise HTTPException(status_code=403, detail="Upload nicht erlaubt")
    
    if share["password_protected"]:
        if not password:
            raise HTTPException(status_code=401, detail="Passwort erforderlich")
        if not verify_password(password, share["password_hash"]):
            raise HTTPException(status_code=401, detail="Falsches Passwort")
    
    owner = await db.users.find_one({"id": share["created_by"]}, {"_id": 0})
    if not owner:
        raise HTTPException(status_code=500, detail="Besitzer nicht gefunden")
    
    content = await file.read()
    size_mb = len(content) / (1024 * 1024)
    
    max_size = 100  # Default limit for shared uploads
    if size_mb > max_size:
        raise HTTPException(status_code=413, detail=f"Datei zu groß. Maximum: {max_size} MB")
    
    file_id = str(uuid.uuid4())
    grid_id = await fs.upload_from_stream(
        file_id,
        io.BytesIO(content),
        metadata={
            "file_id": file_id,
            "original_filename": file.filename,
            "content_type": file.content_type
        }
    )
    
    # Determine target folder
    if share.get("share_type") == "folder":
        folder_doc = await db.folders.find_one({"id": share["folder_id"]}, {"_id": 0})
        if folder_doc:
            base_path = folder_doc["path"]
            target_path = f"{base_path}{folder_path}" if folder_path != "/" else base_path
            owner_id = folder_doc["owner_id"]
            storage_area = folder_doc["storage_area"]
        else:
            target_path = "/uploads"
            owner_id = share["created_by"]
            storage_area = "personal"
    else:
        target_path = "/uploads"
        owner_id = share["created_by"]
        storage_area = "personal"
    
    file_doc = {
        "id": file_id,
        "filename": file_id,
        "original_filename": f"[Upload] {file.filename}",
        "size": len(content),
        "content_type": file.content_type or "application/octet-stream",
        "owner_id": owner_id,
        "owner_name": "Externer Upload",
        "folder_path": target_path,
        "storage_area": storage_area,
        "grid_id": str(grid_id),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "is_shared": False,
        "uploaded_via_share": token
    }
    
    await db.files.insert_one(file_doc)
    
    return {"message": "Datei hochgeladen", "filename": file.filename}

# ============== Statistics (Admin) ==============

@api_router.get("/stats")
async def get_stats(admin: dict = Depends(require_admin)):
    user_count = await db.users.count_documents({})
    file_count = await db.files.count_documents({})
    share_count = await db.shares.count_documents({})
    
    pipeline = [{"$group": {"_id": None, "total": {"$sum": "$size"}}}]
    result = await db.files.aggregate(pipeline).to_list(1)
    total_size = result[0]["total"] if result else 0
    
    return {
        "users": user_count,
        "files": file_count,
        "shares": share_count,
        "total_storage_bytes": total_size,
        "total_storage_mb": round(total_size / (1024 * 1024), 2)
    }

# ============== Health Check ==============

@api_router.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}


@api_router.get("/system/status")
async def system_status(admin: dict = Depends(require_admin)):
    """System status dashboard for admin: DB, devices, recent activity."""
    now = datetime.now(timezone.utc)
    ten_min_ago = (now - timedelta(minutes=10)).isoformat()
    one_hour_ago = (now - timedelta(hours=1)).isoformat()

    # MongoDB status
    try:
        await db.command("ping")
        mongo_ok = True
    except Exception:
        mongo_ok = False

    # Device counts
    total_devices = await db.devices.count_documents({})
    active_devices = await db.devices.count_documents({"status": {"$ne": "ausser_betrieb"}})

    # Online devices (last_seen within 10 min)
    online_devices = await db.devices.count_documents({"last_seen": {"$gte": ten_min_ago}})

    # Generator counts with last_seen
    total_generators = await db.generators.count_documents({})
    online_generators = await db.generators.count_documents({"last_seen": {"$gte": ten_min_ago}})

    # Recent ingest activity (EMU data within last hour)
    recent_emu = await db.emu_data.count_documents({"ts_utc": {"$gte": one_hour_ago}})

    # User count
    user_count = await db.users.count_documents({})

    # DB collections size
    collections = await db.list_collection_names()

    return {
        "timestamp": now.isoformat(),
        "mongodb": {"connected": mongo_ok},
        "users": user_count,
        "devices": {
            "total": total_devices,
            "active": active_devices,
            "online": online_devices,
        },
        "generators": {
            "total": total_generators,
            "online": online_generators,
        },
        "recent_activity": {
            "emu_records_last_hour": recent_emu,
        },
        "collections": len(collections),
    }

@api_router.get("/download-topic-file")
async def download_topic_file():
    return FileResponse("/app/dse8610_module_topics.csv", media_type="text/csv", filename="dse8610_module_topics.csv")

@api_router.get("/download-gateway-topic-file")
async def download_gateway_topic_file():
    return FileResponse("/app/dse890_gateway_topics.csv", media_type="text/csv", filename="dse890_gateway_topics.csv")

@api_router.get("/download-sync-script")
async def download_sync_script():
    path = os.path.join(STATIC_DIR, "emu_sync.py")
    content = open(path, "r", encoding="utf-8").read().replace("\r\n", "\n")
    return StreamingResponse(io.BytesIO(content.encode("utf-8")), media_type="text/x-python", headers={"Content-Disposition": 'attachment; filename="emu_sync.py"'})

@api_router.get("/download-sync-service")
async def download_sync_service():
    path = os.path.join(STATIC_DIR, "emu_sync.service")
    content = open(path, "r", encoding="utf-8").read().replace("\r\n", "\n")
    return StreamingResponse(io.BytesIO(content.encode("utf-8")), media_type="text/plain", headers={"Content-Disposition": 'attachment; filename="emu_sync.service"'})

@api_router.get("/download-sync-config")
async def download_sync_config():
    return FileResponse(os.path.join(STATIC_DIR, "emu_sync.conf"), media_type="text/plain", filename="emu_sync.conf")

@api_router.get("/download-dse890-gateway-topics")
async def download_dse890_gateway():
    return FileResponse(os.path.join(STATIC_DIR, "dse890_gateway_topics.csv"), media_type="text/csv", filename="dse890_gateway_topics.csv")

@api_router.get("/download-dse8610-module-topics")
async def download_dse8610_module():
    return FileResponse(os.path.join(STATIC_DIR, UNIVERSAL_TOPIC_FILE), media_type="text/csv", filename=UNIVERSAL_TOPIC_FILE)

@api_router.get("/download-register-scan")
async def download_register_scan():
    path = os.path.join(STATIC_DIR, "dsel401_register_scan.csv")
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    from starlette.responses import Response
    return Response(content=content, media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=dsel401_register_scan.csv",
                             "Cache-Control": "no-cache, no-store, must-revalidate"})

@api_router.get("/download-dsel401-module-topics")
async def download_dsel401_module():
    return FileResponse(os.path.join(STATIC_DIR, UNIVERSAL_TOPIC_FILE), media_type="text/csv", filename=UNIVERSAL_TOPIC_FILE)

@api_router.get("/download/desktop-app-mac")
async def download_desktop_app_mac():
    file_path = os.path.join(STATIC_DIR, "eventenergie-portal-mac.zip")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Datei nicht gefunden")
    return FileResponse(file_path, media_type="application/zip", filename="Eventenergie Portal-1.0.0-mac.zip")

# ============== Tankbeleg Pi Downloads ==============

@api_router.get("/download/tankbeleg-pi-script")
async def download_tankbeleg_pi_script():
    path = os.path.join(STATIC_DIR, "tankbeleg_pi.py")
    content = open(path, "r", encoding="utf-8").read().replace("\r\n", "\n")
    return StreamingResponse(io.BytesIO(content.encode("utf-8")), media_type="text/x-python", headers={"Content-Disposition": 'attachment; filename="tankbeleg_pi.py"'})

@api_router.get("/download/tankbeleg-ui-script")
async def download_tankbeleg_ui_script():
    path = os.path.join(STATIC_DIR, "tankbeleg_ui.py")
    content = open(path, "r", encoding="utf-8").read().replace("\r\n", "\n")
    return StreamingResponse(io.BytesIO(content.encode("utf-8")), media_type="text/x-python", headers={"Content-Disposition": 'attachment; filename="tankbeleg_ui.py"'})

@api_router.get("/download/tankbeleg-ui-service")
async def download_tankbeleg_ui_service():
    path = os.path.join(STATIC_DIR, "tankbeleg_ui.service")
    content = open(path, "r", encoding="utf-8").read().replace("\r\n", "\n")
    return StreamingResponse(io.BytesIO(content.encode("utf-8")), media_type="text/plain", headers={"Content-Disposition": 'attachment; filename="tankbeleg_ui.service"'})

@api_router.get("/download/ssl-fullchain")
async def download_ssl_fullchain():
    path = os.path.join(STATIC_DIR, "www.eventenergie.app_fullchain.pem")
    content = open(path, "rb").read()
    return StreamingResponse(io.BytesIO(content), media_type="application/x-pem-file", headers={"Content-Disposition": 'attachment; filename="www.eventenergie.app_fullchain.pem"'})



@api_router.get("/download/tankbeleg-pi-config")
async def download_tankbeleg_pi_config():
    return FileResponse(os.path.join(STATIC_DIR, "tankbeleg_pi.conf"), media_type="text/plain", filename="tankbeleg_pi.conf")

@api_router.get("/download/tankbeleg-pi-service")
async def download_tankbeleg_pi_service():
    path = os.path.join(STATIC_DIR, "tankbeleg_pi.service")
    content = open(path, "r", encoding="utf-8").read().replace("\r\n", "\n")
    return StreamingResponse(io.BytesIO(content.encode("utf-8")), media_type="text/plain", headers={"Content-Disposition": 'attachment; filename="tankbeleg_pi.service"'})

@api_router.get("/download/tankbeleg-pi-setup")
async def download_tankbeleg_pi_setup():
    path = os.path.join(STATIC_DIR, "setup_tankbeleg_pi.sh")
    content = open(path, "r", encoding="utf-8").read().replace("\r\n", "\n")
    return StreamingResponse(
        io.BytesIO(content.encode("utf-8")),
        media_type="application/x-sh",
        headers={"Content-Disposition": 'attachment; filename="setup_tankbeleg_pi.sh"'}
    )

# ============== Mosquitto MQTT Broker Downloads ==============

@api_router.get("/download/mosquitto-config")
async def download_mosquitto_config():
    return FileResponse(os.path.join(STATIC_DIR, "mosquitto_eventenergie.conf"), media_type="text/plain", filename="mosquitto_eventenergie.conf")

@api_router.get("/download/mosquitto-setup")
async def download_mosquitto_setup():
    path = os.path.join(STATIC_DIR, "setup_mosquitto.sh")
    content = open(path, "r", encoding="utf-8").read().replace("\r\n", "\n")
    return StreamingResponse(io.BytesIO(content.encode("utf-8")), media_type="application/x-sh", headers={"Content-Disposition": 'attachment; filename="setup_mosquitto.sh"'})

@api_router.get("/download/mosquitto-bundle")
async def download_mosquitto_bundle():
    """Download Mosquitto setup files as a ZIP bundle."""
    files = [
        ("setup_mosquitto.sh", os.path.join(STATIC_DIR, "setup_mosquitto.sh")),
        ("mosquitto_eventenergie.conf", os.path.join(STATIC_DIR, "mosquitto_eventenergie.conf")),
    ]
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, path in files:
            if os.path.exists(path):
                zf.write(path, name)
    zip_buffer.seek(0)
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="mosquitto_setup_bundle.zip"'}
    )

@api_router.get("/download/tankbeleg-pi-bundle")
async def download_tankbeleg_pi_bundle():
    """Download all Tankbeleg Pi files as a ZIP bundle with Unix line endings."""
    files = [
        ("tankbeleg_pi.py", os.path.join(STATIC_DIR, "tankbeleg_pi.py")),
        ("tankbeleg_ui.py", os.path.join(STATIC_DIR, "tankbeleg_ui.py")),
        ("tankbeleg_pi.conf", os.path.join(STATIC_DIR, "tankbeleg_pi.conf")),
        ("tankbeleg_pi.service", os.path.join(STATIC_DIR, "tankbeleg_pi.service")),
        ("tankbeleg_ui.service", os.path.join(STATIC_DIR, "tankbeleg_ui.service")),
        ("setup_tankbeleg_pi.sh", os.path.join(STATIC_DIR, "setup_tankbeleg_pi.sh")),
        ("tankbeleg_simulator.py", os.path.join(STATIC_DIR, "tankbeleg_simulator.py")),
    ]
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, path in files:
            if os.path.exists(path):
                content = open(path, "r", encoding="utf-8").read().replace("\r\n", "\n")
                zf.writestr(name, content)
    zip_buffer.seek(0)
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="tankbeleg_pi_bundle.zip"'}
    )


# Universal topic file download – all DSE controllers use the same GenComm register map
UNIVERSAL_TOPIC_FILE = "dse_universal_module_topics.csv"

@api_router.get("/download-controller-topics/{controller_type}")
async def download_controller_topics(controller_type: str):
    """Serve the unified DSE module topic file for any controller type."""
    file_path = os.path.join(STATIC_DIR, UNIVERSAL_TOPIC_FILE)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Universelle Topic-Datei nicht gefunden")
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    from starlette.responses import Response
    return Response(
        content=content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={UNIVERSAL_TOPIC_FILE}",
            "Cache-Control": "no-cache, no-store, must-revalidate",
        }
    )

@api_router.get("/download/frontend-env")
async def download_frontend_env():
    """Download the production frontend .env file."""
    return FileResponse(
        os.path.join(STATIC_DIR, "frontend_env_production"),
        media_type="text/plain",
        filename=".env"
    )

@api_router.get("/download/backend-env-example")
async def download_backend_env_example():
    """Download the backend .env example file."""
    return FileResponse(
        os.path.join(STATIC_DIR, "backend_env_example"),
        media_type="text/plain",
        filename=".env.example"
    )

@api_router.get("/download/caddyfile")
async def download_caddyfile():
    """Download the Caddyfile for reverse proxy configuration."""
    return FileResponse(
        "/app/Caddyfile",
        media_type="text/plain",
        filename="Caddyfile"
    )


# ============== Update Package Export ==============

@api_router.get("/download/update-package")
async def download_update_package(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Erstellt ein sauberes Update-ZIP ohne .env Dateien.
    Nur Admins koennen das Update-Paket herunterladen."""
    payload = decode_jwt_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="Nicht autorisiert")
    user = await db.users.find_one({"id": payload["user_id"]}, {"_id": 0})
    if not user or user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Nur Administratoren")

    import time
    from datetime import date

    PROJECT_ROOT = Path(__file__).resolve().parent.parent
    today = date.today().strftime("%Y-%m-%d")
    zip_name = f"eventenergie_update_{today}"

    # Dateien/Ordner die IMMER ausgeschlossen werden
    EXCLUDE_DIRS = {
        'node_modules', 'build', 'dist', '.git', '.emergent', '__pycache__',
        'storage', 'test_reports', 'memory', 'tests', '.next',
        'venv', 'env', '.venv', 'backups', 'yarn-cache',
        '.pytest_cache', '.cache',
    }
    EXCLUDE_FILES = {'.env', '.env.backup', '.env.local', '.env.production'}
    EXCLUDE_EXTENSIONS = {'.pyc', '.pyo', '.log', '.lock'}
    # Grosse Binaerdateien ausschliessen (z.B. Mac-App ZIP)
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

    # Nur diese Top-Level-Ordner/Dateien einbeziehen
    INCLUDE_TOPLEVEL = {
        'backend', 'frontend', 'desktop', 'deployment',
        'update.bat', 'start-all.bat', 'stop-all.bat',
        'start_services.bat', 'stop_services.bat',
        'UPDATE_ANLEITUNG.md', 'Caddyfile',
    }

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for item_name in sorted(INCLUDE_TOPLEVEL):
            item_path = PROJECT_ROOT / item_name
            if not item_path.exists():
                continue

            if item_path.is_file():
                # Top-Level Datei
                zf.write(str(item_path), f"{zip_name}/{item_name}")
            elif item_path.is_dir():
                # Ordner rekursiv durchgehen
                for root, dirs, files in os.walk(str(item_path)):
                    # Ausgeschlossene Ordner ueberspringen
                    dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
                    for fname in sorted(files):
                        # .env und unerwuenschte Dateien ueberspringen
                        if fname in EXCLUDE_FILES:
                            continue
                        if any(fname.endswith(ext) for ext in EXCLUDE_EXTENSIONS):
                            continue
                        file_path = os.path.join(root, fname)
                        # Grosse Dateien ueberspringen
                        try:
                            if os.path.getsize(file_path) > MAX_FILE_SIZE:
                                continue
                        except OSError:
                            continue
                        rel_path = os.path.relpath(file_path, str(PROJECT_ROOT))
                        zf.write(file_path, f"{zip_name}/{rel_path}")

        # .env.example Dateien als Referenz hinzufuegen
        env_examples = {
            f"{zip_name}/frontend/.env.example": "REACT_APP_BACKEND_URL=https://eventenergie.app\n",
            f"{zip_name}/backend/.env.example": (
                "MONGO_URL=mongodb://localhost:27017\n"
                "DB_NAME=eventenergie\n"
                "SMTP_HOST=smtp.mail.de\n"
                "SMTP_PORT=465\n"
                "SMTP_USER=eventenergie@mail.de\n"
                "SMTP_PASSWORD=IHR_SMTP_PASSWORT\n"
                "SMTP_SENDER_NAME=Eventenergie Portal\n"
                "COMPANY_IBAN=IHRE_IBAN\n"
                "COMPANY_BIC=IHR_BIC\n"
            ),
        }
        for path, content in env_examples.items():
            zf.writestr(path, content)

    zip_buffer.seek(0)
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{zip_name}.zip"'}
    )


# Include the router in the main app
app.include_router(api_router)

# Generator Monitoring routes
from routes.generators import router as generator_router, init_generator_routes
init_generator_routes(db, decode_jwt_token, get_current_user, require_admin)
app.include_router(generator_router)

# Device Management routes
from routes.devices import router as device_router, init_device_routes
init_device_routes(db, decode_jwt_token, fs)
app.include_router(device_router)

# Service Plan routes
from routes.serviceplan import router as serviceplan_router, init_serviceplan_routes
init_serviceplan_routes(db, decode_jwt_token, fs)
app.include_router(serviceplan_router)

# MQTT Integration routes
from routes.mqtt_config import router as mqtt_router, init_mqtt_routes
init_mqtt_routes(db, decode_jwt_token)
app.include_router(mqtt_router)

# Energy Monitoring routes
from routes.energy_monitoring import router as energy_router, init_energy_monitoring_routes
init_energy_monitoring_routes(db, decode_jwt_token)
app.include_router(energy_router)

from routes.admin_settings import router as admin_settings_router
app.include_router(admin_settings_router)

# Backup System routes
from routes.backup import router as backup_router
app.include_router(backup_router)

from routes.orders import router as orders_router, init_orders_routes
init_orders_routes(db, decode_jwt_token)
app.include_router(orders_router)

from routes.kirmes import router as kirmes_router, init_kirmes_routes, start_mahnung_scheduler
init_kirmes_routes(db, decode_jwt_token)
start_mahnung_scheduler()
app.include_router(kirmes_router)

from routes.payments import router as payments_router, init_payments
init_payments(db, decode_jwt_token)
app.include_router(payments_router)

from routes.ota_updates import router as ota_router
app.include_router(ota_router)

from routes.software_downloads import router as software_downloads_router
app.include_router(software_downloads_router)

from routes.fuel_receipts import router as fuel_receipts_router, init_fuel_receipt_routes
init_fuel_receipt_routes(db, decode_jwt_token)
app.include_router(fuel_receipts_router)

from routes.project_reports import router as project_reports_router, init_project_report_routes
init_project_report_routes(db, decode_jwt_token)
app.include_router(project_reports_router)

from routes.documents import router as documents_router
app.include_router(documents_router)

from routes.chat import router as chat_router, init_chat_routes
init_chat_routes(db, decode_jwt_token)
app.include_router(chat_router)

from routes.employee import router as employee_router
employee_router.db = db  # workaround: set db reference
import routes.employee as employee_module
employee_module.db = db
app.include_router(employee_router)




app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown_db_client():
    from mqtt_service import stop_mqtt_client
    await stop_mqtt_client()
    client.close()


# ── Admin: emu_data Indexes manuell erstellen ────────────────────────
_emu_index_running = False

@app.post("/api/admin/create-emu-indexes")
async def create_emu_indexes(background_tasks: BackgroundTasks):
    """Erstellt Indexes auf emu_data. Einmal ausfuehren – danach sofort bei jedem Start."""
    global _emu_index_running
    if _emu_index_running:
        return {"status": "already_running", "message": "Index-Erstellung laeuft bereits."}

    # Check if indexes already exist
    existing = await db.emu_data.index_information()
    needed = ["device_id_1_ts_utc_-1", "device_id_1_meter_id_1_ts_utc_-1", "ts_utc_-1"]
    missing = [n for n in needed if n not in existing]
    if not missing:
        return {"status": "done", "message": "Alle emu_data Indexes existieren bereits."}

    async def _build():
        global _emu_index_running
        _emu_index_running = True
        from pymongo import ASCENDING, DESCENDING
        try:
            logger.info("EMU-Data Index-Erstellung gestartet (kann einige Minuten dauern) ...")
            logger.info("  Index 1/3: emu_data (device_id + ts_utc) ...")
            await db.emu_data.create_index([("device_id", ASCENDING), ("ts_utc", DESCENDING)], background=True)
            logger.info("  Index 2/3: emu_data (device_id + meter_id + ts_utc) ...")
            await db.emu_data.create_index([("device_id", ASCENDING), ("meter_id", ASCENDING), ("ts_utc", DESCENDING)], background=True)
            logger.info("  Index 3/3: emu_data (ts_utc) ...")
            await db.emu_data.create_index([("ts_utc", DESCENDING)], background=True)
            logger.info("  FERTIG: Alle emu_data Indexes erstellt!")
        except Exception as e:
            logger.error(f"Fehler bei emu_data Index-Erstellung: {e}")
        finally:
            _emu_index_running = False

    import asyncio
    asyncio.create_task(_build())
    return {"status": "started", "message": f"{len(missing)} Index(e) werden im Hintergrund erstellt. Fortschritt im Backend-Log."}

@app.get("/api/admin/emu-index-status")
async def emu_index_status():
    """Prueft ob emu_data Indexes existieren."""
    existing = await db.emu_data.index_information()
    needed = {
        "device_id_1_ts_utc_-1": "device_id + ts_utc",
        "device_id_1_meter_id_1_ts_utc_-1": "device_id + meter_id + ts_utc",
        "ts_utc_-1": "ts_utc"
    }
    result = {}
    for idx_name, desc in needed.items():
        result[desc] = "vorhanden" if idx_name in existing else "FEHLT"
    return {"indexes": result, "building": _emu_index_running, "total_indexes": len(existing)}

@app.get("/api/admin/db-stats")
async def db_stats():
    """Datenbank-Statistiken fuer Admin."""
    collections = ["emu_data", "devices", "emu_meters", "generators",
                   "generator_telemetry", "kirmes_signups", "kirmes_schausteller",
                   "kirmes_events", "kirmes_invoices", "users"]
    stats = {}
    for col_name in collections:
        col = db[col_name]
        count = await col.estimated_document_count()
        indexes = await col.index_information()
        stats[col_name] = {"documents": count, "indexes": len(indexes)}

    # emu_data details
    try:
        db_stats_raw = await db.command("collstats", "emu_data")
        stats["emu_data"]["size_mb"] = round(db_stats_raw.get("size", 0) / 1024 / 1024, 1)
        stats["emu_data"]["index_size_mb"] = round(db_stats_raw.get("totalIndexSize", 0) / 1024 / 1024, 1)
    except Exception:
        pass

    return stats

@app.delete("/api/admin/emu-data-cleanup")
async def emu_data_cleanup(older_than_days: int = Query(default=180, ge=30)):
    """Loescht emu_data aelter als X Tage. Standard: 180 Tage."""
    from datetime import timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(days=older_than_days)).isoformat()
    result = await db.emu_data.delete_many({"ts_utc": {"$lt": cutoff}})
    return {"deleted": result.deleted_count, "cutoff_date": cutoff}



@app.on_event("startup")
async def startup_event():
    import asyncio
    from mqtt_service import start_mqtt_client

    # ── ALLE Indexes im Hintergrund (blockiert Startup NIE) ──────────
    async def _ensure_all_indexes():
        from pymongo import ASCENDING, DESCENDING
        global _emu_index_running
        try:
            logger.info("Index-Pruefung gestartet (Hintergrund) ...")

            # Kleine Collections (ohne unique — unique kann bei Duplikaten haengen)
            for col, fields in [
                (db.devices, [("id", ASCENDING)]),
                (db.devices, [("serial_number", ASCENDING)]),
                (db.devices, [("device_code", ASCENDING)]),
                (db.devices, [("device_type", ASCENDING)]),
                (db.devices, [("last_seen", DESCENDING)]),
                (db.emu_meters, [("device_id", ASCENDING)]),
                (db.emu_meters, [("id", ASCENDING)]),
                (db.generators, [("id", ASCENDING)]),
                (db.generators, [("serial_number", ASCENDING)]),
                (db.generators, [("device_id", ASCENDING)]),
                (db.generators, [("last_seen", DESCENDING)]),
                (db.generator_telemetry, [("generator_id", ASCENDING), ("timestamp", DESCENDING)]),
                (db.kirmes_events, [("id", ASCENDING)]),
                (db.kirmes_signups, [("event_id", ASCENDING)]),
                (db.kirmes_signups, [("schausteller_id", ASCENDING)]),
                (db.kirmes_signups, [("event_id", ASCENDING), ("schausteller_id", ASCENDING)]),
                (db.kirmes_schausteller, [("id", ASCENDING)]),
                (db.kirmes_schausteller, [("email", ASCENDING)]),
                (db.kirmes_invoices, [("schausteller_id", ASCENDING)]),
                (db.kirmes_invoices, [("event_id", ASCENDING)]),
                (db.users, [("id", ASCENDING)]),
                (db.users, [("email", ASCENDING)]),
                (db.service_plans, [("device_id", ASCENDING)]),
                (db.device_documents, [("device_id", ASCENDING)]),
                (db.device_parts, [("device_id", ASCENDING)]),
                (db.login_history, [("user_id", ASCENDING), ("timestamp", DESCENDING)]),
            ]:
                try:
                    await col.create_index(fields, background=True)
                except Exception:
                    pass  # Duplikat-Fehler bei unique ignorieren
            logger.info("Kleine Indexes fertig.")

            # emu_data (groesste Collection)
            _emu_index_running = True
            try:
                existing = await db.emu_data.index_information()
                needed = {"device_id_1_ts_utc_-1", "device_id_1_meter_id_1_ts_utc_-1", "ts_utc_-1"}
                if needed.issubset(set(existing.keys())):
                    logger.info("emu_data Indexes existieren bereits.")
                else:
                    logger.info("emu_data Indexes werden erstellt ...")
                    await db.emu_data.create_index([("device_id", ASCENDING), ("ts_utc", DESCENDING)], background=True)
                    await db.emu_data.create_index([("device_id", ASCENDING), ("meter_id", ASCENDING), ("ts_utc", DESCENDING)], background=True)
                    await db.emu_data.create_index([("ts_utc", DESCENDING)], background=True)
                    logger.info("emu_data Indexes FERTIG.")
            except Exception as e:
                logger.error(f"emu_data Index-Fehler: {e}")
            finally:
                _emu_index_running = False

        except Exception as e:
            logger.error(f"Index-Fehler: {e}")

    # Fire-and-forget: Server startet SOFORT, Indexes im Hintergrund
    asyncio.create_task(_ensure_all_indexes())

    # ── MQTT ──────────────────────────────────────────────────────────
    loop = asyncio.get_event_loop()
    await start_mqtt_client(db, loop)

    # Load SMTP config from DB into env vars
    try:
        from routes.admin_settings import load_smtp_config_from_db
        await load_smtp_config_from_db()
    except Exception:
        pass
    # Start EpiRent order sync background task
    try:
        from routes.orders import start_sync_task
        start_sync_task()
    except Exception:
        pass
    # Start backup scheduler
    try:
        from routes.backup import start_backup_scheduler
        await start_backup_scheduler()
    except Exception:
        pass
    # Init document storage
    try:
        from routes.documents import init_storage
        init_storage()
        logger.info("Document storage initialized")
    except Exception as e:
        logger.warning(f"Document storage init deferred: {e}")

    # Auto-seed FAQs if empty (first deploy on new server)
    try:
        from routes.employee import auto_seed_faqs_if_empty
        asyncio.create_task(auto_seed_faqs_if_empty())
    except Exception as e:
        logger.warning(f"FAQ auto-seed scheduler failed: {e}")

