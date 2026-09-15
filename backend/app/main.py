import os, uuid, json, secrets, shutil, smtplib, logging
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Header, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, String, Float, DateTime, Text, ForeignKey, Boolean, func
from sqlalchemy.orm import declarative_base, sessionmaker, Session
import base64,hmac,hashlib
import jwt
from passlib.context import CryptContext
from dotenv import load_dotenv
from app.utils.geo import calculate_haversine_distance

ROOT=os.path.dirname(os.path.dirname(__file__))
load_dotenv(os.path.join(ROOT,".env"))
DB=os.path.join(ROOT,"legal_metrology.db")
UPLOADS=os.path.join(ROOT,"uploads"); os.makedirs(UPLOADS,exist_ok=True)
engine=create_engine("sqlite:///"+DB,connect_args={"check_same_thread":False})
SessionLocal=sessionmaker(bind=engine,autocommit=False,autoflush=False)
Base=declarative_base()
JWT_SECRET=os.getenv("JWT_SECRET_KEY","dev-only-change-me")
JWT_ALGORITHM=os.getenv("JWT_ALGORITHM","HS256")
pwd_context=CryptContext(schemes=["bcrypt"], deprecated="auto")
OTP_STORE={}
logger=logging.getLogger("legal-metrology.auth")
def hash_password(password):
 return pwd_context.hash(password)
def verify_password(password,stored):
 import hashlib, hmac
 try:
    if stored.startswith("pbkdf2_sha256$"):
     _,it,salt_hex,hash_hex=stored.split("$",3); dk=hashlib.pbkdf2_hmac("sha256",password.encode(),bytes.fromhex(salt_hex),int(it)); return hmac.compare_digest(dk.hex(),hash_hex)
    return pwd_context.verify(password,stored)
 except Exception:return False

def auth_role(role):
 return {"TRADER":"CONSUMER","LMO":"FIELD_OFFICER","GATC":"FIELD_OFFICER","ADMIN":"ADMIN"}.get(role,role)

class User(Base):
    __tablename__="users"
    id=Column(String(36),primary_key=True); full_name=Column(String(150),nullable=False); email=Column(String(255),unique=True,index=True,nullable=False)
    phone=Column(String(20),unique=True,nullable=False); password_hash=Column(String(255),nullable=False); role=Column(String(20),nullable=False,index=True)
    state=Column(String(100),nullable=False); district=Column(String(100),nullable=False); is_active=Column(Boolean,default=True); is_verified=Column(Boolean,default=True)

class Instrument(Base):
    __tablename__="instruments"
    id=Column(String(36),primary_key=True); owner_id=Column(String(36),ForeignKey("users.id"),nullable=False); model_name=Column(String(150),nullable=False)
    manufacturer=Column(String(150),nullable=False); serial_number=Column(String(100),unique=True,index=True,nullable=False); category=Column(String(50),nullable=False)
    capacity=Column(Float,nullable=False); capacity_unit=Column(String(20),nullable=False); precision_class=Column(String(20),nullable=False)
    address_line=Column(String(255),nullable=False); state=Column(String(100),nullable=False); district=Column(String(100),nullable=False); pincode=Column(String(10),nullable=False)
    latitude=Column(Float); longitude=Column(Float)

class Application(Base):
    __tablename__="applications"
    id=Column(String(36),primary_key=True); instrument_id=Column(String(36),ForeignKey("instruments.id"),nullable=False); applicant_id=Column(String(36),ForeignKey("users.id"),nullable=False)
    assigned_officer_id=Column(String(36),ForeignKey("users.id")); status=Column(String(40),default="SUBMITTED",index=True); scheduled_date=Column(DateTime)
    payment_status=Column(String(20),default="PENDING"); payment_reference=Column(String(100)); fee_amount=Column(Float,default=500)
    rejection_reason=Column(String(500)); decided_at=Column(DateTime); created_at=Column(DateTime,default=lambda:datetime.now(timezone.utc))

class Inspection(Base):
    __tablename__="inspection_records"
    id=Column(String(36),primary_key=True); application_id=Column(String(36),ForeignKey("applications.id"),nullable=False); inspector_id=Column(String(36),ForeignKey("users.id"),nullable=False)
    actual_error_readings=Column(Text,default="{}"); mpe_value=Column(Float,default=.05); result=Column(String(20),nullable=False); latitude=Column(Float,nullable=False); longitude=Column(Float,nullable=False)
    inspected_at=Column(DateTime,default=lambda:datetime.now(timezone.utc)); inspector_signature_path=Column(String(500),default=""); remarks=Column(Text)

