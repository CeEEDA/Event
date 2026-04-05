from fastapi import APIRouter, HTTPException, UploadFile, File as FastAPIFile, Form, Query
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone
from typing import Optional
import uuid
import logging
import os

router = APIRouter(prefix="/api/chat")
logger = logging.getLogger(__name__)

db = None
decode_jwt = None


def init_chat_routes(_db, _decode_jwt):
    global db, decode_jwt
    db, decode_jwt = _db, _decode_jwt


def _get_storage_fns():
    from routes.documents import put_object, get_object
    return put_object, get_object


# ─── Helper ───
async def _get_user(token: str):
    payload = decode_jwt(token)
    user = await db.users.find_one({"id": payload["user_id"]}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="Ungültig")
    return user


# ─── Conversations ───

@router.get("/conversations")
async def list_conversations(token: str = Query(...)):
    user = await _get_user(token)
    uid = user["id"]
    convos = await db.chat_conversations.find(
        {"members": uid, "is_deleted": {"$ne": True}},
        {"_id": 0}
    ).sort("updated_at", -1).to_list(200)

    # Attach unread counts and member names
    for c in convos:
        unread = await db.chat_messages.count_documents({
            "conversation_id": c["id"],
            "sender_id": {"$ne": uid},
            "read_by": {"$nin": [uid]}
        })
        c["unread_count"] = unread
        # For direct chats, set the other person's name
        if c.get("type") == "direct":
            other_id = [m for m in c["members"] if m != uid]
            if other_id:
                other = await db.users.find_one({"id": other_id[0]}, {"_id": 0, "name": 1})
                c["display_name"] = other["name"] if other else "Unbekannt"
            else:
                c["display_name"] = "Unbekannt"
        else:
            c["display_name"] = c.get("name", "Gruppe")

    return convos


@router.post("/conversations")
async def create_conversation(body: dict, token: str = Query(...)):
    user = await _get_user(token)
    if body.get("type") == "group" and user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Nur Admins können Gruppen erstellen")

    conv_type = body.get("type", "direct")
    members = body.get("members", [])
    if user["id"] not in members:
        members.append(user["id"])

    # For direct chats, check if conversation already exists
    if conv_type == "direct" and len(members) == 2:
        existing = await db.chat_conversations.find_one({
            "type": "direct",
            "members": {"$all": members, "$size": 2},
            "is_deleted": {"$ne": True}
        }, {"_id": 0})
        if existing:
            return existing

    now = datetime.now(timezone.utc).isoformat()
    convo = {
        "id": str(uuid.uuid4()),
        "type": conv_type,
        "name": body.get("name", ""),
        "members": members,
        "created_by": user["id"],
        "created_at": now,
        "updated_at": now,
        "last_message": None,
        "is_deleted": False,
    }
    await db.chat_conversations.insert_one(convo)
    del convo["_id"]
    return convo


@router.get("/conversations/{conv_id}/messages")
async def get_messages(conv_id: str, token: str = Query(...), before: Optional[str] = None, limit: int = 50):
    user = await _get_user(token)
    convo = await db.chat_conversations.find_one({"id": conv_id, "members": user["id"]}, {"_id": 0})
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation nicht gefunden")

    query = {"conversation_id": conv_id}
    if before:
        query["created_at"] = {"$lt": before}

    messages = await db.chat_messages.find(query, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)
    messages.reverse()

    # Mark as read
    await db.chat_messages.update_many(
        {"conversation_id": conv_id, "sender_id": {"$ne": user["id"]}, "read_by": {"$nin": [user["id"]]}},
        {"$addToSet": {"read_by": user["id"]}}
    )

    return messages


