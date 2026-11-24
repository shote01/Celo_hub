from django.test import TestCase
from django.urls import reverse

from .models import AuditLog, User


class ProfileTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("mika", password="Old-pass-2026!", first_name="Mika", role="staff")
        self.client.force_login(self.user)

    def test_login_required(self):
        self.client.logout()
        response = self.client.get(reverse("accounts:profile"))
        self.assertRedirects(response, f"{reverse('login')}?next={reverse('accounts:profile')}", fetch_redirect_response=False)

    def test_user_can_change_their_name(self):
        response = self.client.post(reverse("accounts:profile"), {
            "first_name": "Michaela", "last_name": "Santos", "email": "mika@example.com",
        })
        self.assertRedirects(response, reverse("accounts:profile"))
        self.user.refresh_from_db()
        self.assertEqual((self.user.first_name, self.user.last_name), ("Michaela", "Santos"))
        self.assertTrue(AuditLog.objects.filter(action="Updated profile").exists())

    def test_first_name_is_required_and_role_cannot_be_changed(self):
        response = self.client.post(reverse("accounts:profile"), {"first_name": "", "last_name": "X", "role": "admin"})
        self.assertEqual(response.status_code, 200)
        self.client.post(reverse("accounts:profile"), {"first_name": "Mika", "last_name": "", "role": "admin"})
        self.user.refresh_from_db()
        self.assertEqual(self.user.role, "staff")

    def test_password_change_keeps_user_logged_in(self):
        response = self.client.post(reverse("accounts:password_change"), {
            "old_password": "Old-pass-2026!",
            "new_password1": "Brand-new-pass-77!",
            "new_password2": "Brand-new-pass-77!",
        })
        self.assertRedirects(response, reverse("accounts:profile"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("Brand-new-pass-77!"))
        self.assertEqual(self.client.get(reverse("accounts:profile")).status_code, 200)  # still logged in
        self.assertTrue(AuditLog.objects.filter(action="Changed password").exists())

    def test_wrong_old_password_is_rejected(self):
        response = self.client.post(reverse("accounts:password_change"), {
            "old_password": "nope", "new_password1": "Brand-new-pass-77!", "new_password2": "Brand-new-pass-77!",
        })
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("Old-pass-2026!"))
