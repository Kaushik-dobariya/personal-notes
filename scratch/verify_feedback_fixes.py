import asyncio
import httpx


async def test_live_fixes():
    base_url = "http://127.0.0.1:8000"
    client = httpx.AsyncClient(base_url=base_url)

    print("\n--- 1. Signing up user for live feedback verification ---")
    signup_data = {
        "full_name": "Feedback Tester",
        "email": "feedback_tester@example.com",
        "password": "Password123!",
        "confirm_password": "Password123!"
    }
    signup_resp = await client.post("/auth/signup", data=signup_data)
    print(f"Signup status: {signup_resp.status_code}")

    print("\n--- 2. Testing Category Modal: Save & Close ---")
    save_cat_resp = await client.post("/categories", data={"name": "Research", "color": "#8b5cf6"})
    print(f"Create Category status: {save_cat_resp.status_code}")
    print(f"HX-Trigger header: {save_cat_resp.headers.get('HX-Trigger')}")
    assert save_cat_resp.status_code == 200, "Category save should return 200"
    assert save_cat_resp.headers.get("HX-Trigger") == "closeModal", "Should include HX-Trigger: closeModal"
    assert 'id="sidebar-categories-list" hx-swap-oob="innerHTML"' in save_cat_resp.text, "Should contain OOB swap for sidebar"
    assert "Research" in save_cat_resp.text, "Sidebar should contain new category name"
    print("SUCCESS: Category modal closes and updates sidebar on save.")

    print("\n--- 3. Testing Category Modal: Duplicate Error Message ---")
    dup_cat_resp = await client.post("/categories", data={"name": "Research", "color": "#ef4444"})
    print(f"Duplicate Category status: {dup_cat_resp.status_code}")
    assert dup_cat_resp.status_code == 400, "Duplicate category should return 400"
    assert "alert alert-danger" in dup_cat_resp.text, "Modal should display danger alert"
    assert "already exists" in dup_cat_resp.text, "Modal should display 'already exists' message"
    assert 'value="Research"' in dup_cat_resp.text, "Modal should retain user input value"
    print("SUCCESS: Category modal properly renders error banner without corrupted sidebar.")

    print("\n--- 4. Testing Tag Modal: Save & Close ---")
    save_tag_resp = await client.post("/tags", data={"name": "ai-models"})
    print(f"Create Tag status: {save_tag_resp.status_code}")
    print(f"HX-Trigger header: {save_tag_resp.headers.get('HX-Trigger')}")
    assert save_tag_resp.status_code == 200, "Tag save should return 200"
    assert save_tag_resp.headers.get("HX-Trigger") == "closeModal", "Should include HX-Trigger: closeModal"
    assert 'id="sidebar-tags-list" hx-swap-oob="innerHTML"' in save_tag_resp.text, "Should contain OOB swap for sidebar"
    assert "ai-models" in save_tag_resp.text, "Sidebar should contain new tag name"
    print("SUCCESS: Tag modal closes and updates sidebar on save.")

    print("\n--- 5. Testing Tag Modal: Duplicate Error Message ---")
    dup_tag_resp = await client.post("/tags", data={"name": "AI-MODELS"})
    print(f"Duplicate Tag status: {dup_tag_resp.status_code}")
    assert dup_tag_resp.status_code == 400, "Duplicate tag should return 400"
    assert "alert alert-danger" in dup_tag_resp.text, "Modal should display danger alert"
    assert "already exists" in dup_tag_resp.text, "Modal should display 'already exists' message"
    print("SUCCESS: Tag modal properly renders error banner without corrupted sidebar.")

    print("\n--- 6. Creating a note to test tag selector and real-time sidebar sync ---")
    note_resp = await client.post("/notes", data={
        "title": "LLM Architecture Notes",
        "content": "Deep dive into attention mechanisms."
    }, follow_redirects=False)
    print(f"Note creation status: {note_resp.status_code}")

    # Get Dashboard to find Note ID
    dash_resp = await client.get("/")
    assert "LLM Architecture Notes" in dash_resp.text
    import re
    note_id_match = re.search(r'id="note-card-(\d+)"', dash_resp.text)
    assert note_id_match is not None, "Note card ID should be found on dashboard"
    note_id = int(note_id_match.group(1))
    print(f"Found Note ID: {note_id}")

    print("\n--- 7. Testing Tag Selector: Existing Selectable Tags ---")
    selector_resp = await client.get(f"/notes/{note_id}/tags/selector")
    assert selector_resp.status_code == 200
    assert "Select existing tag:" in selector_resp.text, "Selector should have 'Select existing tag:' section"
    assert "#ai-models" in selector_resp.text, "Existing tag #ai-models should be shown as selectable chip"
    print("SUCCESS: Tag selector displays existing tags for user selection.")

    print("\n--- 8. Testing Selecting Existing Tag from Chip ---")
    # Fetch tag id for ai-models from sidebar
    tags_resp = await client.get("/tags", headers={"Accept": "application/json"})
    all_tags = tags_resp.json()
    ai_tag = next((t for t in all_tags if t["name"] == "ai-models"), None)
    assert ai_tag is not None

    add_exist_resp = await client.post(f"/notes/{note_id}/tags", data={"tag_id": str(ai_tag["id"])})
    assert add_exist_resp.status_code == 200
    assert "#ai-models" in add_exist_resp.text
    assert 'id="sidebar-tags-list" hx-swap-oob="innerHTML"' in add_exist_resp.text
    print("SUCCESS: Existing tag selected, attached to note, and sidebar updated in real time.")

    print("\n--- 9. Testing Adding Brand New Tag from Note Card Input ---")
    add_new_resp = await client.post(f"/notes/{note_id}/tags", data={"name": "transformer"})
    assert add_new_resp.status_code == 200
    assert "#transformer" in add_new_resp.text, "Note should now show #transformer tag"
    assert 'id="sidebar-tags-list" hx-swap-oob="innerHTML"' in add_new_resp.text, "Response must include OOB sidebar tags update"
    assert "transformer" in add_new_resp.text, "Sidebar OOB update must contain newly added tag"
    print("SUCCESS: Adding new tag from note card updates the left sidebar in real time!")

    await client.aclose()
    print("\n=== ALL LIVE VERIFICATIONS PASSED SUCCESSFULLY! ===")


if __name__ == "__main__":
    asyncio.run(test_live_fixes())
