from django.urls import path, re_path

from . import views
from .tip_proxy import tip_api_proxy

urlpatterns = [
    # SHIPPED BY THE PLATFORM — routes same-origin /tip-api/<path> to the TIP backend
    # with the API key attached server-side. Do NOT remove, reorder, or change this line.
    re_path(r'^tip-api/(?P<path>.+)$', tip_api_proxy),

    # The AI agent implements the page in this index view.
    path('', views.index, name='index'),
]
