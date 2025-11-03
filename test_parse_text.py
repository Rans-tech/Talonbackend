import requests
import json

# The email content
email_text = """This Marriott.com reservation email has been forwarded to you by COOK RANDY (MR.COOK.RANDY@GMAIL.COM)

Walt Disney World Dolphin

Guest name: COOK RANDY
Confirmation Number: 73566291
Check-in: Friday, November 07, 2025
Check-out: Wednesday, November 12, 2025
Number of guests: 2
Number of rooms: 1

Room Preferences & Description
Room 0:
No room preferences were selected.

This hotel has a smoke-free policy

Summary of Charges:

1room(s) for 5night(s)

Friday, November 07, 2025 - 469.00
Saturday, November 08, 2025 - 455.00
Sunday, November 09, 2025 - 455.00
Monday, November 10, 2025 - 469.00
Tuesday, November 11, 2025 - 469.00

Total cash rate-2317.00

Resort Fee-250.00

Estimated government taxes and fees - 320.88

Total for stay in hotel's currency - 2887.88 USD

,Valet parking, fee: 56.00 USD daily,On-site parking, fee: 38.00 USD daily

Rate Rules:
Cancelling Your Reservation
You may cancel your reservation for no charge before 11:59 PM local hotel time on November 2, 2025 (5 day[s] before arrival).Please note that we will assess a fee of 527.63 USD if you must cancel after this deadline. If you have made a prepayment, we will retain all or part of your prepayment. If not, we will charge your credit card.

Modifying Your Reservation
Please note that a change in the length or dates of your reservation may result in a rate change."""

# API endpoint
url = "https://talonbackend-production.up.railway.app/api/documents/parse-text"

# Request payload
payload = {
    "text_content": email_text,
    "trip_id": "ed4387ee-75e4-42e9-8fee-838da29c547d"
}

print("Testing copy/paste text parsing...")
print(f"URL: {url}")
print(f"Trip ID: {payload['trip_id']}")
print(f"Text length: {len(email_text)} chars")
print("\nSending request...")

try:
    response = requests.post(url, json=payload, timeout=60)
    print(f"\nStatus Code: {response.status_code}")
    print(f"\nResponse:")
    print(json.dumps(response.json(), indent=2))
except Exception as e:
    print(f"\nError: {e}")
