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
from typing import List, Optional
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

class UserBase(BaseModel):
    email: EmailStr
    name: str
    role: str = UserRole.KUNDE
    max_upload_size_mb: int = 100
    is_active: bool = True

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    name: str
    role: str = UserRole.KUNDE

class UserUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    max_upload_size_mb: Optional[int] = None
    is_active: Optional[bool] = None

class UserResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    email: str
    name: str
    role: str
    max_upload_size_mb: int
    is_active: bool
    created_at: str

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
    created_at: str
    is_shared: bool = False

class FolderCreate(BaseModel):
    name: str
    parent_path: str = "/"

class FolderResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    name: str
    path: str
    owner_id: str
    created_at: str

class ShareLinkCreate(BaseModel):
    file_id: str
    expires_in_days: int = 7
    password: Optional[str] = None
    allow_download: bool = True

class ShareLinkResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    file_id: str
    token: str
    created_by: str
    expires_at: str
    password_protected: bool
    allow_download: bool
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

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    payload = decode_jwt_token(credentials.credentials)
    user = await db.users.find_one({"id": payload["user_id"]}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="Benutzer nicht gefunden")
    if not user.get("is_active", True):
        raise HTTPException(status_code=403, detail="Konto deaktiviert")
    return user

async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user["role"] != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin-Berechtigung erforderlich")
    return user

async def require_staff(user: dict = Depends(get_current_user)) -> dict:
    if user["role"] not in [UserRole.ADMIN, UserRole.MITARBEITER]:
        raise HTTPException(status_code=403, detail="Mitarbeiter-Berechtigung erforderlich")
    return user

# ============== Auth Endpoints ==============

@api_router.post("/auth/register", response_model=LoginResponse)
async def register(data: UserCreate):
    # Check if email exists
    existing = await db.users.find_one({"email": data.email})
    if existing:
        raise HTTPException(status_code=400, detail="E-Mail bereits registriert")
    
    # Check if first user (make admin)
    user_count = await db.users.count_documents({})
    role = UserRole.ADMIN if user_count == 0 else data.role
    
    user_id = str(uuid.uuid4())
    user_doc = {
        "id": user_id,
        "email": data.email,
        "name": data.name,
        "password_hash": hash_password(data.password),
        "role": role,
        "max_upload_size_mb": 100,
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.users.insert_one(user_doc)
    
    token = create_jwt_token(user_id, data.email, role)
    
    user_response = UserResponse(
        id=user_id,
        email=data.email,
        name=data.name,
        role=role,
        max_upload_size_mb=100,
        is_active=True,
        created_at=user_doc["created_at"]
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
    
    token = create_jwt_token(user["id"], user["email"], user["role"])
    
    user_response = UserResponse(
        id=user["id"],
        email=user["email"],
        name=user["name"],
        role=user["role"],
        max_upload_size_mb=user.get("max_upload_size_mb", 100),
        is_active=user.get("is_active", True),
        created_at=user["created_at"]
    )
    
    return LoginResponse(token=token, user=user_response)

@api_router.get("/auth/me", response_model=UserResponse)
async def get_me(user: dict = Depends(get_current_user)):
    return UserResponse(
        id=user["id"],
        email=user["email"],
        name=user["name"],
        role=user["role"],
        max_upload_size_mb=user.get("max_upload_size_mb", 100),
        is_active=user.get("is_active", True),
        created_at=user["created_at"]
    )

# ============== User Management (Admin) ==============

@api_router.get("/users", response_model=List[UserResponse])
async def list_users(admin: dict = Depends(require_admin)):
    users = await db.users.find({}, {"_id": 0, "password_hash": 0}).to_list(1000)
    return [UserResponse(
        id=u["id"],
        email=u["email"],
        name=u["name"],
        role=u["role"],
        max_upload_size_mb=u.get("max_upload_size_mb", 100),
        is_active=u.get("is_active", True),
        created_at=u["created_at"]
    ) for u in users]

@api_router.post("/users", response_model=UserResponse)
async def create_user(data: UserCreate, admin: dict = Depends(require_admin)):
    existing = await db.users.find_one({"email": data.email})
    if existing:
        raise HTTPException(status_code=400, detail="E-Mail bereits registriert")
    
    user_id = str(uuid.uuid4())
    user_doc = {
        "id": user_id,
        "email": data.email,
        "name": data.name,
        "password_hash": hash_password(data.password),
        "role": data.role,
        "max_upload_size_mb": 100,
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.users.insert_one(user_doc)
    
    return UserResponse(
        id=user_id,
        email=data.email,
        name=data.name,
        role=data.role,
        max_upload_size_mb=100,
        is_active=True,
        created_at=user_doc["created_at"]
    )

@api_router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(user_id: str, data: UserUpdate, admin: dict = Depends(require_admin)):
    user = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="Benutzer nicht gefunden")
    
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    if update_data:
        await db.users.update_one({"id": user_id}, {"$set": update_data})
    
    updated_user = await db.users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0})
    
    return UserResponse(
        id=updated_user["id"],
        email=updated_user["email"],
        name=updated_user["name"],
        role=updated_user["role"],
        max_upload_size_mb=updated_user.get("max_upload_size_mb", 100),
        is_active=updated_user.get("is_active", True),
        created_at=updated_user["created_at"]
    )

