import re
from datetime import time, datetime, timedelta
from django.db import models
from django.contrib.auth.models import User
from django.utils.text import slugify
from django.urls import reverse
from django.utils import timezone

DAY_MAP = {
    'mon': 0, 'monday': 0,
    'tue': 1, 'tues': 1, 'tuesday': 1,
    'wed': 2, 'wednesday': 2,
    'thu': 3, 'thur': 3, 'thurs': 3, 'thursday': 3,
    'fri': 4, 'friday': 4,
    'sat': 5, 'saturday': 5,
    'sun': 6, 'sunday': 6,
}
DAY_NAMES = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
DAY_ABBR = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']


def parse_time_token(t_str):
    if not t_str:
        return None
    t_str = t_str.strip().upper()
    m = re.match(r'^(\d{1,2})(?::(\d{2}))?\s*(AM|PM)?$', t_str)
    if not m:
        return None
    hour = int(m.group(1))
    minute = int(m.group(2) or 0)
    meridiem = m.group(3)
    if meridiem == 'PM' and hour < 12:
        hour += 12
    elif meridiem == 'AM' and hour == 12:
        hour = 0
    return time(hour, minute)


def parse_single_clause(clause):
    clause = clause.strip()
    if not clause:
        return None
    if any(k in clause.lower() for k in ['24 hour', '24/7', '24x7']):
        return {d: (time(0, 0), time(23, 59)) for d in range(7)}

    clause_clean = clause.replace('\u2013', '-').replace('\u2014', '-').replace('\u2212', '-')
    parts = re.split(r'[,|]', clause_clean, maxsplit=1)
    if len(parts) != 2:
        m = re.search(r'(\d{1,2}(?::\d{2})?\s*(?:AM|PM)?)', clause_clean, re.I)
        if m:
            days_part = clause_clean[:m.start()].strip()
            time_part = clause_clean[m.start():].strip()
        else:
            return None
    else:
        days_part = parts[0].strip()
        time_part = parts[1].strip()

    days = set()
    range_match = re.search(r'([A-Za-z]+)\s*(?:-|to)\s*([A-Za-z]+)', days_part, re.I)
    if range_match:
        d1_str = range_match.group(1).lower()
        d2_str = range_match.group(2).lower()
        if d1_str in DAY_MAP and d2_str in DAY_MAP:
            d1 = DAY_MAP[d1_str]
            d2 = DAY_MAP[d2_str]
            if d1 <= d2:
                days.update(range(d1, d2 + 1))
            else:
                days.update(list(range(d1, 7)) + list(range(0, d2 + 1)))
    else:
        for word in re.split(r'[\s,&/]+', days_part):
            w = word.strip().lower()
            if w in DAY_MAP:
                days.add(DAY_MAP[w])

    if not days:
        return None

    time_part = time_part.replace('*', '8')
    t_match = re.search(r'(\d{1,2}(?::\d{2})?\s*(?:AM|PM)?)\s*(?:-|to|until)\s*(\d{1,2}(?::\d{2})?\s*(?:AM|PM)?)', time_part, re.I)
    if not t_match:
        return None

    t1_raw = t_match.group(1).strip()
    t2_raw = t_match.group(2).strip()

    if not re.search(r'(AM|PM)', t1_raw, re.I) and re.search(r'(AM|PM)', t2_raw, re.I):
        m2 = re.search(r'(AM|PM)', t2_raw, re.I).group(1)
        h1 = int(re.match(r'^\d+', t1_raw).group(0))
        if m2.upper() == 'PM' and 7 <= h1 <= 11:
            t1_raw += ' AM'
        else:
            t1_raw += ' ' + m2

    start_t = parse_time_token(t1_raw)
    end_t = parse_time_token(t2_raw)

    if not start_t or not end_t:
        return None

    return {d: (start_t, end_t) for d in days}


def parse_full_availability(avail_str):
    if not avail_str or not avail_str.strip():
        return {}
    schedule = {}
    clauses = avail_str.split(';')
    for clause in clauses:
        res = parse_single_clause(clause)
        if res:
            schedule.update(res)
    return schedule