class Certificate(Base):
    __tablename__="certificates"
    id=Column(String(36),primary_key=True); application_id=Column(String(36),ForeignKey("applications.id"),unique=True,nullable=False); issued_by_id=Column(String(36),ForeignKey("users.id"),nullable=False)
    certificate_number=Column(String(50),unique=True,index=True,nullable=False); certificate_hash=Column(String(128),unique=True,nullable=False); hmac_signature=Column(String(128),nullable=False)
    issue_date=Column(DateTime,nullable=False); expiry_date=Column(DateTime,nullable=False,index=True); status=Column(String(20),default="ACTIVE"); revoked_reason=Column(String(500)); pdf_path=Column(String(500),default=""); qr_code_path=Column(String(500),default="")

class TamperReport(Base):
    __tablename__="tamper_reports"
    id=Column(String(36),primary_key=True); reference=Column(String(40),unique=True); query_value=Column(String(150),nullable=False); jurisdiction=Column(String(150)); reason=Column(String(500),nullable=False)
    created_at=Column(DateTime,default=lambda:datetime.now(timezone.utc)); status=Column(String(30),default="OPEN")

class Advisory(Base):
    __tablename__="advisories"
    id=Column(String(36),primary_key=True); title=Column(String(200),nullable=False); message=Column(Text,nullable=False); created_at=Column(DateTime,default=lambda:datetime.now(timezone.utc))

Base.metadata.create_all(engine)

def get_db():
    s=SessionLocal()
    try: yield s
    finally: s.close()

def make_token(u):
    now=datetime.now(timezone.utc)
    payload={"sub":u.id,"role":auth_role(u.role),"legacy_role":u.role,"email":u.email,"iat":now,"exp":now+timedelta(hours=8)}
    return jwt.encode(payload,JWT_SECRET,algorithm=JWT_ALGORITHM)

def get_user(authorization: str=Header(default=""),db:Session=Depends(get_db)):
    try:
        scheme,tok=authorization.split(" ",1)
        if scheme.lower() != "bearer": raise Exception()
        data=jwt.decode(tok,JWT_SECRET,algorithms=[JWT_ALGORITHM])
        u=db.get(User,data['sub'])
        if not u or not u.is_active: raise Exception()
        return u
    except Exception: raise HTTPException(401,"Authentication required")

class Login(BaseModel): email:str; password:str
class OtpRequest(BaseModel): email:str
class OtpVerify(BaseModel): email:str; otp:str
class ApplicationIn(BaseModel): serial_number:str; fee_amount:float=500
class InspectionIn(BaseModel):
    application_id:str
    result:str
    latitude:float
    longitude:float
    remarks:str=""
    readings:dict={}

class OfflineInspectionIn(InspectionIn):
    local_id:str
    inspected_at:datetime|None=None

class OfflineInspectionBatch(BaseModel):
    records:list[OfflineInspectionIn]
class TamperIn(BaseModel): query_value:str; jurisdiction:str=""; reason:str
class AdvisoryIn(BaseModel): title:str; message:str

app=FastAPI(title="Legal Metrology Online Verification System",version="1.0.0")
app.add_middleware(CORSMiddleware,allow_origins=["*"],allow_credentials=True,allow_methods=["*"],allow_headers=["*"])
app.mount("/uploads",StaticFiles(directory=UPLOADS),name="uploads")

@app.get("/api/health")
def health(): return {"status":"healthy","database":"SQLite"}

@app.post("/api/v1/auth/login")
@app.post("/api/auth/login")
def login(x:Login,db:Session=Depends(get_db)):
    u=db.query(User).filter(func.lower(User.email)==x.email.lower()).first()
    if not u or not verify_password(x.password,u.password_hash): raise HTTPException(401,"Invalid email or password")
    if not u.password_hash.startswith("$2"):
        u.password_hash=hash_password(x.password);db.commit()
    return {"access_token":make_token(u),"token_type":"bearer","user":{"id":u.id,"name":u.full_name,"email":u.email,"role":u.role}}

