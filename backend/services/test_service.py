class TestService:
    async def get_greeting(self, name: str) -> dict:
        return {"message": f"Hello, {name}!"}

    async def process_data(self, data: dict) -> dict:
        return {"received": data, "processed": True}

    async def get_status(self) -> dict:
        return {"status": "ok", "service": "test"}


test_service = TestService()
