import hashlib
import io
import logging
import pathlib
from contextlib import contextmanager
from typing import BinaryIO, Generic, Iterator, TypeVar

from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class FileStorageSettings(BaseSettings):
    model_config = SettingsConfigDict(extra="allow")

    root: str = ".data/files"


class FileStorage:
    def __init__(self, settings: FileStorageSettings):
        self.root = pathlib.Path(settings.root)
        self._initialized = False

    def _ensure_initialized(self):
        if self._initialized:
            return
        self.root.mkdir(parents=True, exist_ok=True)
        self._initialized = True
        logger.info("initialized file storage; root: %s", self.root.absolute())

    def _file_path(self, dir: str, filename: str, mkdir=False) -> pathlib.Path:
        self._ensure_initialized()
        namespace_path = self.root / dir
        if mkdir:
            namespace_path.mkdir(exist_ok=True)
        filename_hash = hashlib.sha256(filename.encode("utf-8")).hexdigest()
        return namespace_path / filename_hash

    def write_file(self, dir: str, filename: str, content: BinaryIO) -> None:
        file_path = self._file_path(dir, filename, mkdir=True)
        with open(file_path, "wb") as f:
            f.write(content.read())

    def delete_file(self, dir: str, filename: str) -> None:
        file_path = self._file_path(dir, filename)
        file_path.unlink(missing_ok=True)

    @contextmanager
    def read_file(self, dir: str, filename: str) -> Iterator[BinaryIO]:
        file_path = self._file_path(dir, filename)
        with open(file_path, "rb") as f:
            yield f


ModelT = TypeVar("ModelT", bound=BaseModel)


class ModelStorage(Generic[ModelT]):
    """
    Provides file-system storage for pydantic models as a utility for assistant service
    implementations.
    """

    def __init__(self, cls: type[ModelT], file_storage: FileStorage, namespace: str) -> None:
        self._cls = cls
        self._file_storage = file_storage
        self._namespace = namespace

    def get(self, key: str, strict: bool | None = None) -> ModelT | None:
        """
        Gets the model value for the given key, or None if the key does not exist. If the
        model has changed since the value was written, and is no longer valid, this will
        raise pydantic.ValidationError.
        """
        try:
            with self._file_storage.read_file(dir=self._namespace, filename=key) as file:
                contents = file.read().decode("utf-8")

        except FileNotFoundError:
            return None

        value = self._cls.model_validate_json(contents, strict=strict)
        return value

    def __getitem__(self, key: str) -> ModelT:
        value = self.get(key)
        if value is None:
            raise KeyError(key)
        return value

    def set(self, key: str, value: ModelT) -> None:
        data_json = value.model_dump_json()
        self._file_storage.write_file(dir=self._namespace, filename=key, content=io.BytesIO(data_json.encode("utf-8")))

    def __setitem__(self, key: str, value: ModelT) -> None:
        self.set(key=key, value=value)

    def delete(self, key: str) -> None:
        self._file_storage.delete_file(dir=self._namespace, filename=key)
