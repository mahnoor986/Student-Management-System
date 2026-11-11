from django.contrib import admin
from django.urls import include, path

from students.login_limits import throttled_admin_login

# Lock out repeated failed admin sign-ins (audit finding M1).
admin.site.login = throttled_admin_login(admin.site.login)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('students.auth_urls')),
    path('api/', include('students.urls')),
]
