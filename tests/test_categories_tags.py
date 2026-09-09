import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category import Category
from app.models.note import Note
from app.models.tag import Tag


@pytest.mark.asyncio
async def test_category_crud_and_lifecycle(client: AsyncClient, db_session: AsyncSession):
    # 1. Sign up User
    await client.post("/auth/signup", data={
        "full_name": "Cat User",
        "email": "cat_user@example.com",
        "password": "Password123!",
        "confirm_password": "Password123!"
    })

    # 2. Create Category via Form POST
    create_cat_resp = await client.post("/categories", data={
        "name": "Work",
        "color": "#3b82f6"
    })
    assert create_cat_resp.status_code == 200
    assert "Work" in create_cat_resp.text

    # Verify in DB
    result = await db_session.execute(select(Category).where(Category.name == "Work"))
    cat = result.scalar_one_or_none()
    assert cat is not None
    assert cat.color == "#3b82f6"
    cat_id = cat.id

    # 3. Duplicate Category name for same user should fail (400)
    dup_resp = await client.post("/categories", data={
        "name": "Work",
        "color": "#ef4444"
    })
    assert dup_resp.status_code == 400
    assert "already exists" in dup_resp.text

    # 4. GET category edit modal
    edit_modal_resp = await client.get(f"/categories/{cat_id}/edit-modal")
    assert edit_modal_resp.status_code == 200
    assert 'value="Work"' in edit_modal_resp.text

    # 5. GET category inline edit
    inline_edit_resp = await client.get(f"/categories/{cat_id}/inline-edit")
    assert inline_edit_resp.status_code == 200
    assert f'id="category-item-{cat_id}"' in inline_edit_resp.text

    # 6. Update Category (PUT /categories/{cat_id})
    update_resp = await client.put(f"/categories/{cat_id}", data={
        "name": "Work Projects",
        "color": "#10b981"
    })
    assert update_resp.status_code == 200
    assert "Work Projects" in update_resp.text

    await db_session.refresh(cat)
    assert cat.name == "Work Projects"
    assert cat.color == "#10b981"

    # 7. Create Note assigned to this category
    note_resp = await client.post("/notes", data={
        "title": "Categorized Note",
        "content": "Note inside Work Projects category",
        "category_id": str(cat_id)
    }, follow_redirects=True)
    assert note_resp.status_code == 200

    note_result = await db_session.execute(select(Note).where(Note.title == "Categorized Note"))
    note = note_result.scalar_one_or_none()
    assert note is not None
    assert note.category_id == cat_id

    # 8. Check sidebar has count = 1
    sidebar_resp = await client.get("/categories/sidebar")
    assert sidebar_resp.status_code == 200
    assert "Work Projects" in sidebar_resp.text
    assert "1" in sidebar_resp.text

    # 9. Delete Category -> Note should remain, category_id set to NULL
    del_cat_resp = await client.delete(f"/categories/{cat_id}")
    assert del_cat_resp.status_code == 200

    await db_session.refresh(note)
    assert note.category_id is None
    assert note.is_deleted is False


@pytest.mark.asyncio
async def test_tag_crud_and_lifecycle(client: AsyncClient, db_session: AsyncSession):
    # 1. Sign up User
    await client.post("/auth/signup", data={
        "full_name": "Tag User",
        "email": "tag_user@example.com",
        "password": "Password123!",
        "confirm_password": "Password123!"
    })

    # 2. Create Tag via Form POST
    create_tag_resp = await client.post("/tags", data={"name": "#Urgent"})
    assert create_tag_resp.status_code == 200
    assert "urgent" in create_tag_resp.text

    # Verify normalized (lowercase, no #) in DB
    result = await db_session.execute(select(Tag).where(Tag.name == "urgent"))
    tag = result.scalar_one_or_none()
    assert tag is not None
    tag_id = tag.id

    # 3. Empty tag name should fail (400)
    empty_resp = await client.post("/tags", data={"name": "   #  "})
    assert empty_resp.status_code == 400

    # 4. Duplicate tag creation should fail (400)
    dup_resp = await client.post("/tags", data={"name": "URGENT"})
    assert dup_resp.status_code == 400
    assert "already exists" in dup_resp.text

    # 5. Rename Tag (PUT /tags/{tag_id})
    rename_resp = await client.put(f"/tags/{tag_id}", data={"name": "critical"})
    assert rename_resp.status_code == 200
    assert "critical" in rename_resp.text

    await db_session.refresh(tag)
    assert tag.name == "critical"

    # 6. Delete Tag
    del_tag_resp = await client.delete(f"/tags/{tag_id}")
    assert del_tag_resp.status_code == 200

    deleted_tag = (await db_session.execute(select(Tag).where(Tag.id == tag_id))).scalar_one_or_none()
    assert deleted_tag is None