def _send_otp_email(email,otp):
    server=os.getenv("SMTP_SERVER"); port=int(os.getenv("SMTP_PORT","587")); username=os.getenv("SMTP_USERNAME"); password=os.getenv("SMTP_PASSWORD")
    if not all((server,username,password)):
        logger.warning("SMTP credentials missing. OTP for %s: %s",email,otp)
        return False
    message=EmailMessage();message["Subject"]="Legal Metrology verification code";message["From"]=username;message["To"]=email
    message.set_content(f"Your e-Verify OTP is {otp}. It expires in 10 minutes.")
    with smtplib.SMTP(server,port,timeout=15) as smtp:
        smtp.starttls();smtp.login(username,password);smtp.send_message(message)
    return True

@app.post("/api/v1/auth/send-otp")
@app.post("/api/auth/send-otp")
def send_otp(x:OtpRequest,db:Session=Depends(get_db)):
    user=db.query(User).filter(func.lower(User.email)==x.email.lower()).first()
    if not user: raise HTTPException(404,"No account exists for this email")
    otp=f"{secrets.randbelow(1000000):06d}";OTP_STORE[x.email.lower()] = (otp,datetime.now(timezone.utc)+timedelta(minutes=10))
    try: delivered=_send_otp_email(x.email,otp)
    except Exception: logger.exception("Unable to send OTP email");delivered=False
    result={"message":"OTP sent" if delivered else "SMTP unavailable; OTP logged to the backend console"}
    if not delivered and os.getenv("APP_ENV","development") != "production": result["dev_otp"]=otp
    return result

@app.post("/api/v1/auth/verify-otp")
@app.post("/api/auth/verify-otp")
def verify_otp(x:OtpVerify,db:Session=Depends(get_db)):
    saved=OTP_STORE.get(x.email.lower())
    if not saved or saved[1] < datetime.now(timezone.utc) or not hmac.compare_digest(saved[0],x.otp):
        raise HTTPException(401,"Invalid or expired OTP")
    user=db.query(User).filter(func.lower(User.email)==x.email.lower()).first()
    if not user: raise HTTPException(404,"No account exists for this email")
    OTP_STORE.pop(x.email.lower(),None)
    return {"access_token":make_token(user),"token_type":"bearer","user":{"id":user.id,"name":user.full_name,"email":user.email,"role":user.role}}

@app.get("/api/auth/me")
def me(u=Depends(get_user)): return {"id":u.id,"name":u.full_name,"email":u.email,"role":u.role}

@app.get("/api/instruments")
def instruments(u=Depends(get_user),db:Session=Depends(get_db)):
    q=db.query(Instrument)
    if u.role=="TRADER": q=q.filter(Instrument.owner_id==u.id)
    return [{"id":x.id,"serial_number":x.serial_number,"model_name":x.model_name,"manufacturer":x.manufacturer,"category":x.category,"state":x.state,"district":x.district} for x in q.all()]

@app.post("/api/applications")
def create_application(x:ApplicationIn,u=Depends(get_user),db:Session=Depends(get_db)):
    i=db.query(Instrument).filter(Instrument.serial_number==x.serial_number).first()
    if not i: raise HTTPException(404,"Instrument not found")
    if u.role=="TRADER" and i.owner_id!=u.id: raise HTTPException(403,"Not your instrument")
    a=Application(id=str(uuid.uuid4()),instrument_id=i.id,applicant_id=u.id,status="PAYMENT_PENDING",fee_amount=x.fee_amount)
    db.add(a);db.commit();db.refresh(a);return {"id":a.id,"serial_number":i.serial_number,"status":a.status,"fee_amount":a.fee_amount}

@app.get("/api/applications")
def applications(u=Depends(get_user),db:Session=Depends(get_db)):
    q=db.query(Application)
    if u.role=="TRADER": q=q.filter(Application.applicant_id==u.id)
    out=[]
    for a in q.order_by(Application.created_at.desc()).all():
        i=db.get(Instrument,a.instrument_id);out.append({"id":a.id,"serial_number":i.serial_number if i else None,"status":a.status,"payment_status":a.payment_status,"fee_amount":a.fee_amount,"scheduled_date":a.scheduled_date.isoformat() if a.scheduled_date else None})
    return out

