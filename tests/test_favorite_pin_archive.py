import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category import Category
from app.models.note import Note
from app.models.tag import Tag


@pytest.mark.asyncio
async def test_favorite_workflow(client: AsyncClient, db_session: AsyncSession):
    """
    Requirements 1-3:
    1. Favorite a note
    2. Unfavorite it
    3. Refresh and confirm persistence
    """
    # 1. Register & authenticate User
    signup_data = {
        "full_name": "Fav Tester",
        "email": "fav_tester@example.com",
        "password": "Password123!",
        "confirm_password": "Password123!"
    }
    signup_resp = await client.post("/auth/signup", data=signup_data)
    assert signup_resp.status_code in (200, 303)

    # 2. Create note
    create_resp = await client.post("/notes", data={
        "title": "Favorite Testing Note",
        "content": "This note will be favorited."
    }, follow_redirects=True)
    assert create_resp.status_code == 200

    result = await db_session.execute(select(Note).where(Note.title == "Favorite Testing Note"))
    note = result.scalar_one_or_none()
    assert note is not None
    assert note.is_favorite is False
    note_id = note.id

    # 3. HTMX Favorite note (☆ Favorite -> ★ Favorite)
    fav_resp = await client.post(
        f"/notes/{note_id}/toggle-favorite",
        headers={"HX-Request": "true"}
    )
    assert fav_resp.status_code == 200
    assert "★" in fav_resp.text
    assert "Favorite" in fav_resp.text
    assert "active-favorite" in fav_resp.text or "btn-warning" in fav_resp.text

    # Verify in DB
    await db_session.refresh(note)
    assert note.is_favorite is True

    # 4. HTMX Unfavorite note (★ Favorite -> ☆ Favorite)
    unfav_resp = await client.post(
        f"/notes/{note_id}/toggle-favorite",
        headers={"HX-Request": "true"}
    )
    assert unfav_resp.status_code == 200
    assert "☆" in unfav_resp.text
    assert "Favorite" in unfav_resp.text

    # Verify in DB
    await db_session.refresh(note)
    assert note.is_favorite is False

    # 5. Explicit favorite endpoint
    mark_fav_resp = await client.post(
        f"/notes/{note_id}/favorite",
        headers={"HX-Request": "true"}
    )
    assert mark_fav_resp.status_code == 200
    assert "★" in mark_fav_resp.text

    await db_session.refresh(note)
    assert note.is_favorite is True

    # 6. Refresh (GET /) and confirm persistence in UI and DB
    dash_resp = await client.get("/")
    assert dash_resp.status_code == 200
    assert "Favorite Testing Note" in dash_resp.text
    assert "★" in dash_resp.text

    # Test explicit unfavorite endpoint
    unmark_fav_resp = await client.post(
        f"/notes/{note_id}/unfavorite",
        headers={"HX-Request": "true"}
    )
    assert unmark_fav_resp.status_code == 200
    assert "☆" in unmark_fav_resp.text

    await db_session.refresh(note)
    assert note.is_favorite is False


