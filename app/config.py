from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    data_dir: Path = Path("./data")
    cors_origins: str = "http://localhost:3000"
    web_concurrency: int = 1

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def raster_paths(self) -> dict[str, Path]:
        return {
            "dem": self.data_dir / "dem/LDEM_80S_80MPP_ADJ.TIF",
            "sun_baseline": self.data_dir / "baseline/AVGVISIB_85S_060M_201608.LBL",
            "earth_baseline": self.data_dir / "baseline/AVGVISIB_85S_060M_201608_EARTH.LBL",
        }
