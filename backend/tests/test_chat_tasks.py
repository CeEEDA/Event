"""
Test Suite for Team Chat & Task Management Features
Tests: Conversations (direct/group), Messages (text/file), Tasks (CRUD, priority, due_date, assignment)
"""
import pytest
import requests
import os
import uuid
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "password"
MITARBEITER_EMAIL = "ma1@test.com"  # Anna Weber
MITARBEITER_PASSWORD = "password"


class TestChatAuth:
    """Authentication helper tests"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        return response.json()["token"]
    
    @pytest.fixture(scope="class")
    def admin_user(self):
        """Get admin user info"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        return response.json()["user"]
    
    @pytest.fixture(scope="class")
    def mitarbeiter_token(self):
        """Get mitarbeiter auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": MITARBEITER_EMAIL,
            "password": MITARBEITER_PASSWORD
        })
        if response.status_code != 200:
            pytest.skip(f"Mitarbeiter login failed: {response.text}")
        return response.json()["token"]
    
    @pytest.fixture(scope="class")
    def mitarbeiter_user(self):
        """Get mitarbeiter user info"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": MITARBEITER_EMAIL,
            "password": MITARBEITER_PASSWORD
        })
        if response.status_code != 200:
            pytest.skip("Mitarbeiter login failed")
        return response.json()["user"]


class TestChatUsers(TestChatAuth):
    """Test /api/chat/users endpoint"""
    
    def test_list_chat_users(self, admin_token):
        """GET /api/chat/users returns list of active users"""
        response = requests.get(f"{BASE_URL}/api/chat/users?token={admin_token}")
        assert response.status_code == 200, f"Failed: {response.text}"
        users = response.json()
        assert isinstance(users, list)
        # Should not include current user
        for u in users:
            assert "id" in u
            assert "name" in u
            assert "email" in u
        print(f"✓ Found {len(users)} chat users")


class TestDirectConversations(TestChatAuth):
    """Test direct message conversations"""
    
    def test_create_direct_conversation(self, admin_token, admin_user):
        """POST /api/chat/conversations creates direct chat between two users"""
        # First get another user
        users_resp = requests.get(f"{BASE_URL}/api/chat/users?token={admin_token}")
        assert users_resp.status_code == 200
        users = users_resp.json()
        if not users:
            pytest.skip("No other users available for direct chat")
        
        other_user = users[0]
        
        # Create direct conversation
        response = requests.post(f"{BASE_URL}/api/chat/conversations?token={admin_token}", json={
            "type": "direct",
            "members": [admin_user["id"], other_user["id"]]
        })
        assert response.status_code == 200, f"Failed: {response.text}"
        convo = response.json()
        
        assert convo["type"] == "direct"
        assert admin_user["id"] in convo["members"]
        assert other_user["id"] in convo["members"]
        assert "id" in convo
        print(f"✓ Created direct conversation: {convo['id']}")
        return convo
    
    def test_direct_conversation_returns_existing(self, admin_token, admin_user):
        """POST /api/chat/conversations returns existing direct chat if already exists"""
        users_resp = requests.get(f"{BASE_URL}/api/chat/users?token={admin_token}")
        users = users_resp.json()
        if not users:
            pytest.skip("No other users available")
        
        other_user = users[0]
        
        # Create first
        resp1 = requests.post(f"{BASE_URL}/api/chat/conversations?token={admin_token}", json={
            "type": "direct",
            "members": [admin_user["id"], other_user["id"]]
        })
        convo1 = resp1.json()
        
        # Create again - should return same
        resp2 = requests.post(f"{BASE_URL}/api/chat/conversations?token={admin_token}", json={
            "type": "direct",
            "members": [admin_user["id"], other_user["id"]]
        })
        convo2 = resp2.json()
        
        assert convo1["id"] == convo2["id"], "Should return existing conversation"
        print(f"✓ Direct conversation deduplication works")