@pytest.mark.asyncio
async def test_pin_workflow_and_ordering(client: AsyncClient, db_session: AsyncSession):
    """
    Requirements 4-6:
    4. Pin a note
    5. Confirm pinned note appears first
    6. Unpin it
    """
    # 1. Register & authenticate User
    signup_data = {
        "full_name": "Pin Tester",
        "email": "pin_tester@example.com",
        "password": "Password123!",
        "confirm_password": "Password123!"
    }
    signup_resp = await client.post("/auth/signup", data=signup_data)
    assert signup_resp.status_code in (200, 303)

    # 2. Create Note 1 (first created)
    await client.post("/notes", data={
        "title": "Older Note Alpha",
        "content": "First created note."
    }, follow_redirects=True)

    # Create Note 2 (newer created)
    await client.post("/notes", data={
        "title": "Newer Note Beta",
        "content": "Second created note."
    }, follow_redirects=True)

    res_alpha = await db_session.execute(select(Note).where(Note.title == "Older Note Alpha"))
    note_alpha = res_alpha.scalar_one()
    res_beta = await db_session.execute(select(Note).where(Note.title == "Newer Note Beta"))
    note_beta = res_beta.scalar_one()

    # Before pinning: Note Beta is newer, so it appears before Note Alpha
    dash_initial = await client.get("/")
    assert dash_initial.status_code == 200
    pos_alpha_initial = dash_initial.text.find("Older Note Alpha")
    pos_beta_initial = dash_initial.text.find("Newer Note Beta")
    assert pos_beta_initial < pos_alpha_initial

    # 3. Ensure Note Beta is newer by updating Note Beta's content
    await client.post(
        f"/notes/{note_beta.id}/title",
        data={"title": "Newer Note Beta [Fresh]"},
        headers={"HX-Request": "true"}
    )

    # Note Beta is newer and both are unpinned, so Note Beta appears before Note Alpha
    dash_fresh = await client.get("/")
    assert dash_fresh.status_code == 200
    pos_alpha_fresh = dash_fresh.text.find("Older Note Alpha")
    pos_beta_fresh = dash_fresh.text.find("Newer Note Beta [Fresh]")
    assert pos_beta_fresh < pos_alpha_fresh

    # 4. Pin Older Note Alpha
    pin_resp = await client.post(
        f"/notes/{note_alpha.id}/toggle-pin",
        headers={"HX-Request": "true"}
    )
    assert pin_resp.status_code == 200
    assert "📌" in pin_resp.text
    assert "Pinned" in pin_resp.text

    await db_session.refresh(note_alpha)
    assert note_alpha.is_pinned is True

    # Now update Note Beta AGAIN so Note Beta has a newer updated_at timestamp than Note Alpha
    await client.post(
        f"/notes/{note_beta.id}/title",
        data={"title": "Newer Note Beta [Fresher]"},
        headers={"HX-Request": "true"}
    )

    # 5. Confirm pinned Note Alpha appears first on All Notes (GET /) even though Note Beta has newer updated_at
    dash_pinned = await client.get("/")
    assert dash_pinned.status_code == 200
    pos_alpha_pinned = dash_pinned.text.find("Older Note Alpha")
    pos_beta_pinned = dash_pinned.text.find("Newer Note Beta [Fresher]")
    assert pos_alpha_pinned < pos_beta_pinned, "Pinned Note Alpha must appear before unpinned Note Beta even when Note Beta is newer"

    # 6. Unpin Older Note Alpha
    unpin_resp = await client.post(
        f"/notes/{note_alpha.id}/toggle-pin",
        headers={"HX-Request": "true"}
    )
    assert unpin_resp.status_code == 200
    assert "Pin" in unpin_resp.text

    await db_session.refresh(note_alpha)
    assert note_alpha.is_pinned is False

    # Now update Note Beta again so Note Beta is definitively the most recently updated
    await client.post(
        f"/notes/{note_beta.id}/title",
        data={"title": "Newer Note Beta [Freshest]"},
        headers={"HX-Request": "true"}
    )

    # Confirm unpinned ordering puts most recently updated Note Beta first
    dash_unpinned = await client.get("/")
    assert dash_unpinned.status_code == 200
    pos_alpha_unpinned = dash_unpinned.text.find("Older Note Alpha")
    pos_beta_unpinned = dash_unpinned.text.find("Newer Note Beta [Freshest]")
    assert pos_beta_unpinned < pos_alpha_unpinned


