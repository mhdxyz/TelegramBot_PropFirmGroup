import pytest

from app.core.exceptions import InvalidInputError
from app.features.commands.service import CommandService, LotteryData


class FakeLottery:
    def __init__(self):
        self.registration = None

    async def create_registration(self, **kwargs):
        if self.registration is not None:
            from app.core.exceptions import RepositoryError
            raise RepositoryError("Lottery registration already exists")
        self.registration = kwargs
        return object()

    async def get_registration(self, telegram_user_id):
        return self.registration


class FakeContent:
    def __init__(self):
        self.values = {}

    async def set_content(self, key, content):
        self.values[key] = content

    async def get_content(self, key):
        return self.values.get(key)


@pytest.mark.asyncio
async def test_lottery_registration_validates_and_persists():
    lottery = FakeLottery()
    service = CommandService(lottery, FakeContent())
    await service.register_lottery(1, "user", LotteryData("John Doe", "a@example.com", "b@example.com"))
    assert lottery.registration["full_name"] == "John Doe"
    assert await service.is_lottery_registered(1)


@pytest.mark.asyncio
async def test_lottery_registration_rejects_invalid_email():
    service = CommandService(FakeLottery(), FakeContent())
    with pytest.raises(InvalidInputError):
        await service.register_lottery(1, "user", LotteryData("John Doe", "not-email", "b@example.com"))


@pytest.mark.asyncio
async def test_content_round_trip():
    content = FakeContent()
    service = CommandService(FakeLottery(), content)
    await service.set_content("discount", "10% off")
    assert await service.get_content("discount") == "10% off"
