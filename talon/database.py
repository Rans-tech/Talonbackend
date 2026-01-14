import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

class SupabaseDB:
    def __init__(self):
        url: str = os.environ.get("SUPABASE_URL", "").strip()
        key: str = os.environ.get("SUPABASE_KEY", "").strip()

        print(f"Supabase URL length: {len(url)}")
        print(f"Supabase URL (first 30 chars): {url[:30] if url else 'EMPTY'}")
        print(f"Supabase KEY length: {len(key)}")
        print(f"Supabase KEY (first 30 chars): {key[:30] if key else 'EMPTY'}")

        if not url or not key:
            raise ValueError("Supabase URL or Key not found in environment variables.")

        self.client: Client = create_client(url, key)

    def get_user_profile(self, user_id):
        try:
            response = self.client.table('profiles').select("*").eq('id', user_id).execute()
            return response.data
        except Exception as e:
            print(f"Error fetching user profile: {e}")
            return None

    def update_trip_data(self, trip_id, data):
        try:
            response = self.client.table('trips').update(data).eq('id', trip_id).execute()
            return response.data
        except Exception as e:
            print(f"Error updating trip data: {e}")
            return None

    def check_duplicate_element(self, trip_id, element_data):
        confirmation_number = element_data.get('confirmation_number')
        if not confirmation_number:
            return None
        try:
            element_type = element_data.get('type')
            start_datetime = element_data.get('start_datetime')

            # For flights and hotels, use start_datetime to differentiate
            # (e.g., hotel check-in vs check-out have same confirmation but different times)
            if element_type in ['flight', 'hotel', 'hotel_checkin', 'hotel_checkout']:
                if not start_datetime:
                    return None
                # Map hotel subtypes to 'hotel' for DB query
                db_type = 'hotel' if element_type in ['hotel_checkin', 'hotel_checkout'] else element_type
                response = self.client.table('trip_elements').select("*").eq('trip_id', trip_id).eq('type', db_type).eq('confirmation_number', confirmation_number).eq('start_datetime', start_datetime).execute()
                if response.data and len(response.data) > 0:
                    return response.data[0]
                return None
            else:
                response = self.client.table('trip_elements').select("*").eq('trip_id', trip_id).eq('confirmation_number', confirmation_number).execute()
                return response.data[0] if response.data else None
        except Exception as e:
            print(f"Error checking duplicate: {e}")
            return None

    def create_trip_element(self, trip_id, element_data):
        try:
            confirmation_number = element_data.get('confirmation_number')
            if confirmation_number:
                existing = self.check_duplicate_element(trip_id, element_data)
                if existing:
                    print(f"Duplicate found: {element_data.get('type')} with confirmation #{confirmation_number} already exists")
                    return existing

            # Get original type and map to DB-compatible type
            original_type = element_data.get('type')
            
            # Map hotel subtypes to 'hotel' for database compatibility
            # but store the subtype in details for frontend display
            db_type_map = {
                'hotel_checkin': 'hotel',
                'hotel_checkout': 'hotel',
            }
            db_type = db_type_map.get(original_type, original_type)
            
            # Store the original subtype in details if it was mapped
            details = element_data.get('details', {})
            if original_type in db_type_map:
                details['hotel_event_type'] = original_type  # 'hotel_checkin' or 'hotel_checkout'
            
            insert_data = {
                'trip_id': trip_id,
                'type': db_type,
                'title': element_data.get('title'),
                'start_datetime': element_data.get('start_datetime'),
                'end_datetime': element_data.get('end_datetime'),
                'location': element_data.get('location'),
                'confirmation_number': confirmation_number,
                'price': element_data.get('price'),
                'status': element_data.get('status', 'confirmed'),
                'details': details
            }
            response = self.client.table('trip_elements').insert(insert_data).execute()
            if response.data:
                print(f"Created trip element: {original_type} -> DB type: {db_type}")
            return response.data[0] if response.data else None
        except Exception as e:
            print(f"Error creating trip element: {e}")
            return None

    def update_trip_document(self, document_id, element_id):
        try:
            response = self.client.table('trip_documents').update({'trip_element_id': element_id}).eq('id', document_id).execute()
            return response.data
        except Exception as e:
            print(f"Error updating trip document: {e}")
            return None

    def get_trip(self, trip_id):
        try:
            response = self.client.table('trips').select("*").eq('id', trip_id).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            print(f"Error fetching trip: {e}")
            return None

    def create_expense_from_element(self, trip_id, user_id, element_data, element_id):
        """Creates an expense record linked to a trip element with currency conversion."""
        try:
            from talon.currency_service import currency_service

            original_amount = element_data.get('price')
            if not original_amount or original_amount <= 0:
                return None

            # Get currency from parsed data (default USD)
            original_currency = (element_data.get('currency') or 'USD').upper()

            # Convert to USD if different currency
            if original_currency != 'USD':
                try:
                    conversion = currency_service.convert_amount(original_amount, original_currency, 'USD')
                    amount_usd = round(conversion['converted_amount'], 2)
                    print(f"Currency conversion: {original_amount} {original_currency} -> {amount_usd} USD")
                except Exception as conv_err:
                    print(f"Currency conversion failed: {conv_err}, using original amount")
                    amount_usd = original_amount
            else:
                amount_usd = original_amount

            element_type = element_data.get('type', 'other')
            category_map = {
                'flight': 'flight',
                'hotel': 'accommodation',
                'hotel_checkin': 'accommodation',
                'hotel_checkout': 'accommodation',
                'dining': 'food_dining',
                'activity': 'tours_activities',
                'transport': 'transportation',
                'car': 'transportation',
                'other': 'other'
            }
            category = category_map.get(element_type, 'other')

            expense_date = element_data.get('start_datetime')
            if expense_date:
                expense_date = expense_date[:10] if len(expense_date) > 10 else expense_date
            else:
                from datetime import date
                expense_date = date.today().isoformat()

            conf_num = element_data.get('confirmation_number', 'N/A')

            # Build notes with currency info
            notes = f"Auto-created from parsed document. Confirmation: {conf_num}"
            if original_currency != 'USD':
                notes += f" | Original: {original_amount} {original_currency}"

            expense_data = {
                'trip_id': trip_id,
                'user_id': user_id,
                'amount': amount_usd,
                'original_amount': original_amount,
                'original_currency': original_currency,
                'category': category,
                'description': element_data.get('title', ''),
                'expense_date': expense_date,
                'notes': notes,
                'source': 'parsed',
                'trip_element_id': element_id
            }

            response = self.client.table('expenses').insert(expense_data).execute()
            if response.data:
                if original_currency != 'USD':
                    print(f"Created expense: {original_amount} {original_currency} = ${amount_usd} USD ({category})")
                else:
                    print(f"Created expense: ${amount_usd} USD ({category})")
                return response.data[0]
            return None
        except Exception as e:
            print(f"Error creating expense from element: {e}")
            return None

    def check_expense_exists_for_element(self, element_id):
        """Check if an expense already exists for a trip element."""
        try:
            response = self.client.table('expenses').select('id').eq('trip_element_id', element_id).execute()
            return len(response.data) > 0 if response.data else False
        except Exception as e:
            print(f"Error checking expense existence: {e}")
            return False

db_client = SupabaseDB()
