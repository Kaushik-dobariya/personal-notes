import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category import Category
from app.models.note import Note
from app.models.tag import Tag


@pytest.mark.asyncio
async def test_trash_restore_and_permanent_delete_lifecycle(
    client: AsyncClient, db_session: AsyncSession
):
    """
    Test complete lifecycle (Steps 1-13 in Requirement 11):
    1. Create note.
    2. Favorite and pin it.
    3. Add category and tags.
    4. Soft delete note.
    5. Confirm disappears from All Notes.
    6. Confirm disappears from Favorites and Pinned.
    7. Open Trash.
    8. Confirm appears in Trash with title, content, category, tags, and formatted deleted date.
    9. Restore note.
    10. Confirm content, category, tags, favorite, and pin remain.
    11. Delete again.
    12. Permanently delete note.
    13. Refresh Trash and confirm gone from database and UI.
    """
    # 1. Register & authenticate user
    signup_data = {
        "full_name": "Charlie Lifecycle",
        "email": "charlie_trash@example.com",
        "password": "Password123!",
        "confirm_password": "Password123!"
    }
    signup_resp = await client.post("/auth/signup", data=signup_data)
    assert signup_resp.status_code in (200, 303)

    # Create category
    cat_resp = await client.post(
        "/categories",
        data={"name": "Trash Lifecycle Engineering", "color": "#0284c7"},
        headers={"HX-Request": "true"}
    )
    assert cat_resp.status_code == 200

    cat_res = await db_session.execute(
        select(Category).where(Category.name == "Trash Lifecycle Engineering")
    )
    category = cat_res.scalar_one()
    cat_id = category.id

    # 1. Create a note with category, tags, favorite, and pin
    create_payload = {
        "title": "Quarterly Architecture Overhaul",
        "content": "Transitioning core state to HTMX with PostgreSQL soft delete support.",
        "category_id": str(cat_id),
        "tag_names": "architecture, postgres, htmx",
        "is_favorite": "true",
        "is_pinned": "true"
    }
    create_resp = await client.post("/notes", data=create_payload, follow_redirects=True)
    assert create_resp.status_code == 200
    assert "Quarterly Architecture Overhaul" in create_resp.text

    # Retrieve note from DB
    res = await db_session.execute(
        select(Note).where(Note.title == "Quarterly Architecture Overhaul")
    )
    note = res.scalar_one()
    note_id = note.id
    assert note.is_favorite is True
    assert note.is_pinned is True
    assert note.is_archived is False
    assert note.is_deleted is False
    assert note.deleted_at is None
    assert len(note.tags) == 3

    # Confirm present on All Notes, Favorites, and Pinned views
    all_resp = await client.get("/")
    assert all_resp.status_code == 200
    assert "Quarterly Architecture Overhaul" in all_resp.text

    fav_resp = await client.get("/favorites")
    assert fav_resp.status_code == 200
    assert "Quarterly Architecture Overhaul" in fav_resp.text

    pinned_resp = await client.get("/pinned")
    assert pinned_resp.status_code == 200
    assert "Quarterly Architecture Overhaul" in pinned_resp.text

    # 4. Soft Delete the note via HTMX
    del_resp = await client.delete(f"/notes/{note_id}", headers={"HX-Request": "true"})
    assert del_resp.status_code == 200
    assert "sidebar-trash-count" in del_resp.text

    # Refresh DB model
    await db_session.refresh(note)
    assert note.is_deleted is True
    assert note.deleted_at is not None

    # 5. Confirm it disappears from All Notes
    all_after_del = await client.get("/")
    assert all_after_del.status_code == 200
    assert "Quarterly Architecture Overhaul" not in all_after_del.text

    # 6. Confirm it disappears from Favorites and Pinned
    fav_after_del = await client.get("/favorites")
    assert fav_after_del.status_code == 200
    assert "Quarterly Architecture Overhaul" not in fav_after_del.text

    pinned_after_del = await client.get("/pinned")
    assert pinned_after_del.status_code == 200
    assert "Quarterly Architecture Overhaul" not in pinned_after_del.text

    # Direct view of note should return 404 while in trash
    single_view_resp = await client.get(f"/notes/{note_id}")
    assert single_view_resp.status_code == 404

    # 7. Open Trash
    trash_resp = await client.get("/trash")
    assert trash_resp.status_code == 200

    # 8. Confirm note appears in Trash with useful information
    assert "Quarterly Architecture Overhaul" in trash_resp.text
    assert "Transitioning core state to HTMX" in trash_resp.text
    assert "Engineering" in trash_resp.text
    assert "#architecture" in trash_resp.text
    assert "Deleted:" in trash_resp.text
    assert f"/notes/{note_id}/restore" in trash_resp.text
    assert f"/notes/{note_id}/permanent" in trash_resp.text

    # 9. Restore Note via HTMX
    restore_resp = await client.post(
        f"/notes/{note_id}/restore", headers={"HX-Request": "true"}
    )
    assert restore_resp.status_code == 200
    assert "sidebar-trash-count" in restore_resp.text

    # Verify DB state
    await db_session.refresh(note)
    assert note.is_deleted is False
    assert note.deleted_at is None

    # 10. Confirm content, category, tags, favorite, and pin remain
    assert note.title == "Quarterly Architecture Overhaul"
    assert note.content == "Transitioning core state to HTMX with PostgreSQL soft delete support."
    assert note.category_id == cat_id
    assert note.is_favorite is True
    assert note.is_pinned is True
    assert note.is_archived is False
    assert len(note.tags) == 3

    # Confirm visible on All Notes, Favorites, and Pinned again
    all_restored = await client.get("/")
    assert "Quarterly Architecture Overhaul" in all_restored.text

    fav_restored = await client.get("/favorites")
    assert "Quarterly Architecture Overhaul" in fav_restored.text

    pinned_restored = await client.get("/pinned")
    assert "Quarterly Architecture Overhaul" in pinned_restored.text

    # Single view should work again
    view_ok_resp = await client.get(f"/notes/{note_id}")
    assert view_ok_resp.status_code == 200
    assert "Quarterly Architecture Overhaul" in view_ok_resp.text

    # 11. Delete it again
    del2_resp = await client.delete(f"/notes/{note_id}", headers={"HX-Request": "true"})
    assert del2_resp.status_code == 200

    # 12. Permanently delete it via HTMX
    perm_resp = await client.delete(
        f"/notes/{note_id}/permanent", headers={"HX-Request": "true"}
    )
    assert perm_resp.status_code == 200
    assert "permanently deleted" in perm_resp.text

    # Verify note physically deleted from DB
    res_deleted = await db_session.execute(select(Note).where(Note.id == note_id))
    assert res_deleted.scalar_one_or_none() is None

    # 13. Refresh Trash and confirm gone
    trash_after_perm = await client.get("/trash")
    assert trash_after_perm.status_code == 200
    assert "Quarterly Architecture Overhaul" not in trash_after_perm.text
    assert "Trash is Empty" in trash_after_perm.text


