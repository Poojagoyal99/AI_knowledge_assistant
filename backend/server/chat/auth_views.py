import json

from django.http import JsonResponse
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from django.views.decorators.csrf import csrf_exempt

from .models import AuthToken


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

    return JsonResponse({"username": user.first_name or user.username, "email": user.email})
