import os
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path

from dotenv import load_dotenv
from skyfield.api import load, wgs84
from skyfield import almanac


load_dotenv()

SENDER_EMAIL = os.getenv("EMAIL")
SENDER_APP_PASSWORD = os.getenv("PASSWORD")
RECIPIENT_EMAILS_RAW = os.getenv("RECIPIENT_EMAILS", "")
CITY_KEY = os.getenv("PLANET_ALERT_LOCATION", "winnipeg").lower()

if not SENDER_EMAIL or not SENDER_APP_PASSWORD or not RECIPIENT_EMAILS_RAW:
    raise SystemExit("Missing EMAIL / PASSWORD / RECIPIENT_EMAILS in .env")

LOCATIONS = {
    "riyadh": {
        "latitude": 24.7136,
        "longitude": 46.6753,
        "elevation_m": 600,
        "timezone": "Asia/Riyadh",
    },
    "winnipeg": {
        "latitude": 49.8955,
        "longitude": -97.1385,
        "elevation_m": 240,
        "timezone": "America/Winnipeg",
    },
}

if CITY_KEY not in LOCATIONS:
    raise SystemExit(f"Unknown PLANET_ALERT_LOCATION '{CITY_KEY}'")

location_info = LOCATIONS[CITY_KEY]
local_timezone = ZoneInfo(location_info["timezone"])

EMAIL_TEMPLATE_PATH = Path(__file__).resolve().parent / "email.html"

# Altitude threshold for "rise/set" 
HORIZON_DEGREES = -0.5

# How far ahead we look for upcoming events .
LOOKAHEAD_HOURS = 48



timescale = load.timescale()
ephemeris = load("de421.bsp")

observer_topos = wgs84.latlon(
    location_info["latitude"],
    location_info["longitude"],
    elevation_m=location_info["elevation_m"],
)

observer = ephemeris["earth"] + observer_topos

PLANETS = {
    "Mercury": "mercury barycenter",
    "Venus": "venus",
    "Mars": "mars",
    "Jupiter": "jupiter barycenter",
    "Saturn": "saturn barycenter",
    "Uranus": "uranus barycenter",
    "Neptune": "neptune barycenter",
}

planet_bodies = {planet_name: ephemeris[ephem_key] for planet_name, ephem_key in PLANETS.items()}


# Altitude of a body at a given skyfield Time.
def altitude_degrees_of_body(body, skyfield_time):
    
    apparent = observer.at(skyfield_time).observe(body).apparent()
    altitude, _, _ = apparent.altaz()
    return altitude.degrees



def find_rise_set_events(body, window_start_dt, window_end_dt, horizon_degrees=HORIZON_DEGREES):
    
    window_start_time = timescale.from_datetime(window_start_dt)
    window_end_time = timescale.from_datetime(window_end_dt)

    event_function = almanac.risings_and_settings(
        ephemeris,
        body,
        observer_topos,
        horizon_degrees=horizon_degrees,
    )

    event_times, event_states = almanac.find_discrete(window_start_time, window_end_time, event_function)

    events = []
    # event_states: 1 means "above horizon", 0 means "below horizon".
    # With risings_and_settings, transitions correspond to rise/set.
    for idx in range(len(event_states)):
        local_dt = event_times[idx].utc_datetime().astimezone(local_timezone)
        state = int(event_states[idx])
        # When it transitions to 1 => rising event, to 0 => setting event.
        event_type = "rise" if state == 1 else "set"
        events.append((local_dt, event_type))


    events.sort(key=lambda x: x[0])
    return events


def pick_times_for_digest(events, now_local_dt):
   
    last_rise_before_now = None
    next_rise_after_now = None

    for event_dt, event_type in events:
        if event_type == "rise" and event_dt <= now_local_dt:
            last_rise_before_now = event_dt
        elif event_type == "rise" and event_dt > now_local_dt and next_rise_after_now is None:
            next_rise_after_now = event_dt

    # Prefer the next set that happens after the chosen rise time (so it pairs nicely).
    chosen_rise = next_rise_after_now or last_rise_before_now
    next_set_after_now = None
    if chosen_rise:
        for event_dt, event_type in events:
            if event_type == "set" and event_dt > max(now_local_dt, chosen_rise):
                next_set_after_now = event_dt
                break
    else:
        
        for event_dt, event_type in events:
            if event_type == "set" and event_dt > now_local_dt:
                next_set_after_now = event_dt
                break

    return last_rise_before_now, next_rise_after_now, next_set_after_now