@pytest.mark.asyncio
async def test_note_category_and_tag_assignment(client: AsyncClient, db_session: AsyncSession):
    # 1. Sign up User
    await client.post("/auth/signup", data={
        "full_name": "Assign Tester",
        "email": "assign_tester@example.com",
        "password": "Password123!",
        "confirm_password": "Password123!"
    })

    # Create category and tag
    await client.post("/categories", data={"name": "Finance", "color": "#f59e0b"})
    cat = (await db_session.execute(select(Category).where(Category.name == "Finance"))).scalar_one()

    # Create note without category or tags
    await client.post("/notes", data={
        "title": "Tax Planning 2026",
        "content": "Quarterly estimates."
    }, follow_redirects=True)
    note = (await db_session.execute(select(Note).where(Note.title == "Tax Planning 2026"))).scalar_one()
    note_id = note.id
    assert note.category_id is None
    assert len(note.tags) == 0

    # 2. Inline Category Assignment: GET edit form
    cat_edit_resp = await client.get(f"/notes/{note_id}/category/edit")
    assert cat_edit_resp.status_code == 200
    assert "Finance" in cat_edit_resp.text

    # 3. Inline Category Assignment: PATCH category
    cat_assign_resp = await client.patch(f"/notes/{note_id}/category", data={"category_id": str(cat.id)})
    assert cat_assign_resp.status_code == 200
    assert "Finance" in cat_assign_resp.text

    await db_session.refresh(note)
    assert note.category_id == cat.id

    # 4. Inline Category Removal: DELETE category
    cat_remove_resp = await client.delete(f"/notes/{note_id}/category")
    assert cat_remove_resp.status_code == 200
    assert "None" in cat_remove_resp.text

    await db_session.refresh(note)
    assert note.category_id is None

    # 5. Inline Tag Assignment: GET tag selector
    tag_selector_resp = await client.get(f"/notes/{note_id}/tags/selector")
    assert tag_selector_resp.status_code == 200
    assert f'id="note-tags-{note_id}"' in tag_selector_resp.text

    # 6. Inline Tag Assignment: POST add tag by name
    add_tag_resp = await client.post(f"/notes/{note_id}/tags", data={"name": "taxes"})
    assert add_tag_resp.status_code == 200
    assert "#taxes" in add_tag_resp.text

    await db_session.refresh(note)
    assert len(note.tags) == 1
    assert note.tags[0].name == "taxes"
    tag_id = note.tags[0].id

    # 7. Add second tag by name
    await client.post(f"/notes/{note_id}/tags", data={"name": "2026"})
    await db_session.refresh(note)
    assert len(note.tags) == 2

    # 8. Adding duplicate tag should be idempotent
    await client.post(f"/notes/{note_id}/tags", data={"name": "taxes"})
    await db_session.refresh(note)
    assert len(note.tags) == 2

    # 9. Inline Tag Removal: DELETE tag from note
    remove_tag_resp = await client.delete(f"/notes/{note_id}/tags/{tag_id}")
    assert remove_tag_resp.status_code == 200
    assert "#taxes" not in remove_tag_resp.text

    await db_session.refresh(note)
    assert len(note.tags) == 1
    assert note.tags[0].name == "2026"


