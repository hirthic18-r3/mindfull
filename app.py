import os
import re
import secrets
import uuid
from datetime import datetime, timezone
from functools import wraps
from hmac import compare_digest
from urllib.parse import unquote, urlsplit, urlunsplit

import certifi
import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, make_response, redirect, render_template, request, session, url_for
from pymongo import MongoClient
from pymongo.errors import (
    DuplicateKeyError,
    OperationFailure,
    PyMongoError,
    ServerSelectionTimeoutError,
)
from werkzeug.security import check_password_hash, generate_password_hash

load_dotenv()

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY") or secrets.token_hex(32)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = (
    os.getenv("FLASK_ENV") == "production" or os.getenv("VERCEL") == "1"
)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
MONGODB_URI = os.getenv("MONGODB_URI", "").strip()
MONGODB_USERNAME = os.getenv("MONGODB_USERNAME", "").strip()
MONGODB_PASSWORD = os.getenv("MONGODB_PASSWORD", "")
MONGODB_DATABASE = os.getenv("MONGODB_DATABASE", "mindful_support").strip()
CHECKIN_COOKIE = "mindful_checkin_id"
ALLOWED_MOODS = {"great", "okay", "low", "anxious", "overwhelmed"}
EMAIL_PATTERN = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,255}\.[^@\s]{2,}$")

SYSTEM_INSTRUCTION = (
    "You are a compassionate, non-judgmental wellbeing companion. Listen, reflect "
    "feelings, and offer small, practical coping ideas when appropriate. Ask at most "
    "one gentle follow-up question at a time. Do not diagnose, prescribe, claim to be "
    "a therapist, or replace professional care. Do not encourage dependence on you. "
    "For serious or persistent distress, encourage contacting a qualified mental "
    "health professional or a trusted person. If the person may be in immediate "
    "danger, encourage local emergency services and a crisis hotline. Do not provide "
    "instructions for self-harm or suicide."
)

CRISIS_PATTERNS = (
    r"\bkill myself\b",
    r"\bsuicid(?:e|al)\b",
    r"\bend my life\b",
    r"\bwant to die\b",
    r"\bhurt myself\b",
    r"\bself[- ]harm\b",
    r"\bnot want to be alive\b",
)

CRISIS_REPLY = (
    "I'm really sorry you're facing this. Your safety matters, and you deserve "
    "support from a real person right now.\n\n"
    "If you may act on these thoughts or are in immediate danger, call your local "
    "emergency number or go to the nearest emergency department. If you can, move "
    "near someone you trust and tell them plainly that you need help staying safe.\n\n"
    "You can find a crisis line for your country at https://findahelpline.com. "
    "In the U.S. or Canada, call or text 988. In the UK or Ireland, call Samaritans "
    "at 116 123. You don't have to handle this alone."
)

_mongo_client = None


def _checkin_collection():
    return _mongo_collection("mood_checkins")


def _users_collection():
    return _mongo_collection("users")


def _mongo_collection(name):
    global _mongo_client
    if not MONGODB_URI:
        raise RuntimeError("MongoDB is unavailable: MONGODB_URI is not configured.")
    mongo_uri = MONGODB_URI
    username = MONGODB_USERNAME
    password = MONGODB_PASSWORD
    parsed_uri = urlsplit(mongo_uri)
    if parsed_uri.username is not None or parsed_uri.password is not None:
        uri_username = unquote(parsed_uri.username or "")
        uri_password = unquote(parsed_uri.password or "")
        if not uri_username or not uri_password:
            raise RuntimeError("MongoDB URI must include both username and password when it contains credentials.")
        if username and username != uri_username:
            raise RuntimeError("MONGODB_USERNAME does not match the username in MONGODB_URI.")
        if password and password != uri_password:
            raise RuntimeError("MONGODB_PASSWORD does not match the password in MONGODB_URI.")
        username = username or uri_username
        password = password or uri_password
        host = parsed_uri.hostname or ""
        if ":" in host:
            host = f"[{host}]"
        if parsed_uri.port:
            host = f"{host}:{parsed_uri.port}"
        mongo_uri = urlunsplit(parsed_uri._replace(netloc=host))
    if bool(username) != bool(password):
        raise RuntimeError("Set both MONGODB_USERNAME and MONGODB_PASSWORD, or leave both blank.")
    if _mongo_client is None:
        options = {
            "serverSelectionTimeoutMS": 4000,
            "connectTimeoutMS": 4000,
            "tlsCAFile": certifi.where(),
        }
        if username and password:
            options.update(username=username, password=password)
        _mongo_client = MongoClient(mongo_uri, **options)
    return _mongo_client[MONGODB_DATABASE][name]


