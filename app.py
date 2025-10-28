from flask import Flask, request, jsonify
from flask_cors import CORS
from talon.agent import TalonAgent
from talon.monitoring import WeatherMonitor, PriceMonitor
from talon.document_parser import DocumentParser
from talon.database import db_client
import os
import base64
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
# Enable CORS for all origins (including localhost for development)
CORS(app, resources={
    r"/api/*": {
        "origins": ["http://localhost:5173", "http://localhost:5174", "*"],
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})

# Initialize TALON agent
talon = TalonAgent()
weather_monitor = WeatherMonitor()
price_monitor = PriceMonitor()
document_parser = DocumentParser()

@app.route('/api/talon/status', methods=['GET'])
def get_talon_status():
    """Get current TALON status and metrics"""
    return jsonify({
        'status': 'active',
        'platforms_unified': 12,
        'disruptions_prevented': 2400,
        'active_monitoring': 12,
        'system_health': 97.4,
        'current_activity': talon.get_current_activity()
    })

@app.route('/api/talon/chat', methods=['POST'])
def talon_chat():
    """Handle chat requests to TALON"""
    data = request.json
    message = data.get('message', '')
    
    response = talon.process_message(message)
    return jsonify({'response': response})

@app.route('/api/monitoring/weather', methods=['GET'])
def get_weather_monitoring():
    """Get weather monitoring data"""
    location = request.args.get('location', 'Orlando, FL')
    return jsonify(weather_monitor.get_status(location))

@app.route('/api/monitoring/prices', methods=['GET'])
def get_price_monitoring():
    """Get price monitoring data"""
    return jsonify(price_monitor.get_status())

@app.route('/api/documents/parse', methods=['POST'])
def parse_document():
    """Parse uploaded travel document and create trip elements"""
    try:
        data = request.json

        # Extract required fields
        file_content = data.get('file_content')  # Base64 encoded
        file_type = data.get('file_type')
        trip_id = data.get('trip_id')
        document_id = data.get('document_id')  # Optional: if you want to link back

        if not file_content or not file_type or not trip_id:
            return jsonify({
                'success': False,
                'error': 'Missing required fields: file_content, file_type, trip_id'
            }), 400

        # Verify trip exists
        print(f"Looking for trip_id: {trip_id}")
        trip = db_client.get_trip(trip_id)
        print(f"Trip found: {trip}")
        if not trip:
            return jsonify({
                'success': False,
                'error': f'Trip not found with id: {trip_id}'
            }), 404

        # Parse the document
        parse_result = document_parser.parse_travel_document(file_content, file_type)

        if not parse_result['success']:
            return jsonify(parse_result), 500

        parsed_data = parse_result['data']
        created_elements = []

        # Create trip elements from parsed data
        if 'elements' in parsed_data:
            for element_data in parsed_data['elements']:
                try:
                    # Validate and clean the element data
                    validated_element = document_parser.validate_element_data(element_data)

                    # Create the trip element in the database
                    created_element = db_client.create_trip_element(trip_id, validated_element)

                    if created_element:
                        created_elements.append(created_element)

                        # Link document to element if document_id provided
                        if document_id and len(created_elements) == 1:  # Link to first element
                            db_client.update_trip_document(document_id, created_element['id'])
                except Exception as e:
                    print(f"Error creating element: {e}")
                    continue

        return jsonify({
            'success': True,
            'message': f'Successfully created {len(created_elements)} trip element(s)',
            'elements': created_elements,
            'metadata': parsed_data.get('metadata', {}),
            'document_type': parsed_data.get('document_type')
        })

    except Exception as e:
        print(f"Error in parse_document: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
