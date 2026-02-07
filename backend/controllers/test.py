from blacksheep import json
from blacksheep.server.controllers import APIController, get, post
from services.test_service import TestService


class Test(APIController):
    def __init__(self, test_service: TestService):
        self.test_service = test_service

    @get("/health")
    async def health_check(self):
        return json({"status": "ok"})

    @get("/test/{name}")
    async def greet(self, name: str):
        return json(await self.test_service.get_greeting(name))

    @post("/test/echo")
    async def echo(self, data: dict):
        return json({"received": data})
