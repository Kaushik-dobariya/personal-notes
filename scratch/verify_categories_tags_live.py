import asyncio
import time
import httpx


async def run_live_tests():
    base_url = "http://127.0.0.1:8000"
    print(f"Connecting to live server at {base_url}...")

    async with httpx.AsyncClient(base_url=base_url, follow_redirects=False) as client:
        ts = int(time.time())
        email_alice = f"alice_live_{ts}@example.com"
        email_bob = f"bob_live_{ts}@example.com"

        # 1. Sign up Alice
        print("1. Signing up Alice...")
        r_signup = await client.post("/auth/signup", data={
            "full_name": "Alice Live",
            "email": email_alice,
            "password": "Password123!",
            "confirm_password": "Password123!"
        })
        assert r_signup.status_code == 303
        alice_cookie = r_signup.cookies.get("personal_notes_session")
        assert alice_cookie is not None
        client.cookies.set("personal_notes_session", alice_cookie)
        print("   Alice authenticated successfully.")

        # 2. Alice creates Category "Work"
        print("2. Alice creating category 'Work'...")
        r_cat = await client.post("/categories", data={"name": "Work", "color": "#3b82f6"}, headers={"HX-Request": "true"})
        assert r_cat.status_code == 200
        assert "Work" in r_cat.text
        import re
        cat_match = re.search(r'id="sidebar-category-(\d+)"', r_cat.text)
        assert cat_match is not None
        alice_cat_id = int(cat_match.group(1))
        print(f"   Category 'Work' created with ID: {alice_cat_id}")

        # 3. Duplicate category creation for Alice returns 400
        print("3. Testing duplicate category error handling...")
        r_cat_dup = await client.post("/categories", data={"name": "Work", "color": "#ef4444"}, headers={"HX-Request": "true"})
        assert r_cat_dup.status_code == 400
        print("   Duplicate category rejected as expected (400).")

        # 4. Alice creates Tag "urgent"
        print("4. Alice creating tag '#Urgent'...")
        r_tag = await client.post("/tags", data={"name": "#Urgent"}, headers={"HX-Request": "true"})
        assert r_tag.status_code == 200
        assert "urgent" in r_tag.text
        tag_match = re.search(r'id="sidebar-tag-(\d+)"', r_tag.text)
        assert tag_match is not None
        alice_tag_id = int(tag_match.group(1))
        print(f"   Tag '#urgent' created with ID: {alice_tag_id}")

        # 5. Alice creates Note with Category & Tags
        print("5. Alice creating Note with Category and Tags...")
        r_note = await client.post("/notes", data={
            "title": "Quarterly Objectives",
            "content": "Deliver milestone on schedule.",
            "category_id": str(alice_cat_id),
            "tags": "urgent, planning"
        }, follow_redirects=True)
        assert r_note.status_code == 200
        assert "Quarterly Objectives" in r_note.text
        assert "Work" in r_note.text
        assert "#urgent" in r_note.text
        note_match = re.search(r'Note ID: #(\d+)', r_note.text)
        assert note_match is not None
        alice_note_id = int(note_match.group(1))
        print(f"   Note created with ID: {alice_note_id}")

        # 6. Test inline Category Change
        print("6. Testing inline category change...")
        # Create second category "Personal"
        r_cat2 = await client.post("/categories", data={"name": "Personal", "color": "#ec4899"}, headers={"HX-Request": "true"})
        cat2_id = int(re.search(r'id="sidebar-category-(\d+)"', r_cat2.text).group(1))

        r_change_cat = await client.patch(f"/notes/{alice_note_id}/category", data={"category_id": str(cat2_id)}, headers={"HX-Request": "true"})
        assert r_change_cat.status_code == 200
        assert "Personal" in r_change_cat.text
        print("   Category changed to Personal.")

        # 7. Test inline Tag Add
        print("7. Testing inline tag addition...")
        r_add_tag = await client.post(f"/notes/{alice_note_id}/tags", data={"name": "strategy"}, headers={"HX-Request": "true"})
        assert r_add_tag.status_code == 200
        assert "#strategy" in r_add_tag.text
        print("   Tag #strategy added to note.")

        # 8. Test Dashboard Filtering by Category
        print("8. Testing Dashboard filtering by Category...")
        r_dash_cat = await client.get(f"/?category_id={cat2_id}")
        assert r_dash_cat.status_code == 200
        assert "Quarterly Objectives" in r_dash_cat.text
        assert "Category: Personal" in r_dash_cat.text

        # 9. Test Dashboard Filtering by Tag
        print("9. Testing Dashboard filtering by Tag...")
        r_dash_tag = await client.get(f"/?tag_id={alice_tag_id}")
        assert r_dash_tag.status_code == 200
        assert "Quarterly Objectives" in r_dash_tag.text
        assert "Tag: #urgent" in r_dash_tag.text

        # 10. Test Cross-User Isolation with Bob
        print("10. Testing cross-user isolation with Bob...")
        client.cookies.clear()
        r_bob_signup = await client.post("/auth/signup", data={
            "full_name": "Bob Live",
            "email": email_bob,
            "password": "Password123!",
            "confirm_password": "Password123!"
        })
        assert r_bob_signup.status_code == 303
        bob_cookie = r_bob_signup.cookies.get("personal_notes_session")
        client.cookies.set("personal_notes_session", bob_cookie)

        # Bob cannot see Alice's category in edit modal
        r_bob_cat_attack = await client.get(f"/categories/{alice_cat_id}/edit-modal")
        assert r_bob_cat_attack.status_code == 404

        # Bob cannot delete Alice's category
        r_bob_del_attack = await client.delete(f"/categories/{alice_cat_id}")
        assert r_bob_del_attack.status_code == 404

        # Bob cannot access Alice's note category
        r_bob_note_attack = await client.patch(f"/notes/{alice_note_id}/category", data={"category_id": "1"})
        assert r_bob_note_attack.status_code == 404

        # Bob cannot see Alice's note when filtering by Alice's category
        r_bob_dash_filter = await client.get(f"/?category_id={alice_cat_id}")
        assert r_bob_dash_filter.status_code == 200
        assert "Quarterly Objectives" not in r_bob_dash_filter.text
        print("   Cross-user authorization fully enforced.")

        # 11. Log back in as Alice and delete category -> note preserved
        print("11. Testing Category deletion note preservation...")
        client.cookies.set("personal_notes_session", alice_cookie)
        r_del_cat = await client.delete(f"/categories/{cat2_id}", headers={"HX-Request": "true"})
        assert r_del_cat.status_code == 200

        r_note_view = await client.get(f"/notes/{alice_note_id}")
        assert r_note_view.status_code == 200
        assert "Quarterly Objectives" in r_note_view.text
        print("   Note preserved after category deletion.")

        print("\n=== ALL LIVE END-TO-END VERIFICATION CHECKS PASSED SUCCESSFULLY! ===")


if __name__ == "__main__":
    asyncio.run(run_live_tests())
