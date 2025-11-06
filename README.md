# PlanetFinder 

Automatically sends a daily email listing **visible planets** for your selected location, using the [Skyfield](https://rhodesmill.org/skyfield/) astronomy library.

This project finds which planets are above the horizon at night and emails you their **rise and set times**, neatly formatted in an HTML email.

---

##  Deployment Overview

Deployed as a **Google Cloud Run Job** named **`planetfinder`** under the **Google Cloud Project** `planetfinder`.

Cloud Scheduler triggers it daily at **3:00 PM Riyadh time (12:00 UTC)**.

---

## Features

- Calculates visible planets for any configured location (Riyadh, Winnipeg, etc.)
- Uses Skyfield’s high-precision `de421.bsp` ephemeris
- Filters only nighttime planets (sun altitude below -6°)
- Sends an HTML email with rise/set times
- Automatically deployable to Google Cloud Run as a **daily job**
- Configurable via `.env`

---


##  Environment Variables

Create a `.env` file (or use Secret Manager in Cloud Run) with:

```env
EMAIL=your_email@gmail.com
PASSWORD=your_app_password
RECIPIENT_EMAILS=someone@example.com,another@example.com
PLANET_ALERT_LOCATION=riyadh
```

> **Note:** Use a Gmail **App Password**, not your real password.  
> You can create one under [Google Account → Security → App Passwords](https://myaccount.google.com/apppasswords).

---

##  Changing the Location

You can easily switch which city or region the script uses for calculations.

### Option 1: Use a preset location

Inside `planet_alert.py`, the following preset cities are available:

```python
LOCATIONS = {
    "riyadh":   {"lat": 24.7136, "lon": 46.6753,  "elev_m": 600, "tz": "Asia/Riyadh"},
    "winnipeg": {"lat": 49.8955, "lon": -97.1385, "elev_m": 240, "tz": "America/Winnipeg"},
}
```

To switch locations, edit your `.env`:

```env
PLANET_ALERT_LOCATION=winnipeg
```

When you redeploy or re-run locally, it will automatically use the new location and timezone.

---

### Option 2: Add your own custom location

If your city isn’t in the list, you can add it easily:

1. Open **`planet_alert.py`**
2. Scroll to the `LOCATIONS` dictionary
3. Add your city entry, for example:

```python
"toronto": {"lat": 43.6532, "lon": -79.3832, "elev_m": 75, "tz": "America/Toronto"},
```

4. Then update your `.env`:

```env
PLANET_ALERT_LOCATION=toronto
```

You can find latitude, longitude, and timezone values from [latlong.net](https://www.latlong.net/) or Google Maps.

---

### Option 3: Temporary override (for local testing)

You can also run it manually for a different city without changing `.env`:

```bash
PLANET_ALERT_LOCATION=winnipeg python planetfinder_simple.py
```

---

##  Run Locally

1. Clone the repo:
   ```bash
   git clone https://github.com/<your-username>/planetfinder.git
   cd planetfinder
   ```

2. Create a virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Create a `.env` file (based on `.env.example`).

5. Run:
   ```bash
   python planet_alert.py
   ```

You should see something like:
```
 Sent email for Riyadh - 3 planet(s).
```

---

##  Deploy to Google Cloud Run Jobs

1. Build and push the container:
   ```bash
   gcloud builds submit --tag gcr.io/planetfinder/planetfinder:latest
   ```

2. Create a Cloud Run **Job**:
   ```bash
   gcloud run jobs create planetfinder      --image gcr.io/planetfinder/planetfinder:latest      --region us-central1      --max-retries 0
   ```

3. Run it manually (for testing):
   ```bash
   gcloud run jobs execute planetfinder --region us-central1
   ```

If successful, you’ll get an email with today’s visible planets 

---

##  Schedule with Cloud Scheduler

To automate daily execution:

1. Go to **Cloud Run → Jobs → planetfinder → Triggers → Add scheduler trigger**
2. Use this cron expression:
   ```
   0 12 * * *
   ```
   → runs daily at **3:00 PM Riyadh time (12:00 UTC)**
3. Save it, you’re done!

Cloud Scheduler will now trigger your job daily.

---

 Connect GitHub for Auto-Deploy

This guide explains how to automatically rebuild and deploy your Cloud Run service whenever you push updates to your GitHub repository.

---

## Steps

1. In the Google Cloud Console, navigate to **Cloud Build → Triggers → Create trigger**.
2. **Source:**  
   Select **GitHub (Cloud Build GitHub App)**, authorize access, and choose your repository and the **main** branch.
3. **Event:**  
   Choose **Push to a branch**.
4. **Configuration:**  
   Select **Cloud Build configuration file**, and set the path to:  
   ```
   cloudbuild.yaml
   ```
5. Click **Create trigger**.

---

## Result

Future commits to your **main** branch will automatically trigger a new build and deployment of your Cloud Run job.

---

## Optional Substitutions

Keep defaults unless you need to override them:

```
_REGION: us-central1
_JOB: planetfinder
```

---

##  Example Email Output

**Subject:**  
> Planets visible over Riyadh

| Planet | Rises | Sets |
|--------|--------|------|
| Uranus | 6:08 PM | 6:32 AM |
| Jupiter | 7:24 PM | 8:12 AM |
| Venus | 8:45 PM | 9:51 AM |

---

##  Notes

- Adjust `ALT_THRESHOLD` and `NIGHT_LIMIT_DEG` in the script for different horizon or twilight definitions.
- Ephemeris file (`de421.bsp`) is automatically downloaded and cached by Skyfield.
- If your email doesn’t send on Cloud Run, double-check your Gmail App Password and `.env` variables under **Cloud Run → Variables & Secrets**.
