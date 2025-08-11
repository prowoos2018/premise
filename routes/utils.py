from functools import wraps
from flask import session, redirect, url_for

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "access_token" not in session:
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated
