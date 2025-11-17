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


STEP_MIN        = 2.5   # sampling resolution (minutes)
ALT_THRESHOLD   = -0.5  # approximate refraction at horizon
NIGHT_LIMIT_DEG = 0  # sun below horizon


TEMPLATE_HTML = Path(__file__).resolve().parent / "email.html"


def planet_alt(ephem_key, t):
    body = eph[ephem_key]
    obs = (eph["earth"] + topos).at(t)
    alt, _, _ = obs.observe(body).apparent().altaz()
    return alt.degrees

def sun_alt(t):
    sun = eph["sun"]
    obs = (eph["earth"] + topos).at(t)
    alt, _, _ = obs.observe(sun).apparent().altaz()
    return alt.degrees

def is_dark(t):
    return sun_alt(t) <= NIGHT_LIMIT_DEG

def find_rise_set(ephem_key, now, hours=48, step_min=STEP_MIN, alt_threshold=ALT_THRESHOLD):
    t0 = ts.from_datetime(now - timedelta(hours=48))
    t1 = ts.from_datetime(now + timedelta(hours=hours))
    step = step_min / (24 * 60)

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


def find_set_after(ephem_key, start_dt, max_hours=72, step_min=STEP_MIN, alt_threshold=ALT_THRESHOLD):
    t = ts.from_datetime(start_dt)
    t_end = ts.from_datetime(start_dt + timedelta(hours=max_hours))
    prev_alt = planet_alt(ephem_key, t)
    step = step_min / (24 * 60)

    while t.tt < t_end.tt:
        t_next = ts.tt_jd(t.tt + step)
        alt = planet_alt(ephem_key, t_next)
        if prev_alt >= alt_threshold and alt < alt_threshold:
            return t_next.utc_datetime().astimezone(tz)
        prev_alt = alt
        t = t_next
    return None

def send_email(subject, html_body):
    msg = MIMEText(html_body, "html", "utf-8")
    msg["From"], msg["To"], msg["Subject"] = EMAIL, RECIPIENT, subject
    to_list = [a.strip() for a in RECIPIENT.split(",") if a.strip()]
    with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as s:
        s.starttls(); s.login(EMAIL, PASSWORD)
        s.sendmail(EMAIL, to_list, msg.as_string())


def main():
    now = datetime.now(tz).replace(microsecond=0)
    t_now = ts.from_datetime(now)
    dark_now = is_dark(t_now)

    rows = []
    for name, key in PLANETS.items():
        alt_now = planet_alt(key, t_now)
        rise_before, rise_after, next_set = find_rise_set(key, now)
        last_rise = rise_before  

        # Case A: currently up AND it's dark now 
        if alt_now >= ALT_THRESHOLD and dark_now:
            rows.append({
                "name": name,
                "rise_dt": last_rise,
                "rise_str": last_rise.strftime("%I:%M %p") if last_rise else "—",
                "set_str": next_set.strftime("%I:%M %p") if next_set else "—",
            })
            continue

        # Case B: not up now; will rise later AND it's dark at rise time 
        if rise_after and rise_after > now and is_dark(ts.from_datetime(rise_after)):
            if next_set and next_set > rise_after:
                set_after_rise = next_set
            else:
                set_after_rise = find_set_after(key, rise_after)
            rows.append({
                "name": name,
                "rise_dt": rise_after,
                "rise_str": rise_after.strftime("%I:%M %p"),
                "set_str": (set_after_rise.strftime("%I:%M %p") if set_after_rise else "—"),
            })
            continue

        # Case C: it's already up now but it's not dark yet
        if alt_now >= ALT_THRESHOLD and not dark_now:
            if next_set and is_dark(ts.from_datetime(next_set - timedelta(hours=1))):
                rows.append({
                    "name": name,
                    "rise_dt": last_rise,
                    "rise_str": last_rise.strftime("%I:%M %p") if last_rise else "Is Up",
                    "set_str": next_set.strftime("%I:%M %p") if next_set else "-",
                })
                continue

    if not rows:
        print("No nighttime-visible planets upcoming. No email sent.")
        return

    
    rows.sort(key=lambda r: (r["rise_dt"] is None, r["rise_dt"]))

    
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
        digest_html=digest
    )

    send_email(f"Planets visible over the {CITY.title()} sky", html)
    print(f"Sent email for {CITY.title()} - {len(rows)} planet(s).")

if __name__ == "__main__":
    main()
