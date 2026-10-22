# Shared resource reads

## Purpose and ownership

`DurabilityResource` provides authenticated context-scoped encrypted-resource downloads and read-only committed workspace manifests. It inherits the normal API authentication, origin and CSRF checks; no public file URL or path-based read is added.

## Contracts

- `context` plus `resource_id` downloads authenticated bytes with attachment disposition, `no-store` and `nosniff` headers. References resolve only inside that context; corruption, missing keys and tombstones hold.
- `action=workspace` reads the versioned manifest published atomically with the worker checkpoint. It exposes relative file paths and resource references, never executes a context or mutates the workspace.
- PostgreSQL mode is required. `ResourceManager` owns decryption and digest validation; connection errors pass through the shared API's fixed safe error response.

## Verification

Run shared-resource and cluster API tests, including authentication/CSRF, cross-context denial, corruption and deleted-context reads.