@pytest.mark.asyncio
async def test_dashboard_filtering_by_category_and_tag(client: AsyncClient, db_session: AsyncSession):
    # 1. Sign up User
    await client.post("/auth/signup", data={
        "full_name": "Filter User",
        "email": "filter_user@example.com",
        "password": "Password123!",
        "confirm_password": "Password123!"
    })

    # Create Categories: Personal, Work
    await client.post("/categories", data={"name": "Personal", "color": "#ec4899"})
    await client.post("/categories", data={"name": "Office", "color": "#3b82f6"})
    cat_personal = (await db_session.execute(select(Category).where(Category.name == "Personal"))).scalar_one()
    cat_office = (await db_session.execute(select(Category).where(Category.name == "Office"))).scalar_one()

    # Create Notes
    # Note 1: Personal + #health
    await client.post("/notes", data={
        "title": "Gym Workout Routine",
        "content": "Leg day Monday.",
        "category_id": str(cat_personal.id),
        "tags": "health, fitness"
    }, follow_redirects=True)

    # Note 2: Office + #deadline
    await client.post("/notes", data={
        "title": "Q3 Deliverable Review",
        "content": "Prepare slides.",
        "category_id": str(cat_office.id),
        "tags": "deadline, work"
    }, follow_redirects=True)

    # Note 3: Uncategorized + #ideas
    await client.post("/notes", data={
        "title": "Random Startup Idea",
        "content": "AI for plants.",
        "tags": "ideas"
    }, follow_redirects=True)

    # 2. Unfiltered dashboard shows all 3 notes
    dash_all = await client.get("/")
    assert dash_all.status_code == 200
    assert "Gym Workout Routine" in dash_all.text
    assert "Q3 Deliverable Review" in dash_all.text
    assert "Random Startup Idea" in dash_all.text

    # 3. Filter by Category: Personal
    dash_cat_personal = await client.get(f"/?category_id={cat_personal.id}")
    assert dash_cat_personal.status_code == 200
    assert "Gym Workout Routine" in dash_cat_personal.text
    assert "Q3 Deliverable Review" not in dash_cat_personal.text
    assert "Random Startup Idea" not in dash_cat_personal.text
    assert "Category: Personal" in dash_cat_personal.text

    # 4. Filter by Category: Office
    dash_cat_office = await client.get(f"/?category_id={cat_office.id}")
    assert dash_cat_office.status_code == 200
    assert "Q3 Deliverable Review" in dash_cat_office.text
    assert "Gym Workout Routine" not in dash_cat_office.text

    # 5. Filter by Tag: #deadline
    tag_deadline = (await db_session.execute(select(Tag).where(Tag.name == "deadline"))).scalar_one()
    dash_tag = await client.get(f"/?tag_id={tag_deadline.id}")
    assert dash_tag.status_code == 200
    assert "Q3 Deliverable Review" in dash_tag.text
    assert "Gym Workout Routine" not in dash_tag.text
    assert "Random Startup Idea" not in dash_tag.text
    assert "Tag: #deadline" in dash_tag.text


@pytest.mark.asyncio
async def test_cross_user_category_and_tag_authorization(client: AsyncClient, db_session: AsyncSession):
    # 1. Register Alice
    await client.post("/auth/signup", data={
        "full_name": "Alice Cross",
        "email": "alice_cross@example.com",
        "password": "Password123!",
        "confirm_password": "Password123!"
    })

    # Alice creates category "Confidential" and tag "classified"
    await client.post("/categories", data={"name": "Confidential", "color": "#ef4444"})
    alice_cat = (await db_session.execute(select(Category).where(Category.name == "Confidential"))).scalar_one()

    await client.post("/tags", data={"name": "classified"})
    alice_tag = (await db_session.execute(select(Tag).where(Tag.name == "classified"))).scalar_one()

    # Alice creates a note with category and tag
    await client.post("/notes", data={
        "title": "Alice Private Note",
        "content": "Secret information.",
        "category_id": str(alice_cat.id),
        "tags": "classified"
    }, follow_redirects=True)
    alice_note = (await db_session.execute(select(Note).where(Note.title == "Alice Private Note"))).scalar_one()

    # 2. Log out Alice and Register Bob
    await client.post("/auth/logout")

    await client.post("/auth/signup", data={
        "full_name": "Bob Attacker",
        "email": "bob_cross@example.com",
        "password": "Password123!",
        "confirm_password": "Password123!"
    })

    # Bob creates his own note
    await client.post("/notes", data={
        "title": "Bob Normal Note",
        "content": "Regular stuff."
    }, follow_redirects=True)
    bob_note = (await db_session.execute(select(Note).where(Note.title == "Bob Normal Note"))).scalar_one()

    # --- CROSS-USER ATTACKS AND VERIFICATIONS ---

    # Attack 1: Bob cannot edit Alice's category (GET edit modal) -> 404
    assert (await client.get(f"/categories/{alice_cat.id}/edit-modal")).status_code == 404

    # Attack 2: Bob cannot update Alice's category -> 404
    assert (await client.put(f"/categories/{alice_cat.id}", data={"name": "Hacked"})).status_code == 404

    # Attack 3: Bob cannot delete Alice's category -> 404
    assert (await client.delete(f"/categories/{alice_cat.id}")).status_code == 404

    # Attack 4: Bob cannot edit Alice's tag (GET edit modal) -> 404
    assert (await client.get(f"/tags/{alice_tag.id}/edit-modal")).status_code == 404

    # Attack 5: Bob cannot rename Alice's tag -> 404
    assert (await client.put(f"/tags/{alice_tag.id}", data={"name": "hacked"})).status_code == 404

    # Attack 6: Bob cannot delete Alice's tag -> 404
    assert (await client.delete(f"/tags/{alice_tag.id}")).status_code == 404

    # Attack 7: Bob cannot assign Alice's category to Bob's note -> 400 or 404 (Not Found for Bob)
    assign_alice_cat = await client.patch(f"/notes/{bob_note.id}/category", data={"category_id": str(alice_cat.id)})
    assert assign_alice_cat.status_code in (400, 403, 404)

    # Attack 8: Bob cannot assign Alice's tag (by tag_id) to Bob's note -> 400 or 404 (Not Found for Bob)
    assign_alice_tag = await client.post(f"/notes/{bob_note.id}/tags", data={"tag_id": str(alice_tag.id)})
    assert assign_alice_tag.status_code in (400, 403, 404)

    # Attack 9: Bob cannot assign/remove category or tag on Alice's note -> 404
    assert (await client.patch(f"/notes/{alice_note.id}/category", data={"category_id": "1"})).status_code == 404
    assert (await client.delete(f"/notes/{alice_note.id}/category")).status_code == 404
    assert (await client.post(f"/notes/{alice_note.id}/tags", data={"name": "hack"})).status_code == 404
    assert (await client.delete(f"/notes/{alice_note.id}/tags/{alice_tag.id}")).status_code == 404

    # Attack 10: Bob filtering by Alice's category or tag ID sees NO notes
    dash_filter_cat = await client.get(f"/?category_id={alice_cat.id}")
    assert dash_filter_cat.status_code == 200
    assert "Alice Private Note" not in dash_filter_cat.text

    dash_filter_tag = await client.get(f"/?tag_id={alice_tag.id}")
    assert dash_filter_tag.status_code == 200
    assert "Alice Private Note" not in dash_filter_tag.text

    # Non-collision: Bob CAN create a category named "Confidential" independently
    bob_cat_resp = await client.post("/categories", data={"name": "Confidential", "color": "#000000"})
    assert bob_cat_resp.status_code == 200
    bob_cat = (await db_session.execute(select(Category).where(Category.name == "Confidential", Category.user_id == bob_note.user_id))).scalar_one_or_none()
    assert bob_cat is not None
    assert bob_cat.id != alice_cat.id


