"""
Context processor that injects the authenticated user's currency symbol
and currency code into every template context automatically.
"""
from .models import UserProfile, CURRENCY_SYMBOLS


def currency(request):
    """
    Injects `currency_symbol` and `currency_code` into every template.
    Falls back to INR if the user has no profile yet.
    """
    if request.user.is_authenticated:
        try:
            profile = request.user.profile
        except UserProfile.DoesNotExist:
            # Lazy-create profile if signal hasn't fired (e.g. pre-existing users)
            profile = UserProfile.objects.create(user=request.user)
        return {
            'currency_symbol': CURRENCY_SYMBOLS.get(profile.currency, '₹'),
            'currency_code': profile.currency,
        }
    return {
        'currency_symbol': '₹',
        'currency_code': 'INR',
    }
