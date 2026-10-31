# Mindful

A small Flask wellbeing-support app with email/password accounts, a Gemini-powered conversation, optional MongoDB Atlas mood check-ins, stress-relief exercises, guided box breathing, an SOS support page, and a Vercel serverless entry point.

## Run locally

1. Use Python 3.10 or newer and create/activate a virtual environment.
2. Install dependencies:

   ```sh
   python -m pip install -r requirements.txt
   ```

3. Edit `.env` and set `GEMINI_API_KEY` to your Gemini API key. The file also contains the MongoDB Atlas URI, username, and password. Create a Gemini API key in Google AI Studio and allow your Atlas IP/network in the Atlas Network Access settings.
4. Start the app:

   ```sh
   python app.py
   ```

Open `http://127.0.0.1:5000`. Create an account or sign in to access the app, stress-relief exercises, breathing guide, and SOS resources; the chat and mood-check-in APIs also require an authenticated session. Accounts require a valid MongoDB Atlas connection and a password of at least 10 characters. Passwords are stored as salted password hashes. The chat needs a valid Gemini API key. MongoDB is only accessed for accounts and when a person explicitly opts in to saving a mood check-in.

If account creation fails, use the specific message shown on the form. A credentials message means check the Atlas **Database Access** user and password (not your Atlas website login); a connection message means verify the cluster status, URI host, and current IP in **Atlas → Network Access**. The Atlas database user needs read/write access to the configured database.

## Deploy to Vercel

Import the project into Vercel and add `SECRET_KEY`, `GEMINI_API_KEY`, `MONGODB_URI`, `MONGODB_USERNAME`, and `MONGODB_PASSWORD` under **Project Settings → Environment Variables**. Set the same `SECRET_KEY` (at least 32 characters) for every Vercel environment where the app runs; generate one with `python -c "import secrets; print(secrets.token_hex(32))"`. Vercel serverless instances must share it to verify Flask's signed session cookies across requests. Redeploy after setting or changing the value; existing sessions will need to sign in again after a key change. Optionally add `GEMINI_MODEL` and `MONGODB_DATABASE`. Do not put secret values in `vercel.json` or commit `.env`.

## Privacy and safety

- Chat messages are sent to Google's Gemini API for reply generation. This app does not save chat messages in MongoDB or server-side sessions.
- Mood check-ins are saved only after the user selects a mood and checks the consent box. They contain the mood, timestamp, and a random browser cookie identifier; they do not include chat text or IP addresses. “Delete saved check-ins” removes records associated with that browser cookie.
- Account passwords are stored as salted hashes in MongoDB. Authentication uses signed, HTTP-only Flask session cookies with `SameSite=Lax`; production cookies are secure-only and available to routes under `/`. Vercel requires a stable `SECRET_KEY` configured in Project Settings → Environment Variables. Local development retains an automatically generated fallback when no key is provided. The `.env` file is ignored by git; keep its MongoDB credentials and Gemini API key private.
- The browser cookie is a convenience identifier, not account authentication. Clearing browser cookies means this app can no longer associate the browser with its previous check-ins.
- This is a supportive tool, not a therapist, diagnosis, or emergency service. The app displays crisis resources and a basic keyword-triggered safety response; it cannot reliably assess risk. In immediate danger, contact local emergency services or a crisis line.

## Configuration

| Variable | Required | Purpose |
| --- | --- | --- |
| `SECRET_KEY` | Yes for deployments | Signs session cookies and CSRF tokens; keep it secret and stable |
| `GEMINI_API_KEY` | For chat | Secret API key used only by the Flask server |
| `GEMINI_MODEL` | No | Gemini model name; defaults to `gemini-2.5-flash` |
| `MONGODB_URI` | For accounts and saved check-ins | MongoDB Atlas cluster connection string |
| `MONGODB_USERNAME` | For authenticated Atlas access | MongoDB database username (optional if URI includes credentials) |
| `MONGODB_PASSWORD` | For authenticated Atlas access | MongoDB database password (optional if URI includes credentials) |
| `MONGODB_DATABASE` | No | Database name; defaults to `mindful_support` |
| `FLASK_DEBUG` | No | Set to `1` for local Flask debug mode only |
