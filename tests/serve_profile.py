import tempfile
from app import app
from accounts import init_schema
store=tempfile.TemporaryDirectory()
app.config.update(TESTING=True, ACCOUNT_DATABASE_URL='sqlite:///'+store.name+'/ui.sqlite', ACCOUNT_SECURE_COOKIE=False, ACCOUNT_PUBLIC_ORIGIN='http://127.0.0.1:19047')
init_schema(app)
app.run(host='127.0.0.1',port=19047)
