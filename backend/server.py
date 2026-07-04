from fastapi import FastAPI, APIRouter, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import random
import math
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional
import uuid
from datetime import datetime, timezone


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

app = FastAPI(title="SafeWalk Mumbai API")
api_router = APIRouter(prefix="/api")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# ---------- Models ----------
class EmergencyContact(BaseModel):
    name: str
    phone: str


class UserCreate(BaseModel):
    phone: str
    name: str
    language: str = "en"  # en | hi | mr
    emergency_contacts: List[EmergencyContact] = Field(default_factory=list)
    is_volunteer: bool = False
    id_verified: bool = False


class UserUpdate(BaseModel):
    name: Optional[str] = None
    language: Optional[str] = None
    emergency_contacts: Optional[List[EmergencyContact]] = None
    is_volunteer: Optional[bool] = None
    id_verified: Optional[bool] = None


class User(BaseModel):
    id: str
    phone: str
    name: str
    language: str
    emergency_contacts: List[EmergencyContact]
    is_volunteer: bool
    id_verified: bool
    response_rate: float = 100.0
    created_at: str


class SendOtpRequest(BaseModel):
    phone: str


class VerifyOtpRequest(BaseModel):
    phone: str
    otp: str


class VerifyOtpResponse(BaseModel):
    token: str
    user_id: str
    is_new: bool


class SOSCreate(BaseModel):
    user_id: str
    lat: float
    lng: float


class VolunteerInfo(BaseModel):
    id: str
    name: str
    distance_m: int
    eta_min: int
    phone: str
    avatar: str
    responding: bool = False


class SOSIncident(BaseModel):
    id: str
    user_id: str
    user_name: str
    lat: float
    lng: float
    status: str  # active | cancelled | resolved
    volunteers: List[VolunteerInfo]
    emergency_contacts_notified: List[EmergencyContact]
    created_at: str


class SOSRespond(BaseModel):
    volunteer_id: str


class RouteRating(BaseModel):
    user_id: str
    lat: float
    lng: float
    stars: int  # 1-5
    tags: List[str] = Field(default_factory=list)
    note: Optional[str] = None


class RoutePin(BaseModel):
    lat: float
    lng: float
    stars: float
    tags: List[str]
    count: int


# ---------- Helpers ----------
def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def clean(doc: dict) -> dict:
    if doc is None:
        return doc
    doc.pop("_id", None)
    return doc


MOCK_VOLUNTEERS = [
    {
        "name": "Priya Sharma",
        "phone": "+91 98200 11111",
        "avatar": "https://images.unsplash.com/photo-1725033489648-a819750348eb?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NTY2NzV8MHwxfHNlYXJjaHwzfHxjb25maWRlbnQlMjBpbmRpYW4lMjB3b21hbiUyMHNtaWxpbmclMjBwb3J0cmFpdHxlbnwwfHx8fDE3ODIwMzgzMzh8MA&ixlib=rb-4.1.0&q=85",
    },
    {
        "name": "Ananya Iyer",
        "phone": "+91 98200 22222",
        "avatar": "https://images.unsplash.com/photo-1463335361701-e90f4c5045d0?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NTY2NzV8MHwxfHNlYXJjaHwyfHxjb25maWRlbnQlMjBpbmRpYW4lMjB3b21hbiUyMHNtaWxpbmclMjBwb3J0cmFpdHxlbnwwfHx8fDE3ODIwMzgzMzh8MA&ixlib=rb-4.1.0&q=85",
    },
    {
        "name": "Meera Kulkarni",
        "phone": "+91 98200 33333",
        "avatar": "https://images.unsplash.com/photo-1725033489648-a819750348eb?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NTY2NzV8MHwxfHNlYXJjaHwzfHxjb25maWRlbnQlMjBpbmRpYW4lMjB3b21hbiUyMHNtaWxpbmclMjBwb3J0cmFpdHxlbnwwfHx8fDE3ODIwMzgzMzh8MA&ixlib=rb-4.1.0&q=85",
    },
    {
        "name": "Riya Kapoor",
        "phone": "+91 98200 44444",
        "avatar": "https://images.unsplash.com/photo-1463335361701-e90f4c5045d0?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NTY2NzV8MHwxfHNlYXJjaHwyfHxjb25maWRlbnQlMjBpbmRpYW4lMjB3b21hbiUyMHNtaWxpbmclMjBwb3J0cmFpdHxlbnwwfHx8fDE3ODIwMzgzMzh8MA&ixlib=rb-4.1.0&q=85",
    },
]


