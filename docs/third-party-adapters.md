# Third-party runtime adapters

A third-party HOWEDO adapter should depend on HOWEDO core plus its own runtime SDK. It should not require PostgreSQL, LangGraph, Temporal, or any other reference adapter unless it explicitly integrates that runtime.

## Minimum implementation

Implement the `RuntimeAdapterV1` surface:

- `manifest()`
- `runtime_revision()`
- `resolve_identity()`
- `capture()`
- `validate_resume()`
- `continue_after_validate()`

Use `AdapterManifest.build()` and `RuntimeIdentity` from `howedo.adapter_sdk`.

## Required safety properties

1. resolve an exact execution identity, not a mutable alias such as "latest";
2. bind the exact adapter manifest digest into the capture result;
3. include the runtime/SDK revision in the HOWEDO snapshot;
4. run HOWEDO recovery validation before any continuation side effect;
5. refuse continuation unless the result is `RECOVER`;
6. never weaken `PAUSE`, `REVALIDATE`, or `ABORT` into a local allow;
7. retain vendor-specific data only as an extension behind the stable v1 identity.

## Testing

Create a runtime-specific `AdapterFixture` and run:

```python
results = await AdapterConformanceSuite().run(adapter, fixture)
AdapterConformanceSuite.assert_passed(results)
```

Then add runtime-specific tests for the capabilities the generic suite cannot prove, especially exact continuation targeting, closed/superseded execution rejection, and any fencing guarantees.

## Versioning

`howedo.runtime-adapter.v1` is immutable as a contract identifier. Backward-compatible library fixes may ship without changing the identifier. A breaking contract change requires a new identifier such as `howedo.runtime-adapter.v2`.
