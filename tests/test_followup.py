"""
Follow-up tests for three backend issues:
  1. LoginThrottle — 5 attempts per 15-minute window
  2. Argon2 production configuration
  3. StudentPayment deterministic ordering
"""
from __future__ import annotations

import time
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone


# ---------------------------------------------------------------------------
# 1. LoginThrottle — 5 / 15-minute window
# ---------------------------------------------------------------------------

class LoginThrottleTests(TestCase):
    """
    Tests the custom LoginThrottle class directly (no HTTP stack needed).
    Each test injects a unique fake IP to keep history isolated.
    """

    def _make_throttle(self):
        from apps.accounts.views import LoginThrottle
        return LoginThrottle()

    def _fake_request(self, ip: str):
        """Minimal request-like object compatible with DRF's get_ident()."""
        class _R:
            META = {"REMOTE_ADDR": ip}
            headers: dict = {}  # DRF get_ident reads headers.get('x-forwarded-for')
        r = _R()
        r.META = {"REMOTE_ADDR": ip}
        return r

    def test_five_attempts_are_allowed(self):
        t = self._make_throttle()
        req = self._fake_request("10.1.1.1")
        for i in range(5):
            self.assertTrue(t.allow_request(req, None), f"Attempt {i + 1} should be allowed")

    def test_sixth_attempt_is_blocked(self):
        t = self._make_throttle()
        req = self._fake_request("10.1.1.2")
        for _ in range(5):
            t.allow_request(req, None)
        self.assertFalse(t.allow_request(req, None), "6th attempt must be blocked")

    def test_wait_time_returned_on_block(self):
        t = self._make_throttle()
        req = self._fake_request("10.1.1.3")
        for _ in range(5):
            t.allow_request(req, None)
        t.allow_request(req, None)  # blocked
        wait = t.wait()
        self.assertIsNotNone(wait)
        self.assertGreater(wait, 0)
        self.assertLessEqual(wait, 900)

    def test_window_expiry_resets_counter(self):
        """After the 15-minute window expires, attempts are allowed again."""
        from django.conf import settings
        from django.core.cache import cache
        window = getattr(settings, "LOGIN_THROTTLE_WINDOW_SECONDS", 900)
        t = self._make_throttle()
        req = self._fake_request("10.1.1.4")

        # Fill 5 slots with timestamps far in the past
        past = time.time() - window - 1
        key = "throttle_login_10.1.1.4"
        cache.set(key, [past] * 5, window)

        # All old entries are outside the window — attempt 1 should be allowed
        self.assertTrue(t.allow_request(req, None), "Attempt after window expiry should be allowed")

    def test_different_ips_have_independent_limits(self):
        t = self._make_throttle()
        req_a = self._fake_request("10.2.2.1")
        req_b = self._fake_request("10.2.2.2")

        # Exhaust IP A
        for _ in range(5):
            t.allow_request(req_a, None)
        self.assertFalse(t.allow_request(req_a, None), "IP A should be blocked")

        # IP B is unaffected
        self.assertTrue(t.allow_request(req_b, None), "IP B should still be allowed")

    def test_cache_failure_allows_request(self):
        """Cache errors fail open (security policy: do not lock out on infra failure)."""
        from apps.accounts.views import LoginThrottle
        t = LoginThrottle()
        req = self._fake_request("10.3.3.1")
        with patch("django.core.cache.cache.get", side_effect=Exception("redis down")):
            result = t.allow_request(req, None)
        self.assertTrue(result, "Cache failure must fail open")

    def test_spoofed_xff_header_does_not_bypass_throttle(self):
        """
        With NUM_PROXIES=1, get_ident() uses REMOTE_ADDR (the IP the trusted proxy
        inserted), not the client-supplied X-Forwarded-For value. A spoofed XFF
        header must NOT allow a blocked IP to bypass the throttle.
        """
        from django.conf import settings
        # Confirm NUM_PROXIES is set to a safe value in the running config
        num_proxies = settings.REST_FRAMEWORK.get("NUM_PROXIES")
        self.assertIsNotNone(num_proxies, "NUM_PROXIES must be set in REST_FRAMEWORK")
        self.assertGreaterEqual(num_proxies, 1, "NUM_PROXIES must be >= 1 to prevent XFF spoofing")

        # Exhaust the limit for a real IP via REMOTE_ADDR
        real_ip = "10.5.5.5"
        t = self._make_throttle()
        req_real = self._fake_request(real_ip)
        for _ in range(5):
            t.allow_request(req_real, None)
        self.assertFalse(t.allow_request(req_real, None), "Real IP must be blocked after 5 attempts")

        # Simulate the full proxy chain: client sends XFF "1.2.3.4" (fake IP),
        # the trusted nginx proxy appends the real client IP, so the final header
        # arriving at Gunicorn is XFF="1.2.3.4, 10.5.5.5"; REMOTE_ADDR is the proxy.
        # With NUM_PROXIES=1, DRF reads ips[-1]="10.5.5.5" (real client), ignoring
        # the client-supplied "1.2.3.4" entry. The real IP is exhausted → blocked.
        class _ProxiedSpoofRequest:
            META = {
                "REMOTE_ADDR": "192.168.1.1",  # trusted nginx proxy IP
                "HTTP_X_FORWARDED_FOR": f"1.2.3.4, {real_ip}",  # spoofed + real appended by proxy
            }
            headers = {"x-forwarded-for": f"1.2.3.4, {real_ip}"}

        req_spoofed = _ProxiedSpoofRequest()
        # With NUM_PROXIES=1, DRF resolves to real_ip (appended by proxy), so still blocked
        blocked = not t.allow_request(req_spoofed, None)
        self.assertTrue(blocked, "Spoofed X-Forwarded-For must not bypass throttle when NUM_PROXIES=1")

    def test_exactly_five_attempts_per_window(self):
        t = self._make_throttle()
        req = self._fake_request("10.1.1.5")
        results = [t.allow_request(req, None) for _ in range(6)]
        self.assertEqual(results, [True, True, True, True, True, False])

    def test_http_login_throttle_returns_429(self):
        """End-to-end: 6th login attempt within the window returns HTTP 429."""
        from django.test import Client
        from apps.accounts.services.registration import register_user

        # Use unique IP so it doesn't cross-contaminate other tests
        ip = "10.9.9.9"
        u, _ = register_user(email="throttle_http@test.com", password="Pass1234!")
        u.email_verified_at = timezone.now()
        u.save()

        import json
        c = Client()
        payload = json.dumps({"username": "throttle_http@test.com", "password": "Pass1234!"})
        headers = {"content_type": "application/json", "HTTP_HOST": "educloud.test", "REMOTE_ADDR": ip}

        # 5 successful logins
        for _ in range(5):
            r = c.post("/api/v1/auth/login/", payload, **headers)
            self.assertEqual(r.status_code, 200, f"Expected 200, got {r.status_code}: {r.content[:200]}")

        # 6th should be throttled
        r = c.post("/api/v1/auth/login/", payload, **headers)
        self.assertEqual(r.status_code, 429, f"Expected 429, got {r.status_code}: {r.content[:200]}")