@router.post("/conversations/{conv_id}/messages")
async def send_message(conv_id: str, token: str = Query(...), text: str = Form(""), file: Optional[UploadFile] = None):
    user = await _get_user(token)
    convo = await db.chat_conversations.find_one({"id": conv_id, "members": user["id"]}, {"_id": 0})
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation nicht gefunden")

    now = datetime.now(timezone.utc).isoformat()
    attachment = None

    if file and file.filename:
        file_bytes = await file.read()
        storage_path = f"eventenergie-chat/{uuid.uuid4()}/{file.filename}"
        put_obj, _ = _get_storage_fns()
        put_obj(storage_path, file_bytes, file.content_type or "application/octet-stream")
        attachment = {
            "id": str(uuid.uuid4()),
            "filename": file.filename,
            "content_type": file.content_type or "application/octet-stream",
            "size": len(file_bytes),
            "storage_path": storage_path,
        }

    msg = {
        "id": str(uuid.uuid4()),
        "conversation_id": conv_id,
        "sender_id": user["id"],
        "sender_name": user["name"],
        "text": text.strip(),
        "attachment": attachment,
        "read_by": [user["id"]],
        "created_at": now,
    }
    await db.chat_messages.insert_one(msg)
    del msg["_id"]

    # Update last_message
    preview = text.strip()[:80] if text.strip() else (f"📎 {attachment['filename']}" if attachment else "")
    await db.chat_conversations.update_one(
        {"id": conv_id},
        {"$set": {"last_message": {"text": preview, "sender_id": user["id"], "sender_name": user["name"], "sent_at": now}, "updated_at": now}}
    )

    return msg


@router.get("/conversations/{conv_id}/file/{attachment_id}")
async def download_attachment(conv_id: str, attachment_id: str, token: str = Query(...)):
    user = await _get_user(token)
    convo = await db.chat_conversations.find_one({"id": conv_id, "members": user["id"]})
    if not convo:
        raise HTTPException(status_code=404, detail="Nicht gefunden")

    msg = await db.chat_messages.find_one(
        {"conversation_id": conv_id, "attachment.id": attachment_id},
        {"_id": 0}
    )
    if not msg or not msg.get("attachment"):
        raise HTTPException(status_code=404, detail="Datei nicht gefunden")

    att = msg["attachment"]
    try:
        _, get_obj = _get_storage_fns()
        result = get_obj(att["storage_path"])
        data = result[0] if isinstance(result, tuple) else result
        from fastapi.responses import Response
        return Response(content=data, media_type=att["content_type"],
                        headers={"Content-Disposition": f'inline; filename="{att["filename"]}"'})
    except Exception as e:
        logger.error(f"Chat file download failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Download fehlgeschlagen: {str(e)}")


@router.get("/users")
async def list_chat_users(token: str = Query(...)):
    """List all active users for starting chats."""
    user = await _get_user(token)
    users = await db.users.find(
        {"is_active": True, "id": {"$ne": user["id"]}},
        {"_id": 0, "id": 1, "name": 1, "email": 1, "role": 1}
    ).to_list(100)
    return users


@router.delete("/conversations/{conv_id}")
async def delete_conversation(conv_id: str, token: str = Query(...)):
    """Admin only: delete a group conversation."""
    user = await _get_user(token)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Nur Admins")
    await db.chat_conversations.update_one({"id": conv_id}, {"$set": {"is_deleted": True}})
    return {"status": "deleted"}


# ─── Tasks ───

@router.get("/tasks")
async def list_tasks(token: str = Query(...), filter: str = "mine"):
    user = await _get_user(token)
    uid = user["id"]

    if filter == "mine":
        query = {"assigned_to": uid, "is_deleted": {"$ne": True}}
    elif filter == "created":
        query = {"created_by": uid, "is_deleted": {"$ne": True}}
    elif filter == "all" and user.get("role") == "admin":
        query = {"is_deleted": {"$ne": True}}
    else:
        query = {"$or": [{"assigned_to": uid}, {"created_by": uid}], "is_deleted": {"$ne": True}}

    tasks = await db.tasks.find(query, {"_id": 0}).sort([("completed", 1), ("due_date", 1), ("priority_order", 1)]).to_list(500)
    # Calculate unread comment count per user
    for t in tasks:
        last_read = t.get("last_read_by", {}).get(uid, 0)
        total = t.get("comment_count", 0)
        t["unread_comments"] = max(0, total - last_read)
    return tasks


