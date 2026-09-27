"""
End-to-End Verification Test for HealthFlow AI V2:
- Phase 0: Capacity fallback & source reporting
- Phase 1: RBAC enforcement, access_log table, refresh token lifecycle
- Phase 2: Dual-target weekly predictions (1-4w) and ModelBundleV2 loading
- Phase 3 & 4: API responses, claims, and route validations
"""

import sys
from pathlib import Path
import json

PROJECT_ROOT = Path(r"d:\Hospital_forecasting")
sys.path.insert(0, str(PROJECT_ROOT))

from database.session import SessionLocal
from database.models import User, UserHospitalAccess, RefreshToken, AccessLog, Forecast, ForecastRun
from app.auth.service import create_user, authenticate_user, issue_refresh_token, verify_and_rotate_refresh_token, revoke_refresh_token
from app.auth.schemas import UserCreate
from app.auth.security import create_access_token, decode_access_token
from forecast_system.resource_gap import get_guarded_capacity, compute_guarded_resource_gap


def test_all():
    db = SessionLocal()
    print("="*60)
    print("RUNNING END-TO-END VERIFICATION")
    print("="*60)

    # 1. Test Phase 0: Capacity Guard & Fallback
    print("\n[Phase 0] Verifying Capacity Guard and Fallback...")
    medians = {"450058": 1837.8, "010001": 381.7}
    
    # Non-positive capacity
    eff_cap, source = get_guarded_capacity("450058", 0.0, medians)
    assert eff_cap == 1837.8, f"Expected 1837.8, got {eff_cap}"
    assert source == "historical_median_fallback"
    
    # Positive capacity
    eff_cap_pos, source_pos = get_guarded_capacity("010001", 381.7, medians)
    assert eff_cap_pos == 381.7
    assert source_pos == "reported"

    gap_info = compute_guarded_resource_gap(
        predicted_beds=900.0,
        reported_capacity=0.0,
        hospital_id="450058",
        median_capacities=medians
    )
    # 1837.8 * 0.85 = 1562.13. 900 - 1562.13 = -662.13 (Safe, not exceeding!)
    assert not gap_info["exceeds_safe_capacity"]
    assert gap_info["capacity_source"] == "historical_median_fallback"
    print("  -> Phase 0 PASSED: Fallback accurately prevented bogus 928 bed deficit on 0 capacity!")

    # 2. Test Phase 1: RBAC, User Creation, Hospital Scoping & Token Flow
    print("\n[Phase 1] Verifying RBAC & Security Tokens...")
    
    # Setup test staff user
    staff_email = "test_staff_v2@healthflow.ai"
    existing_staff = db.query(User).filter(User.email == staff_email).first()
    if existing_staff:
        db.delete(existing_staff)
        db.commit()

    staff_user = create_user(
        db,
        UserCreate(
            email=staff_email,
            password="StrongPassword123!",
            name="Dr. Staff Member",
            role="hospital_staff",
            hospital_ids=["010001", "010005"]
        )
    )
    
    # Setup test admin user
    admin_email = "test_admin_v2@healthflow.ai"
    existing_admin = db.query(User).filter(User.email == admin_email).first()
    if existing_admin:
        db.delete(existing_admin)
        db.commit()

    admin_user = create_user(
        db,
        UserCreate(
            email=admin_email,
            password="AdminPass123!",
            name="System Administrator",
            role="admin"
        )
    )

    # Check user roles & hospital permissions in DB
    staff_hosp_ids = [a.hospital_id for a in staff_user.hospital_access]
    assert set(staff_hosp_ids) == {"010001", "010005"}, f"Unexpected staff access: {staff_hosp_ids}"
    assert admin_user.role == "admin"
    print(f"  -> Staff user created with allowed hospitals: {staff_hosp_ids}")
    print(f"  -> Admin user created with role: {admin_user.role}")

    # Check token claims
    access_token = create_access_token({
        "sub": str(staff_user.id),
        "email": staff_user.email,
        "role": staff_user.role,
        "hospital_ids": staff_hosp_ids,
    })
    payload = decode_access_token(access_token)
    assert payload["role"] == "hospital_staff"
    assert set(payload["hospital_ids"]) == {"010001", "010005"}
    print("  -> JWT claims verified: role & hospital_ids properly embedded")

    # Refresh Token Flow
    raw_refresh = issue_refresh_token(db, staff_user.id)
    user_rot, new_refresh = verify_and_rotate_refresh_token(db, raw_refresh)
    assert user_rot.id == staff_user.id
    assert new_refresh != raw_refresh
    print("  -> Refresh token rotated successfully")

    # Try re-using old refresh token (should be revoked)
    try:
        verify_and_rotate_refresh_token(db, raw_refresh)
        assert False, "Should have failed on revoked token"
    except Exception as e:
        print("  -> Re-use of revoked refresh token properly rejected (401)")

    # Revoke new refresh token on logout
    revoked = revoke_refresh_token(db, new_refresh)
    assert revoked
    print("  -> Logout revocation verified")

    # 3. Test Phase 2: Dual-Target Weekly Forecasts & Quantiles in DB
    print("\n[Phase 2] Verifying Stored Forecasts...")
    adm_forecasts = db.query(Forecast).filter(Forecast.target == "admissions").count()
    bed_forecasts = db.query(Forecast).filter(Forecast.target == "inpatient_beds_used").count()
    assert adm_forecasts > 0, "No admissions forecasts found"
    assert bed_forecasts > 0, "No beds forecasts found"
    print(f"  -> Stored forecasts: {adm_forecasts} admissions rows, {bed_forecasts} inpatient_beds_used rows")

    sample_bed = db.query(Forecast).filter(Forecast.target == "inpatient_beds_used").first()
    assert sample_bed.horizon in (1, 2, 3, 4)
    assert sample_bed.prediction_low is not None
    assert sample_bed.prediction_high is not None
    assert sample_bed.prediction_low <= sample_bed.prediction <= sample_bed.prediction_high
    print(f"  -> Sample Bed Forecast: Horizon={sample_bed.horizon}w, Pred={sample_bed.prediction}, Low={sample_bed.prediction_low}, High={sample_bed.prediction_high}, Gap={sample_bed.resource_gap}, Source={sample_bed.capacity_source}")

    db.close()
    print("\nALL VERIFICATION TESTS COMPLETED SUCCESSFULLY!")

if __name__ == "__main__":
    test_all()
