"""
ML Model Serving Infrastructure
Provides model loading, versioning, A/B testing, and inference serving.
"""

from __future__ import annotations

import asyncio
import logging
import pickle
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)


class ModelStatus(str, Enum):
    """Model status."""

    LOADING = "loading"
    READY = "ready"
    ERROR = "error"
    UNLOADING = "unloading"


@dataclass
class ModelMetadata:
    """Metadata for a model."""

    name: str
    version: str
    path: str
    status: ModelStatus
    loaded_at: Optional[float] = None
    inference_count: int = 0
    avg_latency_ms: float = 0.0
    error_count: int = 0
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class ModelServer:
    """Manages ML model loading, versioning, and serving."""

    def __init__(self, model_dir: str = "./models"):
        self.model_dir = model_dir
        self.models: Dict[str, Dict[str, Any]] = {}  # name -> version -> model
        self.metadata: Dict[str, Dict[str, ModelMetadata]] = {}  # name -> version -> metadata
        self.active_versions: Dict[str, str] = {}  # name -> active version
        self._lock = asyncio.Lock()

    async def load_model(
        self,
        name: str,
        version: str,
        model_path: Optional[str] = None,
        loader_func: Optional[Callable] = None,
    ) -> bool:
        """Load a model."""
        async with self._lock:
            if name not in self.models:
                self.models[name] = {}
                self.metadata[name] = {}

            if version in self.models[name]:
                logger.warning(f"Model {name}:{version} already loaded")
                return True

            # Update metadata
            metadata = ModelMetadata(
                name=name,
                version=version,
                path=model_path or f"{self.model_dir}/{name}/{version}",
                status=ModelStatus.LOADING,
            )
            self.metadata[name][version] = metadata

        try:
            # Load model
            if loader_func:
                model = await loader_func(metadata.path)
            else:
                model = await self._default_loader(metadata.path)

            async with self._lock:
                self.models[name][version] = model
                metadata.status = ModelStatus.READY
                import time

                metadata.loaded_at = time.time()

            logger.info(f"Model {name}:{version} loaded successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to load model {name}:{version}: {e}")
            async with self._lock:
                metadata.status = ModelStatus.ERROR
                metadata.error_count += 1
            return False

    async def _default_loader(self, path: str) -> Any:
        """Default model loader (pickle)."""
        # In production, this would support various formats
        # (pickle, ONNX, TensorFlow SavedModel, PyTorch, etc.)
        with open(path, "rb") as f:
            return pickle.load(f)

    async def unload_model(self, name: str, version: str):
        """Unload a model."""
        async with self._lock:
            if name in self.models and version in self.models[name]:
                metadata = self.metadata[name][version]
                metadata.status = ModelStatus.UNLOADING
                del self.models[name][version]
                del self.metadata[name][version]

                # If this was the active version, clear it
                if self.active_versions.get(name) == version:
                    del self.active_versions[name]

                logger.info(f"Model {name}:{version} unloaded")

    async def predict(
        self,
        name: str,
        input_data: Any,
        version: Optional[str] = None,
    ) -> Any:
        """Run inference on a model."""
        # Get model version
        if version is None:
            version = self.active_versions.get(name)
            if not version:
                raise ValueError(f"No active version for model {name}")

        # Get model
        async with self._lock:
            if name not in self.models or version not in self.models[name]:
                raise ValueError(f"Model {name}:{version} not loaded")

            model = self.models[name][version]
            metadata = self.metadata[name][version]

            if metadata.status != ModelStatus.READY:
                raise ValueError(f"Model {name}:{version} is not ready (status: {metadata.status})")

        # Run inference
        import time

        start_time = time.perf_counter()

        try:
            # Support both sync and async models
            if asyncio.iscoroutinefunction(getattr(model, "predict", None)):
                result = await model.predict(input_data)
            elif hasattr(model, "predict"):
                result = model.predict(input_data)
            else:
                # Fallback: call model directly
                result = model(input_data)

            latency_ms = (time.perf_counter() - start_time) * 1000

            # Update metadata
            async with self._lock:
                metadata.inference_count += 1
                # Update average latency (exponential moving average)
                if metadata.avg_latency_ms == 0:
                    metadata.avg_latency_ms = latency_ms
                else:
                    metadata.avg_latency_ms = 0.9 * metadata.avg_latency_ms + 0.1 * latency_ms

            return result

        except Exception as e:
            logger.error(f"Inference error for {name}:{version}: {e}")
            async with self._lock:
                metadata.error_count += 1
            raise

    def set_active_version(self, name: str, version: str):
        """Set the active version for a model (for A/B testing)."""
        if name not in self.models or version not in self.models[name]:
            raise ValueError(f"Model {name}:{version} not loaded")

        metadata = self.metadata[name][version]
        if metadata.status != ModelStatus.READY:
            raise ValueError(f"Model {name}:{version} is not ready")

        self.active_versions[name] = version
        logger.info(f"Set active version for {name} to {version}")

    async def get_model_info(self, name: Optional[str] = None) -> Dict[str, Any]:
        """Get information about loaded models."""
        async with self._lock:
            if name:
                if name not in self.metadata:
                    return {}
                return {
                    version: {
                        "status": metadata.status.value,
                        "inference_count": metadata.inference_count,
                        "avg_latency_ms": metadata.avg_latency_ms,
                        "error_count": metadata.error_count,
                        "loaded_at": metadata.loaded_at,
                        "is_active": self.active_versions.get(name) == version,
                    }
                    for version, metadata in self.metadata[name].items()
                }
            else:
                return {
                    model_name: {
                        version: {
                            "status": metadata.status.value,
                            "inference_count": metadata.inference_count,
                            "avg_latency_ms": metadata.avg_latency_ms,
                            "error_count": metadata.error_count,
                            "is_active": self.active_versions.get(model_name) == version,
                        }
                        for version, metadata in versions.items()
                    }
                    for model_name, versions in self.metadata.items()
                }

    async def health_check(self) -> Dict[str, Any]:
        """Check health of model server."""
        async with self._lock:
            total_models = sum(len(versions) for versions in self.models.values())
            ready_models = sum(
                1
                for versions in self.metadata.values()
                for metadata in versions.values()
                if metadata.status == ModelStatus.READY
            )
            error_models = sum(
                1
                for versions in self.metadata.values()
                for metadata in versions.values()
                if metadata.status == ModelStatus.ERROR
            )

        return {
            "status": "healthy" if error_models == 0 else "degraded",
            "total_models": total_models,
            "ready_models": ready_models,
            "error_models": error_models,
        }


# Global model server instance
model_server = ModelServer()