def first_rise_on_or_after(events, day_start_local_dt, day_end_local_dt):
    for event_dt, event_type in events:
        if event_type == "rise" and day_start_local_dt <= event_dt < day_end_local_dt:
            return event_dt
    return None



def send_email_html(subject, html_body):
    message = MIMEText(html_body, "html", "utf-8")
    message["From"] = SENDER_EMAIL
    message["To"] = RECIPIENT_EMAILS_RAW
    message["Subject"] = subject

    recipient_list = [addr.strip() for addr in RECIPIENT_EMAILS_RAW.split(",") if addr.strip()]

    with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as smtp:
        smtp.starttls()
        smtp.login(SENDER_EMAIL, SENDER_APP_PASSWORD)
        smtp.sendmail(SENDER_EMAIL, recipient_list, message.as_string())



def main():
    now_local = datetime.now(local_timezone).replace(microsecond=0)


    today_start_local = now_local.replace(hour=0, minute=0, second=0)
    today_end_local = today_start_local + timedelta(days=1)

  
    lookback_local = now_local - timedelta(hours=48)
    lookahead_local = now_local + timedelta(hours=LOOKAHEAD_HOURS)

    rows = []

    for planet_name, body in planet_bodies.items():
      
        events = find_rise_set_events(
            body=body,
            window_start_dt=lookback_local,
            window_end_dt=lookahead_local,
            horizon_degrees=HORIZON_DEGREES,
        )

        last_rise, next_rise, next_set = pick_times_for_digest(events, now_local)

 
        now_skyfield_time = timescale.from_datetime(now_local)
        altitude_now = altitude_degrees_of_body(body, now_skyfield_time)

        if altitude_now >= HORIZON_DEGREES and last_rise and last_rise <= now_local:
            display_rise_time = last_rise
        elif next_rise:
            display_rise_time = next_rise
        else:
            display_rise_time = last_rise

        rise_str = display_rise_time.strftime("%I:%M %p") if display_rise_time else "—"
        set_str = next_set.strftime("%I:%M %p") if next_set else "—"

       
        first_rise_today = first_rise_on_or_after(events, today_start_local, today_end_local)
        ordering_rise_time = first_rise_today or next_rise or last_rise

        rows.append(
            {
                "planet_name": planet_name,
                "rise_str": rise_str,
                "set_str": set_str,
                "ordering_rise_time": ordering_rise_time,
            }
        )

    # Sort by ordering rise time, unknowns last
    far_future_local = datetime.max.replace(tzinfo=local_timezone)
    rows.sort(key=lambda r: r["ordering_rise_time"] or far_future_local)


    table_rows_html = "".join(
        f"<tr><td>{r['planet_name']}</td><td>{r['rise_str']}</td><td>{r['set_str']}</td></tr>"
        for r in rows
    )
    digest_html = (
        "<table style='width:100%;font-size:14px;border-collapse:collapse;'>"
        "<tr><th align='left'>Planet</th><th align='left'>Rises</th><th align='left'>Sets</th></tr>"
        f"{table_rows_html}"
        "</table>"
    )

    template_html = EMAIL_TEMPLATE_PATH.read_text(encoding="utf-8")
    rendered_html = template_html.format(
        city=CITY_KEY.title(),
        date=now_local.strftime("%b %d, %Y"),
        start_time=now_local.strftime("%I:%M %p"),
        end_time=(now_local + timedelta(hours=24)).strftime("%I:%M %p"),
        digest_html=digest_html,
    )

    subject = f"Planet rise & set times over the {CITY_KEY.title()} sky"
    send_email_html(subject, rendered_html)

    print(f"Sent email for {CITY_KEY.title()} - {len(rows)} planets.")


if __name__ == "__main__":
    main()
