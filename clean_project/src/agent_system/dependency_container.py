"""
Dependency Injection Container for managing object dependencies
This resolves circular dependency issues and improves testability.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Optional, Type, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class DependencyContainer:
    """
    Dependency injection container that manages object creation and lifecycle.
    Resolves circular dependencies by providing lazy initialization and dependency injection.
    """
    
    def __init__(self) -> None:
        self._services: Dict[str, Any] = {}
        self._factories: Dict[str, Callable[[], Any]] = {}
        self._singletons: Dict[str, bool] = {}
        self._initializing: set[str] = set()  # Prevent circular dependency infinite loops
    
    def register(
        self, 
        name: str, 
        service: Type[T] | Any = None, 
        *, 
        factory: Optional[Callable[[], T]] = None,
        singleton: bool = True
    ) -> None:
        """
        Register a service in the container.
        
        Args:
            name: Identifier for the service
            service: Service instance or class to register
            factory: Factory function to create the service
            singleton: Whether to create only one instance
        """
        if service is not None:
            self._services[name] = service
            self._singletons[name] = singleton
        elif factory is not None:
            self._factories[name] = factory
            self._singletons[name] = singleton
        else:
            raise ValueError("Either service or factory must be provided")
    
    def get(self, name: str) -> Any:
        """
        Get a service from the container.
        
        Args:
            name: Identifier for the service
            
        Returns:
            The service instance
        """
        # Return existing service if it's a singleton and already created
        if name in self._services and self._singletons[name]:
            return self._services[name]
        
        # Create service from factory
        if name in self._factories:
            if name in self._initializing:
                raise RuntimeError(f"Circular dependency detected for service '{name}'")
            
            self._initializing.add(name)
            try:
                service = self._factories[name]()
                if self._singletons[name]:
                    self._services[name] = service
                return service
            finally:
                self._initializing.remove(name)
        
        raise KeyError(f"Service '{name}' not found in container")
    
    def has(self, name: str) -> bool:
        """Check if a service is registered."""
        return name in self._services or name in self._factories
    
    def clear(self) -> None:
        """Clear all registered services and factories."""
        self._services.clear()
        self._factories.clear()
        self._singletons.clear()
        self._initializing.clear()
    
    def create_child_container(self) -> DependencyContainer:
        """Create a child container that inherits services from parent."""
        child = DependencyContainer()
        child._services = self._services.copy()
        child._singletons = self._singletons.copy()
        return child


# Global dependency container instance
container = DependencyContainer()


def register_service(name: str, service: Type[T] | Any = None, *, singleton: bool = True) -> Callable[..., Any]:
    """Decorator to register a service in the global container."""
    def decorator(cls_or_instance: Type[T] | T) -> Type[T] | T:
        container.register(name, cls_or_instance, singleton=singleton)
        return cls_or_instance
    return decorator


def get_service(name: str) -> Any:
    """Get a service from the global container."""
    return container.get(name)


def inject_dependencies(**service_names: str) -> Callable[..., Any]:
    """
    Decorator to automatically inject dependencies into class methods.
    
    Args:
        **service_names: Mapping of parameter names to service names
    """
    def decorator(cls: Type[Any]) -> Type[Any]:
        # Store original __init__ if it exists
        original_init = cls.__init__
        
        def new_init(self: Any, *args: Any, **kwargs: Any) -> None:
            # Inject services into kwargs
            for param_name, service_name in service_names.items():
                if param_name not in kwargs:
                    try:
                        kwargs[param_name] = get_service(service_name)
                    except KeyError:
                        logger.warning(f"Service '{service_name}' not found for injection into {cls.__name__}")
            
            # Call original __init__
            original_init(self, *args, **kwargs)
        
        cls.__init__ = new_init
        return cls
    
    return decorator


# Example usage:
# @register_service("monitoring")
# class MonitoringSystem:
#     pass
#
# @inject_dependencies(monitoring="monitoring")
# class SomeService:
#     def __init__(self, monitoring):
#         self.monitoring = monitoring