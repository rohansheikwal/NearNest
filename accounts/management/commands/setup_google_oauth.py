"""
Management command to permanently configure Google OAuth credentials
in both .env file and the SQLite database (SocialApp & Site).

Usage:
    python manage.py setup_google_oauth --client-id <ID> --client-secret <SECRET>
    python manage.py setup_google_oauth  # Uses credentials currently in .env
"""
import os
import re
from pathlib import Path
from django.core.management.base import BaseCommand
from django.conf import settings
from django.contrib.sites.models import Site
from allauth.socialaccount.models import SocialApp


class Command(BaseCommand):
    help = "Permanently set up Google OAuth in .env and Django database"

    def add_arguments(self, parser):
        parser.add_argument(
            '--client-id',
            type=str,
            help='Google OAuth Client ID (e.g. xxxxx.apps.googleusercontent.com)',
        )
        parser.add_argument(
            '--client-secret',
            type=str,
            help='Google OAuth Client Secret (e.g. GOCSPX-xxxxx)',
        )

    def handle(self, *args, **options):
        client_id = (options.get('client_id') or os.environ.get('GOOGLE_CLIENT_ID', '')).strip()
        client_secret = (options.get('client_secret') or os.environ.get('GOOGLE_CLIENT_SECRET', '')).strip()

        if not client_id or client_id in {'your-google-client-id-here', 'placeholder'}:
            self.stdout.write(self.style.ERROR(
                "[!] No valid Google Client ID provided.\n"
                "Please run with:\n"
                "  python manage.py setup_google_oauth --client-id <YOUR_CLIENT_ID> --client-secret <YOUR_CLIENT_SECRET>\n"
                "Or edit GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in your .env file."
            ))
            return

        # 1. Update .env file if it exists
        env_path = settings.BASE_DIR / '.env'
        if env_path.exists():
            content = env_path.read_text(encoding='utf-8')
            # Update GOOGLE_CLIENT_ID
            if re.search(r'^GOOGLE_CLIENT_ID=.*$', content, flags=re.MULTILINE):
                content = re.sub(r'^GOOGLE_CLIENT_ID=.*$', f'GOOGLE_CLIENT_ID={client_id}', content, flags=re.MULTILINE)
            else:
                content += f"\nGOOGLE_CLIENT_ID={client_id}"

            # Update GOOGLE_CLIENT_SECRET
            if re.search(r'^GOOGLE_CLIENT_SECRET=.*$', content, flags=re.MULTILINE):
                content = re.sub(r'^GOOGLE_CLIENT_SECRET=.*$', f'GOOGLE_CLIENT_SECRET={client_secret}', content, flags=re.MULTILINE)
            else:
                content += f"\nGOOGLE_CLIENT_SECRET={client_secret}"

            env_path.write_text(content, encoding='utf-8')
            self.stdout.write(self.style.SUCCESS(f"[OK] Updated .env file at {env_path}"))

        # 2. Update Site in database (SITE_ID = 1)
        site_id = getattr(settings, 'SITE_ID', 1)
        site, _ = Site.objects.update_or_create(
            id=site_id,
            defaults={
                'domain': '127.0.0.1:8000',
                'name': 'NearNest',
            }
        )
        self.stdout.write(self.style.SUCCESS(f"[OK] Configured Django Site ID {site.id} ({site.domain})"))

        # 3. Create or update SocialApp in database
        social_app, created = SocialApp.objects.update_or_create(
            provider='google',
            defaults={
                'name': 'Google',
                'client_id': client_id,
                'secret': client_secret,
                'key': '',
            }
        )
        social_app.sites.add(site)
        status_msg = "Created" if created else "Updated"
        self.stdout.write(self.style.SUCCESS(f"[OK] {status_msg} Google SocialApp in database (linked to Site ID {site.id})"))

        self.stdout.write("\n" + "=" * 65)
        self.stdout.write(self.style.SUCCESS("Google OAuth is now permanently configured!"))
        self.stdout.write("=" * 65)
        self.stdout.write("Ensure these URLs are added in Google Cloud Console:\n")
        self.stdout.write("Authorized JavaScript origins:")
        self.stdout.write("  - http://127.0.0.1:8000")
        self.stdout.write("  - http://localhost:8000\n")
        self.stdout.write("Authorized redirect URIs:")
        self.stdout.write("  - http://127.0.0.1:8000/accounts/google/login/callback/")
        self.stdout.write("  - http://localhost:8000/accounts/google/login/callback/")
        self.stdout.write("=" * 65 + "\n")
