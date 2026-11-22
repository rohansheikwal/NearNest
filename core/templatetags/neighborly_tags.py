"""
Custom template filters for Neighborly.
Usage: {% load neighborly_tags %} in templates.
"""
from django import template

register = template.Library()


@register.filter
def split(value, delimiter=','):
    """Split a string by delimiter and return a list."""
    if not value:
        return []
    return [item for item in value.split(delimiter)]


@register.filter
def trim(value):
    """Strip whitespace from a string."""
    if isinstance(value, str):
        return value.strip()
    return value


@register.filter
def category_image(slug):
    """Return the local service-card fallback for a category slug."""
    images = {
        'plumbing': 'images/category-plumbing.jpg',
        'electrical': 'images/category-electrical.jpg',
        'electrical-services': 'images/category-electrical.jpg',
        'home-cleaning': 'images/category-cleaning.jpg',
        'cleaning': 'images/category-cleaning.jpg',
        'carpentry': 'images/category-carpentry.jpg',
        'painting': 'images/category-painting.jpg',
        'gardening': 'images/category-gardening.jpg',
        'gardening-landscaping': 'images/category-gardening.jpg',
        'appliance-repair': 'images/category-appliance-repair.jpg',
        'computer-repair': 'images/category-computer-repair.jpg',
        'home-tutoring': 'images/category-home-tutoring.jpg',
        'tailoring': 'images/category-tailoring.jpg',
    }
    return images.get(slug, 'images/provider-tools.jpg')


@register.simple_tag
def service_image(service, section='explore', index=0):
    """Return a section-specific local photograph for a service card."""
    pools = {
        'community': {
            'plumbing': ('images/community-plumber.jpg', 'images/community-plumber-alt.jpg'),
            'electrical': 'images/community-electrician.jpg',
            'home-cleaning': 'images/community-cleaner.jpg',
            'carpentry': 'images/community-carpenter.jpg',
            'home-tutoring': 'images/community-tutor.jpg',
            'default': 'images/community-service.jpg',
        },
        'explore': {
            'plumbing': ('images/explore-plumber.jpg', 'images/explore-plumber-alt.jpg'),
            'electrical': 'images/explore-electrician.jpg',
            'home-cleaning': 'images/explore-cleaner.jpg',
            'carpentry': 'images/explore-carpenter.jpg',
            'home-tutoring': 'images/explore-tutor.jpg',
            'default': 'images/explore-service.jpg',
        },
    }
    pool = pools.get(section, pools['explore'])
    slug = service.category.slug if service.category else ''
    image = pool.get(slug, pool['default'])
    if isinstance(image, tuple):
        return image[(service.pk // 2) % len(image)]
    return image


@register.filter
def star_range(value):
    """Return range for star rating display."""
    try:
        return range(1, int(value) + 1)
    except (TypeError, ValueError):
        return range(0)


@register.filter
def subtract(value, arg):
    """Subtract arg from value."""
    try:
        return int(value) - int(arg)
    except (TypeError, ValueError):
        return value


@register.simple_tag
def active_if(request, url_name):
    """Return 'active' CSS class if the current URL matches."""
    if hasattr(request, 'resolver_match') and request.resolver_match:
        if request.resolver_match.url_name == url_name:
            return 'active'
    return ''