@router.post("/tasks")
async def create_task(token: str = Query(...), title: str = Form(""), priority: str = Form("medium"),
                      due_date: str = Form(""), assigned_to: str = Form(""), file: Optional[UploadFile] = None):
    user = await _get_user(token)
    now = datetime.now(timezone.utc).isoformat()

    priority_order = {"high": 0, "medium": 1, "low": 2}.get(priority, 1)

    # Parse assigned_to (comma-separated IDs)
    assignees = [a.strip() for a in assigned_to.split(",") if a.strip()] if assigned_to else [user["id"]]

    assigned_to_names = {}
    for aid in assignees:
        if aid == user["id"]:
            assigned_to_names[aid] = user["name"]
        else:
            a = await db.users.find_one({"id": aid}, {"_id": 0, "name": 1})
            assigned_to_names[aid] = a["name"] if a else "Unbekannt"

    attachment = None
    if file and file.filename:
        file_bytes = await file.read()
        storage_path = f"eventenergie-tasks/{uuid.uuid4()}/{file.filename}"
        put_obj, _ = _get_storage_fns()
        put_obj(storage_path, file_bytes, file.content_type or "application/octet-stream")
        attachment = {
            "id": str(uuid.uuid4()),
            "filename": file.filename,
            "content_type": file.content_type or "application/octet-stream",
            "size": len(file_bytes),
            "storage_path": storage_path,
        }

    task = {
        "id": str(uuid.uuid4()),
        "title": title.strip(),
        "description": "",
        "priority": priority,
        "priority_order": priority_order,
        "due_date": due_date if due_date else None,
        "completed": False,
        "completed_at": None,
        "completed_by": None,
        "completed_by_name": None,
        "created_by": user["id"],
        "created_by_name": user["name"],
        "assigned_to": assignees,
        "assigned_to_names": assigned_to_names,
        "attachment": attachment,
        "comment_count": 0,
        "is_deleted": False,
        "created_at": now,
        "updated_at": now,
    }
    await db.tasks.insert_one(task)
    del task["_id"]
    return task


@router.get("/tasks/{task_id}/file")
async def download_task_file(task_id: str, token: str = Query(...)):
    user = await _get_user(token)
    task = await db.tasks.find_one({"id": task_id}, {"_id": 0})
    if not task or not task.get("attachment"):
        raise HTTPException(status_code=404, detail="Datei nicht gefunden")
    att = task["attachment"]
    try:
        _, get_obj = _get_storage_fns()
        result = get_obj(att["storage_path"])
        data = result[0] if isinstance(result, tuple) else result
        from fastapi.responses import Response
        return Response(content=data, media_type=att["content_type"],
                        headers={"Content-Disposition": f'inline; filename="{att["filename"]}"'})
    except Exception:
        raise HTTPException(status_code=500, detail="Download fehlgeschlagen")


# ─── Task Comments ───

@router.get("/tasks/{task_id}/comments")
async def list_task_comments(task_id: str, token: str = Query(...)):
    user = await _get_user(token)
    task = await db.tasks.find_one({"id": task_id}, {"_id": 0})
    if not task:
        raise HTTPException(status_code=404, detail="Aufgabe nicht gefunden")
    assigned = task.get("assigned_to", [])
    if isinstance(assigned, str):
        assigned = [assigned]
    if user["id"] not in assigned and task["created_by"] != user["id"] and user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Keine Berechtigung")

    comments = await db.task_comments.find(
        {"task_id": task_id}, {"_id": 0}
    ).sort("created_at", 1).to_list(200)
    return comments


