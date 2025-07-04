from fastapi import FastAPI, Request, Form, BackgroundTasks
from fastapi.responses import HTMLResponse
from fastapi import HTTPException 
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr
from dotenv import load_dotenv
import os, random, redis, smtplib
from email.message import EmailMessage

# Load .env
load_dotenv()

# Init app + redis + templates
app = FastAPI()
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # or ["http://localhost:3000"] for specific frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

"""Basic connection example.
"""
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Redis Cloud connection
r = redis.Redis(
    host='redis-19010.crce179.ap-south-1-1.ec2.redns.redis-cloud.com',
    port=19010,
    decode_responses=True,
    username="default",
    password="kfkIYdgxoAHrUNnzsTRtPrwyki2zUEI7",
)
# Show form
@app.get("/", response_class=HTMLResponse)
def show_form(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# Pydantic models
class EmailRequest(BaseModel):
    email: EmailStr

class OTPVerify(BaseModel):
    email: EmailStr
    otp: str

# Send email OTP
def send_email_otp(recipient: str, otp: str):
    msg = EmailMessage()
    msg['Subject'] = '🔐 Your OTP Code'
    msg['From'] = os.getenv("EMAIL_FROM")
    msg['To'] = recipient

    html_content = f"""
    <html>
      <body style="font-family: Arial; text-align: center; padding: 20px;">
        <h2>🔒 Email Verification</h2>
        <p>Use the OTP below to verify your email address:</p>
        <h1 style="font-size: 36px; color: #007BFF;">{otp}</h1>
        <p>This OTP will expire in <strong>2 minutes</strong>.</p>
        <br/>
        <p style="font-size: 12px; color: gray;">If you didn't request this, you can ignore this email.</p>
      </body>
    </html>
    """

    msg.set_content(f"Your OTP is: {otp}")
    msg.add_alternative(html_content, subtype="html")

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(os.getenv("EMAIL_FROM"), os.getenv("EMAIL_PASSWORD"))
        smtp.send_message(msg)

# API to send OTP
@app.post("/send-otp/")
def send_otp(data: EmailRequest, bg: BackgroundTasks):
    email = data.email

    # Rate limiting logic
    key = f"otp:count:{email}"
    attempts = r.get(key)
    if attempts and int(attempts) >= 3:
        raise HTTPException(status_code=429, detail="Too many OTP requests. Try again later.")
    else:
        r.incr(key)
        r.expire(key, 3600)  # 1 hour limit window

    otp = str(random.randint(1000,9999))
    r.setex(f"otp:{email}", 120, otp)  # 2 min OTP expiry
    bg.add_task(send_email_otp, email, otp)
    return {"message": "OTP sent to your email"}


# API to verify OTP
@app.post("/verify-otp/")
def verify_otp(data: OTPVerify):
    stored = r.get(f"otp:{data.email}")
    if not stored:
        return {"error": "OTP expired or not found"}
    if stored != data.otp:
        return {"error": "Invalid OTP"}
    r.delete(f"otp:{data.email}")
    return {"message": "OTP verified"}
# REDIS_URL=redis://localhost:6379
# EMAIL_FROM=svceshop@gmail.com
# EMAIL_PASSWORD=mqnpzzfqcaqnglry


