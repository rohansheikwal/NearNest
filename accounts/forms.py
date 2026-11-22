from django import forms
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.contrib.auth.forms import (
    UserCreationForm,
    AuthenticationForm,
    PasswordChangeForm,
    PasswordResetForm,
    SetPasswordForm,
    _unicode_ci_compare,
)
from .models import Profile


class CustomerRegistrationForm(UserCreationForm):
    full_name = forms.CharField(max_length=150, required=True,
                                widget=forms.TextInput(attrs={'placeholder': 'Your full name'}))
    email = forms.EmailField(required=True,
                             widget=forms.EmailInput(attrs={'placeholder': 'your@email.com'}))
    city = forms.CharField(max_length=100, required=True,
                           widget=forms.TextInput(attrs={'placeholder': 'e.g. Bangalore'}))
    area = forms.CharField(max_length=100, required=False,
                           widget=forms.TextInput(attrs={'placeholder': 'e.g. Koramangala'}))
    phone = forms.CharField(max_length=20, required=False,
                            widget=forms.TextInput(attrs={'placeholder': '+91 98765 43210'}))

    class Meta:
        model = User
        fields = ['username', 'full_name', 'email', 'city', 'area', 'phone',
                  'password1', 'password2']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs['placeholder'] = 'Choose a username'
        self.fields['password1'].widget.attrs['placeholder'] = 'Create a password'
        self.fields['password2'].widget.attrs['placeholder'] = 'Confirm your password'
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
            profile = user.profile
            profile.role = Profile.ROLE_CUSTOMER
            profile.full_name = self.cleaned_data['full_name']
            profile.city = self.cleaned_data['city']
            profile.area = self.cleaned_data.get('area', '')
            profile.phone = self.cleaned_data.get('phone', '')
            profile.save()
        return user


class ProviderRegistrationForm(UserCreationForm):
    full_name = forms.CharField(max_length=150, required=True,
                                widget=forms.TextInput(attrs={'placeholder': 'Your full name'}))
    email = forms.EmailField(required=True,
                             widget=forms.EmailInput(attrs={'placeholder': 'your@email.com'}))
    city = forms.CharField(max_length=100, required=True,
                           widget=forms.TextInput(attrs={'placeholder': 'e.g. Bangalore'}))
    area = forms.CharField(max_length=100, required=False,
                           widget=forms.TextInput(attrs={'placeholder': 'e.g. Koramangala'}))
    phone = forms.CharField(max_length=20, required=False,
                            widget=forms.TextInput(attrs={'placeholder': '+91 98765 43210'}))
    bio = forms.CharField(max_length=500, required=False,
                          widget=forms.Textarea(attrs={'placeholder': 'Tell customers about yourself...', 'rows': 3}))
    skills = forms.CharField(max_length=500, required=False,
                             widget=forms.TextInput(attrs={'placeholder': 'e.g. Plumbing, Pipe fitting, Water heater repair'}))

    class Meta:
        model = User
        fields = ['username', 'full_name', 'email', 'city', 'area', 'phone',
                  'bio', 'skills', 'password1', 'password2']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs['placeholder'] = 'Choose a username'
        self.fields['password1'].widget.attrs['placeholder'] = 'Create a password'
        self.fields['password2'].widget.attrs['placeholder'] = 'Confirm your password'
        for field in self.fields.values():
            if not field.widget.attrs.get('class'):
                field.widget.attrs['class'] = 'form-control'
            else:
                field.widget.attrs['class'] = 'form-control'

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
            profile = user.profile
            profile.role = Profile.ROLE_PROVIDER
            profile.full_name = self.cleaned_data['full_name']
            profile.city = self.cleaned_data['city']
            profile.area = self.cleaned_data.get('area', '')
            profile.phone = self.cleaned_data.get('phone', '')
            profile.bio = self.cleaned_data.get('bio', '')
            profile.skills = self.cleaned_data.get('skills', '')
            profile.save()
        return user


class CustomLoginForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Username or Email',
        })
        self.fields['password'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Your password',
        })

    def clean(self):
        username_or_email = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')
        if username_or_email and password:
            user = User.objects.filter(email__iexact=username_or_email).first()
            login_username = user.username if user else username_or_email
            self.user_cache = authenticate(
                self.request,
                username=login_username,
                password=password,
            )
            if self.user_cache is None:
                raise forms.ValidationError(
                    self.error_messages['invalid_login'],
                    code='invalid_login',
                    params={'username': self.username_field.verbose_name},
                )
            self.confirm_login_allowed(self.user_cache)
        return self.cleaned_data