@router.post("/tasks/{task_id}/comments")
async def add_task_comment(task_id: str, token: str = Query(...), text: str = Form(""), file: Optional[UploadFile] = None):
    user = await _get_user(token)
    task = await db.tasks.find_one({"id": task_id}, {"_id": 0})
    if not task:
        raise HTTPException(status_code=404, detail="Aufgabe nicht gefunden")

    now = datetime.now(timezone.utc).isoformat()
    attachment = None
    if file and file.filename:
        file_bytes = await file.read()
        storage_path = f"eventenergie-tasks/{uuid.uuid4()}/{file.filename}"
        put_obj, _ = _get_storage_fns()
        put_obj(storage_path, file_bytes, file.content_type or "application/octet-stream")
        attachment = {
            "id": str(uuid.uuid4()),
            "filename": file.filename,
            "content_type": file.content_type or "application/octet-stream",
            "size": len(file_bytes),
            "storage_path": storage_path,
        }

    comment = {
        "id": str(uuid.uuid4()),
        "task_id": task_id,
        "user_id": user["id"],
        "user_name": user["name"],
        "text": text.strip(),
        "attachment": attachment,
        "created_at": now,
    }
    await db.task_comments.insert_one(comment)
    del comment["_id"]

    await db.tasks.update_one({"id": task_id}, {"$inc": {"comment_count": 1}, "$set": {"updated_at": now}})
    return comment


@router.get("/tasks/{task_id}/comments/{comment_id}/file")
async def download_comment_file(task_id: str, comment_id: str, token: str = Query(...)):
    await _get_user(token)
    comment = await db.task_comments.find_one({"id": comment_id, "task_id": task_id}, {"_id": 0})
    if not comment or not comment.get("attachment"):
        raise HTTPException(status_code=404, detail="Datei nicht gefunden")
    att = comment["attachment"]
    try:
        _, get_obj = _get_storage_fns()
        result = get_obj(att["storage_path"])
        data = result[0] if isinstance(result, tuple) else result
        from fastapi.responses import Response
        return Response(content=data, media_type=att["content_type"],
                        headers={"Content-Disposition": f'inline; filename="{att["filename"]}"'})
    except Exception:
        raise HTTPException(status_code=500, detail="Download fehlgeschlagen")


@router.put("/tasks/{task_id}")
async def update_task(task_id: str, body: dict, token: str = Query(...)):
    user = await _get_user(token)
    task = await db.tasks.find_one({"id": task_id}, {"_id": 0})
    if not task:
        raise HTTPException(status_code=404, detail="Aufgabe nicht gefunden")

    # Permission: assigned user, creator, or admin
    assigned = task.get("assigned_to", [])
    if isinstance(assigned, str):
        assigned = [assigned]
    if user["id"] not in assigned and task["created_by"] != user["id"] and user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Keine Berechtigung")

    updates = {"updated_at": datetime.now(timezone.utc).isoformat()}

    if "title" in body:
        updates["title"] = body["title"].strip()
    if "description" in body:
        updates["description"] = body["description"].strip()
    if "priority" in body:
        updates["priority"] = body["priority"]
        updates["priority_order"] = {"high": 0, "medium": 1, "low": 2}.get(body["priority"], 1)
    if "due_date" in body:
        updates["due_date"] = body["due_date"]
    if "completed" in body:
        updates["completed"] = body["completed"]
        if body["completed"]:
            updates["completed_at"] = datetime.now(timezone.utc).isoformat()
            updates["completed_by"] = user["id"]
            updates["completed_by_name"] = user["name"]
        else:
            updates["completed_at"] = None
            updates["completed_by"] = None
            updates["completed_by_name"] = None

    if body.get("mark_read"):
        updates["last_read_by"] = {**task.get("last_read_by", {}), user["id"]: task.get("comment_count", 0)}

    await db.tasks.update_one({"id": task_id}, {"$set": updates})
    task.update(updates)
    return task


@router.delete("/tasks/{task_id}")
async def delete_task(task_id: str, token: str = Query(...)):
    user = await _get_user(token)
    task = await db.tasks.find_one({"id": task_id}, {"_id": 0})
    if not task:
        raise HTTPException(status_code=404, detail="Aufgabe nicht gefunden")
    if task["created_by"] != user["id"] and user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Keine Berechtigung")

    await db.tasks.update_one({"id": task_id}, {"$set": {"is_deleted": True}})
    return {"status": "deleted"}
