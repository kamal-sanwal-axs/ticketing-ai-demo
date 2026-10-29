from __future__ import annotations

import unittest

from apex_rag_demo.user_display import build_list_users_display, users_directory_rows


class UsersDirectoryTests(unittest.TestCase):
    def test_users_table_from_resources_payload(self) -> None:
        payload = {
            "usersDirectory": {
                "users": [
                    {
                        "id": 1,
                        "email": "a@example.com",
                        "firstName": "Ann",
                        "lastName": "Lee",
                        "userType": "B2B",
                        "isDisabled": False,
                    },
                ],
                "totalCount": 1,
            },
            "me": {"adminUserId": "1"},
        }
        rows = users_directory_rows(payload["usersDirectory"])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["email"], "a@example.com")
        view = build_list_users_display(payload)
        self.assertEqual(view["user_count"], 1)
        self.assertTrue(any(s.get("title", "").startswith("Users") for s in view["sections"]))


if __name__ == "__main__":
    unittest.main()