@app.post("/api/applications/{aid}/schedule")
def schedule(aid,u=Depends(get_user),db:Session=Depends(get_db)):
    if u.role not in ("LMO","ADMIN"): raise HTTPException(403,"Not allowed")
    a=db.get(Application,aid)
    if not a: raise HTTPException(404,"Application not found")
    a.status="SCHEDULED";a.scheduled_date=datetime.now(timezone.utc)+timedelta(days=2);db.commit()
    return {"ok":True,"status":a.status,"scheduled_date":a.scheduled_date.isoformat()}

@app.post("/api/inspections")
def inspect(x:InspectionIn,u=Depends(get_user),db:Session=Depends(get_db)):
    if u.role not in ("LMO","GATC","ADMIN"): raise HTTPException(403,"Inspector role required")
    a=db.get(Application,x.application_id)
    if not a: raise HTTPException(404,"Application not found")
    instrument=db.get(Instrument,a.instrument_id)
    if instrument is None or instrument.latitude is None or instrument.longitude is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,"Instrument has no registered geofence")
    distance=calculate_haversine_distance(x.latitude,x.longitude,instrument.latitude,instrument.longitude)
    if distance>200:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,f"Geo-fence exceeded: inspector is {distance:.1f}m from the registered site")
    i=Inspection(id=str(uuid.uuid4()),application_id=a.id,inspector_id=u.id,result=x.result,latitude=x.latitude,longitude=x.longitude,remarks=x.remarks,actual_error_readings=json.dumps(x.readings))
    a.status="APPROVED" if x.result=="PASS" else "REJECTED";a.decided_at=datetime.now(timezone.utc);db.add(i);db.commit()
    return {"id":i.id,"application_status":a.status}

@app.post("/api/inspections/sync-batch")
def sync_inspections(x:OfflineInspectionBatch,u=Depends(get_user),db:Session=Depends(get_db)):
    if u.role not in ("LMO","GATC","ADMIN"): raise HTTPException(403,"Inspector role required")
    synced=[]; rejected=[]
    for item in x.records:
        a=db.get(Application,item.application_id)
        instrument=db.get(Instrument,a.instrument_id) if a else None
        if not a or not instrument:
            rejected.append({"local_id":item.local_id,"reason":"Application or instrument not found"})
            continue
        if instrument.latitude is None or instrument.longitude is None:
            rejected.append({"local_id":item.local_id,"reason":"Instrument has no registered geofence"})
            continue
        distance=calculate_haversine_distance(item.latitude,item.longitude,instrument.latitude,instrument.longitude)
        if distance>200:
            rejected.append({"local_id":item.local_id,"reason":f"Geo-fence exceeded: {distance:.1f}m"})
            continue
        inspection=Inspection(id=str(uuid.uuid4()),application_id=a.id,inspector_id=u.id,result=item.result,latitude=item.latitude,longitude=item.longitude,remarks=item.remarks,actual_error_readings=json.dumps(item.readings),inspected_at=item.inspected_at or datetime.now(timezone.utc))
        a.status="APPROVED" if item.result=="PASS" else "REJECTED"; a.decided_at=inspection.inspected_at
        db.add(inspection); synced.append(item.local_id)
    db.commit()
    return {"total_received":len(x.records),"synced_count":len(synced),"synced_ids":synced,"rejected":rejected}

@app.post("/api/certificates/{aid}/generate")
def generate(aid,u=Depends(get_user),db:Session=Depends(get_db)):
    if u.role not in ("LMO","GATC","ADMIN"): raise HTTPException(403,"Not allowed")
    a=db.get(Application,aid)
    if not a or a.status!="APPROVED": raise HTTPException(400,"Application must be approved")
    old=db.query(Certificate).filter(Certificate.application_id==aid).first()
    if old:return {"id":old.id,"certificate_number":old.certificate_number}
    i=db.get(Instrument,a.instrument_id);now=datetime.now(timezone.utc);exp=now+timedelta(days=365);num=f"LM-CERT-{now.year}-{secrets.randbelow(900000)+100000}";h=secrets.token_urlsafe(24)
    from app.utils.qr_signing import sign_certificate_payload
    sig=sign_certificate_payload(h,i.serial_number,now.isoformat())
    c=Certificate(id=str(uuid.uuid4()),application_id=aid,issued_by_id=u.id,certificate_number=num,certificate_hash=h,hmac_signature=sig,issue_date=now,expiry_date=exp,status="ACTIVE")
    a.status="CERTIFICATE_ISSUED";db.add(c);db.commit();return {"id":c.id,"certificate_number":num,"expiry_date":exp.isoformat(),"verification_token":sig}

