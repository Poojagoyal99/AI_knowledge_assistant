import secrets
import random
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta


class AuthToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="auth_tokens")
    key = models.CharField(max_length=64, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.key:
            self.key = secrets.token_hex(32)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Token for {self.user.username}"


class Conversation(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="conversations")
    title = models.CharField(max_length=200, default="New Chat")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.title} ({self.user.username})"


class Message(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=10, choices=[("user", "User"), ("bot", "Bot")])
    text = models.TextField()
    sources = models.JSONField(default=list, blank=True)
    highlights = models.JSONField(default=list, blank=True)  # [{"text": "...", "color": "yellow"}, ...]
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.role}: {self.text[:50]}"


class PasswordResetOTP(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="password_reset_otps")
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    is_used = models.BooleanField(default=False)

    def is_expired(self):
        return timezone.now() > self.created_at + timedelta(minutes=10)

    @classmethod
    def generate_otp(cls, user):
        # Invalidate previous OTPs
        cls.objects.filter(user=user, is_used=False).update(is_used=True)
        otp_code = f"{random.randint(100000, 999999)}"
        return cls.objects.create(user=user, otp=otp_code)

    def __str__(self):
        return f"OTP for {self.user.email} - {'used' if self.is_used else 'active'}"
