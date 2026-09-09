import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.note import Note


@pytest.mark.asyncio
async def test_notes_crud_lifecycle(client: AsyncClient, db_session: AsyncSession):
    # 1. Register & authenticate Notes User
    signup_data = {
        "full_name": "Notes Tester",
        "email": "notes_tester@example.com",
        "password": "Password123!",
        "confirm_password": "Password123!"
    }
    signup_resp = await client.post("/auth/signup", data=signup_data)
    assert signup_resp.status_code in (200, 303)

    # 2. Test Create Note via Form POST
    create_data = {
        "title": "My First Project Note",
        "content": "This is the content of my first note."
    }
    create_resp = await client.post("/notes", data=create_data, follow_redirects=True)
    assert create_resp.status_code == 200
    assert "My First Project Note" in create_resp.text
    assert "This is the content of my first note." in create_resp.text

    # Verify Note in database
    result = await db_session.execute(select(Note).where(Note.title == "My First Project Note"))
    note = result.scalar_one_or_none()
    assert note is not None
    assert note.content == "This is the content of my first note."
    assert note.is_deleted is False
    assert note.deleted_at is None
    note_id = note.id

    # 3. Test List Notes on Dashboard (GET /)
    dashboard_resp = await client.get("/")
    assert dashboard_resp.status_code == 200
    assert "My First Project Note" in dashboard_resp.text
    assert f"/notes/{note_id}" in dashboard_resp.text

    # 4. Test View Single Note (GET /notes/{id})
    view_resp = await client.get(f"/notes/{note_id}")
    assert view_resp.status_code == 200
    assert "My First Project Note" in view_resp.text
    assert "This is the content of my first note." in view_resp.text
    assert "Back to Notes" in view_resp.text

    # 5. Test Edit Page (GET /notes/{id}/edit)
    edit_page_resp = await client.get(f"/notes/{note_id}/edit")
    assert edit_page_resp.status_code == 200
    assert "Edit Note" in edit_page_resp.text
    assert 'value="My First Project Note"' in edit_page_resp.text

    # 6. Test Edit Note Submission (POST /notes/{id}/edit)
    update_data = {
        "title": "My First Project Note (Updated)",
        "content": "Updated content with more details."
    }
    update_resp = await client.post(f"/notes/{note_id}/edit", data=update_data, follow_redirects=True)
    assert update_resp.status_code == 200
    assert "My First Project Note (Updated)" in update_resp.text
    assert "Updated content with more details." in update_resp.text

    # Verify updated in DB
    await db_session.refresh(note)
    assert note.title == "My First Project Note (Updated)"
    assert note.content == "Updated content with more details."

    # 7. Test Soft Delete Note (POST /notes/{id}/delete)
    del_resp = await client.post(f"/notes/{note_id}/delete", follow_redirects=True)
    assert del_resp.status_code == 200

    # Verify soft deleted in DB
    await db_session.refresh(note)
    assert note.is_deleted is True
    assert note.deleted_at is not None

    # Verify excluded from normal list (GET /)
    dash_after_del = await client.get("/")
    assert dash_after_del.status_code == 200
    assert "My First Project Note (Updated)" not in dash_after_del.text

    # Verify single view returns 404
    view_deleted_resp = await client.get(f"/notes/{note_id}")
    assert view_deleted_resp.status_code == 404


@pytest.mark.asyncio
async def test_create_note_validation(client: AsyncClient):
    # Authenticate user
    await client.post("/auth/signup", data={
        "full_name": "Validation User",
        "email": "validation@example.com",
        "password": "Password123!",
        "confirm_password": "Password123!"
    })

    # Empty title should fail
    resp = await client.post("/notes", data={"title": "   ", "content": "valid content"})
    assert resp.status_code == 400
    assert "Title cannot be empty" in resp.text


