import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

class SupabaseDB:
    def __init__(self):
        url: str = os.environ.get("SUPABASE_URL", "").strip()
        key: str = os.environ.get("SUPABASE_KEY", "").strip()

        # Debug logging
        print(f"Supabase URL length: {len(url)}")
        print(f"Supabase URL (first 30 chars): {url[:30] if url else 'EMPTY'}")
        print(f"Supabase KEY length: {len(key)}")
        print(f"Supabase KEY (first 30 chars): {key[:30] if key else 'EMPTY'}")

        if not url or not key:
            raise ValueError("Supabase URL or Key not found in environment variables.")

        self.client: Client = create_client(url, key)

    def get_user_profile(self, user_id):
        """Fetches a user profile from the database."""
        try:
            response = self.client.table('profiles').select("*").eq('id', user_id).execute()
            return response.data
        except Exception as e:
            print(f"Error fetching user profile: {e}")
            return None

    def update_trip_data(self, trip_id, data):
        """Updates trip data in the database."""
        try:
            response = self.client.table('trips').update(data).eq('id', trip_id).execute()
            return response.data
        except Exception as e:
            print(f"Error updating trip data: {e}")
            return None

    def check_duplicate_element(self, trip_id, element_data):
        """Check if an element with the same key details already exists for this trip.

        For flights: Check confirmation + flight details + date (allow multiple flights with same confirmation)
        For hotels/other: Check confirmation only (don't allow duplicates)
        """
        confirmation_number = element_data.get('confirmation_number')
        if not confirmation_number:
            return None

        try:
            element_type = element_data.get('type')

            # For flights, be more specific - same confirmation can have multiple flights
            if element_type == 'flight':
                # Check for exact match: same confirmation AND same start time AND same location
                start_datetime = element_data.get('start_datetime')
                location = element_data.get('location')

                if not start_datetime:
                    return None  # Can't check duplicates without date

                response = self.client.table('trip_elements').select("*").eq('trip_id', trip_id).eq('type', 'flight').eq('confirmation_number', confirmation_number).eq('start_datetime', start_datetime).execute()

                # If we find a flight with same confirmation AND same departure time, it's a duplicate
                if response.data and len(response.data) > 0:
                    return response.data[0]
                return None
            else:
                # For non-flights (hotel, car, etc), confirmation number alone is enough
                response = self.client.table('trip_elements').select("*").eq('trip_id', trip_id).eq('confirmation_number', confirmation_number).execute()
                return response.data[0] if response.data else None

        except Exception as e:
            print(f"Error checking duplicate: {e}")
            return None

    def create_trip_element(self, trip_id, element_data):
        """Creates a new trip element in the database."""
        try:
            # Check for duplicate based on element type
            confirmation_number = element_data.get('confirmation_number')
            if confirmation_number:
                existing = self.check_duplicate_element(trip_id, element_data)
                if existing:
                    print(f"Duplicate found: {element_data.get('type')} with confirmation #{confirmation_number} already exists")
                    return existing  # Return existing element instead of creating duplicate

            # Prepare the data for insertion
            insert_data = {
                'trip_id': trip_id,
                'type': element_data.get('type'),
                'title': element_data.get('title'),
                'start_datetime': element_data.get('start_datetime'),
                'end_datetime': element_data.get('end_datetime'),
                'location': element_data.get('location'),
                'confirmation_number': confirmation_number,
                'price': element_data.get('price'),
                'status': element_data.get('status', 'confirmed'),
                'details': element_data.get('details', {})
            }

            response = self.client.table('trip_elements').insert(insert_data).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            print(f"Error creating trip element: {e}")
            return None

    def update_trip_document(self, document_id, element_id):
        """Links a document to a trip element."""
        try:
            response = self.client.table('trip_documents').update({
                'trip_element_id': element_id
            }).eq('id', document_id).execute()
            return response.data
        except Exception as e:
            print(f"Error updating trip document: {e}")
            return None

    def get_trip(self, trip_id):
        """Fetches a trip from the database."""
        try:
            response = self.client.table('trips').select("*").eq('id', trip_id).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            print(f"Error fetching trip: {e}")
            return None

# Initialize a single instance for the app to use
db_client = SupabaseDB()
