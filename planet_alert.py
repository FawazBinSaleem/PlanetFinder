import os
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
from skyfield.api import load, wgs84
from dotenv import load_dotenv


load_dotenv()
EMAIL     = os.getenv("EMAIL")
PASSWORD  = os.getenv("PASSWORD")
RECIPIENT = os.getenv("RECIPIENT_EMAILS", "")
CITY      = os.getenv("PLANET_ALERT_LOCATION", "winnipeg").lower()

if not EMAIL or not PASSWORD or not RECIPIENT:
    raise SystemExit("Missing EMAIL / PASSWORD / RECIPIENT_EMAILS in .env")

LOCATIONS = {
    "riyadh":   {"lat": 24.7136, "lon": 46.6753,  "elev_m": 600, "tz": "Asia/Riyadh"},
    "winnipeg": {"lat": 49.8955, "lon": -97.1385, "elev_m": 240, "tz": "America/Winnipeg"},
}
if CITY not in LOCATIONS:
    raise SystemExit(f"Unknown PLANET_ALERT_LOCATION '{CITY}'")

loc = LOCATIONS[CITY]
tz  = ZoneInfo(loc["tz"])

# Skyfield setup
ts   = load.timescale()
eph  = load('de421.bsp')
topos = wgs84.latlon(loc["lat"], loc["lon"], elevation_m=loc["elev_m"])

PLANETS = {
    "Mercury": "mercury barycenter",
    "Venus":   "venus",
    "Mars":    "mars",
    "Jupiter": "jupiter barycenter",
    "Saturn":  "saturn barycenter",
    "Uranus":  "uranus barycenter",
    "Neptune": "neptune barycenter",
}

# Sampling settings
STEP_MIN      = 2.5   # sampling resolution (minutes)
ALT_THRESHOLD = -0.5  # approximate refraction at horizon

TEMPLATE_HTML = Path(__file__).resolve().parent / "email.html"


def planet_alt(ephem_key, t):
    """Return altitude (in degrees) of a body at time t."""
    body = eph[ephem_key]
    obs = (eph["earth"] + topos).at(t)
    alt, _, _ = obs.observe(body).apparent().altaz()
    return alt.degrees


def find_rise_set(ephem_key, now, hours=48, step_min=STEP_MIN, alt_threshold=ALT_THRESHOLD):
    """
    Scan around 'now' to find:
      - last rise before 'now'
      - next rise after 'now'
      - next set after 'now'
    """
    t0 = ts.from_datetime(now - timedelta(hours=48))
    t1 = ts.from_datetime(now + timedelta(hours=hours))
    step = step_min / (24 * 60)  # days

    t = t0
    prev_alt = planet_alt(ephem_key, t)

    last_rise_before = None
    next_rise_after  = None
    next_set_after   = None
    saw_future_rise  = False

    while t.tt < t1.tt:
        t_next = ts.tt_jd(t.tt + step)
        alt = planet_alt(ephem_key, t_next)

        # Upward crossing = rise
        if prev_alt < alt_threshold and alt >= alt_threshold:
            rise_time = t_next.utc_datetime().astimezone(tz)
            if rise_time <= now:
                last_rise_before = rise_time
            elif next_rise_after is None:
                next_rise_after = rise_time
                saw_future_rise = True

        # Downward crossing = set
        if prev_alt >= alt_threshold and alt < alt_threshold:
            set_time = t_next.utc_datetime().astimezone(tz)
            if set_time > now and next_set_after is None:
                next_set_after = set_time
                if saw_future_rise:
                    break

        prev_alt = alt
        t = t_next

    return last_rise_before, next_rise_after, next_set_after


def send_email(subject, html_body):
    msg = MIMEText(html_body, "html", "utf-8")
    msg["From"], msg["To"], msg["Subject"] = EMAIL, RECIPIENT
    to_list = [a.strip() for a in RECIPIENT.split(",") if a.strip()]

    with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as s:
        s.starttls()
        s.login(EMAIL, PASSWORD)
        s.sendmail(EMAIL, to_list, msg.as_string())


def main():
    now = datetime.now(tz).replace(microsecond=0)
    t_now = ts.from_datetime(now)

    rows = []
    for name, key in PLANETS.items():
        last_rise, next_rise, next_set = find_rise_set(key, now)
        alt_now = planet_alt(key, t_now)

        # Decide what rise time to display:
        # - If the planet is currently up: show the last rise (today)
        # - Otherwise: show the next rise (tonight/tomorrow)
        if alt_now >= ALT_THRESHOLD and last_rise and last_rise <= now:
            rise_dt = last_rise
        elif next_rise:
            rise_dt = next_rise
        else:
            rise_dt = last_rise  # fallback, may be None

        rise_str = rise_dt.strftime("%I:%M %p") if rise_dt else "—"
        set_str  = next_set.strftime("%I:%M %p") if next_set else "—"

        # Priority for sorting:
        #  0 -> currently up
        #  1 -> rises later today
        #  2 -> rises tomorrow or later
        if alt_now >= ALT_THRESHOLD and rise_dt:
            priority = 0
        elif rise_dt and rise_dt > now and rise_dt.date() == now.date():
            priority = 1
        else:
            priority = 2

        rows.append({
            "name":     name,
            "rise_dt":  rise_dt,
            "rise_str": rise_str,
            "set_str":  set_str,
            "priority": priority,
        })

    # Sort: currently-up first (by rise time), then later-today, then later days
    rows.sort(
        key=lambda r: (
            r["priority"],
            r["rise_dt"] or datetime.max.replace(tzinfo=tz),
        )
    )

    # Build HTML table
    digest = "<table style='width:100%;font-size:14px;border-collapse:collapse;'>"
    digest += "<tr><th align='left'>Planet</th><th align='left'>Rises</th><th align='left'>Sets</th></tr>"
    for r in rows:
        digest += f"<tr><td>{r['name']}</td><td>{r['rise_str']}</td><td>{r['set_str']}</td></tr>"
    digest += "</table>"

    html = TEMPLATE_HTML.read_text(encoding="utf-8").format(
        city=CITY.title(),
        date=now.strftime("%b %d, %Y"),
        start_time=now.strftime("%I:%M %p"),
        end_time=(now + timedelta(hours=24)).strftime("%I:%M %p"),
        digest_html=digest,
    )

    send_email(f"Planet rise & set times over the {CITY.title()} sky", html)
    print(f"Sent email for {CITY.title()} - {len(rows)} planets.")


if __name__ == "__main__":
    main()