@pytest.mark.asyncio
async def test_create_and_edit_note_with_category_and_tags(client: AsyncClient, db_session: AsyncSession):
    # Register user
    await client.post("/auth/signup", data={
        "full_name": "Full Form User",
        "email": "full_form@example.com",
        "password": "Password123!",
        "confirm_password": "Password123!"
    })

    # Create category
    await client.post("/categories", data={"name": "Travel", "color": "#06b6d4"})
    cat = (await db_session.execute(select(Category).where(Category.name == "Travel"))).scalar_one()

    # GET Create note page -> verify category is in options
    new_page_resp = await client.get(f"/notes/new?category_id={cat.id}")
    assert new_page_resp.status_code == 200
    assert "Travel" in new_page_resp.text

    # POST Create note with category and comma-separated tags
    create_resp = await client.post("/notes", data={
        "title": "Summer Trip to Tokyo",
        "content": "Flight tickets and hotel reservations.",
        "category_id": str(cat.id),
        "tags": "vacation, japan, travel"
    }, follow_redirects=True)
    assert create_resp.status_code == 200
    assert "Summer Trip to Tokyo" in create_resp.text
    assert "Travel" in create_resp.text
    assert "#vacation" in create_resp.text
    assert "#japan" in create_resp.text

    # Verify DB
    note = (await db_session.execute(select(Note).where(Note.title == "Summer Trip to Tokyo"))).scalar_one()
    assert note.category_id == cat.id
    assert len(note.tags) == 3
    tag_names = [t.name for t in note.tags]
    assert "vacation" in tag_names
    assert "japan" in tag_names
    assert "travel" in tag_names

    # GET Edit note page -> verify current category selected and tags present
    edit_page_resp = await client.get(f"/notes/{note.id}/edit")
    assert edit_page_resp.status_code == 200
    assert "Travel" in edit_page_resp.text
    assert "vacation" in edit_page_resp.text

    # POST Edit note: update title, change tags, clear category
    edit_resp = await client.post(f"/notes/{note.id}/edit", data={
        "title": "Summer Trip to Tokyo (Updated)",
        "content": "Updated itinerary.",
        "category_id": "",
        "tags": "asia, adventure"
    }, follow_redirects=True)
    assert edit_resp.status_code == 200

    await db_session.refresh(note)
    assert note.title == "Summer Trip to Tokyo (Updated)"
    assert note.category_id is None
    new_tag_names = [t.name for t in note.tags]
    assert "asia" in new_tag_names
    assert "adventure" in new_tag_names
    assert "vacation" not in new_tag_names
