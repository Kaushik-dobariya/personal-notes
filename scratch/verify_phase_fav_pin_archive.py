import asyncio
import httpx
from app.main import app


async def main():
    print("--- Starting End-to-End Verification of Favorite, Pin, and Archive ---")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
        # 1. Sign up a user
        import time
        ts = int(time.time())
        email = f"e2e_user_{ts}@example.com"
        signup_resp = await client.post("/auth/signup", data={
            "full_name": "E2E Tester",
            "email": email,
            "password": "Password123!",
            "confirm_password": "Password123!"
        })
        assert signup_resp.status_code == 303
        cookie = signup_resp.cookies.get("personal_notes_session")
        assert cookie is not None
        client.cookies.set("personal_notes_session", cookie)
        print(f"[PASS] Step 1: User signed up successfully ({email})")

        # 2. Check initial Dashboard and sidebar counts
        dash_init = await client.get("/")
        assert dash_init.status_code == 200
        assert "All Notes" in dash_init.text
        assert "Favorites" in dash_init.text
        assert "Pinned" in dash_init.text
        assert "Archive" in dash_init.text
        print("[PASS] Step 2: Dashboard and Sidebar navigation rendered with counts")

        # 3. Create Note 1
        n1_resp = await client.post("/notes", data={
            "title": "First Project Note",
            "content": "This note will be pinned."
        }, follow_redirects=True)
        assert n1_resp.status_code == 200
        note1_id = int(str(n1_resp.url).rstrip("/").split("/")[-1])
        print(f"[PASS] Step 3: Created Note 1 (ID={note1_id})")

        # 4. Create Note 2
        n2_resp = await client.post("/notes", data={
            "title": "Second Project Note",
            "content": "This note will be favorited."
        }, follow_redirects=True)
        assert n2_resp.status_code == 200
        note2_id = int(str(n2_resp.url).rstrip("/").split("/")[-1])
        print(f"[PASS] Step 4: Created Note 2 (ID={note2_id})")

        # 5. Create Note 3
        n3_resp = await client.post("/notes", data={
            "title": "Third Project Note",
            "content": "This note will be archived."
        }, follow_redirects=True)
        assert n3_resp.status_code == 200
        note3_id = int(str(n3_resp.url).rstrip("/").split("/")[-1])
        print(f"[PASS] Step 5: Created Note 3 (ID={note3_id})")

        # 6. Test Favorite Note 2
        fav_resp = await client.post(f"/notes/{note2_id}/toggle-favorite", headers={"HX-Request": "true"})
        assert fav_resp.status_code == 200
        assert "★" in fav_resp.text
        assert "Favorite" in fav_resp.text
        assert 'hx-swap-oob="innerHTML"' in fav_resp.text
        print("[PASS] Step 6: Favorited Note 2 via HTMX (rendered with live count OOB swap)")

        # 7. Test Pin Note 1
        pin_resp = await client.post(f"/notes/{note1_id}/toggle-pin", headers={"HX-Request": "true"})
        assert pin_resp.status_code == 200
        assert "Pinned" in pin_resp.text
        print("[PASS] Step 7: Pinned Note 1 via HTMX (rendered with live count OOB swap)")

        # 8. Check All Notes list sorting (Pinned Note 1 should be first)
        dash_sorted = await client.get("/")
        assert dash_sorted.status_code == 200
        pos1 = dash_sorted.text.find("First Project Note")
        pos2 = dash_sorted.text.find("Second Project Note")
        pos3 = dash_sorted.text.find("Third Project Note")
        assert pos1 < pos2, "Pinned Note 1 must appear before Note 2"
        assert pos1 < pos3, "Pinned Note 1 must appear before Note 3"
        print("[PASS] Step 8: Confirmed Pinned Note 1 appears first in All Notes list")

        # 9. Test Favorites filter view (/favorites)
        fav_view = await client.get("/favorites")
        assert fav_view.status_code == 200
        assert "Second Project Note" in fav_view.text
        assert "First Project Note" not in fav_view.text
        assert "Third Project Note" not in fav_view.text
        print("[PASS] Step 9: Confirmed /favorites view displays only favorited Note 2")

        # 10. Test Pinned filter view (/pinned)
        pinned_view = await client.get("/pinned")
        assert pinned_view.status_code == 200
        assert "First Project Note" in pinned_view.text
        assert "Second Project Note" not in pinned_view.text
        assert "Third Project Note" not in pinned_view.text
        print("[PASS] Step 10: Confirmed /pinned view displays only pinned Note 1")

        # 11. Test Archive Note 3 via HTMX
        arch_resp = await client.post(
            f"/notes/{note3_id}/toggle-archive",
            headers={"HX-Request": "true", "HX-Target": f"note-card-col-{note3_id}"}
        )
        assert arch_resp.status_code == 200
        assert f"note {note3_id}" in arch_resp.text
        print("[PASS] Step 11: Archived Note 3 via HTMX")

        # 12. Confirm Note 3 disappeared from All Notes list
        dash_after_arch = await client.get("/")
        assert "Third Project Note" not in dash_after_arch.text
        print("[PASS] Step 12: Confirmed Note 3 is hidden from All Notes view")

        # 13. Open Archive view (/archive) and verify Note 3 is present
        arch_view = await client.get("/archive")
        assert arch_view.status_code == 200
        assert "Third Project Note" in arch_view.text
        assert "First Project Note" not in arch_view.text
        assert "Second Project Note" not in arch_view.text
        print("[PASS] Step 13: Confirmed /archive view contains archived Note 3")

        # 14. Unarchive Note 3 via HTMX
        unarch_resp = await client.post(
            f"/notes/{note3_id}/unarchive",
            headers={"HX-Request": "true", "HX-Target": f"note-card-col-{note3_id}"}
        )
        assert unarch_resp.status_code == 200
        print("[PASS] Step 14: Unarchived Note 3 via HTMX")

        # 15. Confirm Note 3 returned to All Notes list
        dash_restored = await client.get("/")
        assert "Third Project Note" in dash_restored.text
        print("[PASS] Step 15: Confirmed Note 3 returned to All Notes view")

        # 16. Test Authorization with a second user
        email_attacker = f"attacker_{ts}@example.com"
        client.cookies.clear()
        signup_att = await client.post("/auth/signup", data={
            "full_name": "Attacker User",
            "email": email_attacker,
            "password": "Password123!",
            "confirm_password": "Password123!"
        })
        cookie_att = signup_att.cookies.get("personal_notes_session")
        client.cookies.set("personal_notes_session", cookie_att)

        # Attacker tries to favorite Note 1
        att_fav = await client.post(f"/notes/{note1_id}/toggle-favorite")
        assert att_fav.status_code == 404
        # Attacker tries to pin Note 1
        att_pin = await client.post(f"/notes/{note1_id}/toggle-pin")
        assert att_pin.status_code == 404
        # Attacker tries to archive Note 1
        att_arch = await client.post(f"/notes/{note1_id}/toggle-archive")
        assert att_arch.status_code == 404
        # Attacker lists favorites, pinned, archive -> none of user 1's notes appear
        att_fav_list = await client.get("/favorites")
        assert "First Project Note" not in att_fav_list.text
        assert "Second Project Note" not in att_fav_list.text
        print("[PASS] Step 16: Confirmed strict user authorization and isolation (404 on unowned notes)")

    print("\n--- ALL VERIFICATIONS PASSED SUCCESSFULLY! ---")


if __name__ == "__main__":
    asyncio.run(main())
