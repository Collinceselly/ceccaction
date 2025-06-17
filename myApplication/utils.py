import requests
from django.conf import settings

def get_pesapal_token():
    url = settings.PESAPAL_OAUTH_URL
    headers = {"Content-Type": "application/json"}
    data = {
        "consumer_key": settings.PESAPAL_CONSUMER_KEY,
        "consumer_secret": settings.PESAPAL_CONSUMER_SECRET
    }

    response = requests.post(url, json=data, headers=headers)
    if response.status_code != 200:
        print(f"Pesapal Error: {response.json()}")
    response_data = response.json()

    if response.status_code == 200 and "token" in response_data:
        return response_data["token"]
    
    else:
        return None

