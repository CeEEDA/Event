from fastapi import FastAPI, APIRouter, HTTPException, Depends, UploadFile, File as FastAPIFile, Form, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorGridFSBucket
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict, EmailStr
from typing import List, Optional, Dict
import uuid
from datetime import datetime, timezone, timedelta
import jwt
import bcrypt
from bson import ObjectId
import io

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

class PasswordResetRequest(BaseModel):
    email: EmailStr

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
async def login(data: LoginRequest):
    user = await db.users.find_one({"email": data.email}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="Ungültige Anmeldedaten")
    
    if not verify_password(data.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Ungültige Anmeldedaten")
    
    if not user.get("is_active", True):
        raise HTTPException(status_code=403, detail="Konto deaktiviert")
    
    # Ensure apps field exists
    if "apps" not in user:
        user["apps"] = get_default_apps()
        await db.users.update_one({"id": user["id"]}, {"$set": {"apps": user["apps"]}})
    
    token = create_jwt_token(user["id"], user["email"], user["role"])
    
    user_response = UserResponse(
        id=user["id"],
        email=user["email"],
        name=user["name"],
        role=user["role"],
        is_active=user.get("is_active", True),
        created_at=user["created_at"],
        apps=user.get("apps", get_default_apps())
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
        apps=user.get("apps", get_default_apps())
    )

# ============== Password Reset ==============

@api_router.post("/auth/request-password-reset")
async def request_password_reset(data: PasswordResetRequest):
    """Request a password reset - creates a reset token"""
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
    
    # In production, send email here
    # For now, return success message
    logger.info(f"Password reset requested for {data.email}, token: {reset_token}")
    
    return {"message": "Falls die E-Mail existiert, wurde ein Link gesendet", "reset_token": reset_token}

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
        {"$set": {"password_hash": hash_password(data.new_password)}}
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
        apps=u.get("apps", get_default_apps())
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
        apps=updated_user.get("apps", get_default_apps())
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
            "password_plain": data.new_password  # Store plain for admin viewing
        }}
    )
    
    return {"message": "Passwort gesetzt", "password": data.new_password}

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
async def download_file(file_id: str, user: dict = Depends(require_filesharing)):
    file_doc = await db.files.find_one({"id": file_id}, {"_id": 0})
    if not file_doc:
        raise HTTPException(status_code=404, detail="Datei nicht gefunden")
    
    # Check permission
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

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