@app.get("/api/certificates/verify")
def verify(number:str,db:Session=Depends(get_db)):
    c=db.query(Certificate).filter(Certificate.certificate_number==number).first()
    if not c: raise HTTPException(404,"Certificate not found")
    a=db.get(Application,c.application_id);i=db.get(Instrument,a.instrument_id);status=c.status
    if c.expiry_date.replace(tzinfo=timezone.utc)<datetime.now(timezone.utc) and status=="ACTIVE":status="EXPIRED"
    return {"verified":status=="ACTIVE","id":c.id,"certificate_number":c.certificate_number,"status":status,"instrument_serial":i.serial_number,"manufacturer":i.manufacturer,"model":i.model_name,"issue_date":c.issue_date.isoformat(),"expiry_date":c.expiry_date.isoformat()}

@app.get("/api/certificates/verify-token")
def verify_token(token:str):
    from app.utils.qr_signing import verify_certificate_payload
    payload=verify_certificate_payload(token)
    if not payload:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,"Invalid or tampered certificate signature")
    return {"verified":True,"certificate_id":payload["cid"],"instrument_serial":payload["sn"],"issued_at_utc":payload["ts"]}

@app.get("/api/v1/dev/sample-token")
@app.get("/api/dev/sample-token")
def sample_dev_token():
    from app.utils.qr_signing import sign_certificate_payload
    valid=sign_certificate_payload("sandbox-cert","DEV-SCALE-001","2026-09-14T00:00:00+00:00")
    return {"valid_token":valid,"tampered_token":valid[:-8]+"INVALID0"}

@app.get("/api/certificates/{cid}/pdf")
def pdf(cid:str,db:Session=Depends(get_db)):
    c=db.get(Certificate,cid)
    if not c:raise HTTPException(404,"Certificate not found")
    a=db.get(Application,c.application_id);i=db.get(Instrument,a.instrument_id);owner=db.get(User,a.applicant_id)
    from app.services.certificate_pdf_service import generate_certificate_pdf
    data=generate_certificate_pdf(certificate_id=c.id,instrument_serial=i.serial_number,instrument_type=i.category,owner_name=owner.full_name,inspection_date=c.issue_date.date().isoformat(),verification_status=c.status,verify_base_url="http://localhost:8000/api")
    return Response(data,media_type="application/pdf",headers={"Content-Disposition":f'attachment; filename="{c.certificate_number}.pdf"'})

@app.post("/api/tamper-reports")
def tamper(x:TamperIn,db:Session=Depends(get_db)):
    r=TamperReport(id=str(uuid.uuid4()),reference="INC-"+str(secrets.randbelow(900000)+100000),query_value=x.query_value,jurisdiction=x.jurisdiction,reason=x.reason)
    db.add(r);db.commit();return {"reference":r.reference,"status":"OPEN"}

@app.get("/api/admin/stats")
def stats(u=Depends(get_user),db:Session=Depends(get_db)):
    if u.role!="ADMIN":raise HTTPException(403,"Admin role required")
    return {"applications":db.query(Application).count(),"pending":db.query(Application).filter(Application.status.in_(["SUBMITTED","PAYMENT_PENDING","SCHEDULED"])).count(),"instruments":db.query(Instrument).count(),"certificates":db.query(Certificate).count(),"reports":db.query(TamperReport).count()}

@app.post("/api/admin/advisories")
def advisory(x:AdvisoryIn,u=Depends(get_user),db:Session=Depends(get_db)):
    if u.role!="ADMIN":raise HTTPException(403,"Admin role required")
    a=Advisory(id=str(uuid.uuid4()),title=x.title,message=x.message);db.add(a);db.commit();return {"id":a.id,"message":"Advisory dispatched"}

