import datetime
import asyncio
import json
import httpx  # Import httpx instead of requests
import uvicorn
from ics import Calendar
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

ICAL_URL = r"https://calendar.google.com/calendar/ical/naveen%40leadwalnut.com/public/basic.ics" 
REMINDER_MIN = 10

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MODIFICATION: This function is now async and uses httpx
async def get_upcoming_events(client: httpx.AsyncClient):
    """Asynchronously fetches and returns upcoming events from the iCal URL."""
    try:
        response = await client.get(ICAL_URL, timeout=10)
        response.raise_for_status()  # Raise an error for bad responses (4xx or 5xx)

        cal = Calendar(response.text)
        now = datetime.datetime.now(datetime.timezone.utc)
        
        upcoming_events = []
        for ev in cal.timeline:
            delta = ev.begin - now
            if 0 < delta.total_seconds() <= REMINDER_MIN * 60:
                upcoming_events.append(ev)
        return upcoming_events
                
    except httpx.RequestError as e:
        print(f"An error occurred while requesting {e.request.url!r}: {e}")
    except Exception as e:
        print(f"An unexpected error occurred in get_upcoming_events: {e}")
    return []

# MODIFICATION: The generator now uses an httpx client
async def reminder_event_generator(request: Request):
    """Yields meeting reminders as server-sent events for a specific client."""
    spoken_ids = set()
    async with httpx.AsyncClient() as client: # Create a client session to reuse
        while True:
            if await request.is_disconnected():
                print("Client disconnected, closing reminder generator.")
                break

            events = await get_upcoming_events(client)
            for ev in events:
                if ev.uid not in spoken_ids:
                    reminder_data = {"name": ev.name, "start": ev.begin.isoformat()}
                    # For SSE, it's better to yield a dictionary
                    yield {
                        "event": "reminder",
                        "data": json.dumps(reminder_data)
                    }
                    spoken_ids.add(ev.uid)
            
            await asyncio.sleep(60)

@app.get("/reminders")
async def sse_reminders(request: Request):
    """Endpoint for the frontend to subscribe to meeting reminders."""
    return EventSourceResponse(reminder_event_generator(request))

if __name__ == "__main__":
    print("🚀 Starting FastAPI server on http://0.0.0.0:8000")
    if "YOUR_ICAL_URL_HERE" in ICAL_URL:
        print("⚠️ WARNING: Please replace 'YOUR_ICAL_URL_HERE' with your actual iCal URL.")
    uvicorn.run(app, host="0.0.0.0", port=8000)