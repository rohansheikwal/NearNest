# NearNest — Local Services, Stronger Communities

A full-stack Django web application for a college demonstration project connecting local customers with service providers.

**Final Year BTech Computer Science Project**

---

## Overview

NearNest is a community-focused service marketplace that allows:

- **Customers** to discover, browse, save, and request local services
- **Providers** to list their services, manage incoming requests, and build a community reputation
- **Administrators** to manage users, services, categories, and content through Django's admin panel

---

## Features

### For Customers
- Browse and search services by keyword, category, city, and area
- Filter by price range and sort by rating or newest
- View detailed service and provider profile pages
- Submit service requests with preferred date, time, and work description
- Track request status from Pending to Completed via a personal dashboard
- Save services to a personal list for easy access later
- Leave verified reviews only after a service is marked Completed

### For Service Providers
- Create a professional provider profile with bio and skills
- List services with detailed descriptions, pricing, and availability
- Receive and manage customer requests (Accept/Reject/In Progress/Complete)
- View all customer reviews and average rating on a dedicated Reviews page
- Public profile page visible to all users

### General
- Role-based access control (Customer / Provider)
- Responsive design with custom CSS design system
- Clean, accessible HTML with semantic structure
- AJAX save-service toggle with toast notifications
- FAQ accordion, contact form, and informational static pages
- Custom 403, 404, and 500 error pages
- Django Admin with full model management

---

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.x, Django 5.x / 6.x |
| Database | SQLite (development) |
| ORM | Django ORM |
| Authentication | Django built-in auth + session + Google OAuth (django-allauth) |
| Frontend | HTML5, CSS3, Bootstrap 5, Vanilla JS |
| Icons | Lucide Icons (CDN) |
| Typography | Manrope via Google Fonts |
| Image handling | Pillow |
| Forms | django-crispy-forms + crispy-bootstrap5 |

---

## Project Structure

```
NearNest/
├── config/              # Django project settings and main URL config
│   ├── settings.py
│   └── urls.py
├── accounts/            # User registration, login, profiles, dashboards
├── services/            # Service listings, categories, provider dashboard
├── bookings/            # Service requests, saved services
├── reviews/             # Review submission and display
├── core/                # Homepage, static pages, contact, template tags
│   └── templatetags/
│       └── neighborly_tags.py
├── templates/           # All HTML templates
│   ├── base.html
│   ├── accounts/
│   ├── bookings/
│   ├── core/
│   ├── dashboards/
│   ├── errors/
│   ├── includes/
│   ├── reviews/
│   └── services/
├── static/              # CSS, JS, images
│   ├── css/neighborly.css
│   ├── js/neighborly.js
│   └── images/
├── media/               # User-uploaded files (auto-created)
├── tests.py             # Test suite (50+ test cases)
├── requirements.txt
└── manage.py
```

---

## Database Models

| App | Model | Description |
|-----|-------|-------------|
| accounts | `Profile` | Extends User with role, bio, skills, city, area, phone |
| services | `ServiceCategory` | Category name, slug, icon, order |
| services | `Service` | Provider, category, title, description, price, location, status |
| bookings | `ServiceRequest` | Customer request with date, location, work description, status |
| bookings | `SavedService` | Customer's saved services list |
| reviews | `Review` | OneToOne with completed ServiceRequest, rating, comment |
| core | `ContactMessage` | Contact form submissions |

---

## Setup Instructions

### 1. Clone / Download the project

```bash
cd path/to/NearNest
```

### 2. Create and activate a virtual environment

```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Apply database migrations

```bash
py manage.py migrate
```

### 5. Load sample data (optional but recommended)

```bash
py manage.py seed_data
```

This creates:
- 12 service categories (Plumbing, Electrical, Cleaning, etc.)
- 5 provider accounts and 2 customer accounts
- 7 sample service listings
- Sample requests and a review

**Sample credentials** (all share the same password):

| Username | Role | Password |
|----------|------|----------|
| `ravi_plumber` | Provider | `Neighborly@123` |
| `priya_cleaner` | Provider | `Neighborly@123` |
| `meera_tutor` | Provider | `Neighborly@123` |
| `suresh_electric` | Provider | `Neighborly@123` |
| `ahmed_carpenter` | Provider | `Neighborly@123` |
| `ananya_customer` | Customer | `Neighborly@123` |
| `vikram_customer` | Customer | `Neighborly@123` |

### 6. Create a superuser (for admin panel)

```bash
py manage.py createsuperuser
```

### 7. Run checks and tests

```powershell
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
```

### 8. Run the development server

```bash
$env:DJANGO_DEBUG = "1"
$env:DJANGO_ALLOWED_HOSTS = "127.0.0.1,localhost"
python manage.py runserver
```

Open: **http://127.0.0.1:8000/**

Admin panel: **http://127.0.0.1:8000/admin/**

### Google Sign-In and password reset configuration

Install the dependencies and apply the authentication migrations:

```powershell
py -m pip install -r requirements.txt
py manage.py migrate
```

In Google Cloud Console:

1. Create or select a project and configure the OAuth consent screen.
2. Create an OAuth 2.0 **Web application** client.
3. Add `http://127.0.0.1:8000/accounts/google/login/callback/` as an authorized
   redirect URI. Add the equivalent HTTPS URI for production.