class TestGroupConversations(TestChatAuth):
    """Test group conversations (admin only)"""
    
    def test_admin_can_create_group(self, admin_token, admin_user):
        """POST /api/chat/conversations creates group (admin only)"""
        users_resp = requests.get(f"{BASE_URL}/api/chat/users?token={admin_token}")
        users = users_resp.json()
        if len(users) < 2:
            pytest.skip("Need at least 2 other users for group")
        
        group_name = f"TEST_Group_{uuid.uuid4().hex[:6]}"
        member_ids = [admin_user["id"], users[0]["id"], users[1]["id"]]
        
        response = requests.post(f"{BASE_URL}/api/chat/conversations?token={admin_token}", json={
            "type": "group",
            "name": group_name,
            "members": member_ids
        })
        assert response.status_code == 200, f"Failed: {response.text}"
        convo = response.json()
        
        assert convo["type"] == "group"
        assert convo["name"] == group_name
        assert len(convo["members"]) >= 3
        print(f"✓ Admin created group: {group_name}")
        return convo
    
    def test_non_admin_cannot_create_group(self, mitarbeiter_token, mitarbeiter_user):
        """POST /api/chat/conversations with type=group returns 403 for non-admin"""
        users_resp = requests.get(f"{BASE_URL}/api/chat/users?token={mitarbeiter_token}")
        users = users_resp.json()
        if not users:
            pytest.skip("No other users available")
        
        response = requests.post(f"{BASE_URL}/api/chat/conversations?token={mitarbeiter_token}", json={
            "type": "group",
            "name": "Unauthorized Group",
            "members": [mitarbeiter_user["id"], users[0]["id"]]
        })
        assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
        print(f"✓ Non-admin correctly blocked from creating group (403)")