class ServiceCategory(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, blank=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=100, blank=True, help_text="Lucide icon name e.g. 'wrench'")
    image = models.ImageField(upload_to='categories/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = 'Service Category'
        verbose_name_plural = 'Service Categories'
        ordering = ['order', 'name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('services:category', kwargs={'slug': self.slug})

    @property
    def service_count(self):
        return self.services.filter(is_active=True).count()


class Service(models.Model):
    UNIT_HOUR = 'hour'
    UNIT_VISIT = 'visit'
    UNIT_DAY = 'day'
    UNIT_PROJECT = 'project'
    UNIT_CHOICES = [
        (UNIT_HOUR, 'Per Hour'),
        (UNIT_VISIT, 'Per Visit'),
        (UNIT_DAY, 'Per Day'),
        (UNIT_PROJECT, 'Per Project'),
    ]

    provider = models.ForeignKey(User, on_delete=models.CASCADE, related_name='services')
    category = models.ForeignKey(ServiceCategory, on_delete=models.SET_NULL, null=True, related_name='services')
    title = models.CharField(max_length=200)
    description = models.TextField()
    image = models.ImageField(upload_to='services/', blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    pricing_unit = models.CharField(max_length=20, choices=UNIT_CHOICES, default=UNIT_VISIT)
    city = models.CharField(max_length=100)
    area = models.CharField(max_length=100, blank=True)
    availability = models.TextField(blank=True, help_text="e.g. Mon–Sat, 9 AM–6 PM")
    available_days = models.CharField(max_length=50, blank=True, default='', help_text="Comma-separated weekday numbers (0=Mon...6=Sun)")
    start_time = models.TimeField(null=True, blank=True, help_text="Daily starting time e.g. 09:00:00")
    end_time = models.TimeField(null=True, blank=True, help_text="Daily closing time e.g. 18:00:00")
    duration_hours = models.PositiveIntegerField(default=1, help_text="Estimated service duration in hours")
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Service'
        verbose_name_plural = 'Services'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} by {self.provider.username}"

    def get_absolute_url(self):
        return reverse('services:service_detail', kwargs={'pk': self.pk})

    def get_average_rating(self):
        from reviews.models import Review
        from django.db.models import Avg
        result = Review.objects.filter(service_request__service=self).aggregate(avg=Avg('rating'))
        return round(result['avg'], 1) if result['avg'] else None

    def get_review_count(self):
        from reviews.models import Review
        return Review.objects.filter(service_request__service=self).count()

    def get_price_display(self):
        return f"₹{self.price:,.0f} {self.get_pricing_unit_display()}"

    def get_location_display(self):
        parts = [p for p in [self.area, self.city] if p]
        return ', '.join(parts) if parts else 'Location not specified'

    def get_availability_schedule(self):
        """
        Return structured schedule dictionary for the service/provider:
        {
            'has_availability': bool,
            'duration_hours': int,
            'days': {
                weekday_int: {
                    'available': bool,
                    'start_time': time,
                    'end_time': time,
                    'start_str': str,
                    'end_str': str
                }
            },
            'available_weekday_indices': list of ints (0=Mon, ..., 6=Sun),
            'available_days_display': str (e.g. "Monday to Saturday"),
            'start_time_str': str,
            'end_time_str': str,
            'summary': str
        }
        """
        day_indices = []
        if self.available_days:
            for item in self.available_days.split(','):
                item = item.strip()
                if item.isdigit():
                    val = int(item)
                    if 0 <= val <= 6 and val not in day_indices:
                        day_indices.append(val)

        days_dict = {}
        if day_indices and self.start_time and self.end_time:
            for d in range(7):
                if d in day_indices:
                    days_dict[d] = {
                        'available': True,
                        'start_time': self.start_time,
                        'end_time': self.end_time,
                        'start_str': self.start_time.strftime('%I:%M %p'),
                        'end_str': self.end_time.strftime('%I:%M %p'),
                    }
                else:
                    days_dict[d] = {'available': False}
        else:
            parsed = parse_full_availability(self.availability)
            if parsed:
                day_indices = sorted(list(parsed.keys()))
                for d in range(7):
                    if d in parsed:
                        st, et = parsed[d]
                        days_dict[d] = {
                            'available': True,
                            'start_time': st,
                            'end_time': et,
                            'start_str': st.strftime('%I:%M %p'),
                            'end_str': et.strftime('%I:%M %p'),
                        }
                    else:
                        days_dict[d] = {'available': False}

        if not day_indices:
            return {
                'has_availability': False,
                'duration_hours': self.duration_hours or 1,
                'days': {d: {'available': False} for d in range(7)},
                'available_weekday_indices': [],
                'available_days_display': 'None configured',
                'start_time_str': '',
                'end_time_str': '',
                'summary': 'Availability not configured'
            }

        day_indices.sort()
        if day_indices == list(range(7)):
            days_display = 'Everyday (Monday to Sunday)'
        elif day_indices == list(range(5)):
            days_display = 'Monday to Friday'
        elif day_indices == list(range(6)):
            days_display = 'Monday to Saturday'
        elif day_indices == list(range(1, 7)):
            days_display = 'Tuesday to Sunday'
        else:
            days_display = ', '.join(DAY_NAMES[d] for d in day_indices)

        first_day = days_dict[day_indices[0]]
        st_str = first_day['start_str']
        et_str = first_day['end_str']
        summary = f"{days_display}, {st_str} – {et_str}"

        return {
            'has_availability': True,
            'duration_hours': self.duration_hours or 1,
            'days': days_dict,
            'available_weekday_indices': day_indices,
            'available_days_display': days_display,
            'start_time_str': st_str,
            'end_time_str': et_str,
            'summary': summary
        }

    def is_date_available(self, date_obj):
        """Check if date is valid (not past, weekday open). Returns (bool, str)."""
        if not date_obj:
            return False, "Preferred date is required."
        if date_obj < timezone.now().date():
            return False, "The requested date cannot be in the past."

        schedule = self.get_availability_schedule()
        if not schedule['has_availability']:
            return False, "Availability is not configured for this service."

        weekday = date_obj.weekday()
        if weekday not in schedule['available_weekday_indices']:
            provider_name = self.provider.profile.get_display_name() if hasattr(self.provider, 'profile') else self.provider.username
            day_name = DAY_NAMES[weekday]
            return False, f"{provider_name} is not available on {day_name}s. Available working days: {schedule['available_days_display']}."

        return True, ""

    def is_time_available(self, date_obj, time_obj):
        """Check if time is valid within hours, fits duration, and does not conflict. Returns (bool, str)."""
        date_ok, date_msg = self.is_date_available(date_obj)
        if not date_ok:
            return False, date_msg

        if not time_obj:
            return True, ""

        schedule = self.get_availability_schedule()
        weekday = date_obj.weekday()
        day_sched = schedule['days'].get(weekday)
        if not day_sched or not day_sched['available']:
            return False, "Provider is not available on this day."

        opening_time = day_sched['start_time']
        closing_time = day_sched['end_time']
        duration_hrs = self.duration_hours or 1

        if time_obj < opening_time:
            return False, f"Selected time ({time_obj.strftime('%I:%M %p')}) is before the provider's opening time ({opening_time.strftime('%I:%M %p')})."

        if time_obj >= closing_time:
            return False, f"Selected time ({time_obj.strftime('%I:%M %p')}) is at or after the provider's closing time ({closing_time.strftime('%I:%M %p')})."

        start_dt = datetime.combine(date_obj, time_obj)
        end_dt = start_dt + timedelta(hours=duration_hrs)
        closing_dt = datetime.combine(date_obj, closing_time)
        if end_dt > closing_dt:
            latest_start = (closing_dt - timedelta(hours=duration_hrs)).time()
            return False, (
                f"This service takes {duration_hrs} hour(s). A booking at {time_obj.strftime('%I:%M %p')} "
                f"would finish at {end_dt.strftime('%I:%M %p')}, after the provider's closing time ({closing_time.strftime('%I:%M %p')}). "
                f"The latest possible booking time is {latest_start.strftime('%I:%M %p')}."
            )

        now = timezone.now()
        if date_obj == now.date():
            current_time = now.time()
            if time_obj < current_time:
                return False, f"Selected time ({time_obj.strftime('%I:%M %p')}) has already passed for today."

        from bookings.models import ServiceRequest
        conflicting_requests = ServiceRequest.objects.filter(
            service__provider=self.provider,
            requested_date=date_obj,
            status__in=[ServiceRequest.STATUS_ACCEPTED, ServiceRequest.STATUS_INPROGRESS]
        )
        for req in conflicting_requests:
            if req.requested_time:
                req_dur = getattr(req.service, 'duration_hours', 1) or 1
                b_start = datetime.combine(date_obj, req.requested_time)
                b_end = b_start + timedelta(hours=req_dur)
                if start_dt < b_end and end_dt > b_start:
                    return False, (
                        f"This time slot conflicts with an existing confirmed booking for this provider "
                        f"({b_start.strftime('%I:%M %p')} – {b_end.strftime('%I:%M %p')}). Please choose another time."
                    )

        return True, ""

    def get_booked_slots(self, date_obj=None):
        from bookings.models import ServiceRequest
        qs = ServiceRequest.objects.filter(
            service__provider=self.provider,
            status__in=[ServiceRequest.STATUS_ACCEPTED, ServiceRequest.STATUS_INPROGRESS]
        )
        if date_obj:
            qs = qs.filter(requested_date=date_obj)
        else:
            qs = qs.filter(requested_date__gte=timezone.now().date())

        slots = []
        for req in qs.order_by('requested_date', 'requested_time'):
            if req.requested_time:
                req_dur = getattr(req.service, 'duration_hours', 1) or 1
                start_dt = datetime.combine(req.requested_date, req.requested_time)
                end_dt = start_dt + timedelta(hours=req_dur)
                slots.append({
                    'request_id': req.pk,
                    'service_id': req.service_id,
                    'service_title': req.service.title,
                    'date': req.requested_date.isoformat(),
                    'start_time': req.requested_time.strftime('%H:%M'),
                    'end_time': end_dt.time().strftime('%H:%M'),
                    'start_str': req.requested_time.strftime('%I:%M %p'),
                    'end_str': end_dt.time().strftime('%I:%M %p'),
                })
        return slots
