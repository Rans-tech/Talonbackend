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

    def create_trip_element(self, trip_id, element_data):
        """Creates a new trip element in the database."""
        try:
            # Prepare the data for insertion
            insert_data = {
                'trip_id': trip_id,
                'type': element_data.get('type'),
                'title': element_data.get('title'),
                'start_datetime': element_data.get('start_datetime'),
                'end_datetime': element_data.get('end_datetime'),
                'location': element_data.get('location'),
                'confirmation_number': element_data.get('confirmation_number'),
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
