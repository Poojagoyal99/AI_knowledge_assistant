from django.urls import path
from .views import chat_view, chat_stream_view, upload_pdf, list_pdfs, delete_pdf, global_search_view, export_chat_pdf
from .auth_views import register_view, login_view, logout_view, me_view

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
]