@pytest.mark.asyncio
async def test_permanent_delete_rejected_for_active_note(
    client: AsyncClient, db_session: AsyncSession
):
    """
    Requirement 4: Do not permanently delete a note directly from normal Notes view.
    Only allow permanent deletion from Trash.
    """
    signup_data = {
        "full_name": "Active Note Tester",
        "email": "active_perm_test@example.com",
        "password": "Password123!",
        "confirm_password": "Password123!"
    }
    await client.post("/auth/signup", data=signup_data)

    create_resp = await client.post("/notes", data={
        "title": "Active Note That Must Not Be Permanently Deleted",
        "content": "Active note content."
    }, follow_redirects=True)
    assert create_resp.status_code == 200

    res = await db_session.execute(
        select(Note).where(Note.title == "Active Note That Must Not Be Permanently Deleted")
    )
    note = res.scalar_one()
    note_id = note.id
    assert note.is_deleted is False

    # Attempt to permanently delete active note -> MUST fail (404 / rejected)
    perm_attempt = await client.delete(f"/notes/{note_id}/permanent")
    assert perm_attempt.status_code == 404

    # Verify note still exists in database and is not deleted
    await db_session.refresh(note)
    assert note.is_deleted is False


@pytest.mark.asyncio
async def test_empty_trash(client: AsyncClient, db_session: AsyncSession):
    """
    Requirement 5 & 14: Test Empty Trash.
    Permanently deletes all trashed notes belonging to logged-in user.
    """
    signup_data = {
        "full_name": "Empty Trash Tester",
        "email": "empty_trash_test@example.com",
        "password": "Password123!",
        "confirm_password": "Password123!"
    }
    await client.post("/auth/signup", data=signup_data)

    # Create 3 notes
    for i in range(1, 4):
        await client.post("/notes", data={
            "title": f"Trashed Note {i}",
            "content": f"Content for note {i}"
        }, follow_redirects=True)

    # Soft delete all 3
    notes_res = await db_session.execute(
        select(Note).where(Note.title.like("Trashed Note %"))
    )
    notes = list(notes_res.scalars().all())
    assert len(notes) == 3

    for n in notes:
        await client.delete(f"/notes/{n.id}", headers={"HX-Request": "true"})

    # Check Trash page displays 3 notes and Empty Trash button
    trash_page = await client.get("/trash")
    assert trash_page.status_code == 200
    for i in range(1, 4):
        assert f"Trashed Note {i}" in trash_page.text
    assert "Empty Trash" in trash_page.text

    # Execute Empty Trash via HTMX
    empty_resp = await client.delete("/notes/trash/empty", headers={"HX-Request": "true"})
    assert empty_resp.status_code == 200
    assert "Trash is Empty" in empty_resp.text

    # Verify all 3 notes are permanently removed from DB
    notes_check = await db_session.execute(
        select(Note).where(Note.title.like("Trashed Note %"))
    )
    assert len(list(notes_check.scalars().all())) == 0

    # Refresh Trash page
    refresh_trash = await client.get("/trash")
    assert refresh_trash.status_code == 200
    assert "Trash is Empty" in refresh_trash.text