@pytest.mark.asyncio
async def test_archive_and_unarchive_workflow(client: AsyncClient, db_session: AsyncSession):
    """
    Requirements 7-11:
    7. Archive a note
    8. Confirm it disappears from All Notes
    9. Open Archive
    10. Unarchive the note
    11. Confirm it returns to All Notes
    """
    # 1. Register & authenticate User
    signup_data = {
        "full_name": "Archive Tester",
        "email": "archive_tester@example.com",
        "password": "Password123!",
        "confirm_password": "Password123!"
    }
    signup_resp = await client.post("/auth/signup", data=signup_data)
    assert signup_resp.status_code in (200, 303)

    # 2. Create note
    await client.post("/notes", data={
        "title": "Secret Project Archive",
        "content": "Content to be archived."
    }, follow_redirects=True)

    result = await db_session.execute(select(Note).where(Note.title == "Secret Project Archive"))
    note = result.scalar_one()
    assert note.is_archived is False
    note_id = note.id

    # Confirm note appears in All Notes (GET /)
    dash_before = await client.get("/")
    assert dash_before.status_code == 200
    assert "Secret Project Archive" in dash_before.text

    # 3. Archive the note via HTMX
    archive_resp = await client.post(
        f"/notes/{note_id}/toggle-archive",
        headers={"HX-Request": "true", "HX-Target": f"note-card-col-{note_id}"}
    )
    assert archive_resp.status_code == 200
    assert f"note {note_id} archived/unarchived" in archive_resp.text

    await db_session.refresh(note)
    assert note.is_archived is True
    assert note.is_deleted is False

    # 4. Confirm note disappears from All Notes (GET /)
    dash_after = await client.get("/")
    assert dash_after.status_code == 200
    assert "Secret Project Archive" not in dash_after.text

    # 5. Open Archive view (GET /archive)
    archive_view_resp = await client.get("/archive")
    assert archive_view_resp.status_code == 200
    assert "Secret Project Archive" in archive_view_resp.text
    assert "Unarchive" in archive_view_resp.text

    # Also test /?filter=archive query param
    filter_archive_resp = await client.get("/?filter=archive")
    assert filter_archive_resp.status_code == 200
    assert "Secret Project Archive" in filter_archive_resp.text

    # 6. Unarchive note via HTMX
    unarchive_resp = await client.post(
        f"/notes/{note_id}/unarchive",
        headers={"HX-Request": "true", "HX-Target": f"note-card-col-{note_id}"}
    )
    assert unarchive_resp.status_code == 200

    await db_session.refresh(note)
    assert note.is_archived is False

    # 7. Confirm note is removed from Archive view (GET /archive)
    archive_view_after = await client.get("/archive")
    assert archive_view_after.status_code == 200
    assert "Secret Project Archive" not in archive_view_after.text

    # 8. Confirm note returns to All Notes (GET /)
    dash_restored = await client.get("/")
    assert dash_restored.status_code == 200
    assert "Secret Project Archive" in dash_restored.text


@pytest.mark.asyncio
async def test_favorites_and_pinned_filters(client: AsyncClient, db_session: AsyncSession):
    """
    Requirements 12-13:
    12. Test Favorites filter
    13. Test Pinned filter
    """
    # 1. Register & authenticate User
    signup_data = {
        "full_name": "Filter Tester",
        "email": "filter_tester@example.com",
        "password": "Password123!",
        "confirm_password": "Password123!"
    }
    signup_resp = await client.post("/auth/signup", data=signup_data)
    assert signup_resp.status_code in (200, 303)

    # 2. Create 4 notes with different statuses:
    # Note 1: Standard Active Note
    await client.post("/notes", data={"title": "Standard Active Note 1", "content": "Basic note"}, follow_redirects=True)
    # Note 2: Favorite Note
    await client.post("/notes", data={"title": "Favorite Only Note 2", "content": "Favorite note"}, follow_redirects=True)
    # Note 3: Pinned Note
    await client.post("/notes", data={"title": "Pinned Only Note 3", "content": "Pinned note"}, follow_redirects=True)
    # Note 4: Archived Note
    await client.post("/notes", data={"title": "Archived Note 4", "content": "Archived note"}, follow_redirects=True)

    res_1 = (await db_session.execute(select(Note).where(Note.title == "Standard Active Note 1"))).scalar_one()
    res_2 = (await db_session.execute(select(Note).where(Note.title == "Favorite Only Note 2"))).scalar_one()
    res_3 = (await db_session.execute(select(Note).where(Note.title == "Pinned Only Note 3"))).scalar_one()
    res_4 = (await db_session.execute(select(Note).where(Note.title == "Archived Note 4"))).scalar_one()

    # Set statuses
    await client.post(f"/notes/{res_2.id}/favorite")
    await client.post(f"/notes/{res_3.id}/pin")
    await client.post(f"/notes/{res_4.id}/archive")

    # 3. Test Favorites filter (/favorites and /?filter=favorites)
    fav_resp = await client.get("/favorites")
    assert fav_resp.status_code == 200
    assert "Favorite Only Note 2" in fav_resp.text
    assert "Standard Active Note 1" not in fav_resp.text
    assert "Archived Note 4" not in fav_resp.text

    fav_query_resp = await client.get("/?filter=favorites")
    assert fav_query_resp.status_code == 200
    assert "Favorite Only Note 2" in fav_query_resp.text
    assert "Standard Active Note 1" not in fav_query_resp.text

    # 4. Test Pinned filter (/pinned and /?filter=pinned)
    pinned_resp = await client.get("/pinned")
    assert pinned_resp.status_code == 200
    assert "Pinned Only Note 3" in pinned_resp.text
    assert "Standard Active Note 1" not in pinned_resp.text
    assert "Archived Note 4" not in pinned_resp.text

    pinned_query_resp = await client.get("/?filter=pinned")
    assert pinned_query_resp.status_code == 200
    assert "Pinned Only Note 3" in pinned_query_resp.text
    assert "Standard Active Note 1" not in pinned_query_resp.text

    # 5. Test All Notes view
    all_resp = await client.get("/")
    assert all_resp.status_code == 200
    assert "Pinned Only Note 3" in all_resp.text
    assert "Favorite Only Note 2" in all_resp.text
    assert "Standard Active Note 1" in all_resp.text
    assert "Archived Note 4" not in all_resp.text