def generate_nearby_volunteers(count: int = 4) -> List[dict]:
    vols = []
    for i in range(count):
        base = MOCK_VOLUNTEERS[i % len(MOCK_VOLUNTEERS)]
        distance_m = random.randint(80, 480)
        eta_min = max(1, round(distance_m / 80))  # ~80m/min walking
        vols.append(
            {
                "id": str(uuid.uuid4()),
                "name": base["name"],
                "phone": base["phone"],
                "avatar": base["avatar"],
                "distance_m": distance_m,
                "eta_min": eta_min,
                "responding": False,
            }
        )
    vols.sort(key=lambda v: v["distance_m"])
    return vols


# ---------- Routes ----------
@api_router.get("/")
async def root():
    return {"service": "safewalk-mumbai", "status": "ok"}


# --- Auth (mock OTP) ---
@api_router.post("/auth/send-otp")
async def send_otp(payload: SendOtpRequest):
    # Mocked: pretend we sent an SMS. Any 6-digit OTP will pass verify.
    logger.info(f"[MOCK OTP] Sending OTP to {payload.phone} -> 123456")
    return {"sent": True, "hint": "Use OTP 123456 (mocked)"}


@api_router.post("/auth/verify-otp", response_model=VerifyOtpResponse)
async def verify_otp(payload: VerifyOtpRequest):
    if len(payload.otp) != 6 or not payload.otp.isdigit():
        raise HTTPException(status_code=400, detail="OTP must be 6 digits")
    # Accept 123456 as the mock code
    if payload.otp != "123456":
        raise HTTPException(status_code=401, detail="Invalid OTP (use 123456)")

    existing = await db.users.find_one({"phone": payload.phone})
    if existing:
        return VerifyOtpResponse(
            token=f"mock-token-{existing['id']}",
            user_id=existing["id"],
            is_new=False,
        )

    user_id = str(uuid.uuid4())
    return VerifyOtpResponse(token=f"mock-token-{user_id}", user_id=user_id, is_new=True)


# --- Users ---
@api_router.post("/users", response_model=User)
async def create_user(payload: UserCreate):
    existing = await db.users.find_one({"phone": payload.phone})
    if existing:
        raise HTTPException(status_code=409, detail="User already exists")
    user_doc = {
        "id": str(uuid.uuid4()),
        "phone": payload.phone,
        "name": payload.name,
        "language": payload.language,
        "emergency_contacts": [c.dict() for c in payload.emergency_contacts],
        "is_volunteer": payload.is_volunteer,
        "id_verified": payload.id_verified,
        "response_rate": 100.0,
        "created_at": now_iso(),
    }
    await db.users.insert_one(user_doc.copy())
    return User(**clean(user_doc))


@api_router.get("/users/{user_id}", response_model=User)
async def get_user(user_id: str):
    doc = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="User not found")
    return User(**doc)


@api_router.patch("/users/{user_id}", response_model=User)
async def update_user(user_id: str, payload: UserUpdate):
    update = {k: v for k, v in payload.dict(exclude_unset=True).items() if v is not None}
    if "emergency_contacts" in update:
        update["emergency_contacts"] = [
            c.dict() if hasattr(c, "dict") else c for c in update["emergency_contacts"]
        ]
    if update:
        result = await db.users.update_one({"id": user_id}, {"$set": update})
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="User not found")
    doc = await db.users.find_one({"id": user_id}, {"_id": 0})
    return User(**doc)


