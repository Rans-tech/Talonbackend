"""
Currency conversion service using free exchange rate API
"""
import os
import requests
from datetime import datetime, timedelta
from functools import lru_cache
import json

class CurrencyService:
    """Service for currency conversion with caching"""

    # Common currency codes
    SUPPORTED_CURRENCIES = [
        'USD', 'EUR', 'GBP', 'JPY', 'CAD', 'AUD', 'CHF', 'CNY', 'INR', 'MXN',
        'BRL', 'KRW', 'SGD', 'HKD', 'NOK', 'SEK', 'DKK', 'NZD', 'ZAR', 'THB',
        'PLN', 'CZK', 'HUF', 'ILS', 'TRY', 'AED', 'SAR', 'PHP', 'MYR', 'IDR'
    ]

    # Currency symbols mapping
    CURRENCY_SYMBOLS = {
        'USD': '$', 'EUR': '€', 'GBP': '£', 'JPY': '¥', 'CAD': 'C$', 'AUD': 'A$',
        'CHF': 'CHF', 'CNY': '¥', 'INR': '₹', 'MXN': '$', 'BRL': 'R$', 'KRW': '₩',
        'SGD': 'S$', 'HKD': 'HK$', 'NOK': 'kr', 'SEK': 'kr', 'DKK': 'kr', 'NZD': 'NZ$',
        'ZAR': 'R', 'THB': '฿', 'PLN': 'zł', 'CZK': 'Kč', 'HUF': 'Ft', 'ILS': '₪',
        'TRY': '₺', 'AED': 'د.إ', 'SAR': '﷼', 'PHP': '₱', 'MYR': 'RM', 'IDR': 'Rp'
    }

    def __init__(self):
        self.api_key = os.getenv('EXCHANGE_RATE_API_KEY', '')
        self.base_url = 'https://api.exchangerate-api.com/v4/latest'  # Free tier, no key needed
        self._cache = {}
        self._cache_expiry = {}
        self._cache_duration = timedelta(hours=1)  # Cache rates for 1 hour

    def _get_cached_rates(self, base_currency: str) -> dict:
        """Get cached exchange rates if still valid"""
        cache_key = base_currency.upper()
        if cache_key in self._cache:
            if datetime.now() < self._cache_expiry.get(cache_key, datetime.min):
                return self._cache[cache_key]
        return None

    def _set_cached_rates(self, base_currency: str, rates: dict):
        """Cache exchange rates"""
        cache_key = base_currency.upper()
        self._cache[cache_key] = rates
        self._cache_expiry[cache_key] = datetime.now() + self._cache_duration

    def get_exchange_rate(self, from_currency: str, to_currency: str = 'USD') -> float:
        """
        Get exchange rate from one currency to another

        Args:
            from_currency: Source currency code (e.g., 'EUR')
            to_currency: Target currency code (default: 'USD')

        Returns:
            float: Exchange rate (multiply source amount by this to get target amount)
        """
        from_currency = from_currency.upper()
        to_currency = to_currency.upper()

        # Same currency, no conversion needed
        if from_currency == to_currency:
            return 1.0

        try:
            # Check cache first
            cached_rates = self._get_cached_rates(from_currency)
            if cached_rates and to_currency in cached_rates:
                return cached_rates[to_currency]

            # Fetch from API
            response = requests.get(
                f'{self.base_url}/{from_currency}',
                timeout=10
            )
            response.raise_for_status()
            data = response.json()

            rates = data.get('rates', {})
            self._set_cached_rates(from_currency, rates)

            if to_currency in rates:
                return rates[to_currency]
            else:
                print(f"Currency {to_currency} not found in rates")
                return 1.0

        except requests.RequestException as e:
            print(f"Error fetching exchange rate: {e}")
            # Return fallback rates for common currencies
            return self._get_fallback_rate(from_currency, to_currency)
        except Exception as e:
            print(f"Unexpected error in currency conversion: {e}")
            return 1.0

    def _get_fallback_rate(self, from_currency: str, to_currency: str) -> float:
        """Fallback rates when API is unavailable (approximate rates as of 2024)"""
        fallback_usd_rates = {
            'EUR': 1.09, 'GBP': 1.27, 'JPY': 0.0067, 'CAD': 0.74, 'AUD': 0.65,
            'CHF': 1.13, 'CNY': 0.14, 'INR': 0.012, 'MXN': 0.058, 'BRL': 0.20,
            'KRW': 0.00075, 'SGD': 0.74, 'HKD': 0.13, 'NOK': 0.093, 'SEK': 0.095,
            'DKK': 0.15, 'NZD': 0.60, 'ZAR': 0.055, 'THB': 0.028, 'PLN': 0.25,
            'AED': 0.27, 'USD': 1.0
        }

        if to_currency == 'USD':
            return fallback_usd_rates.get(from_currency, 1.0)
        elif from_currency == 'USD':
            rate = fallback_usd_rates.get(to_currency, 1.0)
            return 1.0 / rate if rate else 1.0
        else:
            # Convert through USD
            from_to_usd = fallback_usd_rates.get(from_currency, 1.0)
            usd_to_target = fallback_usd_rates.get(to_currency, 1.0)
            return from_to_usd / usd_to_target if usd_to_target else 1.0

    def convert_amount(self, amount: float, from_currency: str, to_currency: str = 'USD') -> dict:
        """
        Convert an amount from one currency to another

        Args:
            amount: The amount to convert
            from_currency: Source currency code
            to_currency: Target currency code (default: 'USD')

        Returns:
            dict: {
                'original_amount': float,
                'original_currency': str,
                'converted_amount': float,
                'converted_currency': str,
                'exchange_rate': float,
                'conversion_date': str (ISO format)
            }
        """
        from_currency = from_currency.upper()
        to_currency = to_currency.upper()

        rate = self.get_exchange_rate(from_currency, to_currency)
        converted = round(amount * rate, 2)

        return {
            'original_amount': amount,
            'original_currency': from_currency,
            'converted_amount': converted,
            'converted_currency': to_currency,
            'exchange_rate': round(rate, 6),
            'conversion_date': datetime.now().isoformat()
        }

    def detect_currency_from_symbol(self, text: str) -> str:
        """
        Detect currency from common symbols in text

        Args:
            text: Text containing currency symbol

        Returns:
            str: Detected currency code or 'USD' as default
        """
        text = text.strip()

        # Check for currency codes first (e.g., "EUR 50" or "50 EUR")
        for code in self.SUPPORTED_CURRENCIES:
            if code in text.upper():
                return code

        # Check for symbols
        symbol_to_currency = {
            '€': 'EUR', '£': 'GBP', '¥': 'JPY', '₹': 'INR', '₩': 'KRW',
            '฿': 'THB', 'zł': 'PLN', '₪': 'ILS', '₺': 'TRY', '₱': 'PHP',
            'R$': 'BRL', 'C$': 'CAD', 'A$': 'AUD', 'S$': 'SGD', 'HK$': 'HKD',
            'NZ$': 'NZD', 'CHF': 'CHF', 'kr': 'SEK',  # Could be NOK, SEK, DKK
        }

        for symbol, currency in symbol_to_currency.items():
            if symbol in text:
                return currency

        # Default to USD if $ is found or no symbol detected
        if '$' in text:
            return 'USD'

        return 'USD'

    def get_currency_symbol(self, currency_code: str) -> str:
        """Get the symbol for a currency code"""
        return self.CURRENCY_SYMBOLS.get(currency_code.upper(), currency_code)

    def format_amount(self, amount: float, currency_code: str) -> str:
        """Format an amount with its currency symbol"""
        symbol = self.get_currency_symbol(currency_code)
        if currency_code in ['JPY', 'KRW', 'IDR']:
            return f"{symbol}{int(amount):,}"
        return f"{symbol}{amount:,.2f}"


# Singleton instance
currency_service = CurrencyService()
