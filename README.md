# PlanetFinder ☄️

Automatically sends a daily email listing **visible planets** for your selected location using the [Skyfield](https://rhodesmill.org/skyfield/) astronomy library.

The script calculates which planets are above the horizon during nighttime, determines rise/set times, and emails a clean HTML report straight to your inbox.

---

## 🚀 Deployment Options

PlanetFinder supports two methods of automation:

| Method | Cost | Reliability | Description |
|--------|------|-------------|-------------|
| **GitHub Actions + cron-job.org (current)** ✅ | ✅ Free | ✅ Very reliable | cron-job.org triggers GitHub Action daily |
| **Google Cloud Run + Cloud Build CI/CD (previous)** | ⚠️ May incur costs | ✅ Production-ready | Cloud Run deploys + executes automatically on push |

---

## ✨ Features

- Identifies which planets are visible from your location
- Uses high-precision JPL ephemeris (`de421.bsp`)
- Filters only nighttime planets (`sun altitude < -6°`)
- Sends HTML email with:
  - Planet name
  - Rise time
  - Set time
- Adjustable city / timezone
- No manual execution required once deployed

---

## 🔧 Environment Variables (`.env`)

```
EMAIL=your_email@gmail.com
PASSWORD=your_gmail_app_password
RECIPIENT_EMAILS=someone@example.com,another@example.com
PLANET_ALERT_LOCATION=riyadh
```

> Use a Gmail **App Password**: https://myaccount.google.com/apppasswords

---

## 🌍 Switch Location

`planet_alert.py` has built‑in presets:

```python
LOCATIONS = {
    "riyadh":   {"lat": 24.7136, "lon": 46.6753,  "elev_m": 600, "tz": "Asia/Riyadh"},
    "winnipeg": {"lat": 49.8955, "lon": -97.1385, "elev_m": 240, "tz": "America/Winnipeg"},
}
```

Change location via `.env`:

```
PLANET_ALERT_LOCATION=winnipeg
```

Add a new city by editing the dict.

---

## ▶️ Run Locally

```bash
git clone https://github.com/FawazBinSaleem/PlanetFinder.git
cd PlanetFinder

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

python planet_alert.py
```

Expected output:

```
Sent email for Riyadh – 3 planet(s) visible.
```

---

## ✅ Deployment (Current): GitHub Actions + cron‑job.org

### GitHub Actions workflow file:
Located at: `.github/workflows/planetfinder.yml`

### On cron‑job.org

Create job → URL:

```
https://api.github.com/repos/FawazBinSaleem/PlanetFinder/actions/workflows/planetfinder.yml/dispatches
```

**Request Method:** `POST`  
**Headers:**

```
Authorization: Bearer <YOUR_TOKEN>
Accept: application/vnd.github+json
```

**Body:**

```json
{
  "ref": "main"
}
```

⏰ Schedule: **Every day at 3:00 PM (Asia/Riyadh)**

---

## 📦 Optional: Google Cloud Run CI/CD (Old Deployment)

Cloud Build YAML:

```yaml
steps:
  - name: gcr.io/cloud-builders/docker
    args: ['build', '-t', 'gcr.io/$PROJECT_ID/planetfinder:$SHORT_SHA', '.']

  - name: gcr.io/cloud-builders/docker
    args: ['push', 'gcr.io/$PROJECT_ID/planetfinder:$SHORT_SHA']

  - name: gcr.io/google.com/cloudsdktool/cloud-sdk
    entrypoint: gcloud
    args:
      ['run', 'jobs', 'update', 'planetfinder', '--image', 'gcr.io/$PROJECT_ID/planetfinder:$SHORT_SHA', '--region', 'us-central1']
```

---

## 🧠 Skills Learned

- Python automation
- Email via SMTP
- Astronomy calculations
- CI/CD pipelines (GitHub Actions & Cloud Build)
- Cron scheduling
- Docker containerization
- Secrets & security handling

---

Made with ❤️ under the night sky.
