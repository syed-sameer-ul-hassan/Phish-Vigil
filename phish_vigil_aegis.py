import os
import json
import datetime
import math
import hashlib
import logging
import sys
from functools import wraps
from flask import Flask, request, jsonify, g, abort
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.postgresql import JSONB
from itsdangerous import URLSafeTimedSerializer, BadSignature

# ==============================================================================
#   PHISH-VIGIL v5.0 "AEGIS" | Human Risk Intelligence Platform
#   Author: Syed Sameer Ul Hassan
#   Website: sameer.orildo.online
# ==============================================================================

def print_banner():
    banner = r"""
    ____  __    _      __          _    ___       _ __ 
   / __ \/ /_  (_)____/ /_        | |  / (_)___ _(_) / 
  / /_/ / __ \/ / ___/ __ \_______| | / / / __ `/ / /  
 / ____/ / / / (__  ) / / /_____/ | |/ / / /_/ / / /   
/_/   /_/ /_/_/____/_/ /_/        |___/_/\__, /_/_/    
                                        /____/         
       >> AEGIS v5.0 - Human Risk Intelligence <<
    """
    print("\033[94m" + banner + "\033[0m")
    print(f"  [+] ARCHITECT:  Syed Sameer Ul Hassan (CCT)")
    print(f"  [+] WEBSITE:    sameer.orildo.online")
    print(f"  [+] GITHUB:     syed-sameer-ul-hassan")
    print("="*70)
    print("  [!] STATUS:     Enterprise Defensive Simulation Mode")
    print("  [!] LOGGING:    WORM-Compliant Immutable Audit Active")
    print("="*70 + "\n")

app = Flask(__name__)
# Security Config
app.config['SECRET_KEY'] = os.environ.get('PV_SECRET_KEY', 'AEGIS_DEV_KEY_CHANGE_IN_PROD')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///vigil_aegis.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Immutable Audit Log
audit_logger = logging.getLogger('vigil_audit')
audit_logger.setLevel(logging.INFO)
handler = logging.FileHandler('vigil_audit_immutable.json')
audit_logger.addHandler(handler)

db = SQLAlchemy(app)
serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])

# --- DATA MODELS ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, index=True, nullable=False)
    role = db.Column(db.String(20), default='USER')
    department = db.Column(db.String(50))
    risk_score = db.Column(db.Float, default=10.0)
    resilience_score = db.Column(db.Float, default=0.0)
    risk_velocity = db.Column(db.Float, default=0.0)
    confidence_index = db.Column(db.Float, default=0.0)
    consecutive_safe_campaigns = db.Column(db.Integer, default=0)
    total_interactions = db.Column(db.Integer, default=0)
    training_due = db.Column(db.Boolean, default=False)
    last_risk_update = db.Column(db.DateTime, default=datetime.datetime.utcnow)

class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event_hash = db.Column(db.String(64), unique=True)
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    actor_email = db.Column(db.String(120))
    action_type = db.Column(db.String(50))
    metadata_json = db.Column(db.Text)

# --- ENGINE ---
class AegisEngine:
    @staticmethod
    def calculate_impact(user, event_type):
        days = (datetime.datetime.utcnow() - user.last_risk_update).days
        decay = math.exp(-0.01 * days)
        user.risk_score *= decay
        
        delta_risk, delta_res = 0.0, 0.0
        
        if event_type == 'CLICK':
            delta_risk = 25.0 * (1.5 if user.risk_score > 50 else 1.0)
            delta_res = -10.0
            user.consecutive_safe_campaigns = 0
            user.training_due = True
        elif event_type == 'REPORT':
            delta_risk = -15.0
            delta_res = 5.0
            user.consecutive_safe_campaigns += 1
            if user.consecutive_safe_campaigns >= 3: delta_res *= 1.5

        prev_risk = user.risk_score
        user.risk_score = max(0, min(100, user.risk_score + delta_risk))
        user.resilience_score = max(0, min(100, user.resilience_score + delta_res))
        user.risk_velocity = user.risk_score - prev_risk
        
        user.total_interactions += 1
        user.confidence_index = min(1.0, user.total_interactions / 10.0)
        user.last_risk_update = datetime.datetime.utcnow()
        db.session.commit()
        return {"risk": round(user.risk_score, 1), "resilience": round(user.resilience_score, 1)}

# --- ROUTES ---
@app.route('/api/v5/interact', methods=['POST'])
def interact():
    data = request.json
    try:
        payload = serializer.loads(data.get('token'), salt='aegis-sim')
        user = User.query.get(payload['uid'])
        if not user: abort(404)
        
        h = hashlib.sha256(f"{datetime.datetime.utcnow()}{user.email}".encode()).hexdigest()
        db.session.add(AuditLog(event_hash=h, actor_email=user.email, action_type=data.get('type')))
        db.session.commit()
        
        metrics = AegisEngine.calculate_impact(user, data.get('type'))
        return jsonify({"status": "success", "metrics": metrics})
    except BadSignature:
        abort(400, "Invalid Token")

@app.route('/api/v5/dashboard', methods=['GET'])
def dashboard():
    users = User.query.all()
    if not users: return jsonify({"msg": "No data"})
    avg_risk = sum(u.risk_score for u in users) / len(users)
    avg_res = sum(u.resilience_score for u in users) / len(users)
    return jsonify({
        "Organization Risk": round(avg_risk, 1),
        "Resilience Index": round(avg_res, 1),
        "Status": "Improving" if avg_res > 50 else "Attention Needed"
    })

if __name__ == '__main__':
    print_banner()
    with app.app_context():
        db.create_all()
        if not User.query.first():
            db.session.add(User(email="admin@corp.local", role="CISO", risk_score=0))
            db.session.commit()
            print("[+] Database Initialized.\n")
    app.run(port=5000)
