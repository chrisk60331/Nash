import unittest

import pyotp

from api.middleware.jwt_auth import create_mfa_temp_token, decode_mfa_temp_token
from api.services.mfa_service import (
    generate_totp_secret,
    generate_backup_codes,
    hash_backup_codes,
    mfa_requirement_for_user,
    validate_backup_code,
    verify_totp,
)


class MfaServiceTests(unittest.TestCase):
    def test_totp_round_trip(self):
        secret = generate_totp_secret()
        token = pyotp.TOTP(secret).now()

        self.assertTrue(verify_totp(secret, token))

    def test_backup_code_is_single_use(self):
        [code] = generate_backup_codes(count=1)
        hashed_codes = [record.model_dump(mode="json") for record in hash_backup_codes([code])]

        first_attempt = validate_backup_code(hashed_codes, code)
        self.assertTrue(first_attempt.valid)
        self.assertTrue(first_attempt.records[0].used)
        self.assertIsNotNone(first_attempt.records[0].usedAt)

        second_attempt = validate_backup_code(
            [record.model_dump(mode="json") for record in first_attempt.records],
            code,
        )
        self.assertFalse(second_attempt.valid)

    def test_mfa_requirement_policy(self):
        self.assertEqual(mfa_requirement_for_user("ADMIN", False), "required")
        self.assertEqual(mfa_requirement_for_user("USER", True), "required")
        self.assertEqual(mfa_requirement_for_user("USER", False), "optional")

    def test_mfa_temp_token_round_trip(self):
        token = create_mfa_temp_token("user@example.com", purpose="enroll")
        payload = decode_mfa_temp_token(token)

        self.assertEqual(payload["sub"], "user@example.com")
        self.assertEqual(payload["purpose"], "enroll")
        self.assertEqual(payload["type"], "mfa_temp")


if __name__ == "__main__":
    unittest.main()
