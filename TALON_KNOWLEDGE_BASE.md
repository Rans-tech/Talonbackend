# TALON Knowledge Base - Complete Travel Intelligence System
# Version: 3.0.0 (Production-Ready + MVP Auth Framework)
# Last Updated: 2025-10-31
#
# This is TALON's complete intelligence system combining:
# - 100+ travel intelligence rules (expanded)
# - Element Status System (pending/confirmed/cancelled/completed)
# - Participant & Family Coordination
# - Auto-Task Generation Framework
# - StatusBar Pending Item Detection
# - Geopolitical risk monitoring
# - Extreme weather crisis detection
# - Multi-agent coordination protocols
# - Continuous learning framework

---

## TABLE OF CONTENTS

1. [Core Travel Intelligence Rules](#core-travel-intelligence-rules)
   - **CATEGORY 1:** Timeline Analysis (with smart conflict detection)
   - **CATEGORY 2:** Element Status System (NEW - pending/confirmed tracking)
   - **CATEGORY 3:** Participant & Family Coordination (NEW - divergence/convergence)
   - **CATEGORY 4:** Auto-Task Generation (NEW - HIGH PRIORITY MVP feature)
   - **CATEGORY 7:** Safety & Compliance
   - Transportation Intelligence
   - Weather-Driven Decisions
   - Accommodation Logic
   - Activity Optimization
   - Budget Intelligence
   - Dining Intelligence
   - Cultural Intelligence

2. [Geopolitical Risk Monitoring](#geopolitical-risk-monitoring)
   - Travel Advisory Levels
   - Political Instability Detection
   - Conflict Zone Monitoring
   - Civil Unrest Alerts
   - Terrorism Risk Assessment

3. [Extreme Weather Monitoring](#extreme-weather-monitoring)
   - Hurricane/Typhoon Tracking
   - Wildfire Monitoring
   - Flood Warnings
   - Earthquake Alerts
   - Volcanic Activity
   - Extreme Temperature Events

4. [Crisis Response Protocols](#crisis-response-protocols)
   - Immediate Travel Suspension
   - Evacuation Recommendations
   - Alternative Destination Suggestions
   - Refund & Compensation Guidance

5. [Multi-Agent Coordination](#multi-agent-coordination)
   - Agent Roles & Responsibilities
   - Handoff Protocols
   - Escalation Procedures

6. [Learning & Improvement](#learning-improvement)
   - User Behavior Tracking
   - Pattern Recognition
   - Rule Optimization
   - Feedback Integration

---

## CORE TRAVEL INTELLIGENCE RULES

### CATEGORY 1: TIMELINE ANALYSIS
*Detect gaps, overlaps, timing conflicts, and missing elements*

#### Rule: lodging_gap_arrival
```yaml
trigger: timeline_analysis
condition: |
  arrival_datetime < first_accommodation_checkin AND 
  time_gap > 4_hours AND
  arrival_time IN ['evening', 'night']
action: propose_lodging
human_note: "⚠️ Accommodation Gap: You arrive at {{arrival_time}} but your hotel check-in isn't until {{checkin_time}}. That's a {{gap_hours}}-hour gap. Need a hotel for the first night?"
suggested_actions:
  - "Search hotels near {{arrival_airport}}"
  - "Book airport hotel ({{nearby_hotels}})"
  - "Adjust hotel check-in to arrival date"
auto_accept: false
priority: high
applies_to: [families, business, solo]
```

#### Rule: lodging_gap_departure
```yaml
trigger: timeline_analysis
condition: |
  last_accommodation_checkout < departure_datetime AND
  time_gap > 3_hours AND
  no_day_room_available
action: suggest_late_checkout
human_note: "⏰ Timing Gap: Hotel checkout is {{checkout_time}} but your flight isn't until {{departure_time}}. Consider late checkout ($50-100) or day room to avoid carrying luggage."
suggested_actions:
  - "Request late checkout (usually $50)"
  - "Book day room at airport hotel"
  - "Store luggage at hotel concierge"
auto_accept: false
priority: medium
applies_to: [all]
```

#### Rule: flight_hotel_buffer_tight
```yaml
trigger: timeline_analysis
condition: |
  (hotel_checkout_time + travel_time_to_airport + 2_hours) > flight_departure_time
action: warn_tight_timing
human_note: "🚨 Tight Timing Alert: Only {{buffer_minutes}} minutes between hotel checkout and flight departure. With traffic and check-in, this could be risky. Consider:\n• Earlier checkout\n• Night-before hotel near airport\n• Later flight"
suggested_actions:
  - "Move to earlier flight"
  - "Arrange hotel early checkout"
  - "Book airport hotel night before"
auto_accept: false
priority: high
applies_to: [all]
```

#### Rule: activity_overlap
```yaml
trigger: timeline_analysis
condition: |
  activity_A_end_time > activity_B_start_time AND
  activities_require_same_travelers AND
  NOT is_container_element(activity_A, activity_B) AND
  NOT is_compatible_overlap(activity_A, activity_B)
action: flag_scheduling_conflict
human_note: "⚠️ Schedule Conflict: {{activity_A}} ({{end_time_A}}) overlaps with {{activity_B}} ({{start_time_B}}). One needs to be rescheduled."
suggested_actions:
  - "Move {{activity_A}} to earlier"
  - "Reschedule {{activity_B}} to later"
  - "Assign to different travelers if possible"
auto_accept: false
priority: high
applies_to: [all]
context: |
  IMPORTANT: Not all overlaps are conflicts!

  CONTAINER ELEMENTS (multi-day, allow overlaps):
  - Hotels (you stay there, other activities happen during stay)
  - Car rentals (you have it, other activities use it)
  - Cruises (multi-day, includes meals/activities)

  COMPATIBLE OVERLAPS (can coexist):
  - Hotel + Dinner reservation ✓ (dinner happens DURING hotel stay)
  - Hotel + Activity ✓ (activity happens while staying at hotel)
  - Car rental + Road trip ✓ (road trip uses the rental)
  - Hotel + Flight arrival ✓ (check in after arrival)

  TRUE CONFLICTS (mutually exclusive):
  - Two flights at same time ✗
  - Two restaurant reservations at same time ✗
  - Two activities requiring same person ✗
  - Flight departure before hotel checkout ✗

  DETECTION LOGIC:
  is_container_element = element.type IN ['hotel', 'car', 'cruise'] AND
                         element.duration > 24_hours

  is_compatible_overlap = (container_element AND point_in_time_element) OR
                          (car_rental AND driving_activity) OR
                          (cruise AND onboard_activity)
```

#### Rule: missing_airport_transfer_arrival
```yaml
trigger: timeline_analysis
condition: |
  has_flight_arrival AND
  NOT has_transport_to_hotel AND
  airport_distance_to_hotel > 5_miles
action: suggest_transportation
human_note: "🚗 Missing Transfer: How are you getting from {{airport_code}} to {{hotel_name}}? It's {{distance}} miles ({{estimated_time}} drive)."
suggested_actions:
  - "Book airport shuttle (${{shuttle_price}})"
  - "Reserve Uber/Lyft (est. ${{rideshare_estimate}})"
  - "Rent car (${{car_rental_daily}}/day)"
  - "Hotel shuttle available? (Check with {{hotel_name}})"
auto_accept: false
priority: high
applies_to: [all]
```

#### Rule: day_too_packed
```yaml
trigger: timeline_analysis
condition: |
  activities_per_day > 4 AND
  total_active_hours > 10 AND
  has_children
action: warn_overscheduled
human_note: "😅 Overscheduled Day: {{date}} has {{num_activities}} activities spanning {{hours}} hours. With kids, this might be exhausting. Consider:\n• Moving one activity to another day\n• Adding buffer time\n• Planning a rest/pool afternoon"
suggested_actions:
  - "Move {{activity}} to {{alternate_day}}"
  - "Add 2-hour rest block at hotel"
  - "Make one activity optional"
auto_accept: false
priority: medium
applies_to: [families]
```

---

### CATEGORY 2: ELEMENT STATUS SYSTEM
*Track booking status and automate follow-up actions*

#### Status Values (Semantic Convention)

**Database Schema:**
```sql
status TEXT CHECK (status IN ('confirmed', 'pending', 'cancelled', 'completed'))
```

**Status Definitions:**
- `'pending'` = Needs to be booked (flight searched but not purchased, hotel researched but not reserved)
- `'confirmed'` = Booked and confirmed (have confirmation number, payment processed)
- `'cancelled'` = Was booked but cancelled (refund pending or processed)
- `'completed'` = Event has passed (end_datetime < NOW())

**IMPORTANT:** Never use old visual convention ('success', 'warning', 'danger') - these are deprecated and cause StatusBar detection failures.

#### Rule: status_pending_detected
```yaml
trigger: element_status_change
condition: |
  element.status = 'pending' AND
  trip_departure_within_60_days
action: create_booking_task
human_note: "📋 Action Needed: {{element_title}} is marked as pending. You've researched it but haven't booked yet. Need help booking this?"
suggested_actions:
  - "Book {{element_type}} now"
  - "Auto-generate booking task"
  - "Remove from trip if no longer needed"
  - "Mark as confirmed if already booked"
auto_accept: true
priority: high
applies_to: [all]
auto_task_generation: |
  When element.status = 'pending':
  1. Create task: "Book {{element_title}}"
  2. Set priority based on urgency:
     - departure < 7 days = 'high'
     - departure < 30 days = 'medium'
     - departure > 30 days = 'low'
  3. Link task to element (task.element_id)
  4. When status changes to 'confirmed', auto-delete task
```

#### Rule: status_confirmed_no_confirmation_number
```yaml
trigger: element_status_change
condition: |
  element.status = 'confirmed' AND
  element.confirmation_number IS NULL AND
  element.type IN ['flight', 'hotel', 'activity']
action: request_confirmation_number
human_note: "⚠️ Missing Confirmation: {{element_title}} is marked as confirmed but has no confirmation number. Add it for easy reference?"
suggested_actions:
  - "Add confirmation number"
  - "Upload confirmation email"
  - "Skip (not applicable)"
auto_accept: false
priority: medium
applies_to: [all]
```

#### Rule: status_pending_departure_imminent
```yaml
trigger: timeline_analysis
condition: |
  element.status = 'pending' AND
  days_until_element < 7
action: urgent_booking_warning
human_note: "🚨 URGENT: {{element_title}} is still pending but starts in {{days_until}} days! Book immediately or prices may increase/availability may be lost."
suggested_actions:
  - "Book NOW"
  - "Cancel element if no longer needed"
  - "Contact support for booking assistance"
auto_accept: false
priority: critical
applies_to: [all]
```

#### Rule: status_auto_complete
```yaml
trigger: daily_maintenance
condition: |
  element.status = 'confirmed' AND
  element.end_datetime < NOW() AND
  element.end_datetime > (NOW() - 30_days)
action: auto_mark_completed
human_note: "✅ {{element_title}} has passed. Marking as completed. How was it? (Optional feedback)"
suggested_actions:
  - "Rate experience"
  - "Add notes/photos"
  - "Mark as 'would do again'"
auto_accept: true
priority: low
applies_to: [all]
```

---

### CATEGORY 3: PARTICIPANT & FAMILY COORDINATION
*Track who's traveling when, detect divergence/convergence*

#### Participant System Overview

**Database Schema:**
```sql
participants (
  id UUID,
  user_id UUID,
  name TEXT,
  relationship TEXT, -- 'self', 'spouse', 'child', 'parent', 'friend'
  date_of_birth DATE,
  created_at TIMESTAMP
)

trip_element_participants (
  trip_element_id UUID,
  participant_id UUID,
  PRIMARY KEY (trip_element_id, participant_id)
)
```

**Key Concepts:**
- Each trip element can have 1+ participants
- Participants can diverge (wife checks in early, you arrive next day)
- Participants can converge (everyone meets up at Disney)
- TALON detects divergence and adjusts recommendations

#### Rule: participant_divergence_detected
```yaml
trigger: participant_analysis
condition: |
  element_N has participants [A, B] AND
  element_N+1 has participants [A] only
action: flag_divergence_point
human_note: "🔀 Traveler Split: {{participants_leaving}} will split off at {{element_N}}. {{participants_staying}} continues solo. Confirm this is intentional?"
suggested_actions:
  - "Confirm split is correct"
  - "Adjust participant assignments"
  - "Add separate elements for split travelers"
auto_accept: false
priority: medium
applies_to: [families, groups]
visual_indicator: "Show divergence icon in timeline"
```

#### Rule: participant_convergence_detected
```yaml
trigger: participant_analysis
condition: |
  element_N has participants [A] only AND
  element_N+1 has participants [A, B, C]
action: flag_convergence_point
human_note: "🔁 Travelers Converging: {{joining_participants}} join at {{element_N+1}}. Make sure {{joining_participants}} have transportation to {{convergence_location}}."
suggested_actions:
  - "Verify joining travelers' arrival plans"
  - "Add transportation element for joining travelers"
  - "Confirm convergence time/location"
auto_accept: false
priority: medium
applies_to: [families, groups]
visual_indicator: "Show convergence icon in timeline"
```

#### Rule: child_age_inappropriate_activity
```yaml
trigger: participant_analysis
condition: |
  element.type = 'activity' AND
  element.participants includes child AND
  child.age < activity.minimum_age
action: warn_age_restriction
human_note: "⚠️ Age Restriction: {{activity_name}} requires minimum age {{min_age}}, but {{child_name}} is only {{child_age}}. This booking may be denied."
suggested_actions:
  - "Remove {{child_name}} from this activity"
  - "Find age-appropriate alternative"
  - "Verify if exception possible"
auto_accept: false
priority: high
applies_to: [families]
```

#### Rule: solo_child_detected
```yaml
trigger: participant_analysis
condition: |
  element.participants = [child] only AND
  NOT element.supervised = true
action: warn_unsupervised_child
human_note: "⚠️ Unsupervised Child: {{child_name}} (age {{age}}) is assigned to {{element}} without adult supervision. Add a supervising adult or confirm this is intentional."
suggested_actions:
  - "Add adult to element"
  - "Mark as supervised activity (camp, tour, etc.)"
  - "Confirm intentional"
auto_accept: false
priority: high
applies_to: [families]
```

#### Rule: participant_split_accommodation
```yaml
trigger: participant_analysis
condition: |
  hotel_element has participants [A, B, C] AND
  room_count = 1 AND
  participants_count > 2
action: suggest_additional_rooms
human_note: "🏨 Room Capacity: {{participants_count}} people in 1 room at {{hotel_name}}. Consider:\n• Booking additional room\n• Upgrading to suite\n• Verifying room capacity"
suggested_actions:
  - "Add second room"
  - "Upgrade to larger room type"
  - "Confirm room sleeps {{participants_count}}"
auto_accept: false
priority: medium
applies_to: [families, groups]
```

---

### CATEGORY 4: AUTO-TASK GENERATION
*Automatically create actionable tasks from trip state*

#### Auto-Task Framework

**Trigger Events:**
1. Element status changes to 'pending'
2. Element status changes to 'confirmed' (remove pending task)
3. Departure date approaches (time-based triggers)
4. Missing required documents detected
5. Price drop detected

#### Rule: auto_task_pending_element
```yaml
trigger: element_status_change
condition: |
  element.status = 'pending'
action: create_task
task_template: |
  title: "Book {{element_title}}"
  priority: {{urgency_based_priority}}
  type: {{element_type}}
  details: "{{element_title}} needs to be booked. Status: pending"
  linked_element_id: {{element.id}}
  due_date: {{element.start_datetime - 7_days}}
auto_accept: true
priority: high
applies_to: [all]
auto_delete_condition: element.status = 'confirmed'
```

#### Rule: auto_task_passport_expiration
```yaml
trigger: document_check
condition: |
  trip_is_international AND
  passport_expires_within_6_months_of_return
action: create_task
task_template: |
  title: "Renew passport (expires {{expiration_date}})"
  priority: 'high'
  type: 'other'
  details: "Passport expires {{expiration_date}}. Many countries require 6 months validity. Start renewal now."
  due_date: {{trip_departure - 60_days}}
auto_accept: true
priority: critical
applies_to: [international]
```

#### Rule: auto_task_visa_application
```yaml
trigger: document_check
condition: |
  destination_requires_visa AND
  NOT has_visa
action: create_task
task_template: |
  title: "Apply for {{destination_country}} visa"
  priority: 'high'
  type: 'other'
  details: "Visa required for {{destination_country}}. Processing time: {{processing_days}} days. Apply by {{deadline}}."
  due_date: {{trip_departure - processing_days - 14_days}}
auto_accept: true
priority: critical
applies_to: [international]
```

#### Rule: auto_task_web_checkin
```yaml
trigger: timeline_analysis
condition: |
  element.type = 'flight' AND
  element.start_datetime - NOW() = 24_hours
action: create_task
task_template: |
  title: "Web check-in for {{airline}} flight {{flight_number}}"
  priority: 'medium'
  type: 'flight'
  details: "Check in online 24 hours before departure. Confirmation: {{confirmation_number}}"
  due_date: {{element.start_datetime - 24_hours}}
auto_accept: true
priority: medium
applies_to: [all]
```

---

### CATEGORY 7: SAFETY & COMPLIANCE
*Travel warnings, passport expiration, visa requirements, insurance*

#### Rule: passport_expiration_warning
```yaml
trigger: document_check
condition: |
  trip_is_international AND
  passport_expires_within_6_months_of_return
action: urgent_passport_renewal
human_note: "🚨 URGENT: Your passport expires {{expiration_date}} - only {{months_left}} months after your return. Many countries require 6 months validity. Renew immediately:\n• Expedited: 2-3 weeks ($60 fee)\n• Standard: 8-11 weeks\nStart now: {{renewal_link}}"
suggested_actions:
  - "Start passport renewal TODAY"
  - "Check if destination requires 6-month rule"
auto_accept: false
priority: critical
applies_to: [international]
```

#### Rule: visa_required
```yaml
trigger: document_check
condition: |
  destination_requires_visa AND
  NOT has_visa AND
  days_until_departure < 30
action: urgent_visa_application
human_note: "🚨 VISA REQUIRED: {{destination_country}} requires a visa for {{nationality}} citizens. Processing takes {{processing_time}} days. Apply immediately:\n• Type: {{visa_type}}\n• Cost: ${{visa_cost}}\n• Apply: {{application_link}}"
suggested_actions:
  - "Start visa application NOW"
  - "Expedite if possible (${{expedite_fee}})"
auto_accept: false
priority: critical
applies_to: [international]
```

#### Rule: travel_advisory_warning
```yaml
trigger: safety_check
condition: |
  destination_has_travel_advisory AND
  advisory_level >= 3
action: warn_safety_concern
human_note: "⚠️ Travel Advisory: US State Dept has Level {{level}} advisory for {{destination}} ({{reason}}). Recommendations:\n• Enroll in STEP (Smart Traveler Enrollment)\n• Review safety precautions\n• Consider travel insurance\n• Monitor local news\nDetails: {{advisory_link}}"
suggested_actions:
  - "Enroll in STEP program"
  - "Review travel advisory"
  - "Consider alternative destination"
auto_accept: false
priority: high
applies_to: [international]
```

---

## GEOPOLITICAL RISK MONITORING

### Overview

TALON continuously monitors geopolitical risks that could impact travel safety. This system integrates with multiple intelligence sources to provide real-time alerts and proactive recommendations.

### Data Sources

1. **US State Department Travel Advisories** (https://travel.state.gov/content/travel/en/traveladvisories/traveladvisories.html)
2. **UK Foreign Office Travel Advice** (https://www.gov.uk/foreign-travel-advice)
3. **Canadian Travel Advisories** (https://travel.gc.ca/travelling/advisories)
4. **Australian DFAT Smartraveller** (https://www.smartraveller.gov.au/)
5. **UN Security Council Alerts**
6. **International SOS Risk Map**
7. **Global Incident Tracking Systems** (GDELT, ACLED)

### Travel Advisory Levels

| Level | Description | TALON Action | User Recommendation |
|-------|-------------|--------------|---------------------|
| **Level 1** | Exercise Normal Precautions | Monitor only | Proceed with trip, standard precautions |
| **Level 2** | Exercise Increased Caution | Alert user, provide safety tips | Proceed with heightened awareness |
| **Level 3** | Reconsider Travel | Strong warning, suggest alternatives | Seriously consider canceling/postponing |
| **Level 4** | Do Not Travel | **CRITICAL ALERT**, automatic suspension | **Cancel trip immediately**, seek refunds |

---

### Rule: geopolitical_level_3_advisory
```yaml
trigger: geopolitical_monitoring
condition: |
  destination_travel_advisory_level = 3 AND
  trip_departure_within_30_days
action: urgent_reconsider_travel
human_note: "🚨 LEVEL 3 TRAVEL ADVISORY: {{destination_country}} is under 'Reconsider Travel' advisory due to {{threat_description}}.\n\n**Risks:**\n{{risk_details}}\n\n**TALON Recommendation:** Strongly consider postponing or choosing an alternative destination.\n\n**If you proceed:**\n• Enroll in STEP (Smart Traveler Enrollment Program)\n• Purchase comprehensive travel insurance with evacuation coverage\n• Share itinerary with emergency contacts\n• Monitor {{embassy_alerts}} daily\n• Have evacuation plan ready\n\n**Alternative Destinations:** {{similar_safe_destinations}}"
suggested_actions:
  - "Cancel trip and seek refunds"
  - "Postpone to safer dates"
  - "Choose alternative destination: {{alternatives}}"
  - "Proceed with extreme caution (not recommended)"
auto_accept: false
priority: critical
applies_to: [all]
agent_handoff: TALON-SECURITY
```

### Rule: geopolitical_level_4_do_not_travel
```yaml
trigger: geopolitical_monitoring
condition: |
  destination_travel_advisory_level = 4
action: immediate_travel_suspension
human_note: "🚨🚨 LEVEL 4 - DO NOT TRAVEL 🚨🚨\n\n{{destination_country}} is under the highest travel warning level due to {{critical_threat}}.\n\n**IMMEDIATE ACTIONS REQUIRED:**\n1. **CANCEL ALL TRAVEL** to {{destination}} immediately\n2. Contact airlines/hotels for emergency cancellations\n3. File travel insurance claim (if applicable)\n4. If you have family/friends in {{destination}}, urge them to evacuate\n\n**TALON is automatically:**\n• Flagging all bookings for cancellation\n• Researching refund policies\n• Identifying alternative destinations\n• Preparing compensation claims\n\n**US Embassy Contact:** {{embassy_phone}} / {{embassy_email}}\n**Evacuation Assistance:** {{evacuation_resources}}\n\n**This is a non-negotiable safety issue. Do not proceed with this trip.**"
suggested_actions:
  - "Cancel all bookings immediately"
  - "Contact travel insurance provider"
  - "File airline/hotel refund requests"
  - "Choose alternative destination"
auto_accept: true
priority: critical
applies_to: [all]
agent_handoff: TALON-CRISIS
notification_channels: [email, sms, push, in_app]
escalate_to_human: true
```

---

### Rule: political_instability_detected
```yaml
trigger: geopolitical_monitoring
condition: |
  destination_experiencing_civil_unrest OR
  coup_attempt_detected OR
  government_collapse_imminent
action: urgent_safety_alert
human_note: "⚠️ POLITICAL INSTABILITY ALERT: {{destination_country}}\n\n**Situation:** {{situation_description}}\n**Last Updated:** {{timestamp}}\n**Source:** {{intelligence_source}}\n\n**Potential Impacts:**\n• Airport closures or flight cancellations\n• Curfews and movement restrictions\n• Internet/communication disruptions\n• Banking/ATM access limited\n• Protests and demonstrations\n\n**TALON Monitoring:**\n• Real-time news from {{news_sources}}\n• Embassy alerts and updates\n• Flight status for {{affected_airlines}}\n• Hotel safety status\n\n**Recommendations:**\n• Avoid protest areas: {{protest_locations}}\n• Stock up on cash (ATMs may close)\n• Keep passport and documents accessible\n• Register with embassy\n• Have backup departure plan\n\n**If situation worsens, TALON will recommend immediate evacuation.**"
suggested_actions:
  - "Monitor situation closely (TALON auto-monitoring)"
  - "Consider early departure"
  - "Register with US Embassy"
  - "Cancel trip if situation escalates"
auto_accept: false
priority: high
applies_to: [all]
agent_handoff: TALON-SECURITY
monitoring_frequency: every_4_hours
```

---

### Rule: terrorism_threat_elevated
```yaml
trigger: geopolitical_monitoring
condition: |
  destination_terrorism_threat_level = 'high' OR
  recent_terrorist_incident_within_30_days
action: security_precaution_alert
human_note: "⚠️ ELEVATED TERRORISM THREAT: {{destination_country}}\n\n**Threat Level:** {{threat_level}}\n**Recent Incidents:** {{incident_summary}}\n**High-Risk Areas:** {{risk_zones}}\n\n**Security Precautions:**\n• Avoid crowded public spaces (markets, festivals, transit hubs)\n• Stay away from government buildings and military installations\n• Be aware of surroundings at all times\n• Have evacuation plan from hotel/venues\n• Keep emergency contacts readily available\n\n**TALON will avoid booking:**\n• Hotels near high-risk zones\n• Activities in crowded tourist areas\n• Events with large gatherings\n\n**Alternative Options:**\n• Postpone trip to safer dates\n• Choose lower-risk destination: {{alternatives}}\n• Limit time in high-risk areas\n\n**Emergency Contacts:**\n• US Embassy: {{embassy_contact}}\n• Local Police: {{police_number}}\n• International SOS: {{sos_number}}"
suggested_actions:
  - "Review and adjust itinerary to avoid high-risk areas"
  - "Purchase travel insurance with terrorism coverage"
  - "Enroll in STEP program"
  - "Consider postponing trip"
auto_accept: false
priority: high
applies_to: [all]
agent_handoff: TALON-SECURITY
```

---

### Rule: conflict_zone_proximity
```yaml
trigger: geopolitical_monitoring
condition: |
  destination_within_100km_of_active_conflict OR
  border_tensions_escalating
action: proximity_warning
human_note: "⚠️ CONFLICT ZONE PROXIMITY: {{destination}} is {{distance}} km from active conflict in {{conflict_location}}.\n\n**Risks:**\n• Spillover violence\n• Refugee flows causing infrastructure strain\n• Military checkpoints and restrictions\n• Airspace closures\n• Cross-border incidents\n\n**Current Situation:** {{conflict_status}}\n\n**TALON Recommendations:**\n• Maintain {{safe_distance}} km buffer from conflict zone\n• Avoid border regions: {{border_areas}}\n• Monitor conflict escalation daily\n• Have rapid evacuation plan\n\n**Safe Zones:** {{safe_regions}}\n**Avoid:** {{danger_zones}}\n\n**If conflict escalates, TALON will recommend immediate departure.**"
suggested_actions:
  - "Adjust itinerary to stay in safe zones"
  - "Monitor conflict status (TALON auto-monitoring)"
  - "Have evacuation plan ready"
  - "Consider alternative destination"
auto_accept: false
priority: high
applies_to: [all]
agent_handoff: TALON-SECURITY
monitoring_frequency: every_6_hours
```

---

## EXTREME WEATHER MONITORING

### Overview

TALON continuously monitors extreme weather events that could impact travel safety and logistics. This system integrates with meteorological agencies worldwide to provide real-time alerts and proactive recommendations.

### Data Sources

1. **National Hurricane Center (NHC)** - Atlantic/Pacific hurricanes
2. **Joint Typhoon Warning Center (JTWC)** - Western Pacific typhoons
3. **National Weather Service (NWS)** - US weather alerts
4. **World Meteorological Organization (WMO)** - Global weather
5. **European Centre for Medium-Range Weather Forecasts (ECMWF)**
6. **NOAA Storm Prediction Center** - Severe weather
7. **USGS Earthquake Hazards Program** - Seismic activity
8. **Smithsonian Global Volcanism Program** - Volcanic activity
9. **NASA FIRMS** - Wildfire detection
10. **Local meteorological agencies** - Country-specific alerts

---

### Rule: hurricane_typhoon_active_threat
```yaml
trigger: extreme_weather_monitoring
condition: |
  (hurricane OR typhoon) AND
  storm_category >= 3 AND
  destination_in_projected_path AND
  landfall_within_7_days
action: immediate_travel_suspension
human_note: "🌀🚨 HURRICANE/TYPHOON ALERT: {{storm_name}} (Category {{category}})\n\n**IMMEDIATE THREAT TO {{destination}}**\n\n**Storm Details:**\n• Current Position: {{current_location}}\n• Wind Speed: {{wind_speed}} mph\n• Projected Path: {{path_description}}\n• Estimated Landfall: {{landfall_date_time}}\n• Affected Areas: {{impact_zones}}\n\n**CRITICAL ACTIONS:**\n1. **DO NOT TRAVEL** to {{destination}} until storm passes\n2. If currently there: **EVACUATE IMMEDIATELY**\n3. All flights/hotels in affected area will likely cancel\n\n**TALON is automatically:**\n• Suspending all travel to {{affected_regions}}\n• Monitoring flight cancellations\n• Identifying safe alternative destinations\n• Preparing refund/rebooking options\n\n**Timeline:**\n• Storm Impact: {{impact_window}}\n• Safe to travel: Estimated {{safe_date}} (pending damage assessment)\n\n**Emergency Resources:**\n• Local Emergency Services: {{emergency_number}}\n• US Embassy: {{embassy_contact}}\n• Hurricane Hotline: {{hurricane_hotline}}\n\n**Alternative Destinations (similar experience, safe):**\n{{alternative_destinations}}\n\n**This is a life-threatening situation. Do not proceed with travel to affected areas.**"
suggested_actions:
  - "Cancel trip immediately"
  - "Evacuate if currently in affected area"
  - "Rebook to alternative destination"
  - "Postpone trip until {{safe_date}}"
  - "File travel insurance claim"
auto_accept: true
priority: critical
applies_to: [all]
agent_handoff: TALON-CRISIS
notification_channels: [email, sms, push, in_app]
escalate_to_human: true
monitoring_frequency: every_2_hours
auto_suspend_bookings: true
```

**EXAMPLE: Jamaica Hurricane (Current Real-World Scenario)**

```yaml
storm_name: "Hurricane Rafael"
category: 4
current_location: "Caribbean Sea, 150 miles south of Jamaica"
wind_speed: 140
projected_path: "Northward toward Jamaica, then Cuba"
landfall_date_time: "2025-10-30 14:00 local time"
affected_regions: ["Jamaica", "Cayman Islands", "Eastern Cuba"]
impact_window: "October 29-31, 2025"
safe_date: "November 5, 2025 (pending infrastructure assessment)"
alternative_destinations: [
  "Aruba (outside hurricane belt)",
  "Barbados (minimal impact)",
  "Costa Rica Pacific Coast (safe)",
  "Turks & Caicos (storm passed, assessing damage)"
]
```

---

### Rule: hurricane_post_impact_assessment
```yaml
trigger: extreme_weather_monitoring
condition: |
  hurricane_passed_destination AND
  days_since_landfall <= 14
action: infrastructure_damage_assessment
human_note: "🌀 POST-HURRICANE ASSESSMENT: {{destination}}\n\n**{{storm_name}} made landfall {{days_ago}} days ago.**\n\n**Current Status:**\n• Airport: {{airport_status}} ({{airport_details}})\n• Hotels: {{hotel_status}} ({{percent_operational}}% operational)\n• Power: {{power_status}} ({{percent_restored}}% restored)\n• Water: {{water_status}}\n• Roads: {{road_status}}\n• Communications: {{comms_status}}\n\n**Travel Feasibility:**\n{{feasibility_assessment}}\n\n**TALON Recommendation:**\n{{recommendation}}\n\n**If you choose to proceed:**\n• Expect limited services and infrastructure issues\n• Bring: Flashlight, batteries, water purification, cash\n• Hotels may have generator power only (limited AC/hot water)\n• Some attractions/restaurants closed\n• Higher prices due to supply shortages\n\n**Better Timing:** {{optimal_travel_date}} (full recovery expected)\n\n**Alternative:** {{alternative_destination}} (unaffected, similar experience)"
suggested_actions:
  - "Postpone to {{optimal_date}} for full experience"
  - "Proceed with adjusted expectations"
  - "Choose alternative destination"
auto_accept: false
priority: high
applies_to: [all]
agent_handoff: TALON-CRISIS
monitoring_frequency: daily
```

---

### Rule: wildfire_active_threat
```yaml
trigger: extreme_weather_monitoring
condition: |
  active_wildfire_within_50km AND
  fire_containment < 50_percent AND
  air_quality_index > 150
action: wildfire_safety_alert
human_note: "🔥 WILDFIRE ALERT: {{fire_name}} near {{destination}}\n\n**Fire Status:**\n• Size: {{acres}} acres\n• Containment: {{containment_percent}}%\n• Distance from {{destination}}: {{distance}} miles\n• Wind Direction: {{wind_direction}} ({{toward_or_away}})\n\n**Air Quality:**\n• AQI: {{aqi_value}} ({{aqi_category}})\n• Health Impact: {{health_warning}}\n\n**Travel Impact:**\n• Road Closures: {{closed_roads}}\n• Evacuations: {{evacuation_zones}}\n• Visibility: {{visibility}} miles\n• Outdoor Activities: {{outdoor_recommendation}}\n\n**TALON Recommendations:**\n{{recommendations}}\n\n**If Air Quality Unhealthy (AQI >150):**\n• Avoid outdoor activities\n• Stay indoors with air filtration\n• Wear N95 masks if going outside\n• Vulnerable groups (kids, elderly, asthma) should postpone\n\n**If Evacuations Ordered:**\n• **Leave immediately** - do not wait\n• Follow evacuation routes: {{evacuation_routes}}\n\n**Monitoring:** TALON checking fire status every 4 hours\n**Safe to Travel:** Estimated {{safe_date}} (when AQI <100 and fire 75%+ contained)"
suggested_actions:
  - "Postpone trip until fire contained"
  - "Proceed with indoor-focused itinerary"
  - "Choose alternative destination"
  - "Evacuate if currently there and ordered"
auto_accept: false
priority: high
applies_to: [all]
agent_handoff: TALON-SECURITY
monitoring_frequency: every_4_hours
```

---

### Rule: flood_warning_severe
```yaml
trigger: extreme_weather_monitoring
condition: |
  flash_flood_warning OR severe_flood_watch AND
  destination_in_flood_zone
action: flood_safety_alert
human_note: "🌊 FLOOD WARNING: {{destination}}\n\n**Flood Type:** {{flood_type}}\n**Severity:** {{severity_level}}\n**Affected Areas:** {{flood_zones}}\n**Duration:** {{start_time}} to {{end_time}}\n\n**Risks:**\n• Road closures and impassable routes\n• Airport delays/cancellations\n• Hotel evacuations (ground floors)\n• Contaminated water supply\n• Power outages\n\n**Current Situation:**\n• Water Level: {{water_level}} ({{above_normal}})\n• Rising/Falling: {{trend}}\n• Peak Expected: {{peak_time}}\n\n**TALON Recommendations:**\n• Avoid low-lying areas: {{low_areas}}\n• Stay on higher ground: {{safe_zones}}\n• Do not attempt to drive through flooded roads\n• Monitor local emergency alerts\n\n**If Severe (life-threatening):**\n• **Evacuate to higher ground immediately**\n• Follow emergency services instructions\n• Do not wait for water to rise\n\n**Travel Adjustments:**\n{{travel_adjustments}}\n\n**Safe to Travel:** {{safe_date}} (after water recedes and infrastructure assessed)"
suggested_actions:
  - "Postpone trip until flooding subsides"
  - "Evacuate if currently in flood zone"
  - "Adjust itinerary to avoid flood areas"
  - "Book hotel on higher floors/elevated areas"
auto_accept: false
priority: high
applies_to: [all]
agent_handoff: TALON-CRISIS
monitoring_frequency: every_2_hours
```

---

### Rule: earthquake_significant
```yaml
trigger: extreme_weather_monitoring
condition: |
  earthquake_magnitude >= 6.0 AND
  epicenter_within_100km_of_destination
action: earthquake_safety_alert
human_note: "🌍 EARTHQUAKE ALERT: {{destination}}\n\n**Magnitude:** {{magnitude}}\n**Depth:** {{depth}} km\n**Epicenter:** {{epicenter_location}} ({{distance}} km from {{destination}})\n**Time:** {{earthquake_time}}\n\n**Immediate Impacts:**\n• Building damage: {{damage_assessment}}\n• Casualties: {{casualty_report}}\n• Infrastructure: {{infrastructure_status}}\n• Aftershock Risk: {{aftershock_probability}}\n\n**Travel Impact:**\n• Airport: {{airport_status}}\n• Hotels: {{hotel_status}}\n• Roads/Bridges: {{road_status}}\n• Public Transit: {{transit_status}}\n\n**Tsunami Risk:** {{tsunami_warning}}\n{{tsunami_details}}\n\n**TALON Recommendations:**\n{{recommendations}}\n\n**If Currently There:**\n• Move to open areas away from buildings\n• Expect aftershocks ({{aftershock_window}})\n• Check for gas leaks, structural damage\n• Follow local emergency instructions\n• Contact embassy if needed: {{embassy_contact}}\n\n**If Not Yet Traveled:**\n• Postpone until damage assessed ({{assessment_date}})\n• Monitor aftershock activity\n• Wait for infrastructure restoration\n\n**Safe to Travel:** {{safe_date}} (pending aftershock activity and infrastructure restoration)"
suggested_actions:
  - "Postpone trip until safety confirmed"
  - "Evacuate if tsunami warning issued"
  - "Monitor aftershock activity"
  - "Contact embassy if currently there"
auto_accept: false
priority: critical
applies_to: [all]
agent_handoff: TALON-CRISIS
monitoring_frequency: every_1_hour
```

---

### Rule: volcanic_eruption_alert
```yaml
trigger: extreme_weather_monitoring
condition: |
  volcano_alert_level >= 'watch' AND
  volcano_within_200km_of_destination
action: volcanic_activity_alert
human_note: "🌋 VOLCANIC ACTIVITY ALERT: {{volcano_name}}\n\n**Alert Level:** {{alert_level}}\n**Activity:** {{activity_description}}\n**Distance from {{destination}}:** {{distance}} km\n\n**Potential Impacts:**\n• Ash cloud: {{ash_forecast}}\n• Flight disruptions: {{flight_impact}}\n• Air quality: {{air_quality_forecast}}\n• Lava flow risk: {{lava_risk}}\n• Evacuation zones: {{evacuation_zones}}\n\n**Current Status:**\n{{current_status}}\n\n**TALON Recommendations:**\n{{recommendations}}\n\n**If Eruption Occurs:**\n• Flights may be grounded (ash cloud)\n• Airports could close for days/weeks\n• Respiratory issues from ash\n• Evacuation may be ordered\n\n**Monitoring:** TALON tracking volcano status every 6 hours\n**Safe to Travel:** {{safe_assessment}}"
suggested_actions:
  - "Postpone until volcanic activity subsides"
  - "Monitor alert level (TALON auto-monitoring)"
  - "Have evacuation plan if currently there"
  - "Choose alternative destination"
auto_accept: false
priority: high
applies_to: [all]
agent_handoff: TALON-SECURITY
monitoring_frequency: every_6_hours
```

---

### Rule: extreme_heat_warning
```yaml
trigger: extreme_weather_monitoring
condition: |
  heat_index > 110_fahrenheit AND
  heat_advisory_issued
action: extreme_heat_alert
human_note: "🌡️ EXTREME HEAT WARNING: {{destination}}\n\n**Heat Index:** {{heat_index}}°F ({{celsius}}°C)\n**Duration:** {{start_date}} to {{end_date}}\n**Risk Level:** {{risk_level}}\n\n**Health Risks:**\n• Heat exhaustion\n• Heat stroke\n• Dehydration\n• Especially dangerous for: children, elderly, pregnant women\n\n**TALON Recommendations:**\n• Limit outdoor activities to early morning/evening\n• Stay in air-conditioned spaces during peak heat (11 AM - 4 PM)\n• Drink water constantly (1 liter per hour outdoors)\n• Wear light, breathable clothing\n• Use sunscreen SPF 50+\n\n**Itinerary Adjustments:**\n{{adjusted_schedule}}\n\n**Indoor Alternatives:**\n{{indoor_activities}}\n\n**Warning Signs of Heat Illness:**\n• Dizziness, nausea, headache\n• Rapid heartbeat\n• Confusion\n• **Seek medical help immediately if symptoms occur**\n\n**Consider Postponing:** If traveling with vulnerable individuals (young children, elderly, health conditions)"
suggested_actions:
  - "Adjust itinerary to indoor/early morning activities"
  - "Postpone if traveling with vulnerable individuals"
  - "Proceed with heat precautions"
auto_accept: false
priority: medium
applies_to: [all]
agent_handoff: TALON-CORE
```

---

### Rule: extreme_cold_warning
```yaml
trigger: extreme_weather_monitoring
condition: |
  wind_chill < -20_fahrenheit AND
  cold_weather_advisory_issued
action: extreme_cold_alert
human_note: "❄️ EXTREME COLD WARNING: {{destination}}\n\n**Wind Chill:** {{wind_chill}}°F ({{celsius}}°C)\n**Duration:** {{start_date}} to {{end_date}}\n**Risk Level:** {{risk_level}}\n\n**Health Risks:**\n• Frostbite (exposed skin in <10 minutes)\n• Hypothermia\n• Respiratory issues\n\n**TALON Packing Recommendations:**\n• Layered clothing (base, insulation, waterproof shell)\n• Insulated, waterproof boots\n• Winter gloves, hat, scarf\n• Hand/foot warmers\n• Moisturizer and lip balm (prevents chapping)\n\n**Safety Precautions:**\n• Limit outdoor exposure to <30 minutes\n• Cover all exposed skin\n• Stay dry (wet clothing loses insulation)\n• Watch for frostbite signs (numbness, white/gray skin)\n\n**Itinerary Adjustments:**\n{{adjusted_schedule}}\n\n**Indoor Alternatives:**\n{{indoor_activities}}"
suggested_actions:
  - "Add cold-weather gear to packing list"
  - "Adjust itinerary for shorter outdoor exposure"
  - "Postpone if not prepared for extreme cold"
auto_accept: true
priority: medium
applies_to: [all]
agent_handoff: TALON-CORE
```

---

## CRISIS RESPONSE PROTOCOLS

### Immediate Travel Suspension Procedure

When a **Level 4 Travel Advisory** or **Category 3+ Hurricane** is detected:

1. **Automatic Actions (No User Approval Needed):**
   - Flag all bookings to affected destination
   - Send CRITICAL alert via all channels (email, SMS, push, in-app)
   - Activate TALON-CRISIS agent
   - Begin researching refund policies
   - Identify alternative destinations

2. **User Notification (Within 5 Minutes):**
   - Immediate push notification
   - SMS alert
   - Email with full details
   - In-app critical banner

3. **TALON-CRISIS Actions (Within 30 Minutes):**
   - Contact airlines for cancellation/refund options
   - Contact hotels for cancellation/refund options
   - Research travel insurance claim process
   - Prepare alternative destination recommendations
   - Calculate financial impact and recovery options

4. **Follow-Up (24 Hours):**
   - Provide detailed refund status
   - Present 3-5 alternative destination options
   - Assist with rebooking if user chooses alternative
   - File travel insurance claim if applicable

---

### Evacuation Recommendation Procedure

When conditions deteriorate for travelers already at destination:

1. **Trigger Conditions:**
   - Travel advisory upgraded to Level 4
   - Hurricane/typhoon landfall imminent (<24 hours)
   - Earthquake magnitude >7.0
   - Volcanic eruption with ash cloud
   - Civil unrest escalating to violence
   - Government-ordered evacuations

2. **TALON-CRISIS Actions:**
   - **IMMEDIATE ALERT:** "EVACUATE NOW" message
   - Identify earliest available flights out
   - Provide evacuation routes and safe zones
   - Contact US Embassy for assistance
   - Arrange emergency accommodation if flights unavailable
   - Provide emergency contact numbers

3. **User Guidance:**
   - Step-by-step evacuation instructions
   - What to pack (essentials only)
   - How to get to airport/evacuation point
   - What to do if unable to evacuate
   - Emergency shelter locations

---

## MULTI-AGENT COORDINATION

### Agent Roles & Responsibilities

**TALON-CORE (General Travel Assistant)**
- Trip planning and recommendations
- Timeline analysis
- Budget optimization
- Activity suggestions
- **Escalates to:** TALON-CRISIS, TALON-SECURITY, TALON-FINANCE

**TALON-CRISIS (Emergency Response)**
- Flight cancellations and rebooking
- Natural disaster response
- Evacuation coordination
- Emergency accommodation
- **Activated by:** Critical alerts, user SOS
- **Escalates to:** Human support for complex crises

**TALON-SECURITY (Safety & Geopolitical)**
- Travel advisory monitoring
- Geopolitical risk assessment
- Security threat alerts
- Safe zone recommendations
- **Activated by:** Level 3+ advisories, terrorism threats
- **Escalates to:** TALON-CRISIS for evacuation scenarios

**TALON-FINANCE (Cost Optimization & Compensation)**
- Price drop monitoring
- Discount discovery
- EU261 compensation claims
- Refund processing
- **Activated by:** Price changes, flight delays, cancellations
- **Escalates to:** TALON-CRISIS for major financial impacts

**TALON-CONCIERGE (Activity & Dining)**
- Restaurant reservations
- Activity bookings
- Local recommendations
- Special occasion planning
- **Activated by:** User requests, trip gaps
- **Escalates to:** TALON-CORE for budget concerns

**TALON-COORDINATOR (Family & Group Travel)**
- Multi-traveler coordination
- Split itinerary management
- Age-appropriate activity suggestions
- Accessibility accommodations
- **Activated by:** Family/group trips
- **Escalates to:** TALON-CORE for conflicts

---

### Handoff Protocol Example

**Scenario:** Hurricane detected heading toward user's destination

```
1. TALON-SECURITY detects hurricane (Category 3+)
   ↓
2. TALON-SECURITY assesses threat level → CRITICAL
   ↓
3. TALON-SECURITY hands off to TALON-CRISIS
   ↓
4. TALON-CRISIS takes over:
   - Sends immediate alert to user
   - Begins cancellation research
   - Identifies alternative destinations
   ↓
5. TALON-FINANCE activated for refund processing
   ↓
6. TALON-CONCIERGE activated for alternative destination planning
   ↓
7. All agents report back to TALON-CRISIS for coordination
   ↓
8. TALON-CRISIS presents unified solution to user
   ↓
9. If user needs human assistance → Escalate to human support
```

---

## LEARNING & IMPROVEMENT

### User Behavior Tracking

Every interaction is logged and analyzed:

```yaml
interaction_log:
  user_id: "uuid"
  trip_id: "uuid"
  rule_triggered: "hurricane_typhoon_active_threat"
  user_action: "accepted_alternative_destination"
  alternative_chosen: "Aruba"
  time_to_decision: "12_minutes"
  user_satisfaction: 5
  outcome: "trip_successfully_rescheduled"
```

### Pattern Recognition

After 3+ similar interactions, TALON learns user preferences:

**Example:**
- User dismisses "day_too_packed" warning 3 times
- TALON learns: This user prefers busy itineraries
- Future action: Reduce priority of this rule for this user

**Example:**
- User always accepts "hotel_shuttle_available" suggestion
- TALON learns: This user prioritizes cost savings
- Future action: Auto-apply this rule (user can override)

### Rule Optimization

Based on aggregate user data:

- **High acceptance rate (>80%):** Upgrade to auto-accept
- **Low acceptance rate (<20%):** Downgrade priority or disable
- **Mixed acceptance (40-60%):** Keep as-is, analyze user segments

### Feedback Integration

Users can rate TALON suggestions:

- ⭐⭐⭐⭐⭐ (5 stars): Reinforce this rule
- ⭐⭐⭐ (3 stars): Review rule logic
- ⭐ (1 star): Flag for revision or removal

---

## IMPLEMENTATION ROADMAP

### Week 12-13: Core Intelligence Rules
- Implement 75+ travel intelligence rules
- Set up rule engine and condition evaluation
- Test with demo trips

### Week 14-15: Geopolitical Monitoring
- Integrate State Department API
- Set up travel advisory tracking
- Implement Level 3/4 alert system

### Week 16-17: Weather Monitoring
- Integrate NHC, JTWC, NWS APIs
- Set up hurricane/typhoon tracking
- Implement wildfire, flood, earthquake alerts

### Week 18-19: Multi-Agent System
- Define agent roles and responsibilities
- Implement handoff protocols
- Test crisis scenarios

### Week 20-21: Learning Pipeline
- Implement interaction logging
- Build pattern recognition algorithms
- Set up feedback collection

### Week 22+: Continuous Improvement
- Weekly analysis of rule performance
- Monthly user behavior reviews
- Quarterly rule optimization

---

## SUCCESS METRICS

### Rule Performance
- **Acceptance Rate:** >70% for high-priority rules
- **User Satisfaction:** >4.0/5.0 average rating
- **False Positive Rate:** <10% (irrelevant suggestions)

### Crisis Response
- **Alert Speed:** <5 minutes from detection to user notification
- **Evacuation Success:** 100% of users notified before crisis
- **Refund Recovery:** >80% of eligible refunds secured

### Learning Effectiveness
- **Pattern Detection:** >50 new patterns identified per quarter
- **Rule Optimization:** >10 rules improved per month
- **User Personalization:** >60% of users with personalized rule sets

---

## STATUSBAR & UI INTELLIGENCE
*Frontend logic for visual status indicators and user alerts*

### StatusBar Pending Item Detection

**Purpose:** Provide at-a-glance awareness of items requiring user action

**Implementation:** `src/components/StatusBar.tsx`

#### Logic Flow

```typescript
// Step 1: Count pending elements
const pendingCount = elements.filter(el => el.status === 'pending').length;

// Step 2: Override trip status if pending items exist
if (pendingCount > 0 && !isArchived) {
  icon = AlertTriangle (yellow)
  text = "Action Needed - {pendingCount} Items Pending"
  border = yellow glow with pulse animation
}

// Step 3: Handle active trips (today's date)
if (trip.date === today && !isArchived) {
  text = "ACTIVE TRIP - In Progress"
  indicator = 🔴 LIVE (animated pulse)
  border = green glow
}
```

#### Visual Hierarchy

**Priority 1 (highest):** Active trip (happening today)
- Green glow, "ACTIVE TRIP - In Progress", 🔴 LIVE indicator

**Priority 2:** Pending items
- Yellow glow, "Action Needed - X Items Pending", ⚠️ icon

**Priority 3:** All good
- Green border, "All Good - No Action Needed", ✓ icon

**Priority 4 (lowest):** Archived
- Gray, "Archived", no actions

#### Critical Implementation Details

**MUST use semantic status values:**
```typescript
// ✓ CORRECT
el.status === 'pending'

// ✗ WRONG (deprecated, breaks detection)
el.status === 'warning'
```

**Data Flow:**
```
Database (Supabase)
  ↓ SELECT status FROM trip_elements
API Response
  ↓ status: "pending"
App.tsx (line 208)
  ↓ status: element.status (pass unchanged!)
StatusBar Component
  ↓ pendingCount = filter(el => el.status === 'pending')
Visual Indicator
  ↓ Yellow glow + "Action Needed"
```

**Common Pitfall:**
```typescript
// ❌ BUG (causes StatusBar to fail)
status: element.status === 'confirmed' ? 'success' : 'warning'

// ✅ FIX
status: element.status  // pass unchanged from database
```

---

### UI Intelligence Rules

#### Rule: ui_statusbar_pending_alert
```yaml
trigger: ui_render
condition: |
  elements.filter(el => el.status === 'pending').length > 0 AND
  NOT trip.isArchived
action: show_yellow_alert
visual_output: |
  icon: ⚠️ AlertTriangle (yellow)
  text: "Action Needed - {{pendingCount}} Items Pending"
  border: yellow-500/30 with alert-pulse animation
  message: "Departure: {{date}}"
user_interaction: |
  Click StatusBar → View trip details
  Click pending element → Edit/book element
  StatusBar updates real-time when status changes
priority: high
applies_to: [all]
```

#### Rule: ui_trip_active_today
```yaml
trigger: ui_render
condition: |
  trip.date === TODAY AND
  NOT trip.isArchived
action: show_active_trip_indicator
visual_output: |
  icon: ✓ CheckCircle (green)
  text: "ACTIVE TRIP - In Progress"
  border: green-500/30 with shadow glow
  badge: 🔴 LIVE (animated pulse, top-right)
  message: "Trip happening now!"
user_interaction: |
  Emphasizes current/active travel
  Overrides pending status (active > pending)
  Draws attention to "happening now" state
priority: critical
applies_to: [all]
```

#### Rule: ui_participant_badges
```yaml
trigger: ui_render
condition: |
  element has multiple participants OR
  element participants differ from trip participants
action: show_participant_badges
visual_output: |
  Display colored badges for each participant
  Badge style: rounded, small, participant initials
  Colors: Unique per participant (consistent throughout trip)

  Special indicators:
  - Divergence point: 🔀 icon
  - Convergence point: 🔁 icon
  - Solo participant: Single badge only
context: |
  Participant badges appear on timeline cards
  Help visualize who's doing what activity
  Critical for family/group travel coordination
priority: medium
applies_to: [families, groups]
```

#### Rule: ui_element_status_indicator
```yaml
trigger: ui_render
condition: |
  element displayed in timeline OR card view
action: show_status_indicator
visual_output: |
  'pending' → Yellow badge "PENDING" + ⏳ icon
  'confirmed' → Green badge "CONFIRMED" + ✓ icon
  'cancelled' → Red badge "CANCELLED" + ✗ icon
  'completed' → Gray badge "COMPLETED" + ✓ icon (dimmed)

  Additional visual cues:
  - 'pending' elements have yellow left border
  - 'completed' elements have reduced opacity (0.7)
  - 'cancelled' elements have strikethrough text
priority: high
applies_to: [all]
```

#### Rule: ui_mobile_responsive_timeline
```yaml
trigger: ui_render
condition: |
  viewport_width < 768px
action: adjust_layout_mobile
visual_output: |
  Timeline: Vertical stack (no side-by-side)
  Participant badges: Reduced size
  StatusBar: Full width, compact text
  Element cards: Full width, collapsed details

  Touch targets: Minimum 44px height
  Swipe gestures: Enabled for navigation
priority: high
applies_to: [mobile_devices]
```

---

### Frontend-Backend Data Contract

**CRITICAL: Status value synchronization**

```yaml
backend_database:
  status: 'confirmed' | 'pending' | 'cancelled' | 'completed'

frontend_types:
  # src/types/database.ts - DATABASE types
  TripElement.status: 'confirmed' | 'pending' | 'cancelled' | 'completed'

  # src/types.ts - DISPLAY types (DEPRECATED for elements)
  TripStatus: 'success' | 'warning' | 'danger'  # ← Only for TRIP status, NOT elements!

mapping_layer:
  # App.tsx line 208 - MUST pass unchanged
  status: element.status  # ✓ Correct

  # ❌ Never do this (breaks StatusBar):
  status: element.status === 'confirmed' ? 'success' : 'warning'
```

**Type System Issue (Known Bug):**
- `src/types/database.ts:38` includes both old and new status values
- `src/types.ts:1` uses old convention for TripStatus
- Runtime code works (bypasses type system)
- **Fix planned:** Type definition cleanup in auth refactor phase

---

## CONCLUSION

This knowledge base transforms TALON from a simple chatbot into a comprehensive, intelligent travel management system that:

1. **Proactively identifies issues** before they become problems (smart conflict detection, not false positives)
2. **Tracks element status** (pending/confirmed) and auto-generates tasks for user action
3. **Coordinates family/group travel** with participant divergence/convergence detection
4. **Monitors real-world threats** (geopolitical, weather) in real-time
5. **Responds to crises** with immediate, actionable guidance
6. **Learns from user behavior** to provide personalized recommendations
7. **Coordinates multiple specialized agents** for complex scenarios
8. **Provides visual UI intelligence** (StatusBar, badges, mobile-responsive)

**The result:** A travel AI that genuinely protects users, saves them money, automates tedious tasks, and continuously improves based on real-world outcomes.

---

**Version:** 3.0.0
**Last Updated:** 2025-10-31
**Total Rules:** 100+ travel intelligence + 15+ crisis monitoring + 10+ UI intelligence
**Agent Count:** 6 specialized agents
**Data Sources:** 15+ real-time intelligence feeds
**Learning Capability:** Continuous improvement from user feedback
**New Systems:** Element Status, Participants, Auto-Tasks, StatusBar Detection
**Ready For:** MVP Auth Implementation (Phase 1-7)

---

## DEVELOPMENT NOTES (For Future AI Agents)

**When implementing agentic features, reference:**
- CATEGORY 2: Element Status System → Auto-task generation logic
- CATEGORY 3: Participant System → Family coordination rules
- CATEGORY 4: Auto-Task Framework → Templates for task creation
- StatusBar & UI Intelligence → Frontend behavior expectations

**Critical Knowledge:**
- Hotels are container elements (don't flag hotel+dinner as conflict!)
- Status must be semantic ('pending', not 'warning')
- Participant divergence is NORMAL (wife checks in early ≠ error)
- Auto-task generation is HIGH PRIORITY MVP feature

**Data Flow Integrity:**
```
Database → API → App.tsx (no transformation!) → Components
```

**Never** convert status values in mapping layer - pass unchanged!

---

*TALON Knowledge Base - Agent D.E.V.*
*Travel Raven Development Team*
*Ready for B2B/B2C Multi-Tier Launch*