@pytest.mark.asyncio
async def test_authorization_two_separate_users(client: AsyncClient, db_session: AsyncSession):
    """
    Requirements 14-15:
    14. Test with two separate users
    15. Verify one user cannot modify another user's note states
    """
    # 1. Register User Alice
    alice_data = {
        "full_name": "Alice Auth",
        "email": "alice_auth@example.com",
        "password": "Password123!",
        "confirm_password": "Password123!"
    }
    signup_alice = await client.post("/auth/signup", data=alice_data)
    assert signup_alice.status_code in (200, 303)

    # Alice creates a note
    alice_create = await client.post("/notes", data={
        "title": "Alice Protected Note",
        "content": "Only Alice should control this."
    }, follow_redirects=True)
    assert alice_create.status_code == 200

    result = await db_session.execute(select(Note).where(Note.title == "Alice Protected Note"))
    alice_note = result.scalar_one()
    alice_note_id = alice_note.id

    # 2. Log out Alice and Register User Bob
    await client.post("/auth/logout")

    bob_data = {
        "full_name": "Bob Attacker",
        "email": "bob_attacker@example.com",
        "password": "Password123!",
        "confirm_password": "Password123!"
    }
    signup_bob = await client.post("/auth/signup", data=bob_data)
    assert signup_bob.status_code in (200, 303)

    # 3. Bob attempts to favorite Alice's note -> must fail with 404
    bob_fav = await client.post(f"/notes/{alice_note_id}/toggle-favorite")
    assert bob_fav.status_code == 404

    bob_fav_explicit = await client.post(f"/notes/{alice_note_id}/favorite")
    assert bob_fav_explicit.status_code == 404

    # 4. Bob attempts to pin Alice's note -> must fail with 404
    bob_pin = await client.post(f"/notes/{alice_note_id}/toggle-pin")
    assert bob_pin.status_code == 404

    bob_pin_explicit = await client.post(f"/notes/{alice_note_id}/pin")
    assert bob_pin_explicit.status_code == 404

    # 5. Bob attempts to archive Alice's note -> must fail with 404
    bob_archive = await client.post(f"/notes/{alice_note_id}/toggle-archive")
    assert bob_archive.status_code == 404

    bob_archive_explicit = await client.post(f"/notes/{alice_note_id}/archive")
    assert bob_archive_explicit.status_code == 404

    # 6. Bob attempts to unarchive Alice's note -> must fail with 404
    bob_unarchive = await client.post(f"/notes/{alice_note_id}/unarchive")
    assert bob_unarchive.status_code == 404

    # 7. Verify Alice's note in DB is completely unchanged
    await db_session.refresh(alice_note)
    assert alice_note.is_favorite is False
    assert alice_note.is_pinned is False
    assert alice_note.is_archived is False

    # 8. Verify Bob's views do not leak Alice's notes
    bob_dash = await client.get("/")
    assert "Alice Protected Note" not in bob_dash.text
    bob_fav_list = await client.get("/favorites")
    assert "Alice Protected Note" not in bob_fav_list.text
    bob_pinned_list = await client.get("/pinned")
    assert "Alice Protected Note" not in bob_pinned_list.text
    bob_archive_list = await client.get("/archive")
    assert "Alice Protected Note" not in bob_archive_list.text


