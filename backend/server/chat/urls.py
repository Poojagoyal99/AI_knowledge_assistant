from django.urls import path
from .views import (
    chat_view, chat_stream_view, upload_pdf, list_pdfs, delete_pdf,
    global_search_view, export_chat_pdf,
    list_conversations, create_conversation, get_conversation_messages,
    rename_conversation, delete_conversation, update_highlights,
)
from .auth_views import register_view, login_view, logout_view, me_view, forgot_password_view, verify_otp_view, reset_password_view, admin_dashboard_view

urlpatterns = [
    path("chat/", chat_view),
    path("chat-stream/", chat_stream_view),
    path("global-search/", global_search_view),
    path("upload/", upload_pdf),
    path("list-pdfs/", list_pdfs),
    path("delete-pdf/", delete_pdf),
    path("export-chat/", export_chat_pdf),
    path("auth/register/", register_view),
    path("auth/login/", login_view),
    path("auth/logout/", logout_view),
    path("auth/me/", me_view),
    path("auth/forgot-password/", forgot_password_view),
    path("auth/verify-otp/", verify_otp_view),
    path("auth/reset-password/", reset_password_view),
    path("admin/dashboard/", admin_dashboard_view),
    # Conversations
    path("conversations/", list_conversations),
    path("conversations/create/", create_conversation),
    path("conversations/<int:conversation_id>/", get_conversation_messages),
    path("conversations/<int:conversation_id>/rename/", rename_conversation),
    path("conversations/<int:conversation_id>/delete/", delete_conversation),
    path("messages/<int:message_id>/highlights/", update_highlights),
]
