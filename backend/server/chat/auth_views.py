import json
import os

from django.http import JsonResponse
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from django.views.decorators.csrf import csrf_exempt
from django.core.mail import send_mail
from django.conf import settings
from django.db.models import Count

from .models import AuthToken, PasswordResetOTP, Conversation, Message


def get_user_from_token(request):
    """Extract user from Authorization header: Token <key>"""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Token "):
        return None
    key = auth_header[6:]
    try:
        token = AuthToken.objects.select_related("user").get(key=key)
        return token.user
    except AuthToken.DoesNotExist:
        return None


@csrf_exempt
def register_view(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    name = body.get("name", "").strip()
    email = body.get("email", "").strip().lower()
    password = body.get("password", "").strip()
    confirm_password = body.get("confirm_password", "").strip()

    if not name or not email or not password:
        return JsonResponse({"error": "Name, email, and password are required"}, status=400)

    if password != confirm_password:
        return JsonResponse({"error": "Passwords do not match"}, status=400)

    if len(password) < 6:
        return JsonResponse({"error": "Password must be at least 6 characters"}, status=400)

    if User.objects.filter(email=email).exists():
        return JsonResponse({"error": "Email already registered"}, status=409)

    # Use email as username (unique identifier)
    if User.objects.filter(username=email).exists():
        return JsonResponse({"error": "Email already registered"}, status=409)

    user = User.objects.create_user(username=email, email=email, password=password, first_name=name)
    token = AuthToken(user=user)
    token.save()

    return JsonResponse({
        "token": token.key,
        "username": user.first_name or user.username,
        "is_admin": user.is_staff,
    }, status=201)


@csrf_exempt
def login_view(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    email = body.get("email", "").strip().lower()
    password = body.get("password", "").strip()

    if not email or not password:
        return JsonResponse({"error": "Email and password are required"}, status=400)

    # Authenticate using email as username
    user = authenticate(username=email, password=password)
    if user is None:
        return JsonResponse({"error": "Invalid email or password"}, status=401)

    # Delete old tokens and create a new one
    AuthToken.objects.filter(user=user).delete()
    token = AuthToken(user=user)
    token.save()

    return JsonResponse({
        "token": token.key,
        "username": user.first_name or user.username,
        "is_admin": user.is_staff,
    })


@csrf_exempt
def logout_view(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    user = get_user_from_token(request)
    if user:
        AuthToken.objects.filter(user=user).delete()

    return JsonResponse({"message": "Logged out"})


@csrf_exempt
def me_view(request):
    """Return current user info if token is valid."""
    user = get_user_from_token(request)
    if not user:
        return JsonResponse({"error": "Not authenticated"}, status=401)

    return JsonResponse({"username": user.first_name or user.username, "email": user.email, "is_admin": user.is_staff})


@csrf_exempt
def forgot_password_view(request):
    """Send an OTP to the user's email for password reset."""
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    email = body.get("email", "").strip().lower()
    if not email:
        return JsonResponse({"error": "Email is required"}, status=400)

    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        # Don't reveal whether email exists
        return JsonResponse({"message": "If this email is registered, you will receive an OTP."})

    otp_obj = PasswordResetOTP.generate_otp(user)

    try:
        send_mail(
            subject="InsightDocs - Password Reset OTP",
            message=f"Your OTP for password reset is: {otp_obj.otp}\n\nThis code expires in 10 minutes.\n\nIf you didn't request this, please ignore this email.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )
    except Exception:
        return JsonResponse({"error": "Failed to send email. Please try again later."}, status=500)

    return JsonResponse({"message": "If this email is registered, you will receive an OTP."})


@csrf_exempt
def verify_otp_view(request):
    """Verify the OTP sent to user's email."""
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    email = body.get("email", "").strip().lower()
    otp = body.get("otp", "").strip()

    if not email or not otp:
        return JsonResponse({"error": "Email and OTP are required"}, status=400)

    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        return JsonResponse({"error": "Invalid OTP"}, status=400)

    otp_obj = PasswordResetOTP.objects.filter(user=user, otp=otp, is_used=False).order_by("-created_at").first()

    if not otp_obj:
        return JsonResponse({"error": "Invalid OTP"}, status=400)

    if otp_obj.is_expired():
        return JsonResponse({"error": "OTP has expired. Please request a new one."}, status=400)

    return JsonResponse({"message": "OTP verified", "verified": True})


@csrf_exempt
def reset_password_view(request):
    """Reset password after OTP verification."""
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    email = body.get("email", "").strip().lower()
    otp = body.get("otp", "").strip()
    new_password = body.get("new_password", "").strip()

    if not email or not otp or not new_password:
        return JsonResponse({"error": "Email, OTP, and new password are required"}, status=400)

    if len(new_password) < 6:
        return JsonResponse({"error": "Password must be at least 6 characters"}, status=400)

    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        return JsonResponse({"error": "Invalid request"}, status=400)

    otp_obj = PasswordResetOTP.objects.filter(user=user, otp=otp, is_used=False).order_by("-created_at").first()

    if not otp_obj:
        return JsonResponse({"error": "Invalid OTP"}, status=400)

    if otp_obj.is_expired():
        return JsonResponse({"error": "OTP has expired. Please request a new one."}, status=400)

    # Mark OTP as used and reset password
    otp_obj.is_used = True
    otp_obj.save()

    user.set_password(new_password)
    user.save()

    return JsonResponse({"message": "Password reset successful. You can now sign in."})


# ---- UPLOAD ROOT (same as views.py) ----
_UPLOAD_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uploads")

SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md", ".doc", ".docx"}


@csrf_exempt
def admin_dashboard_view(request):
    """Return aggregated stats for all users. Requires is_staff."""
    user = get_user_from_token(request)
    if not user:
        return JsonResponse({"error": "Authentication required"}, status=401)
    if not user.is_staff:
        return JsonResponse({"error": "Admin access required"}, status=403)

    users = User.objects.all().order_by("-date_joined")
    user_stats = []

    for u in users:
        # Count uploaded files from filesystem
        upload_folder = os.path.join(_UPLOAD_ROOT, str(u.id))
        upload_count = 0
        if os.path.exists(upload_folder):
            upload_count = len([
                f for f in os.listdir(upload_folder)
                if os.path.splitext(f)[1].lower() in SUPPORTED_EXTENSIONS
            ])

        conversation_count = Conversation.objects.filter(user=u).count()
        message_count = Message.objects.filter(conversation__user=u).count()

        user_stats.append({
            "id": u.id,
            "name": u.first_name or u.username,
            "email": u.email,
            "date_joined": u.date_joined.isoformat(),
            "last_login": u.last_login.isoformat() if u.last_login else None,
            "is_active": u.is_active,
            "is_admin": u.is_staff,
            "upload_count": upload_count,
            "conversation_count": conversation_count,
            "message_count": message_count,
        })

    return JsonResponse({
        "total_users": len(user_stats),
        "users": user_stats,
    })
