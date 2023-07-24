from django.contrib.auth import get_user_model

def create_user(email, password, **kwargs):
    return get_user_model().objects.create_user(email, password, **kwargs)
