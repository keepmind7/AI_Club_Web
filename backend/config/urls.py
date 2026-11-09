from django.contrib import admin
from django.urls import path

from club import api

urlpatterns = [
    path("club-admin/", admin.site.urls),
    path("api/auth/me", api.me),
    path("api/auth/login", api.login_view),
    path("api/auth/signup", api.signup),
    path("api/auth/username-check", api.username_check),
    path("api/auth/logout", api.logout_view),
    path("api/auth/password", api.change_password),
    path("api/events", api.event_list),
    path("api/events/<int:pk>", api.event_detail),
    path("api/events/<int:pk>/register", api.event_register),
    path("api/events/<int:pk>/cancel", api.event_cancel),
    path("api/me/attendance", api.my_attendance),
    path("api/me/payments", api.my_payments),
    path("api/announcements", api.announcements),
    path("api/shared-accounts", api.shared_accounts),
    path("api/posts", api.posts),
    path("api/posts/<int:pk>", api.post_detail),
    path("api/posts/<int:pk>/edit", api.post_edit),
    path("api/posts/<int:pk>/delete", api.post_delete),
    path("api/posts/<int:pk>/comments", api.comment_create),
    path("api/comments/<int:pk>/delete", api.comment_delete),
    path("api/dashboard", api.dashboard),
]