# ---------------------------------------------------------------------------
# 2. Argon2 production configuration
# ---------------------------------------------------------------------------

class Argon2ProductionConfigTest(TestCase):
    """
    Verifies the production Django settings configure Argon2 as the primary
    password hasher — independently of test settings (which override to MD5
    for speed).
    """

    def test_production_settings_use_argon2_as_primary_hasher(self):
        """The first entry in base.py PASSWORD_HASHERS must be Argon2."""
        # Import base settings directly, bypassing any test overrides
        import importlib
        base = importlib.import_module("config.settings.base")
        hashers: list[str] = getattr(base, "PASSWORD_HASHERS", [])
        self.assertTrue(
            len(hashers) > 0,
            "PASSWORD_HASHERS must not be empty in production settings",
        )
        primary = hashers[0]
        self.assertEqual(
            primary,
            "django.contrib.auth.hashers.Argon2PasswordHasher",
            f"Production primary hasher must be Argon2, got: {primary}",
        )

    @override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.Argon2PasswordHasher"])
    def test_argon2_hashes_passwords_correctly(self):
        """Argon2 hasher produces correct argon2 prefix when active."""
        from django.contrib.auth.hashers import make_password, identify_hasher
        pw_hash = make_password("TestPass123!")
        self.assertTrue(
            pw_hash.startswith("argon2") or pw_hash.startswith("$argon2"),
            f"Expected argon2 hash prefix, got: {pw_hash[:30]}",
        )
        hasher = identify_hasher(pw_hash)
        self.assertIn(
            "argon2",
            hasher.algorithm.lower(),
            "Identified hasher algorithm must contain 'argon2'",
        )

    @override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.Argon2PasswordHasher"])
    def test_argon2_verify_roundtrip(self):
        """Argon2-hashed password can be verified correctly."""
        from django.contrib.auth.hashers import make_password, check_password
        pw = "RoundTrip!99"
        pw_hash = make_password(pw)
        self.assertTrue(check_password(pw, pw_hash))
        self.assertFalse(check_password("wrong", pw_hash))

    def test_test_settings_do_not_affect_production_config(self):
        """Test PASSWORD_HASHERS override must not be Argon2 (confirms isolation)."""
        from django.conf import settings
        primary = settings.PASSWORD_HASHERS[0]
        self.assertNotEqual(
            primary,
            "django.contrib.auth.hashers.Argon2PasswordHasher",
            "Test settings should use a fast hasher, not Argon2",
        )