class CustomPasswordResetForm(PasswordResetForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['email'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'you@example.com',
        })

    def get_users(self, email):
        """Return active users matching email.
        Allow setting a password even if previously created via Google OAuth (unusable password).
        """
        UserModel = get_user_model()
        email_field_name = UserModel.get_email_field_name()
        active_users = UserModel._default_manager.filter(
            **{
                f"{email_field_name}__iexact": email,
                "is_active": True,
            }
        )
        return (
            u for u in active_users
            if _unicode_ci_compare(email, getattr(u, email_field_name))
        )


class CustomSetPasswordForm(SetPasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'


class ForgotPasswordRequestForm(forms.Form):
    email = forms.EmailField(
        label="Email address",
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your registered email address',
            'autocomplete': 'email',
            'autofocus': True,
        })
    )

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        if not email:
            raise ValidationError("Please provide a valid email address.")
        if not User.objects.filter(email__iexact=email, is_active=True).exists():
            raise ValidationError("No active account found with this email address. Please check your spelling or register.")
        return email


class OTPVerificationForm(forms.Form):
    otp = forms.CharField(
        label="Verification Code",
        max_length=6,
        min_length=6,
        widget=forms.TextInput(attrs={
            'class': 'form-control text-center',
            'placeholder': '------',
            'maxlength': '6',
            'autocomplete': 'one-time-code',
            'inputmode': 'numeric',
            'pattern': '[0-9]{6}',
            'style': 'font-size:1.75rem;letter-spacing:0.5rem;font-weight:700;font-family:monospace;max-width:280px;margin:0 auto;',
            'autofocus': True,
        })
    )

    def clean_otp(self):
        otp = self.cleaned_data.get('otp', '').strip()
        if not (otp.isdigit() and len(otp) == 6):
            raise ValidationError("Please enter the complete 6-digit verification code.")
        return otp


class ResetPasswordConfirmForm(forms.Form):
    new_password1 = forms.CharField(
        label="New Password",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your new password',
            'autocomplete': 'new-password',
            'id': 'id_new_password1',
        }),
        help_text="Password must be at least 8 characters long and contain letters and numbers.",
    )
    new_password2 = forms.CharField(
        label="Confirm New Password",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm your new password',
            'autocomplete': 'new-password',
            'id': 'id_new_password2',
        }),
    )

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get('new_password1')
        p2 = cleaned_data.get('new_password2')

        if p1 and p2:
            if p1 != p2:
                self.add_error('new_password2', "Passwords do not match. Please re-enter.")
            else:
                try:
                    validate_password(p1, self.user)
                except ValidationError as error:
                    self.add_error('new_password1', error)
        return cleaned_data

    def save(self):
        new_password = self.cleaned_data['new_password1']
        self.user.set_password(new_password)
        self.user.save()
        return self.user


class ProfileEditForm(forms.ModelForm):
    first_name = forms.CharField(max_length=150, required=False,
                                 widget=forms.TextInput(attrs={'class': 'form-control'}))
    last_name = forms.CharField(max_length=150, required=False,
                                widget=forms.TextInput(attrs={'class': 'form-control'}))
    email = forms.EmailField(required=True,
                             widget=forms.EmailInput(attrs={'class': 'form-control'}))

    class Meta:
        model = Profile
        fields = ['full_name', 'profile_image', 'bio', 'skills', 'city', 'area', 'phone']
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-control'}),
            'bio': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'skills': forms.TextInput(attrs={'class': 'form-control'}),
            'city': forms.TextInput(attrs={'class': 'form-control'}),
            'area': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'profile_image': forms.FileInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if not self.user or not self.user.profile.is_provider:
            self.fields.pop('skills')
        if self.user:
            self.fields['first_name'].initial = self.user.first_name
            self.fields['last_name'].initial = self.user.last_name
            self.fields['email'].initial = self.user.email

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if self.user and User.objects.filter(email=email).exclude(pk=self.user.pk).exists():
            raise forms.ValidationError("This email is already used by another account.")
        return email

    def save(self, commit=True):
        profile = super().save(commit=False)
        if self.user:
            self.user.first_name = self.cleaned_data['first_name']
            self.user.last_name = self.cleaned_data['last_name']
            self.user.email = self.cleaned_data['email']
            self.user.save()
        if commit:
            profile.save()
        return profile
