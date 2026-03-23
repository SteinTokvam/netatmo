import logging
import time 

from caldav import DAVClient
from datetime import datetime, timedelta
import pytz
from icalendar import Calendar
from datetime import datetime, date
import utils

calendarLogger = logging.getLogger(__name__)
events_filename = "data/events.json"
DEFAULT_CALDAV_TIMEOUT_SECONDS = 30


def calendar_service(config):
    """Fetches calendar events from iCloud and saves them to events.json."""
    
    sleep_time = 60 * 60  # 1 time i sekunder

    while True:
        try:
            fetch_calendar_events(config)
        except Exception as e:
            calendarLogger.error("Error fetching calendar events:", exc_info=1)

        time.sleep(sleep_time)
        
def fetch_calendar_events(config):
    client = DAVClient(
        url=config["caldav_url"],
        username=config["apple_id"],
        password=config["apple_password"],
        timeout=config.get("caldav_timeout_seconds", DEFAULT_CALDAV_TIMEOUT_SECONDS),
    )

    principal = client.principal()
    calendars = principal.calendars()

    if not calendars:
        calendarLogger.error("Found no calendars.")
        return

    now = datetime.now(pytz.utc)
    end = now + timedelta(days=7)

    calendarLogger.info("Fetching events from %s to %s", now.isoformat(), end.isoformat())

    output = []

    for calendar in calendars:
        calendarLogger.info("Fetching events from calendar: %s", calendar.name)
        
        # 🔥 NY metode (erstatter date_search)
        results = calendar.search(
            start=now,
            end=end,
            event=True,
        )

        events_list = []

        for result in results:
            raw_data = result.data
            cal = Calendar.from_ical(raw_data)

            for component in cal.walk():
                if component.name == "VEVENT":
                    summary = str(component.get("summary", "Ingen tittel"))
                    dtstart = component.get("dtstart")
                    dtend = component.get("dtend")
                    location = str(component.get("location", ""))

                    start_dt = dtstart.dt.isoformat() if dtstart else None
                    end_dt = dtend.dt.isoformat() if dtend else None

                    if isinstance(dtstart.dt, date) and not isinstance(dtstart.dt, datetime):
                        continue

                    events_list.append({
                        "title": summary,
                        "start": start_dt,
                        "end": end_dt,
                        "location": location,
                    })

        # sorter kronologisk
        events_list.sort(key=lambda x: x["start"] or "")

        if len(events_list) > 0:
            output.append({
                "calendar": calendar.name,
                "events": events_list,
            })
            calendarLogger.info("Saved %d events from calendar: %s", len(events_list), calendar.name)
        else:
            calendarLogger.info("No events found in calendar: %s", calendar.name)

    utils.write_json(output, events_filename, ensure_ascii=False)