def _csrf_token():
    token = session.get("_csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["_csrf_token"] = token
    return token


def _valid_csrf_token():
    submitted = request.form.get("csrf_token", "")
    expected = session.get("_csrf_token", "")
    return bool(submitted and expected and compare_digest(submitted, expected))


@app.context_processor
def inject_auth_state():
    return {
        "current_user": (
            {"name": session["user_name"]}
            if session.get("user_id") and session.get("user_name")
            else None
        ),
        "csrf_token": _csrf_token,
    }


def _auth_page(mode, error=None, name="", email=""):
    return render_template(
        "auth.html",
        mode=mode,
        error=error,
        name=name,
        email=email,
    )


def _crisis_message(text):
    normalized = text.lower()
    return any(re.search(pattern, normalized) for pattern in CRISIS_PATTERNS)


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            if request.path.startswith("/api/"):
                return jsonify(error="Please sign in to use this feature."), 401
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped


@app.get("/")
@login_required
def home():
    return render_template("index.html")


@app.get("/stress-relief")
@login_required
def stress_relief():
    return render_template("stress_relief.html")


@app.get("/breathing")
@login_required
def breathing():
    return render_template("breathing.html")


@app.get("/sos")
@login_required
def sos():
    return render_template("sos.html")


@app.get("/signup")
def signup():
    if session.get("user_id"):
        return redirect(url_for("home"))
    return _auth_page("signup")


@app.post("/signup")
def create_account():
    if not _valid_csrf_token():
        return _auth_page("signup", "Your form expired. Please try again."), 400

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    if not 2 <= len(name) <= 60:
        return _auth_page("signup", "Name must be between 2 and 60 characters.", name, email), 400
    if len(email) > 254 or not EMAIL_PATTERN.fullmatch(email):
        return _auth_page("signup", "Enter a valid email address.", name, email), 400
    if not 10 <= len(password) <= 128:
        return _auth_page("signup", "Password must be between 10 and 128 characters.", name, email), 400

    try:
        users = _users_collection()
        users.create_index("email", unique=True)
        result = users.insert_one(
            {
                "name": name,
                "email": email,
                "password_hash": generate_password_hash(password),
                "created_at": datetime.now(timezone.utc),
            }
        )
    except DuplicateKeyError:
        return _auth_page("signup", "An account with that email already exists. Try signing in.", name, email), 409
    except ServerSelectionTimeoutError:
        app.logger.warning("Account creation failed because MongoDB could not be reached")
        return _auth_page(
            "signup",
            "Could not connect to MongoDB Atlas. Check that the cluster is running and your current IP is allowed in Atlas Network Access.",
            name,
            email,
        ), 503
    except OperationFailure as error:
        app.logger.warning("Account creation failed with MongoDB operation code %s", error.code)
        if error.code == 18:
            message = "MongoDB rejected the database credentials. Check the Atlas database username and password."
        elif error.code == 13:
            message = "The MongoDB database user needs read/write access to the configured database."
        else:
            message = "MongoDB could not create the account. Check the database user's permissions."
        return _auth_page("signup", message, name, email), 503
    except (PyMongoError, RuntimeError) as error:
        app.logger.warning("Account creation failed (%s)", type(error).__name__)
        return _auth_page("signup", "Account creation is temporarily unavailable. Please try again."), 503

    session.clear()
    session["user_id"] = str(result.inserted_id)
    session["user_name"] = name
    return redirect(url_for("home"))


@app.get("/login")
def login():
    if session.get("user_id"):
        return redirect(url_for("home"))
    return _auth_page("login")


@app.post("/login")
def sign_in():
    if not _valid_csrf_token():
        return _auth_page("login", "Your form expired. Please try again."), 400

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    if not email or len(email) > 254 or not password:
        return _auth_page("login", "Enter your email and password.", email=email), 400

    try:
        user = _users_collection().find_one({"email": email})
    except ServerSelectionTimeoutError:
        app.logger.warning("Sign-in failed because MongoDB could not be reached")
        return _auth_page(
            "login",
            "Could not connect to MongoDB Atlas. Check that the cluster is running and your current IP is allowed in Atlas Network Access.",
            email=email,
        ), 503
    except OperationFailure as error:
        app.logger.warning("Sign-in failed with MongoDB operation code %s", error.code)
        return _auth_page(
            "login",
            "MongoDB rejected the database credentials or permissions. Check the Atlas database user and its read/write access.",
            email=email,
        ), 503
    except (PyMongoError, RuntimeError) as error:
        app.logger.warning("Sign-in lookup failed (%s)", type(error).__name__)
        return _auth_page("login", "Sign-in is temporarily unavailable. Please try again."), 503

    if not user or not check_password_hash(user["password_hash"], password):
        return _auth_page("login", "Email or password is incorrect.", email=email), 401

    session.clear()
    session["user_id"] = str(user["_id"])
    session["user_name"] = user["name"]
    return redirect(url_for("home"))


@app.post("/logout")
def logout():
    if not _valid_csrf_token():
        return redirect(url_for("home"))
    session.clear()
    return redirect(url_for("home"))


@app.post("/api/chat")
@login_required
def chat():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or not isinstance(payload.get("messages"), list):
        return jsonify(error="Please send a valid chat message."), 400

    messages = payload["messages"][-12:]
    valid_messages = []
    for message in messages:
        if not isinstance(message, dict):
            return jsonify(error="One of the chat messages is invalid."), 400
        role = message.get("role")
        text = message.get("text")
        if role not in {"user", "assistant"} or not isinstance(text, str):
            return jsonify(error="One of the chat messages is invalid."), 400
        text = text.strip()
        if not text or len(text) > 2000:
            return jsonify(error="Messages must be between 1 and 2,000 characters."), 400
        valid_messages.append({"role": role, "text": text})

    if not valid_messages or valid_messages[-1]["role"] != "user":
        return jsonify(error="Please send a message to continue."), 400

    if _crisis_message(valid_messages[-1]["text"]):
        return jsonify(reply=CRISIS_REPLY, crisis=True)

    if not GEMINI_API_KEY:
        return jsonify(error="The AI chat is not configured yet. Add GEMINI_API_KEY to your environment."), 503

    contents = [
        {
            "role": "model" if message["role"] == "assistant" else "user",
            "parts": [{"text": message["text"]}],
        }
        for message in valid_messages
    ]
    endpoint = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent"
    )
    try:
        response = requests.post(
            endpoint,
            headers={"x-goog-api-key": GEMINI_API_KEY},
            json={
                "system_instruction": {"parts": [{"text": SYSTEM_INSTRUCTION}]},
                "contents": contents,
                "generationConfig": {"temperature": 0.7, "maxOutputTokens": 500},
            },
            timeout=(5, 60),
        )
        response.raise_for_status()
        result = response.json()
    except requests.Timeout:
        app.logger.warning("Gemini request timed out")
        return jsonify(error="The support chat took too long to respond. Please try again."), 504
    except requests.RequestException as error:
        app.logger.warning("Gemini request failed (%s)", type(error).__name__)
        return jsonify(error="The support chat is temporarily unavailable. Please try again shortly."), 503
    except ValueError:
        app.logger.exception("Gemini returned an invalid response")
        return jsonify(error="The support chat returned an invalid response. Please try again."), 502

    try:
        reply = result["candidates"][0]["content"]["parts"][0]["text"].strip()
    except (KeyError, IndexError, TypeError, AttributeError):
        app.logger.warning("Gemini response did not contain a text reply")
        return jsonify(error="The support chat could not create a reply. Please try again."), 502

    if not reply:
        return jsonify(error="The support chat returned an empty reply. Please try again."), 502
    return jsonify(reply=reply, crisis=False)


