import asyncio
import httpx


async def verify_live_server():
    base_url = "http://127.0.0.1:8000"
    print(f"Connecting to live server at {base_url}...")

    async with httpx.AsyncClient(base_url=base_url, follow_redirects=False) as client:
        # 1. Unauthenticated request to / should redirect to /auth/login
        r1 = await client.get("/")
        print(f"1. GET / -> Status: {r1.status_code} (Redirected to: {r1.headers.get('location')})")
        assert r1.status_code == 303
        assert r1.headers.get("location") == "/auth/login"

        # 2. View login page
        r2 = await client.get("/auth/login")
        print(f"2. GET /auth/login -> Status: {r2.status_code}, Length: {len(r2.text)}")
        assert r2.status_code == 200
        assert "Personal Notes" in r2.text
        assert "Welcome Back" in r2.text

        # 3. User Signup
        import time
        email = f"demolive_{int(time.time())}@example.com"
        signup_payload = {
            "full_name": "Demo Live User",
            "email": email,
            "password": "StrongPassword123!",
            "confirm_password": "StrongPassword123!"
        }
        r3 = await client.post("/auth/signup", data=signup_payload)
        print(f"3. POST /auth/signup -> Status: {r3.status_code}")
        assert r3.status_code == 303
        cookie = r3.cookies.get("personal_notes_session")
        assert cookie is not None
        print(f"   Session cookie established: {cookie[:20]}...")

        # 4. Access Dashboard with Session Cookie
        client.cookies.set("personal_notes_session", cookie)
        r4 = await client.get("/")
        print(f"4. GET / (Authenticated) -> Status: {r4.status_code}, Length: {len(r4.text)}")
        assert r4.status_code == 200
        assert "Demo" in r4.text
        assert "Total Notes" in r4.text
        assert "sidebar-menu" in r4.text

        # 5. Create a Category via HTMX
        import re
        cat_payload = {"name": f"Eng_{int(time.time())}", "color": "#0ea5e9"}
        r5 = await client.post("/categories", data=cat_payload, headers={"HX-Request": "true"})
        print(f"5. POST /categories (HTMX) -> Status: {r5.status_code}")
        assert r5.status_code == 200

        cat_match = re.search(r'id="sidebar-category-(\d+)"', r5.text)
        cat_id = cat_match.group(1) if cat_match else None
        print(f"   Created Category ID: {cat_id}")

        # 6. Create a Note via HTMX Modal Submission
        note_payload = {
            "title": "FastAPI + HTMX Mastery",
            "content": "Building interactive single-page applications without heavy JavaScript.",
            "category_id": str(cat_id) if cat_id else "",
            "tag_names": "fastapi, python, architecture",
            "is_pinned": "true",
            "is_favorite": "true"
        }
        r6 = await client.post("/notes", data=note_payload, headers={"HX-Request": "true"})
        print(f"6. POST /notes (HTMX) -> Status: {r6.status_code}")
        assert r6.status_code == 200
        assert "FastAPI + HTMX Mastery" in r6.text
        assert "#fastapi" in r6.text

        # Extract note ID
        import re
        match = re.search(r'id="note-card-(\d+)"', r6.text)
        assert match is not None
        note_id = int(match.group(1))
        print(f"   Created Note ID: {note_id}")

        # 7. Test Inline Title Edit Form
        r7 = await client.get(f"/notes/{note_id}/title/edit", headers={"HX-Request": "true"})
        print(f"7. GET /notes/{note_id}/title/edit -> Status: {r7.status_code}")
        assert r7.status_code == 200
        assert 'name="title"' in r7.text

        # 8. Save Inline Title Edit
        r8 = await client.put(f"/notes/{note_id}/title", data={"title": "FastAPI + HTMX Mastery [Updated]"}, headers={"HX-Request": "true"})
        print(f"8. PUT /notes/{note_id}/title -> Status: {r8.status_code}")
        assert r8.status_code == 200
        assert "FastAPI + HTMX Mastery [Updated]" in r8.text

        # 9. Test Inline Content Append
        r9 = await client.post(f"/notes/{note_id}/append", data={"text": "Appended insight: OOB swaps are amazing."}, headers={"HX-Request": "true"})
        print(f"9. POST /notes/{note_id}/append -> Status: {r9.status_code}")
        assert r9.status_code == 200
        assert "Appended insight: OOB swaps are amazing." in r9.text

        # 10. Test Quick Toggles (Pin, Favorite, Archive)
        r10_fav = await client.patch(f"/notes/{note_id}/toggle-favorite", headers={"HX-Request": "true"})
        assert r10_fav.status_code == 200
        print(f"10. PATCH /notes/{note_id}/toggle-favorite -> Status: {r10_fav.status_code}")

        # 11. Test Live Search
        r11_search = await client.get("/notes/search?q=insight", headers={"HX-Request": "true"})
        print(f"11. GET /notes/search?q=insight -> Status: {r11_search.status_code}")
        assert r11_search.status_code == 200
        assert "FastAPI + HTMX Mastery [Updated]" in r11_search.text

        # 12. Test Soft Delete (Move to Trash)
        r12_del = await client.delete(f"/notes/{note_id}", headers={"HX-Request": "true"})
        print(f"12. DELETE /notes/{note_id} -> Status: {r12_del.status_code}")
        assert r12_del.status_code == 200

        # 13. Verify Trash View
        r13_trash = await client.get("/notes/search?status=trash", headers={"HX-Request": "true"})
        print(f"13. GET /notes/search?status=trash -> Status: {r13_trash.status_code}")
        assert r13_trash.status_code == 200
        assert "FastAPI + HTMX Mastery [Updated]" in r13_trash.text
        assert "Restore" in r13_trash.text

        # 14. Restore from Trash
        r14_restore = await client.patch(f"/notes/{note_id}/restore", headers={"HX-Request": "true"})
        print(f"14. PATCH /notes/{note_id}/restore -> Status: {r14_restore.status_code}")
        assert r14_restore.status_code == 200

        # 15. Check Active Notes again
        r15_active = await client.get("/notes/search?status=active", headers={"HX-Request": "true"})
        print(f"15. GET /notes/search?status=active -> Status: {r15_active.status_code}")
        assert r15_active.status_code == 200
        assert "FastAPI + HTMX Mastery [Updated]" in r15_active.text

        print("\n=== ALL 15 LIVE END-TO-END VERIFICATION CHECKS PASSED SUCCESSFULLY! ===")


if __name__ == "__main__":
    asyncio.run(verify_live_server())