@pytest.mark.asyncio
async def test_interactions_with_categories_and_tags(client: AsyncClient, db_session: AsyncSession):
    """
    Requirement 16:
    16. Test interactions together with Categories and Tags
    """
    # 1. Register User
    signup_data = {
        "full_name": "Combo Tester",
        "email": "combo_tester@example.com",
        "password": "Password123!",
        "confirm_password": "Password123!"
    }
    await client.post("/auth/signup", data=signup_data)

    # 2. Create Category "Engineering Combo" and "Personal Combo"
    cat_resp = await client.post("/categories", data={"name": "Engineering Combo", "color": "#2563eb"}, headers={"HX-Request": "true"})
    assert cat_resp.status_code == 200

    cat_personal_resp = await client.post("/categories", data={"name": "Personal Combo", "color": "#10b981"}, headers={"HX-Request": "true"})
    assert cat_personal_resp.status_code == 200

    res_cat = (await db_session.execute(select(Category).where(Category.name == "Engineering Combo"))).scalar_one()
    cat_eng_id = res_cat.id

    res_cat_pers = (await db_session.execute(select(Category).where(Category.name == "Personal Combo"))).scalar_one()
    cat_pers_id = res_cat_pers.id

    # 3. Create Note with Category "Engineering Combo" and Tags "combo_fastapi, combo_htmx"
    create_resp = await client.post("/notes", data={
        "title": "Full Stack Architecture",
        "content": "Deep dive into FastAPI and HTMX.",
        "category_id": str(cat_eng_id),
        "tag_names": "combo_fastapi, combo_htmx"
    }, follow_redirects=True)
    assert create_resp.status_code == 200

    note = (await db_session.execute(select(Note).where(Note.title == "Full Stack Architecture"))).scalar_one()
    note_id = note.id

    # Retrieve Tag ID
    res_tag = (await db_session.execute(select(Tag).where(Tag.name == "combo_fastapi"))).scalar_one()
    tag_fastapi_id = res_tag.id

    # 4. Favorite and Pin this note
    await client.post(f"/notes/{note_id}/favorite")
    await client.post(f"/notes/{note_id}/pin")

    await db_session.refresh(note)
    assert note.is_favorite is True
    assert note.is_pinned is True

    # 5. Test Category filter on Favorites view
    fav_cat_resp = await client.get(f"/favorites?category_id={cat_eng_id}")
    assert fav_cat_resp.status_code == 200
    assert "Full Stack Architecture" in fav_cat_resp.text

    fav_cat_pers_resp = await client.get(f"/favorites?category_id={cat_pers_id}")
    assert fav_cat_pers_resp.status_code == 200
    assert "Full Stack Architecture" not in fav_cat_pers_resp.text

    # 6. Test Tag filter on Pinned view
    pinned_tag_resp = await client.get(f"/pinned?tag_id={tag_fastapi_id}")
    assert pinned_tag_resp.status_code == 200
    assert "Full Stack Architecture" in pinned_tag_resp.text

    # 7. Archive the note
    await client.post(f"/notes/{note_id}/archive")

    # Now it disappears from /favorites?category_id=...
    fav_after_archive = await client.get(f"/favorites?category_id={cat_eng_id}")
    assert "Full Stack Architecture" not in fav_after_archive.text

    # And it appears in /archive?category_id=...
    archive_cat_resp = await client.get(f"/archive?category_id={cat_eng_id}")
    assert archive_cat_resp.status_code == 200
    assert "Full Stack Architecture" in archive_cat_resp.text
    assert "#combo_fastapi" in archive_cat_resp.text
    assert "Engineering Combo" in archive_cat_resp.text