@pytest.mark.asyncio
async def test_htmx_inline_editing(client: AsyncClient, db_session: AsyncSession):
    # Register & authenticate user
    await client.post("/auth/signup", data={
        "full_name": "Inline Tester",
        "email": "inline_tester@example.com",
        "password": "Password123!",
        "confirm_password": "Password123!"
    })

    # Create note
    create_resp = await client.post("/notes", data={
        "title": "Initial Dashboard Title",
        "content": "Client requested dashboard."
    }, follow_redirects=True)
    assert create_resp.status_code == 200

    result = await db_session.execute(select(Note).where(Note.title == "Initial Dashboard Title"))
    note = result.scalar_one_or_none()
    assert note is not None
    note_id = note.id

    # 1. Test GET inline title edit form
    title_form_resp = await client.get(f"/notes/{note_id}/title/edit")
    assert title_form_resp.status_code == 200
    assert f'id="note-title-container-{note_id}"' in title_form_resp.text
    assert 'value="Initial Dashboard Title"' in title_form_resp.text

    # 2. Test PUT and POST inline title save
    title_save_resp = await client.put(f"/notes/{note_id}/title", data={"title": "Updated Inline Title"})
    assert title_save_resp.status_code == 200
    assert "Updated Inline Title" in title_save_resp.text
    assert f'id="note-title-container-{note_id}"' in title_save_resp.text

    # Verify DB updated
    await db_session.refresh(note)
    assert note.title == "Updated Inline Title"

    # Test POST inline title save (as used by HTMX form)
    title_post_resp = await client.post(f"/notes/{note_id}/title", data={"title": "Updated Via Post"})
    assert title_post_resp.status_code == 200
    assert "Updated Via Post" in title_post_resp.text
    assert f'id="note-title-container-{note_id}"' in title_post_resp.text

    await db_session.refresh(note)
    assert note.title == "Updated Via Post"

    # 3. Test PUT inline title with empty string -> should return 400 with error
    bad_title_resp = await client.put(f"/notes/{note_id}/title", data={"title": "   "})
    assert bad_title_resp.status_code == 400
    assert "Title cannot be empty" in bad_title_resp.text

    # 4. Test GET inline title cancel -> returns read-only fragment
    title_cancel_resp = await client.get(f"/notes/{note_id}/title")
    assert title_cancel_resp.status_code == 200
    assert "Updated Via Post" in title_cancel_resp.text

    # 5. Test GET inline content edit form
    content_form_resp = await client.get(f"/notes/{note_id}/content/edit")
    assert content_form_resp.status_code == 200
    assert f'id="note-content-container-{note_id}"' in content_form_resp.text
    assert "Client requested dashboard." in content_form_resp.text

    # 6. Test PUT inline content save
    content_save_resp = await client.put(f"/notes/{note_id}/content", data={"content": "Client requested dashboard v2."})
    assert content_save_resp.status_code == 200
    assert "Client requested dashboard v2." in content_save_resp.text
    assert f'id="note-content-container-{note_id}"' in content_save_resp.text

    # Verify DB updated
    await db_session.refresh(note)
    assert note.content == "Client requested dashboard v2."

    # 7. Test GET inline content cancel -> returns read-only fragment
    content_cancel_resp = await client.get(f"/notes/{note_id}/content")
    assert content_cancel_resp.status_code == 200
    assert "Client requested dashboard v2." in content_cancel_resp.text

    # 8. Test GET inline append form
    append_form_resp = await client.get(f"/notes/{note_id}/append")
    assert append_form_resp.status_code == 200
    assert f'id="note-content-container-{note_id}"' in append_form_resp.text
    assert "Append to note:" in append_form_resp.text

    # 9. Test POST inline append save with separator
    append_save_resp = await client.post(f"/notes/{note_id}/append", data={"text": "Client also requested Excel export."})
    assert append_save_resp.status_code == 200
    assert "Client requested dashboard v2." in append_save_resp.text
    assert "Client also requested Excel export." in append_save_resp.text
    assert "---" in append_save_resp.text

    # Verify in DB that content contains separator and appended text
    await db_session.refresh(note)
    expected_content = "Client requested dashboard v2.\n\n---\n\nClient also requested Excel export."
    assert note.content == expected_content

    # 10. Test POST inline append with empty text -> returns 400 with error
    bad_append_resp = await client.post(f"/notes/{note_id}/append", data={"text": "   "})
    assert bad_append_resp.status_code == 400
    assert "Appended text cannot be empty" in bad_append_resp.text

    # 11. Refresh dashboard page and confirm saved changes remain
    dash_resp = await client.get("/")
    assert dash_resp.status_code == 200
    assert "Updated Via Post" in dash_resp.text
    assert "Client also requested Excel export." in dash_resp.text