@app.post("/api/v1/dev/seed")
@app.post("/api/dev/seed")
def seed_dev_data(u=Depends(get_user),db:Session=Depends(get_db)):
    if u.role!="ADMIN": raise HTTPException(403,"Admin role required")
    created_officers=0;created_instruments=0
    officers=[]
    for index in range(1,4):
        email=f"test-officer-{index}@example.com"
        officer=db.query(User).filter(User.email==email).first()
        if not officer:
            officer=User(id=str(uuid.uuid4()),full_name=f"Sandbox Officer {index}",email=email,phone=f"91000000{index:02d}",password_hash=hash_password("Demo@123"),role="LMO",state="Tamil Nadu",district="Chennai")
            db.add(officer);created_officers+=1
        officers.append(officer)
    db.flush()
    for index in range(1,11):
        serial=f"DEV-SCALE-{index:03d}"
        if db.query(Instrument).filter(Instrument.serial_number==serial).first(): continue
        db.add(Instrument(id=str(uuid.uuid4()),owner_id=u.id,model_name=f"Sandbox Scale {index}",manufacturer="e-Verify Test Lab",serial_number=serial,category="WEIGHING_SCALE",capacity=200,capacity_unit="kg",precision_class="Class III",address_line=f"Sandbox Shop {((index-1)%5)+1}",state="Tamil Nadu",district="Chennai",pincode="600001",latitude=13.0827+((index-1)%5)*0.001,longitude=80.2707+((index-1)%5)*0.001))
        created_instruments+=1
    db.commit()
    return {"message":"Developer seed complete","shops":5,"verified_scales":10,"officers":len(officers),"created_officers":created_officers,"created_scales":created_instruments}

@app.post("/api/uploads/inspection-photo")
def upload(file:UploadFile=File(...),u=Depends(get_user)):
    if u.role not in ("LMO","GATC","ADMIN"):raise HTTPException(403,"Not allowed")
    ext=os.path.splitext(file.filename or "")[1].lower()
    if ext not in {".jpg",".jpeg",".png",".pdf"}:raise HTTPException(400,"Only JPG, PNG and PDF are allowed")
    name=secrets.token_hex(16)+ext
    with open(os.path.join(UPLOADS,name),"wb") as f:shutil.copyfileobj(file.file,f)
    return {"file_path":"/uploads/"+name}

FRONT=os.path.join(ROOT,"..","frontend")
@app.get("/",include_in_schema=False)
def root():return FileResponse(os.path.join(FRONT,"index.html"))
@app.get("/app.js",include_in_schema=False)
def javascript():return FileResponse(os.path.join(FRONT,"app.js"),media_type="application/javascript")
@app.get("/{page}.html",include_in_schema=False)
def page(page:str):
    if page not in {"index","merchant","lmo","admin","verify","sandbox","login"}:raise HTTPException(404)
    return FileResponse(os.path.join(FRONT,page+".html"))

@app.get("/sandbox",include_in_schema=False)
def sandbox_page():return FileResponse(os.path.join(FRONT,"sandbox.html"))
@app.get("/login",include_in_schema=False)
def login_page():return FileResponse(os.path.join(FRONT,"login.html"))
@app.get("/inspector-dashboard",include_in_schema=False)
def inspector_dashboard_page():return FileResponse(os.path.join(FRONT,"lmo.html"))
@app.get("/verify-submission",include_in_schema=False)
def verify_submission_page():return FileResponse(os.path.join(FRONT,"verify.html"))

def seed():
    db=SessionLocal()
    if db.query(User).count():db.close();return
    users=[]
    for name,email,phone,role in [("Trader Demo","trader@example.com","9000000001","TRADER"),("LMO Officer","lmo@example.com","9000000002","LMO"),("GATC Inspector","gatc@example.com","9000000003","GATC"),("State Admin","admin@example.com","9000000004","ADMIN")]:
        u=User(id=str(uuid.uuid4()),full_name=name,email=email,phone=phone,password_hash=hash_password("Demo@123"),role=role,state="Tamil Nadu",district="Chennai");db.add(u);users.append(u)
    db.commit();trader=users[0]
    for serial,model,cat in [("LM-SCL-00125","EW-200","WEIGHING_SCALE"),("LM-FM-00420","FlowPro 500","FLOW_METER")]:
        db.add(Instrument(id=str(uuid.uuid4()),owner_id=trader.id,model_name=model,manufacturer="Demo Instruments",serial_number=serial,category=cat,capacity=200,capacity_unit="kg",precision_class="Class III",address_line="Legal Metrology Demo Site",state="Tamil Nadu",district="Chennai",pincode="600001",latitude=13.0827,longitude=80.2707))
    db.commit();db.close()
seed()