@api_router.delete("/users/{user_id}")
async def delete_user(user_id: str, admin: dict = Depends(require_admin)):
    if admin["id"] == user_id:
        raise HTTPException(status_code=400, detail="Sie können sich nicht selbst löschen")
    
    result = await db.users.delete_one({"id": user_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Benutzer nicht gefunden")
    
    # Delete user's files and shares
    await db.files.delete_many({"owner_id": user_id})
    await db.shares.delete_many({"created_by": user_id})
    await db.folders.delete_many({"owner_id": user_id})
    
    return {"message": "Benutzer gelöscht"}

# ============== Folder Management ==============

@api_router.get("/folders")
async def list_folders(
    path: str = "/",
    user: dict = Depends(get_current_user)
):
    query = {"owner_id": user["id"]}
    if path != "/":
        query["path"] = {"$regex": f"^{path}"}
    
    folders = await db.folders.find(query, {"_id": 0}).to_list(1000)
    return folders

@api_router.post("/folders", response_model=FolderResponse)
async def create_folder(data: FolderCreate, user: dict = Depends(get_current_user)):
    # Build full path
    parent = data.parent_path.rstrip("/")
    full_path = f"{parent}/{data.name}" if parent else f"/{data.name}"
    
    # Check if folder exists
    existing = await db.folders.find_one({
        "owner_id": user["id"],
        "path": full_path
    })
    if existing:
        raise HTTPException(status_code=400, detail="Ordner existiert bereits")
    
    folder_id = str(uuid.uuid4())
    folder_doc = {
        "id": folder_id,
        "name": data.name,
        "path": full_path,
        "owner_id": user["id"],
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.folders.insert_one(folder_doc)
    
    return FolderResponse(
        id=folder_id,
        name=data.name,
        path=full_path,
        owner_id=user["id"],
        created_at=folder_doc["created_at"]
    )

@api_router.delete("/folders/{folder_id}")
async def delete_folder(folder_id: str, user: dict = Depends(get_current_user)):
    folder = await db.folders.find_one({"id": folder_id, "owner_id": user["id"]}, {"_id": 0})
    if not folder:
        raise HTTPException(status_code=404, detail="Ordner nicht gefunden")
    
    # Delete folder and all subfolders
    await db.folders.delete_many({
        "owner_id": user["id"],
        "path": {"$regex": f"^{folder['path']}"}
    })
    
    # Delete files in folder
    await db.files.delete_many({
        "owner_id": user["id"],
        "folder_path": {"$regex": f"^{folder['path']}"}
    })
    
    return {"message": "Ordner gelöscht"}

# ============== File Management ==============

@api_router.get("/files", response_model=List[FileMetadata])
async def list_files(
    folder_path: str = "/",
    user: dict = Depends(get_current_user)
):
    query = {"owner_id": user["id"], "folder_path": folder_path}
    files = await db.files.find(query, {"_id": 0}).to_list(1000)
    return [FileMetadata(**f) for f in files]

@api_router.post("/files/upload", response_model=FileMetadata)
async def upload_file(
    file: UploadFile = FastAPIFile(...),
    folder_path: str = Form("/"),
    user: dict = Depends(get_current_user)
):
    # Check file size
    content = await file.read()
    size_mb = len(content) / (1024 * 1024)
    
    if size_mb > user.get("max_upload_size_mb", 100):
        raise HTTPException(
            status_code=413, 
            detail=f"Datei zu groß. Maximum: {user.get('max_upload_size_mb', 100)} MB"
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
    
    # Store metadata
    file_doc = {
        "id": file_id,
        "filename": file_id,
        "original_filename": file.filename,
        "size": len(content),
        "content_type": file.content_type or "application/octet-stream",
        "owner_id": user["id"],
        "owner_name": user["name"],
        "folder_path": folder_path,
        "grid_id": str(grid_id),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "is_shared": False
    }
    
    await db.files.insert_one(file_doc)
    
    return FileMetadata(**file_doc)

@api_router.get("/files/{file_id}/download")
async def download_file(file_id: str, user: dict = Depends(get_current_user)):
    file_doc = await db.files.find_one({"id": file_id}, {"_id": 0})
    if not file_doc:
        raise HTTPException(status_code=404, detail="Datei nicht gefunden")
    
    # Check permission
    if file_doc["owner_id"] != user["id"] and user["role"] not in [UserRole.ADMIN, UserRole.MITARBEITER]:
        raise HTTPException(status_code=403, detail="Keine Berechtigung")
    
    # Get file from GridFS
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
async def delete_file(file_id: str, user: dict = Depends(get_current_user)):
    file_doc = await db.files.find_one({"id": file_id}, {"_id": 0})
    if not file_doc:
        raise HTTPException(status_code=404, detail="Datei nicht gefunden")
    
    # Check permission
    if file_doc["owner_id"] != user["id"] and user["role"] != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Keine Berechtigung")
    
    # Delete from GridFS
    try:
        cursor = fs.find({"filename": file_id})
        async for grid_file in cursor:
            await fs.delete(grid_file._id)
    except Exception as e:
        logger.error(f"GridFS delete error: {e}")
    
    # Delete metadata and shares
    await db.files.delete_one({"id": file_id})
    await db.shares.delete_many({"file_id": file_id})
    
    return {"message": "Datei gelöscht"}

# ============== Share Management ==============

@api_router.post("/shares", response_model=ShareLinkResponse)
async def create_share_link(data: ShareLinkCreate, user: dict = Depends(get_current_user)):
    file_doc = await db.files.find_one({"id": data.file_id}, {"_id": 0})
    if not file_doc:
        raise HTTPException(status_code=404, detail="Datei nicht gefunden")
    
    # Check permission
    if file_doc["owner_id"] != user["id"] and user["role"] not in [UserRole.ADMIN, UserRole.MITARBEITER]:
        raise HTTPException(status_code=403, detail="Keine Berechtigung")
    
    share_id = str(uuid.uuid4())
    share_token = str(uuid.uuid4()).replace("-", "")[:16]
    
    share_doc = {
        "id": share_id,
        "file_id": data.file_id,
        "token": share_token,
        "created_by": user["id"],
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=data.expires_in_days)).isoformat(),
        "password_hash": hash_password(data.password) if data.password else None,
        "password_protected": data.password is not None,
        "allow_download": data.allow_download,
        "access_count": 0,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.shares.insert_one(share_doc)
    
    # Update file shared status
    await db.files.update_one({"id": data.file_id}, {"$set": {"is_shared": True}})
    
    return ShareLinkResponse(
        id=share_id,
        file_id=data.file_id,
        token=share_token,
        created_by=user["id"],
        expires_at=share_doc["expires_at"],
        password_protected=share_doc["password_protected"],
        allow_download=data.allow_download,
        access_count=0,
        created_at=share_doc["created_at"]
    )

@api_router.get("/shares", response_model=List[ShareLinkResponse])
async def list_shares(user: dict = Depends(get_current_user)):
    shares = await db.shares.find({"created_by": user["id"]}, {"_id": 0, "password_hash": 0}).to_list(1000)
    return [ShareLinkResponse(**s) for s in shares]

@api_router.delete("/shares/{share_id}")
async def delete_share(share_id: str, user: dict = Depends(get_current_user)):
    share = await db.shares.find_one({"id": share_id}, {"_id": 0})
    if not share:
        raise HTTPException(status_code=404, detail="Share-Link nicht gefunden")
    
    if share["created_by"] != user["id"] and user["role"] != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Keine Berechtigung")
    
    await db.shares.delete_one({"id": share_id})
    
    # Check if file has other shares
    remaining = await db.shares.count_documents({"file_id": share["file_id"]})
    if remaining == 0:
        await db.files.update_one({"id": share["file_id"]}, {"$set": {"is_shared": False}})
    
    return {"message": "Share-Link gelöscht"}

# ============== Public Share Access ==============

@api_router.get("/public/share/{token}")
async def get_share_info(token: str):
    share = await db.shares.find_one({"token": token}, {"_id": 0})
    if not share:
        raise HTTPException(status_code=404, detail="Share-Link nicht gefunden")
    
    # Check expiration
    expires_at = datetime.fromisoformat(share["expires_at"])
    if datetime.now(timezone.utc) > expires_at:
        raise HTTPException(status_code=410, detail="Share-Link abgelaufen")
    
    file_doc = await db.files.find_one({"id": share["file_id"]}, {"_id": 0})
    if not file_doc:
        raise HTTPException(status_code=404, detail="Datei nicht gefunden")
    
    return {
        "filename": file_doc["original_filename"],
        "size": file_doc["size"],
        "content_type": file_doc["content_type"],
        "password_protected": share["password_protected"],
        "allow_download": share["allow_download"],
        "expires_at": share["expires_at"]
    }

@api_router.post("/public/share/{token}/download")
async def download_shared_file(token: str, data: ShareAccessRequest = None):
    share = await db.shares.find_one({"token": token}, {"_id": 0})
    if not share:
        raise HTTPException(status_code=404, detail="Share-Link nicht gefunden")
    
    # Check expiration
    expires_at = datetime.fromisoformat(share["expires_at"])
    if datetime.now(timezone.utc) > expires_at:
        raise HTTPException(status_code=410, detail="Share-Link abgelaufen")
    
    if not share["allow_download"]:
        raise HTTPException(status_code=403, detail="Download nicht erlaubt")
    
    # Check password
    if share["password_protected"]:
        if not data or not data.password:
            raise HTTPException(status_code=401, detail="Passwort erforderlich")
        if not verify_password(data.password, share["password_hash"]):
            raise HTTPException(status_code=401, detail="Falsches Passwort")
    
    file_doc = await db.files.find_one({"id": share["file_id"]}, {"_id": 0})
    if not file_doc:
        raise HTTPException(status_code=404, detail="Datei nicht gefunden")
    
    # Increment access count
    await db.shares.update_one({"token": token}, {"$inc": {"access_count": 1}})
    
    # Get file from GridFS
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

# ============== Customer Upload (Public) ==============

@api_router.post("/public/share/{token}/upload")
async def customer_upload(
    token: str,
    file: UploadFile = FastAPIFile(...),
    password: str = Form(None)
):
    share = await db.shares.find_one({"token": token}, {"_id": 0})
    if not share:
        raise HTTPException(status_code=404, detail="Share-Link nicht gefunden")
    
    # Check expiration
    expires_at = datetime.fromisoformat(share["expires_at"])
    if datetime.now(timezone.utc) > expires_at:
        raise HTTPException(status_code=410, detail="Share-Link abgelaufen")
    
    # Check password
    if share["password_protected"]:
        if not password:
            raise HTTPException(status_code=401, detail="Passwort erforderlich")
        if not verify_password(password, share["password_hash"]):
            raise HTTPException(status_code=401, detail="Falsches Passwort")
    
    # Get owner info
    owner = await db.users.find_one({"id": share["created_by"]}, {"_id": 0})
    if not owner:
        raise HTTPException(status_code=500, detail="Besitzer nicht gefunden")
    
    # Read and store file
    content = await file.read()
    size_mb = len(content) / (1024 * 1024)
    
    # Use owner's upload limit
    if size_mb > owner.get("max_upload_size_mb", 100):
        raise HTTPException(
            status_code=413,
            detail=f"Datei zu groß. Maximum: {owner.get('max_upload_size_mb', 100)} MB"
        )
    
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
    
    file_doc = {
        "id": file_id,
        "filename": file_id,
        "original_filename": f"[Kunde] {file.filename}",
        "size": len(content),
        "content_type": file.content_type or "application/octet-stream",
        "owner_id": share["created_by"],
        "owner_name": "Kunde",
        "folder_path": "/uploads",
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
    
    # Calculate total storage
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
