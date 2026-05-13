"""
Utility helpers — property context and shared tools.

Property data is hardcoded here for this assessment. In production
this would be fetched from a database using property_id as the key.
Keeping it here means claude_service.py stays clean — it asks for
context, it doesn't know where context comes from.
"""

import uuid


# In production: database lookup by property_id.
# For this assessment: one property, hardcoded, well-structured.
PROPERTY_CONTEXT = {
    "villa-b1": {
        "name": "Villa B1, Assagao, North Goa",
        "bedrooms": 3,
        "max_guests": 6,
        "private_pool": True,
        "check_in": "2:00 PM",
        "check_out": "11:00 AM",
        "base_rate": "INR 18,000 per night (up to 4 guests)",
        "extra_guest_rate": "INR 2,000 per night per additional guest",
        "wifi_password": "Nistula@2024",
        "caretaker_hours": "8:00 AM to 10:00 PM",
        "chef_on_call": "Yes, pre-booking required",
        "availability_april_20_24": "Available",
        "cancellation_policy": "Free cancellation up to 7 days before check-in"
    }
}


def get_property_context(property_id: str) -> dict:
    """
    Returns property details for prompt injection.

    Falls back to empty dict if property is unknown — the AI
    will handle missing context more gracefully than a hard crash.
    """
    return PROPERTY_CONTEXT.get(property_id, {})


def format_property_for_prompt(context: dict) -> str:
    """
    Converts property dict into a clean string block for the Claude prompt.
    Structured text performs better in prompts than raw JSON.
    """
    if not context:
        return "Property details unavailable."

    return f"""
Property: {context['name']}
Bedrooms: {context['bedrooms']} | Max Guests: {context['max_guests']} | Private Pool: {'Yes' if context['private_pool'] else 'No'}
Check-in: {context['check_in']} | Check-out: {context['check_out']}
Base Rate: {context['base_rate']}
Extra Guest Rate: {context['extra_guest_rate']}
WiFi Password: {context['wifi_password']}
Caretaker: {context['caretaker_hours']}
Chef on Call: {context['chef_on_call']}
Availability (April 20-24): {context['availability_april_20_24']}
Cancellation Policy: {context['cancellation_policy']}
""".strip()


def generate_message_id() -> str:
    """Generates a unique ID for each inbound message."""
    return str(uuid.uuid4())