class TestMessages(TestChatAuth):
    """Test message sending and retrieval"""
    
    @pytest.fixture
    def test_conversation(self, admin_token, admin_user):
        """Create a test conversation for message tests"""
        users_resp = requests.get(f"{BASE_URL}/api/chat/users?token={admin_token}")
        users = users_resp.json()
        if not users:
            pytest.skip("No other users available")
        
        response = requests.post(f"{BASE_URL}/api/chat/conversations?token={admin_token}", json={
            "type": "direct",
            "members": [admin_user["id"], users[0]["id"]]
        })
        return response.json()
    
    def test_send_text_message(self, admin_token, test_conversation):
        """POST /api/chat/conversations/{id}/messages sends text message"""
        conv_id = test_conversation["id"]
        test_text = f"TEST_Message_{uuid.uuid4().hex[:6]}"
        
        response = requests.post(
            f"{BASE_URL}/api/chat/conversations/{conv_id}/messages?token={admin_token}",
            data={"text": test_text}
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        msg = response.json()
        
        assert msg["text"] == test_text
        assert msg["conversation_id"] == conv_id
        assert "sender_id" in msg
        assert "sender_name" in msg
        assert "created_at" in msg
        print(f"✓ Sent text message: {test_text[:30]}...")
        return msg
    
    def test_send_file_attachment(self, admin_token, test_conversation):
        """POST /api/chat/conversations/{id}/messages sends file attachment"""
        conv_id = test_conversation["id"]
        
        # Create a test file
        file_content = b"Test file content for chat attachment"
        files = {"file": ("test_attachment.txt", file_content, "text/plain")}
        data = {"text": ""}
        
        response = requests.post(
            f"{BASE_URL}/api/chat/conversations/{conv_id}/messages?token={admin_token}",
            files=files,
            data=data
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        msg = response.json()
        
        assert msg["attachment"] is not None
        assert msg["attachment"]["filename"] == "test_attachment.txt"
        assert "id" in msg["attachment"]
        print(f"✓ Sent file attachment: {msg['attachment']['filename']}")
        return msg
    
    def test_get_messages_in_order(self, admin_token, test_conversation):
        """GET /api/chat/conversations/{id}/messages returns messages in order"""
        conv_id = test_conversation["id"]
        
        # Send multiple messages
        for i in range(3):
            requests.post(
                f"{BASE_URL}/api/chat/conversations/{conv_id}/messages?token={admin_token}",
                data={"text": f"TEST_Order_Message_{i}"}
            )
        
        # Get messages
        response = requests.get(f"{BASE_URL}/api/chat/conversations/{conv_id}/messages?token={admin_token}")
        assert response.status_code == 200, f"Failed: {response.text}"
        messages = response.json()
        
        assert isinstance(messages, list)
        # Messages should be in chronological order (oldest first after reverse)
        if len(messages) >= 2:
            for i in range(len(messages) - 1):
                assert messages[i]["created_at"] <= messages[i+1]["created_at"], "Messages not in order"
        print(f"✓ Retrieved {len(messages)} messages in order")


class TestConversationsList(TestChatAuth):
    """Test conversation listing with unread counts"""
    
    def test_list_conversations_with_unread(self, admin_token):
        """GET /api/chat/conversations returns conversations with unread counts"""
        response = requests.get(f"{BASE_URL}/api/chat/conversations?token={admin_token}")
        assert response.status_code == 200, f"Failed: {response.text}"
        convos = response.json()
        
        assert isinstance(convos, list)
        for c in convos:
            assert "id" in c
            assert "type" in c
            assert "unread_count" in c
            assert "display_name" in c
            assert isinstance(c["unread_count"], int)
        print(f"✓ Listed {len(convos)} conversations with unread counts")


class TestTasks(TestChatAuth):
    """Test task management endpoints"""
    
    def test_create_task_with_priority_and_due_date(self, admin_token):
        """POST /api/chat/tasks creates a task with priority and due date"""
        due_date = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
        task_title = f"TEST_Task_{uuid.uuid4().hex[:6]}"
        
        response = requests.post(f"{BASE_URL}/api/chat/tasks?token={admin_token}", json={
            "title": task_title,
            "priority": "high",
            "due_date": due_date
        })
        assert response.status_code == 200, f"Failed: {response.text}"
        task = response.json()
        
        assert task["title"] == task_title
        assert task["priority"] == "high"
        assert task["due_date"] == due_date
        assert task["completed"] == False
        assert "id" in task
        print(f"✓ Created task: {task_title} (priority: high, due: {due_date})")
        return task
    
    def test_create_task_assigned_to_other(self, admin_token, admin_user):
        """POST /api/chat/tasks with assigned_to assigns task to another user"""
        users_resp = requests.get(f"{BASE_URL}/api/chat/users?token={admin_token}")
        users = users_resp.json()
        if not users:
            pytest.skip("No other users available")
        
        other_user = users[0]
        task_title = f"TEST_Assigned_Task_{uuid.uuid4().hex[:6]}"
        
        response = requests.post(f"{BASE_URL}/api/chat/tasks?token={admin_token}", json={
            "title": task_title,
            "priority": "medium",
            "assigned_to": other_user["id"]
        })
        assert response.status_code == 200, f"Failed: {response.text}"
        task = response.json()
        
        assert task["assigned_to"] == other_user["id"]
        assert task["created_by"] == admin_user["id"]
        assert task["assigned_to_name"] == other_user["name"]
        print(f"✓ Created task assigned to {other_user['name']}")
        return task
    
    def test_mark_task_completed(self, admin_token):
        """PUT /api/chat/tasks/{id} marks task as completed"""
        # Create a task first
        task_title = f"TEST_Complete_Task_{uuid.uuid4().hex[:6]}"
        create_resp = requests.post(f"{BASE_URL}/api/chat/tasks?token={admin_token}", json={
            "title": task_title,
            "priority": "low"
        })
        task = create_resp.json()
        task_id = task["id"]
        
        # Mark as completed
        response = requests.put(f"{BASE_URL}/api/chat/tasks/{task_id}?token={admin_token}", json={
            "completed": True
        })
        assert response.status_code == 200, f"Failed: {response.text}"
        updated = response.json()
        
        assert updated["completed"] == True
        assert updated["completed_at"] is not None
        print(f"✓ Marked task as completed")
        
        # Verify with GET
        tasks_resp = requests.get(f"{BASE_URL}/api/chat/tasks?token={admin_token}&filter=created")
        tasks = tasks_resp.json()
        completed_task = next((t for t in tasks if t["id"] == task_id), None)
        assert completed_task is not None
        assert completed_task["completed"] == True
        print(f"✓ Verified task completion persisted")
    
    def test_update_task_priority_and_due_date(self, admin_token):
        """PUT /api/chat/tasks/{id} updates priority and due_date"""
        # Create a task
        task_title = f"TEST_Update_Task_{uuid.uuid4().hex[:6]}"
        create_resp = requests.post(f"{BASE_URL}/api/chat/tasks?token={admin_token}", json={
            "title": task_title,
            "priority": "low"
        })
        task = create_resp.json()
        task_id = task["id"]
        
        new_due_date = (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d")
        
        # Update priority and due_date
        response = requests.put(f"{BASE_URL}/api/chat/tasks/{task_id}?token={admin_token}", json={
            "priority": "high",
            "due_date": new_due_date
        })
        assert response.status_code == 200, f"Failed: {response.text}"
        updated = response.json()
        
        assert updated["priority"] == "high"
        assert updated["due_date"] == new_due_date
        print(f"✓ Updated task priority to high and due_date to {new_due_date}")
    
    def test_delete_task_creator_only(self, admin_token):
        """DELETE /api/chat/tasks/{id} deletes task (creator/admin only)"""
        # Create a task
        task_title = f"TEST_Delete_Task_{uuid.uuid4().hex[:6]}"
        create_resp = requests.post(f"{BASE_URL}/api/chat/tasks?token={admin_token}", json={
            "title": task_title,
            "priority": "medium"
        })
        task = create_resp.json()
        task_id = task["id"]
        
        # Delete
        response = requests.delete(f"{BASE_URL}/api/chat/tasks/{task_id}?token={admin_token}")
        assert response.status_code == 200, f"Failed: {response.text}"
        result = response.json()
        assert result["status"] == "deleted"
        print(f"✓ Deleted task successfully")
        
        # Verify deleted (should not appear in list)
        tasks_resp = requests.get(f"{BASE_URL}/api/chat/tasks?token={admin_token}&filter=created")
        tasks = tasks_resp.json()
        deleted_task = next((t for t in tasks if t["id"] == task_id), None)
        assert deleted_task is None, "Deleted task should not appear in list"
        print(f"✓ Verified task no longer in list")
    
    def test_get_tasks_filter_mine(self, admin_token, admin_user):
        """GET /api/chat/tasks?filter=mine returns tasks assigned to current user"""
        # Create a task assigned to self
        task_title = f"TEST_Mine_Task_{uuid.uuid4().hex[:6]}"
        requests.post(f"{BASE_URL}/api/chat/tasks?token={admin_token}", json={
            "title": task_title,
            "priority": "medium",
            "assigned_to": admin_user["id"]
        })
        
        response = requests.get(f"{BASE_URL}/api/chat/tasks?token={admin_token}&filter=mine")
        assert response.status_code == 200, f"Failed: {response.text}"
        tasks = response.json()
        
        assert isinstance(tasks, list)
        for t in tasks:
            assert t["assigned_to"] == admin_user["id"], f"Task {t['id']} not assigned to current user"
        print(f"✓ Filter 'mine' returns {len(tasks)} tasks assigned to current user")
    
    def test_get_tasks_filter_created(self, admin_token, admin_user):
        """GET /api/chat/tasks?filter=created returns tasks created by current user"""
        response = requests.get(f"{BASE_URL}/api/chat/tasks?token={admin_token}&filter=created")
        assert response.status_code == 200, f"Failed: {response.text}"
        tasks = response.json()
        
        assert isinstance(tasks, list)
        for t in tasks:
            assert t["created_by"] == admin_user["id"], f"Task {t['id']} not created by current user"
        print(f"✓ Filter 'created' returns {len(tasks)} tasks created by current user")


class TestTaskPermissions(TestChatAuth):
    """Test task permission enforcement"""
    
    def test_non_creator_cannot_delete_task(self, admin_token, mitarbeiter_token, admin_user):
        """Non-creator/non-admin cannot delete task"""
        # Admin creates a task
        task_title = f"TEST_Perm_Task_{uuid.uuid4().hex[:6]}"
        create_resp = requests.post(f"{BASE_URL}/api/chat/tasks?token={admin_token}", json={
            "title": task_title,
            "priority": "medium",
            "assigned_to": admin_user["id"]  # Assigned to admin, not mitarbeiter
        })
        task = create_resp.json()
        task_id = task["id"]
        
        # Mitarbeiter tries to delete - should fail with 403
        response = requests.delete(f"{BASE_URL}/api/chat/tasks/{task_id}?token={mitarbeiter_token}")
        assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
        print(f"✓ Non-creator correctly blocked from deleting task (403)")


# Cleanup fixture
@pytest.fixture(scope="session", autouse=True)
def cleanup_test_data():
    """Cleanup TEST_ prefixed data after all tests"""
    yield
    # Note: In production, you'd want to clean up test data
    # For now, we rely on is_deleted flags
    print("Test session complete - TEST_ prefixed data may remain (soft deleted)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