@app.post("/api/checkins")
@login_required
def save_checkin():
    payload = request.get_json(silent=True)
    mood = payload.get("mood") if isinstance(payload, dict) else None
    consent = payload.get("consent") if isinstance(payload, dict) else False
    if mood not in ALLOWED_MOODS:
        return jsonify(error="Choose one of the available mood options."), 400
    if consent is not True:
        return jsonify(error="Please confirm that you want to save this check-in."), 400

    owner_id = request.cookies.get(CHECKIN_COOKIE) or str(uuid.uuid4())
    checkin = {
        "owner_id": owner_id,
        "mood": mood,
        "created_at": datetime.now(timezone.utc),
    }
    if session.get("user_id"):
        checkin["user_id"] = session["user_id"]
    try:
        _checkin_collection().insert_one(checkin)
    except (PyMongoError, RuntimeError):
        app.logger.exception("Could not save mood check-in")
        return jsonify(error="Could not save your check-in. Please try again later."), 503

    response = make_response(jsonify(saved=True))
    response.set_cookie(
        CHECKIN_COOKIE,
        owner_id,
        httponly=True,
        secure=os.getenv("FLASK_ENV") == "production" or os.getenv("VERCEL") == "1",
        samesite="Lax",
        max_age=60 * 60 * 24 * 365,
    )
    return response


@app.delete("/api/checkins")
@login_required
def delete_checkins():
    owner_id = request.cookies.get(CHECKIN_COOKIE)
    user_id = session.get("user_id")
    if not owner_id and not user_id:
        return jsonify(deleted=0)
    owner_filter = []
    if owner_id:
        owner_filter.append({"owner_id": owner_id})
    if user_id:
        owner_filter.append({"user_id": user_id})
    try:
        result = _checkin_collection().delete_many({"$or": owner_filter})
    except (PyMongoError, RuntimeError):
        app.logger.exception("Could not delete mood check-ins")
        return jsonify(error="Could not delete your check-ins. Please try again later."), 503
    response = make_response(jsonify(deleted=result.deleted_count))
    response.delete_cookie(
        CHECKIN_COOKIE,
        httponly=True,
        secure=os.getenv("FLASK_ENV") == "production" or os.getenv("VERCEL") == "1",
        samesite="Lax",
    )
    return response


if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_DEBUG") == "1")