# ---------------------------------------------------------------------------
# 3. StudentPayment deterministic ordering
# ---------------------------------------------------------------------------

class StudentPaymentOrderingTests(TestCase):
    """Verifies that StudentPayment has deterministic ordering: -created_at, -id."""

    def _make_ws_and_student(self, subdomain, email):
        from apps.workspaces.models import Workspace, WorkspaceMembership
        from apps.accounts.services.registration import register_user
        ws = Workspace.objects.create(
            subdomain=subdomain, status="ACTIVE", settings_json={"display_name": subdomain}
        )
        u, _ = register_user(email=email, password="Pass1234!")
        WorkspaceMembership.objects.create(user=u, workspace=ws, role="STUDENT")
        return ws, u

    def _make_payment(self, ws, student, amount="100.00"):
        from apps.payments.models import StudentPayment
        return StudentPayment.objects.create(
            workspace=ws, student=student,
            payment_model="WORKSPACE_MONTHLY",
            amount_egp=amount,
        )

    def test_meta_ordering_is_defined(self):
        from apps.payments.models import StudentPayment
        self.assertEqual(
            list(StudentPayment._meta.ordering),
            ["-created_at", "-id"],
            "StudentPayment must have ordering = ['-created_at', '-id']",
        )

    def test_newer_payment_appears_first(self):
        ws, student = self._make_ws_and_student("ord-ws-1", "ord1@test.com")
        p1 = self._make_payment(ws, student, "100.00")
        p2 = self._make_payment(ws, student, "200.00")

        from apps.payments.models import StudentPayment
        qs = list(StudentPayment.objects.filter(workspace=ws))
        self.assertEqual(qs[0].id, p2.id, "Newer payment (p2) must come first")
        self.assertEqual(qs[1].id, p1.id)

    def test_stable_ordering_by_id_when_timestamps_match(self):
        """When created_at values are equal, id desc is used as tiebreaker."""
        ws, student = self._make_ws_and_student("ord-ws-2", "ord2@test.com")
        from apps.payments.models import StudentPayment
        import datetime

        fixed_ts = timezone.now()
        p1 = StudentPayment.objects.create(
            workspace=ws, student=student,
            payment_model="WORKSPACE_MONTHLY", amount_egp="50.00",
        )
        p2 = StudentPayment.objects.create(
            workspace=ws, student=student,
            payment_model="WORKSPACE_MONTHLY", amount_egp="75.00",
        )
        # Force identical created_at
        StudentPayment.objects.filter(pk__in=[p1.pk, p2.pk]).update(created_at=fixed_ts)

        qs = list(StudentPayment.objects.filter(workspace=ws))
        self.assertEqual(qs[0].id, p2.id, "Higher ID must come first when timestamps tie")
        self.assertEqual(qs[1].id, p1.id)

    def test_pagination_is_consistent(self):
        """Paginating ordered results produces stable non-overlapping pages."""
        ws, student = self._make_ws_and_student("ord-ws-3", "ord3@test.com")
        from apps.payments.models import StudentPayment

        payments = [self._make_payment(ws, student, f"{100 + i}.00") for i in range(6)]
        payment_ids = [p.id for p in reversed(payments)]  # newest first

        qs = StudentPayment.objects.filter(workspace=ws)
        page1 = list(qs[:3].values_list("id", flat=True))
        page2 = list(qs[3:6].values_list("id", flat=True))

        self.assertEqual(page1, payment_ids[:3], "Page 1 must be the 3 newest")
        self.assertEqual(page2, payment_ids[3:], "Page 2 must be the 3 oldest")
        self.assertEqual(len(set(page1) & set(page2)), 0, "Pages must not overlap")

    def test_ordering_not_affected_by_status_filter(self):
        ws, student = self._make_ws_and_student("ord-ws-4", "ord4@test.com")
        from apps.payments.models import StudentPayment
        p1 = self._make_payment(ws, student, "10.00")
        p2 = self._make_payment(ws, student, "20.00")
        StudentPayment.objects.filter(pk=p1.pk).update(status="PAID")

        qs = list(StudentPayment.objects.filter(workspace=ws))
        self.assertEqual(qs[0].id, p2.id, "Ordering by -created_at/-id must survive status filter")
