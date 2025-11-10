"""
Debug what schemas are actually generated in OpenAPI
"""

from scripts.test_client import client

# Get OpenAPI schema
response = client.get("/openapi.json")
schema = response.json()

print("OpenAPI Schema Keys:")
print("===================")
print(f"OpenAPI version: {schema.get('openapi')}")
print(f"Title: {schema.get('info', {}).get('title')}")
print(f"Version: {schema.get('info', {}).get('version')}")

print("\nSecurity Schemes:")
print("=================")
for scheme_name in schema.get("components", {}).get("securitySchemes", {}).keys():
    print(f"  - {scheme_name}")

print("\nSchema Definitions:")
print("===================")
schemas = schema.get("components", {}).get("schemas", {})
for schema_name in sorted(schemas.keys()):
    print(f"  - {schema_name}")

print(f"\nTotal schemas: {len(schemas)}")

print("\nPath Keys:")
print("==========")
for path in sorted(schema.get("paths", {}).keys()):
    print(f"  - {path}")
