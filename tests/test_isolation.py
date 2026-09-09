import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.note import Note


@pytest.mark.asyncio
async def test_user_note_authorization_and_isolation(client: AsyncClient, db_session: AsyncSession):
    # 1. Register User Alice
    alice_data = {
        "full_name": "Alice Smith",
        "email": "alice_isolation@example.com",
        "password": "Password123!",
        "confirm_password": "Password123!"
    }
    signup_alice = await client.post("/auth/signup", data=alice_data)
    assert signup_alice.status_code in (200, 303)

    # Alice creates a private note
    alice_create = await client.post("/notes", data={
        "title": "Alice Classified Plan",
        "content": "Secret information only Alice should see."
    }, follow_redirects=True)
    assert alice_create.status_code == 200

    # Retrieve Alice's note ID from database
    result = await db_session.execute(select(Note).where(Note.title == "Alice Classified Plan"))
    alice_note = result.scalar_one_or_none()
    assert alice_note is not None
    alice_note_id = alice_note.id

    # 2. Log out Alice
    await client.post("/auth/logout")

    # 3. Register User Bob
    bob_data = {
        "full_name": "Bob Jones",
        "email": "bob_isolation@example.com",
        "password": "Password123!",
        "confirm_password": "Password123!"
    }
    signup_bob = await client.post("/auth/signup", data=bob_data)
    assert signup_bob.status_code in (200, 303)

    # Bob creates his own note
    bob_create = await client.post("/notes", data={
        "title": "Bob Public Tasks",
        "content": "Buy groceries and feed the cat."
    }, follow_redirects=True)
    assert bob_create.status_code == 200

    # --- Verify Authorization / Isolation Rules ---

    # Rule 1: Bob listing notes (GET /) must NOT see Alice's note
    bob_dash = await client.get("/")
    assert bob_dash.status_code == 200
    assert "Bob Public Tasks" in bob_dash.text
    assert "Alice Classified Plan" not in bob_dash.text
    assert "Secret information only Alice should see." not in bob_dash.text

    # Rule 2: Bob cannot view Alice's note (GET /notes/{alice_note_id}) -> 404
    bob_view_attack = await client.get(f"/notes/{alice_note_id}")
    assert bob_view_attack.status_code == 404
    assert "Secret information only Alice should see." not in bob_view_attack.text

    # Rule 3: Bob cannot access Alice's full edit form (GET /notes/{alice_note_id}/edit) -> 404
    bob_edit_page_attack = await client.get(f"/notes/{alice_note_id}/edit")
    assert bob_edit_page_attack.status_code == 404

    # Rule 4: Bob cannot edit Alice's note (POST /notes/{alice_note_id}/edit) -> 404
    bob_edit_submit_attack = await client.post(f"/notes/{alice_note_id}/edit", data={
        "title": "Hacked Title",
        "content": "Hacked content"
    })
    assert bob_edit_submit_attack.status_code == 404

    # Rule 5: Bob cannot access Alice's inline title edit form (GET /notes/{alice_note_id}/title/edit) -> 404
    bob_title_form_attack = await client.get(f"/notes/{alice_note_id}/title/edit")
    assert bob_title_form_attack.status_code == 404

    # Rule 6: Bob cannot inline edit Alice's title (PUT /notes/{alice_note_id}/title) -> 404
    bob_title_put_attack = await client.put(f"/notes/{alice_note_id}/title", data={"title": "Hacked Title"})
    assert bob_title_put_attack.status_code == 404

    # Rule 7: Bob cannot access Alice's inline content edit form (GET /notes/{alice_note_id}/content/edit) -> 404
    bob_content_form_attack = await client.get(f"/notes/{alice_note_id}/content/edit")
    assert bob_content_form_attack.status_code == 404

    # Rule 8: Bob cannot inline edit Alice's content (PUT /notes/{alice_note_id}/content) -> 404
    bob_content_put_attack = await client.put(f"/notes/{alice_note_id}/content", data={"content": "Hacked Content"})
    assert bob_content_put_attack.status_code == 404

    # Rule 9: Bob cannot access Alice's append form (GET /notes/{alice_note_id}/append) -> 404
    bob_append_form_attack = await client.get(f"/notes/{alice_note_id}/append")
    assert bob_append_form_attack.status_code == 404

    # Rule 10: Bob cannot append to Alice's note (POST /notes/{alice_note_id}/append) -> 404
    bob_append_post_attack = await client.post(f"/notes/{alice_note_id}/append", data={"text": "Hacked Append"})
    assert bob_append_post_attack.status_code == 404

    # Verify Alice's note in DB remains untouched
    await db_session.refresh(alice_note)
    assert alice_note.title == "Alice Classified Plan"
    assert alice_note.content == "Secret information only Alice should see."

    # Rule 11: Bob cannot delete Alice's note (POST /notes/{alice_note_id}/delete) -> 404
    bob_delete_attack = await client.post(f"/notes/{alice_note_id}/delete")
    assert bob_delete_attack.status_code == 404

    # Rule 12: Bob cannot DELETE Alice's note (DELETE /notes/{alice_note_id}) -> 404
    bob_raw_delete_attack = await client.delete(f"/notes/{alice_note_id}")
    assert bob_raw_delete_attack.status_code == 404

    # Verify Alice's note in DB is NOT deleted
    await db_session.refresh(alice_note)
    assert alice_note.is_deleted is False
    assert alice_note.deleted_at is None

    # 4. Log out Bob and log back in as Alice to confirm she can still access her note
    await client.post("/auth/logout")
    login_alice = await client.post("/auth/login", data={
        "email": "alice_isolation@example.com",
        "password": "Password123!"
    })
    assert login_alice.status_code in (200, 303)

    alice_view = await client.get(f"/notes/{alice_note_id}")
    assert alice_view.status_code == 200
    assert "Alice Classified Plan" in alice_view.text
    assert "Secret information only Alice should see." in alice_view.text