# --- SOS ---
@api_router.post("/sos", response_model=SOSIncident)
async def create_sos(payload: SOSCreate):
    user = await db.users.find_one({"id": payload.user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    incident_id = str(uuid.uuid4())
    volunteers = generate_nearby_volunteers()
    incident = {
        "id": incident_id,
        "user_id": payload.user_id,
        "user_name": user["name"],
        "lat": payload.lat,
        "lng": payload.lng,
        "status": "active",
        "volunteers": volunteers,
        "emergency_contacts_notified": user.get("emergency_contacts", []),
        "created_at": now_iso(),
    }
    await db.sos_incidents.insert_one(incident.copy())
    logger.info(
        f"[SOS] user={user['name']} at ({payload.lat},{payload.lng}) -> "
        f"notified {len(volunteers)} volunteers + {len(user.get('emergency_contacts', []))} contacts"
    )
    return SOSIncident(**clean(incident))


@api_router.get("/sos/{sos_id}", response_model=SOSIncident)
async def get_sos(sos_id: str):
    doc = await db.sos_incidents.find_one({"id": sos_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="SOS incident not found")
    return SOSIncident(**doc)


@api_router.post("/sos/{sos_id}/cancel", response_model=SOSIncident)
async def cancel_sos(sos_id: str):
    await db.sos_incidents.update_one(
        {"id": sos_id}, {"$set": {"status": "cancelled"}}
    )
    doc = await db.sos_incidents.find_one({"id": sos_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="SOS incident not found")
    return SOSIncident(**doc)


@api_router.post("/sos/{sos_id}/respond", response_model=SOSIncident)
async def respond_sos(sos_id: str, payload: SOSRespond):
    doc = await db.sos_incidents.find_one({"id": sos_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="SOS incident not found")
    volunteers = doc.get("volunteers", [])
    matched = False
    for v in volunteers:
        if v["id"] == payload.volunteer_id:
            v["responding"] = True
            matched = True
            break
    if not matched:
        raise HTTPException(status_code=404, detail="Volunteer not found on incident")
    await db.sos_incidents.update_one(
        {"id": sos_id}, {"$set": {"volunteers": volunteers}}
    )
    doc = await db.sos_incidents.find_one({"id": sos_id}, {"_id": 0})
    return SOSIncident(**doc)


# Simulate that a volunteer starts responding after a short delay (for MVP polling)
@api_router.post("/sos/{sos_id}/simulate-response")
async def simulate_response(sos_id: str):
    doc = await db.sos_incidents.find_one({"id": sos_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="SOS incident not found")
    volunteers = doc.get("volunteers", [])
    changed = 0
    for v in volunteers:
        if not v.get("responding"):
            v["responding"] = True
            changed += 1
            if changed >= 2:
                break
    await db.sos_incidents.update_one(
        {"id": sos_id}, {"$set": {"volunteers": volunteers}}
    )
    return {"updated": changed}


# --- Ratings & Community Map ---
@api_router.post("/ratings")
async def create_rating(payload: RouteRating):
    doc = {
        "id": str(uuid.uuid4()),
        "user_id": payload.user_id,
        "lat": payload.lat,
        "lng": payload.lng,
        "stars": payload.stars,
        "tags": payload.tags,
        "note": payload.note,
        "created_at": now_iso(),
    }
    await db.ratings.insert_one(doc.copy())
    return clean(doc)


@api_router.get("/community/pins")
async def community_pins():
    """Aggregate ratings into map pins with color coding."""
    pins: List[dict] = []
    async for r in db.ratings.find({}, {"_id": 0}):
        # Simple grid bucket ~50m
        key_lat = round(r["lat"], 4)
        key_lng = round(r["lng"], 4)
        found = None
        for p in pins:
            if p["_key"] == (key_lat, key_lng):
                found = p
                break
        if found is None:
            pins.append(
                {
                    "_key": (key_lat, key_lng),
                    "lat": key_lat,
                    "lng": key_lng,
                    "stars_sum": r["stars"],
                    "count": 1,
                    "tags": list(r.get("tags", [])),
                }
            )
        else:
            found["stars_sum"] += r["stars"]
            found["count"] += 1
            found["tags"].extend(r.get("tags", []))
    out = []
    for p in pins:
        out.append(
            {
                "lat": p["lat"],
                "lng": p["lng"],
                "stars": round(p["stars_sum"] / p["count"], 2),
                "count": p["count"],
                "tags": list(set(p["tags"]))[:5],
            }
        )
    return {"pins": out}


# --- Helplines ---
@api_router.get("/helplines")
async def helplines():
    return {
        "helplines": [
            {"id": "nirbhaya", "name": "Nirbhaya Helpline", "number": "1091", "priority": 1},
            {"id": "police", "name": "Mumbai Police", "number": "100", "priority": 2},
            {"id": "womens_police_bandra", "name": "Bandra Women's Police Station", "number": "+912226401234", "priority": 3},
            {"id": "womens_police_andheri", "name": "Andheri Women's Police Station", "number": "+912226681234", "priority": 3},
            {"id": "ambulance", "name": "Ambulance", "number": "108", "priority": 4},
        ]
    }


# ---------- App wiring ----------
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
