from django import forms
from .models import ServiceRequest
from django.utils import timezone


class ServiceRequestForm(forms.ModelForm):
    class Meta:
        model = ServiceRequest
        fields = ['requested_date', 'requested_time', 'service_location', 'work_description', 'notes']
        widgets = {
            'requested_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'requested_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'service_location': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 2,
                'placeholder': 'e.g. Flat 4B, Sunrise Apartments, MG Road'
            }),
            'work_description': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 4,
                'placeholder': 'Describe the work you need — be specific so the provider can help you effectively...'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 2,
                'placeholder': 'Any special instructions? (optional)'
            }),
        }

    def __init__(self, *args, service=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.service = service
        today_iso = timezone.localdate().isoformat()
        self.fields['requested_date'].widget.attrs['min'] = today_iso

        if self.service:
            schedule = self.service.get_availability_schedule()
            if schedule.get('has_availability'):
                self.fields['requested_date'].widget.attrs['data-available-days'] = ','.join(
                    str(d) for d in schedule['available_weekday_indices']
                )
                self.fields['requested_date'].widget.attrs['data-service-id'] = str(self.service.pk)
                self.fields['requested_time'].widget.attrs['data-start-time'] = schedule.get('start_time_str', '')
                self.fields['requested_time'].widget.attrs['data-end-time'] = schedule.get('end_time_str', '')
                self.fields['requested_time'].widget.attrs['data-duration'] = str(self.service.duration_hours or 1)

    def clean_requested_date(self):
        date = self.cleaned_data.get('requested_date')
        if not date:
            return date
        if date < timezone.localdate():
            raise forms.ValidationError("The requested date cannot be in the past.")
        if self.service:
            is_valid, msg = self.service.is_date_available(date)
            if not is_valid:
                raise forms.ValidationError(msg)
        return date

    def clean_requested_time(self):
        time_val = self.cleaned_data.get('requested_time')
        date_val = self.cleaned_data.get('requested_date')
        if not time_val:
            return time_val
        if self.service and date_val:
            is_valid, msg = self.service.is_time_available(date_val, time_val)
            if not is_valid:
                raise forms.ValidationError(msg)
        return time_val

    def clean(self):
        cleaned_data = super().clean()
        date_val = cleaned_data.get('requested_date')
        time_val = cleaned_data.get('requested_time')
        if self.service and date_val and time_val:
            is_valid, msg = self.service.is_time_available(date_val, time_val)
            if not is_valid and 'requested_time' not in self.errors:
                self.add_error('requested_time', msg)
        return cleaned_data
