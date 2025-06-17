from django.urls import path
from . import views


urlpatterns = [
    path('', views.home, name='home'),
    path('donate/', views.initiate_payment, name='initiate_payment'),
    path('payment-callback/', views.payment_callback, name='payment_callback'),
    path('ipn-callback/', views.ipn_callback, name='ipn_callback'),
    path('contact/', views.contact_form, name='contact'),
]
