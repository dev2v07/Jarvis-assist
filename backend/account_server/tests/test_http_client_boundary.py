from __future__ import annotations

import os
import unittest

from account.application.auth_client import HttpAuthProvider


class MemoryCredentials:
    def __init__(self) -> None:
        self.access = None
        self.refresh = None

    def read_access_token(self):
        return self.access

    def read_refresh_token(self):
        return self.refresh

    def write_tokens(self, access_token, refresh_token):
        self.access, self.refresh = access_token, refresh_token

    def clear(self):
        self.access = self.refresh = None


@unittest.skipUnless(os.getenv("ACCOUNT_API_TEST_URL"), "requires running local Account API")
class HttpAuthBoundaryTests(unittest.TestCase):
    def test_invalid_credentials_are_translated_without_token_storage(self) -> None:
        credentials = MemoryCredentials()
        provider = HttpAuthProvider(os.environ["ACCOUNT_API_TEST_URL"], credentials)
        result = provider.login("managment2v@gmail.com", "deliberately-invalid-password")
        self.assertFalse(result.ok)
        self.assertEqual(result.error.code, "invalid_credentials")
        self.assertIsNone(credentials.access)
        self.assertIsNone(credentials.refresh)


if __name__ == "__main__":
    unittest.main()