@pytest.mark.asyncio
async def test_two_users_trash_isolation_and_authorization(
    client: AsyncClient, db_session: AsyncSession
):
    """
    Requirements 7, 15, and 16:
    Verify strict authorization and isolation between two users:
    - User A cannot view User B's trashed notes.
    - User B cannot restore User A's note.
    - User B cannot permanently delete User A's note.
    - User B emptying trash does NOT affect User A's trashed notes.
    """
    # 1. Register Alice
    await client.post("/auth/signup", data={
        "full_name": "Alice Trash",
        "email": "alice_trash@example.com",
        "password": "Password123!",
        "confirm_password": "Password123!"
    })

    # Alice creates a secret note and deletes it
    await client.post("/notes", data={
        "title": "Alice Confidential Note",
        "content": "Alice's secrets in trash."
    }, follow_redirects=True)

    res_a = await db_session.execute(
        select(Note).where(Note.title == "Alice Confidential Note")
    )
    note_alice = res_a.scalar_one()
    alice_note_id = note_alice.id

    # Alice soft-deletes her note
    await client.delete(f"/notes/{alice_note_id}", headers={"HX-Request": "true"})
    await db_session.refresh(note_alice)
    assert note_alice.is_deleted is True

    # 2. Log out Alice and register Bob
    await client.post("/auth/logout")

    await client.post("/auth/signup", data={
        "full_name": "Bob Trash",
        "email": "bob_trash@example.com",
        "password": "Password123!",
        "confirm_password": "Password123!"
    })

    # Bob creates his own note and soft-deletes it
    await client.post("/notes", data={
        "title": "Bob Trashed Note",
        "content": "Bob's content in trash."
    }, follow_redirects=True)

    res_b = await db_session.execute(
        select(Note).where(Note.title == "Bob Trashed Note")
    )
    note_bob = res_b.scalar_one()
    bob_note_id = note_bob.id

    await client.delete(f"/notes/{bob_note_id}", headers={"HX-Request": "true"})

    # --- Verification 1: Bob opening Trash sees ONLY Bob's note, NOT Alice's ---
    bob_trash_view = await client.get("/trash")
    assert bob_trash_view.status_code == 200
    assert "Bob Trashed Note" in bob_trash_view.text
    assert "Alice Confidential Note" not in bob_trash_view.text
    assert "Alice's secrets in trash." not in bob_trash_view.text

    # --- Verification 2: Bob attempting to restore Alice's note -> 404 ---
    bob_restore_attack = await client.post(
        f"/notes/{alice_note_id}/restore", headers={"HX-Request": "true"}
    )
    assert bob_restore_attack.status_code == 404

    # Verify Alice's note remains in trash
    await db_session.refresh(note_alice)
    assert note_alice.is_deleted is True

    # --- Verification 3: Bob attempting to permanently delete Alice's note -> 404 ---
    bob_perm_del_attack = await client.delete(
        f"/notes/{alice_note_id}/permanent", headers={"HX-Request": "true"}
    )
    assert bob_perm_del_attack.status_code == 404

    # Verify Alice's note still exists in DB
    res_still_there = await db_session.execute(
        select(Note).where(Note.id == alice_note_id)
    )
    assert res_still_there.scalar_one_or_none() is not None

    # --- Verification 4: Bob empties his trash ---
    bob_empty = await client.delete("/notes/trash/empty", headers={"HX-Request": "true"})
    assert bob_empty.status_code == 200

    # Bob's note is deleted from DB
    res_bob_check = await db_session.execute(
        select(Note).where(Note.id == bob_note_id)
    )
    assert res_bob_check.scalar_one_or_none() is None

    # BUT Alice's trashed note is completely unharmed!
    await db_session.refresh(note_alice)
    assert note_alice.is_deleted is True

    # --- Verification 5: Alice logs back in, views her Trash and restores her note ---
    await client.post("/auth/logout")
    await client.post("/auth/login", data={
        "email": "alice_trash@example.com",
        "password": "Password123!"
    })

    alice_trash_view = await client.get("/trash")
    assert alice_trash_view.status_code == 200
    assert "Alice Confidential Note" in alice_trash_view.text

    # Alice restores her note
    alice_restore = await client.post(
        f"/notes/{alice_note_id}/restore", headers={"HX-Request": "true"}
    )
    assert alice_restore.status_code == 200

    await db_session.refresh(note_alice)
    assert note_alice.is_deleted is False
    assert note_alice.deleted_at is None

    # Note appears back in Alice's All Notes
    alice_all = await client.get("/")
    assert "Alice Confidential Note" in alice_all.text
