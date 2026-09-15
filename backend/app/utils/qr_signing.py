import hmac,hashlib,json,base64,os
SECRET=os.getenv("CERTIFICATE_HMAC_SECRET","dev-certificate-secret-change-me")
def sign_certificate_payload(certificate_id,instrument_serial,issued_at_iso):
 p=f"{certificate_id}:{instrument_serial}:{issued_at_iso}";sig=hmac.new(SECRET.encode(),p.encode(),hashlib.sha256).hexdigest();return base64.urlsafe_b64encode(json.dumps({"cid":str(certificate_id),"sn":instrument_serial,"ts":issued_at_iso,"sig":sig},separators=(",",":")).encode()).decode()
def verify_certificate_payload(token):
 try:
  d=json.loads(base64.urlsafe_b64decode(token.encode()).decode());p=f"{d['cid']}:{d['sn']}:{d['ts']}";e=hmac.new(SECRET.encode(),p.encode(),hashlib.sha256).hexdigest();return d if hmac.compare_digest(d["sig"],e) else None
 except:return None