4. Keep the client ID and client secret out of source control. Set them in the
   VS Code PowerShell terminal before starting Django:

```powershell
$env:GOOGLE_CLIENT_ID = "your-client-id.apps.googleusercontent.com"
$env:GOOGLE_CLIENT_SECRET = "your-client-secret"
$env:DJANGO_DEBUG = "1"
$env:DJANGO_ALLOWED_HOSTS = "127.0.0.1,localhost"
py manage.py runserver
```

After migrations, set the Sites framework domain to the host used by the
browser (for local development, `localhost:8000`):

```powershell
py manage.py shell -c "from django.contrib.sites.models import Site; Site.objects.update_or_create(id=1, defaults={'domain':'localhost:8000','name':'NearNest local'})"
```

Google sign-in creates a customer profile by default. Provider accounts must
still use the provider registration form, so OAuth cannot grant provider or
admin privileges. A verified Google email may be linked to one matching
existing account; ambiguous duplicate emails are rejected rather than linked.

Password reset uses Django's one-time secure reset tokens. For local testing,
leave the default console backend and run the server; submit a registered email
at `/accounts/password-reset/`, then copy the reset URL printed in the VS Code
terminal. For SMTP delivery, set these variables before starting Django:

```powershell
$env:EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
$env:EMAIL_HOST = "smtp.example.com"
$env:EMAIL_PORT = "587"
$env:EMAIL_USE_TLS = "true"
$env:EMAIL_HOST_USER = "smtp-user"
$env:EMAIL_HOST_PASSWORD = "smtp-password"
$env:DEFAULT_FROM_EMAIL = "no-reply@example.com"
```

Never commit OAuth secrets, SMTP passwords, reset links, or user passwords.

---

## Running Tests

```bash
py manage.py test
```

The test suite includes automated tests covering:
- Model creation and properties
- View access control (login required, role-based access)
- Form submission and validation
- Full provider workflow (Accept → In Progress → Complete)
- Status transition guards
- Review uniqueness
- Saved service toggle and private saved-service access
- Contact form validation and database persistence
- Review ownership, completion status, one-review-per-request, rating, and text validation

---

## Key URLs

| URL | Description |
|-----|-------------|
| `/` | Homepage |
| `/services/` | Explore all services |
| `/services/<pk>/` | Service detail page |
| `/accounts/login/` | Login |
| `/accounts/register/customer/` | Customer registration |
| `/accounts/register/provider/` | Provider registration |
| `/accounts/dashboard/` | Customer dashboard |
| `/services/provider/dashboard/` | Provider dashboard |
| `/bookings/my-requests/` | Customer's requests |
| `/bookings/saved/` | Saved services |
| `/admin/` | Django Admin |

---

## Design System

The application uses a custom CSS design system (`static/css/neighborly.css`) with:

- **Primary colour**: Deep forest green `#234C3A`
- **Secondary**: Muted sage `#A8B8A1`
- **Background**: Warm cream `#F6F4ED`
- **Accent**: Restrained amber `#C8943A`
- **Typography**: Manrope (Google Fonts)
- Component classes: `.btn-*`, `.card`, `.hero`, `.step-item`, `.stat-card`, `.dashboard-sidebar`, `.faq-item`, `.badge-*`, etc.

---

## Environment and security settings

The local demonstration server uses SQLite and the console email backend. Set these environment variables for a deployment-like environment:

```powershell
$env:DJANGO_SECRET_KEY = "replace-with-a-long-random-secret"
$env:DJANGO_DEBUG = "0"
$env:DJANGO_ALLOWED_HOSTS = "example.com"
```

When `DJANGO_DEBUG=0`, secure session/CSRF cookie and browser security settings are enabled. Do not commit real secrets, uploaded files, or production database credentials.

## Known Limitations

- Email delivery is not configured. Messages are stored in the database (console backend in development).
- Payments are not processed. Pricing shown is indicative; actual arrangements are between users.
- No real-time notifications (no WebSocket / Celery). Dashboard must be refreshed manually.
- Images are stored locally in `media/` — not cloud-hosted.
- This is a locally tested college demonstration project, not a production deployment. It has no payment processing, background jobs, cloud media storage, monitoring, rate limiting, or production SMTP configuration.

---

## Project Information

- **Project type**: BTech Computer Science Final Year Project
- **Framework**: Django
- **Database**: SQLite (development)
- **Purpose**: To demonstrate a complete full-stack web application with real-world features, clean architecture, and thoughtful UX
