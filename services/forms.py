from django import forms
from PIL import Image, UnidentifiedImageError
from .models import Service, ServiceCategory, DAY_NAMES, parse_full_availability

WEEKDAY_CHOICES = [
    ('0', 'Monday'),
    ('1', 'Tuesday'),
    ('2', 'Wednesday'),
    ('3', 'Thursday'),
    ('4', 'Friday'),
    ('5', 'Saturday'),
    ('6', 'Sunday'),
]


class ServiceForm(forms.ModelForm):
    working_days = forms.MultipleChoiceField(
        choices=WEEKDAY_CHOICES,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        required=False,
        label="Available Working Days"
    )

    class Meta:
        model = Service
        fields = ['category', 'title', 'description', 'image', 'price', 'pricing_unit',
                  'city', 'area', 'start_time', 'end_time', 'duration_hours', 'availability', 'is_active']
        widgets = {
            'category': forms.Select(attrs={'class': 'form-select'}),
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Professional Home Plumbing'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4,
                                                  'placeholder': 'Describe what you offer, your experience, and what customers can expect...'}),
            'image': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0.00', 'min': '0', 'step': '0.01'}),
            'pricing_unit': forms.Select(attrs={'class': 'form-select'}),
            'city': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Bangalore'}),
            'area': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Koramangala'}),
            'start_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'duration_hours': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'max': '24', 'placeholder': '1'}),
            'availability': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Mon–Sat, 9 AM–6 PM'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].queryset = ServiceCategory.objects.filter(is_active=True)
        self.fields['category'].empty_label = "Select a category"
        self.fields['image'].required = False
        self.fields['start_time'].required = False
        self.fields['end_time'].required = False
        self.fields['duration_hours'].required = False
        self.fields['availability'].required = False

        if self.instance and self.instance.pk:
            sched = self.instance.get_availability_schedule()
            if sched['has_availability']:
                self.fields['working_days'].initial = [str(d) for d in sched['available_weekday_indices']]
                if not self.instance.start_time and sched['days']:
                    first_d = sched['days'][sched['available_weekday_indices'][0]]
                    self.fields['start_time'].initial = first_d['start_time']
                    self.fields['end_time'].initial = first_d['end_time']
        else:
            self.fields['working_days'].initial = ['0', '1', '2', '3', '4', '5']
            self.fields['start_time'].initial = '09:00'
            self.fields['end_time'].initial = '18:00'
            self.fields['duration_hours'].initial = 1

    def save(self, commit=True):
        instance = super().save(commit=False)
        working_days = self.cleaned_data.get('working_days')
        if working_days:
            instance.available_days = ','.join(sorted(working_days))
        elif not instance.available_days and instance.availability:
            parsed = parse_full_availability(instance.availability)
            if parsed:
                instance.available_days = ','.join(str(d) for d in sorted(parsed.keys()))

        if instance.available_days and instance.start_time and instance.end_time:
            sched = instance.get_availability_schedule()
            instance.availability = sched['summary']

        if commit:
            instance.save()
        return instance

    def clean_price(self):
        price = self.cleaned_data.get('price')
        if price is not None and price < 0:
            raise forms.ValidationError("Price cannot be negative.")
        return price

    def clean_image(self):
        image = self.cleaned_data.get('image')
        if not image:
            return image
        if image.size > 5 * 1024 * 1024:
            raise forms.ValidationError("Service images must be smaller than 5 MB.")
        if image.content_type not in {'image/jpeg', 'image/png', 'image/webp'}:
            raise forms.ValidationError("Upload a JPG, PNG, or WebP image.")
        try:
            with Image.open(image) as uploaded_image:
                uploaded_image.verify()
        except (UnidentifiedImageError, OSError):
            raise forms.ValidationError("Upload a valid image file.")
        image.seek(0)
        return image


class ServiceSearchForm(forms.Form):
    q = forms.CharField(required=False, label='Search',
                        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Search services...'}))
    category = forms.ModelChoiceField(queryset=ServiceCategory.objects.filter(is_active=True),
                                      required=False, empty_label="All Categories",
                                      widget=forms.Select(attrs={'class': 'form-select'}))
    city = forms.CharField(required=False, label='City',
                           widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'City'}))
    area = forms.CharField(required=False, label='Area',
                           widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Area'}))
    min_price = forms.DecimalField(required=False, label='Min Price', min_value=0,
                                   widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Min ₹'}))
    max_price = forms.DecimalField(required=False, label='Max Price', min_value=0,
                                   widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Max ₹'}))
    sort = forms.ChoiceField(
        required=False,
        choices=[('newest', 'Newest'), ('price_asc', 'Price: Low to High'),
                 ('price_desc', 'Price: High to Low'), ('rating', 'Top Rated')],
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    def clean(self):
        cleaned = super().clean()
        min_p = cleaned.get('min_price')
        max_p = cleaned.get('max_price')
        if min_p and max_p and min_p > max_p:
            raise forms.ValidationError("Minimum price cannot be greater than maximum price.")
        return cleaned
