"""
Management command to load sample development data for Neighborly.
Usage: py manage.py seed_data
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from accounts.models import Profile
from services.models import ServiceCategory, Service
from bookings.models import ServiceRequest
from reviews.models import Review
from core.models import ContactMessage


CATEGORIES = [
    {'name': 'Plumbing', 'icon': 'wrench', 'description': 'Pipe repairs, installations, and water systems', 'order': 1},
    {'name': 'Electrical', 'icon': 'zap', 'description': 'Wiring, repairs, and electrical installations', 'order': 2},
    {'name': 'Home Cleaning', 'icon': 'sparkles', 'description': 'Deep cleaning, regular housekeeping', 'order': 3},
    {'name': 'Carpentry', 'icon': 'hammer', 'description': 'Furniture, woodwork, and custom builds', 'order': 4},
    {'name': 'Painting', 'icon': 'brush', 'description': 'Interior and exterior painting', 'order': 5},
    {'name': 'Gardening', 'icon': 'leaf', 'description': 'Garden maintenance, planting, and landscaping', 'order': 6},
    {'name': 'Appliance Repair', 'icon': 'cpu', 'description': 'Repair for household appliances', 'order': 7},
    {'name': 'Computer Repair', 'icon': 'monitor', 'description': 'Laptop, PC, and tech support', 'order': 8},
    {'name': 'Home Tutoring', 'icon': 'book-open', 'description': 'Academic tutoring and coaching', 'order': 9},
    {'name': 'Tailoring', 'icon': 'scissors', 'description': 'Clothing alterations and stitching', 'order': 10},
    {'name': 'Errands & Delivery', 'icon': 'package', 'description': 'Local errands and delivery services', 'order': 11},
    {'name': 'Event Assistance', 'icon': 'calendar', 'description': 'Event setup, catering help, and coordination', 'order': 12},
]

PROVIDERS = [
    {
        'username': 'ravi_plumber',
        'password': 'Neighborly@123',
        'email': 'ravi@example.com',
        'full_name': 'Ravi Kumar',
        'city': 'Bangalore',
        'area': 'Koramangala',
        'bio': 'Experienced plumber with 10+ years serving Bangalore households.',
        'skills': 'Pipe repair, tap replacement, water heater, drainage',
        'phone': '+91 9876543210',
    },
    {
        'username': 'priya_cleaner',
        'password': 'Neighborly@123',
        'email': 'priya@example.com',
        'full_name': 'Priya Sharma',
        'city': 'Bangalore',
        'area': 'Indiranagar',
        'bio': 'Professional home cleaner providing reliable and thorough cleaning services.',
        'skills': 'Deep cleaning, kitchen sanitisation, bathroom cleaning, laundry',
        'phone': '+91 9876543211',
    },
    {
        'username': 'suresh_electric',
        'password': 'Neighborly@123',
        'email': 'suresh@example.com',
        'full_name': 'Suresh Babu',
        'city': 'Bangalore',
        'area': 'JP Nagar',
        'bio': 'Licensed electrician. Safe, certified, and reliable electrical services.',
        'skills': 'Wiring, switchboard repair, fan installation, MCB panel',
        'phone': '+91 9876543212',
    },
    {
        'username': 'meera_tutor',
        'password': 'Neighborly@123',
        'email': 'meera@example.com',
        'full_name': 'Meera Nair',
        'city': 'Bangalore',
        'area': 'HSR Layout',
        'bio': 'MSc Mathematics. Helping students excel in CBSE and ICSE from Class 6 to 12.',
        'skills': 'Mathematics, Physics, Chemistry, English',
        'phone': '+91 9876543213',
    },
    {
        'username': 'ahmed_carpenter',
        'password': 'Neighborly@123',
        'email': 'ahmed@example.com',
        'full_name': 'Ahmed Shaikh',
        'city': 'Bangalore',
        'area': 'Whitefield',
        'bio': 'Skilled carpenter specialising in custom furniture and repairs.',
        'skills': 'Furniture repair, wardrobes, shelves, custom woodwork',
        'phone': '+91 9876543214',
    },
]

CUSTOMERS = [
    {
        'username': 'ananya_customer',
        'password': 'Neighborly@123',
        'email': 'ananya@example.com',
        'full_name': 'Ananya Reddy',
        'city': 'Bangalore',
        'area': 'Koramangala',
    },
    {
        'username': 'vikram_customer',
        'password': 'Neighborly@123',
        'email': 'vikram@example.com',
        'full_name': 'Vikram Singh',
        'city': 'Bangalore',
        'area': 'HSR Layout',
    },
]

SERVICES = [
    {
        'provider': 'ravi_plumber',
        'category': 'Plumbing',
        'title': 'Home Plumbing Repairs',
        'description': 'Professional plumbing services including pipe leak repairs, tap replacements, drainage unblocking, and water heater installation. 10 years of experience serving Bangalore homes. All work guaranteed.',
        'price': 400,
        'pricing_unit': 'visit',
        'city': 'Bangalore',
        'area': 'Koramangala',
        'availability': 'Mon–Sat, 8 AM–7 PM',
        'is_featured': True,
    },
    {
        'provider': 'ravi_plumber',
        'category': 'Plumbing',
        'title': 'Bathroom Fitting & Renovation',
        'description': 'Complete bathroom plumbing — new installations, toilet fitting, shower units, and full renovation support.',
        'price': 1200,
        'pricing_unit': 'project',
        'city': 'Bangalore',
        'area': 'Koramangala',
        'availability': 'Mon–Sat, 9 AM–6 PM',
        'is_featured': False,
    },
    {
        'provider': 'priya_cleaner',
        'category': 'Home Cleaning',
        'title': 'Professional Deep Home Cleaning',
        'description': 'Thorough deep cleaning of your home — kitchen, bathrooms, living areas, and bedrooms. Eco-friendly products used. Team of trained professionals.',
        'price': 800,
        'pricing_unit': 'visit',
        'city': 'Bangalore',
        'area': 'Indiranagar',
        'availability': 'Mon–Sun, 9 AM–5 PM',
        'is_featured': True,
    },
    {
        'provider': 'priya_cleaner',
        'category': 'Home Cleaning',
        'title': 'Regular Weekly Housekeeping',
        'description': 'Weekly housekeeping service tailored to your schedule. Sweeping, mopping, dusting, and kitchen cleaning.',
        'price': 350,
        'pricing_unit': 'visit',
        'city': 'Bangalore',
        'area': 'Indiranagar',
        'availability': 'Mon–Sat, 9 AM–5 PM',
        'is_featured': False,
    },
    {
        'provider': 'suresh_electric',
        'category': 'Electrical',
        'title': 'Home Electrical Repairs',
        'description': 'Certified electrician for switchboard repairs, MCB replacement, fan installation, and general wiring issues. Safety-first approach.',
        'price': 300,
        'pricing_unit': 'visit',
        'city': 'Bangalore',
        'area': 'JP Nagar',
        'availability': 'Mon–Sat, 8 AM–8 PM',
        'is_featured': True,
    },
    {
        'provider': 'meera_tutor',
        'category': 'Home Tutoring',
        'title': 'CBSE Maths & Science Tutoring (Class 8–12)',
        'description': 'Personalised tutoring in Mathematics, Physics, and Chemistry for CBSE students. Board exam preparation included. Clear concepts, practice tests.',
        'price': 500,
        'pricing_unit': 'hour',
        'city': 'Bangalore',
        'area': 'HSR Layout',
        'availability': 'Mon–Fri, 4 PM–8 PM; Sat–Sun, 10 AM–5 PM',
        'is_featured': True,
    },
    {
        'provider': 'ahmed_carpenter',
        'category': 'Carpentry',
        'title': 'Furniture Repair & Custom Woodwork',
        'description': 'Expert carpentry — furniture repairs, custom shelves, wardrobe fitting, and woodwork. Quality materials, clean finish.',
        'price': 600,
        'pricing_unit': 'day',
        'city': 'Bangalore',
        'area': 'Whitefield',
        'availability': 'Mon–Sat, 9 AM–6 PM',
        'is_featured': False,
    },
]


class Command(BaseCommand):
    help = 'Seeds the database with sample development data'

    def handle(self, *args, **options):
        self.stdout.write('Creating categories...')
        categories = {}
        for cat_data in CATEGORIES:
            cat, created = ServiceCategory.objects.get_or_create(
                name=cat_data['name'],
                defaults={
                    'icon': cat_data['icon'],
                    'description': cat_data['description'],
                    'order': cat_data['order'],
                    'is_active': True,
                }
            )
            categories[cat.name] = cat
            if created:
                self.stdout.write(f'  Created category: {cat.name}')

        self.stdout.write('Creating provider accounts...')
        provider_users = {}
        for p in PROVIDERS:
            user, created = User.objects.get_or_create(username=p['username'])
            if created:
                user.set_password(p['password'])
                user.email = p['email']
                user.save()
                profile = user.profile
                profile.role = Profile.ROLE_PROVIDER
                profile.full_name = p['full_name']
                profile.city = p['city']
                profile.area = p['area']
                profile.bio = p['bio']
                profile.skills = p['skills']
                profile.phone = p['phone']
                profile.save()
                self.stdout.write(f'  Created provider: {user.username}')
            provider_users[p['username']] = user

        self.stdout.write('Creating customer accounts...')
        customer_users = {}
        for c in CUSTOMERS:
            user, created = User.objects.get_or_create(username=c['username'])
            if created:
                user.set_password(c['password'])
                user.email = c['email']
                user.save()
                profile = user.profile
                profile.role = Profile.ROLE_CUSTOMER
                profile.full_name = c['full_name']
                profile.city = c['city']
                profile.area = c['area']
                profile.save()
                self.stdout.write(f'  Created customer: {user.username}')
            customer_users[c['username']] = user

        self.stdout.write('Creating services...')
        services_created = []
        for s in SERVICES:
            provider = provider_users.get(s['provider'])
            category = categories.get(s['category'])
            if not provider or not category or not provider.profile.is_provider:
                continue
            service, created = Service.objects.get_or_create(
                provider=provider,
                title=s['title'],
                defaults={
                    'category': category,
                    'description': s['description'],
                    'price': s['price'],
                    'pricing_unit': s['pricing_unit'],
                    'city': s['city'],
                    'area': s['area'],
                    'availability': s['availability'],
                    'is_active': True,
                    'is_featured': s.get('is_featured', False),
                }
            )
            services_created.append(service)
            if created:
                self.stdout.write(f'  Created service: {service.title}')

        self.stdout.write('Creating sample requests and reviews...')
        from datetime import date, timedelta
        ananya = customer_users.get('ananya_customer')
        vikram = customer_users.get('vikram_customer')

        if ananya and services_created:
            plumbing_service = next((s for s in services_created if 'Plumbing' in s.title), None)
            if plumbing_service:
                req, created = ServiceRequest.objects.get_or_create(
                    customer=ananya,
                    service=plumbing_service,
                    defaults={
                        'requested_date': date.today() - timedelta(days=10),
                        'requested_time': None,
                        'service_location': 'Flat 12, Sunrise Apartments, Koramangala',
                        'work_description': 'Kitchen tap is leaking and needs replacement.',
                        'status': ServiceRequest.STATUS_COMPLETED,
                        'provider_response': 'Tap replaced. Work completed in 1.5 hours.',
                    }
                )
                if created and not hasattr(req, 'review'):
                    try:
                        Review.objects.create(
                            service_request=req,
                            rating=5,
                            comment='Excellent work! Ravi was punctual and professional. Fixed the leak quickly. Highly recommended.'
                        )
                        self.stdout.write('  Created sample review')
                    except Exception:
                        pass

        if vikram and len(services_created) > 2:
            cleaning_service = next((s for s in services_created if 'Deep' in s.title), None)
            if cleaning_service:
                ServiceRequest.objects.get_or_create(
                    customer=vikram,
                    service=cleaning_service,
                    defaults={
                        'requested_date': date.today() + timedelta(days=3),
                        'service_location': 'HSR Layout, 3BHK flat',
                        'work_description': 'Need full deep cleaning before Diwali.',
                        'status': ServiceRequest.STATUS_PENDING,
                    }
                )

        self.stdout.write(self.style.SUCCESS('\n[OK] Sample data loaded successfully!'))
        self.stdout.write('\nProvider login credentials:')
        for p in PROVIDERS:
            self.stdout.write(f"  Username: {p['username']}  Password: {p['password']}")
        self.stdout.write('\nCustomer login credentials:')
        for c in CUSTOMERS:
            self.stdout.write(f"  Username: {c['username']}  Password: {c['password']}")
