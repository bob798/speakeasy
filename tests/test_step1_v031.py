import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from app.models.db import Base, UserSettings

TEST_USER = "test_user_v031_step1"
TEST_DB = "sqlite:///test_v031_step1.db"


@pytest.fixture(autouse=True)
def setup_db():
    engine = create_engine(TEST_DB)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.query(UserSettings).filter_by(user_id=TEST_USER).delete()
    session.commit()
    session.close()
    Base.metadata.drop_all(engine)


def test_user_settings_table_exists(setup_db):
    engine = create_engine(TEST_DB)
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    assert "user_settings" in tables


def test_user_settings_columns(setup_db):
    engine = create_engine(TEST_DB)
    inspector = inspect(engine)
    columns = {col["name"] for col in inspector.get_columns("user_settings")}
    assert columns == {"user_id", "voice", "speed", "activation", "updated_at"}


def test_user_settings_default_values(setup_db):
    session = setup_db
    settings = UserSettings(user_id=TEST_USER)
    session.add(settings)
    session.commit()
    result = session.query(UserSettings).filter_by(user_id=TEST_USER).first()
    assert result.voice == "warm"
    assert result.speed == "normal"
    assert result.activation == "push_to_talk"


def test_silero_vad_importable():
    import silero_vad
    model = silero_vad.load_silero_vad()
    assert model is not None
