from blacksheep import Application
from services.test_service import TestService
from rodi import Container

services = Container()

test_service = TestService()

services.add_instance(test_service, TestService)

app = Application(services = services)

# TODO: REMOVE IN PRODUCTION, FOR DEV ONLY
app.use_cors(
    allow_methods="*",
    allow_origins="*",
    allow_headers="*",
)


# test routes

@app.router.get("/")
def hello_world():
    return "Hello World"

@app.router.get("/test")
async def test_route():
    return await test_service.get_greeting("austin jian")