## V2.3 Texture Audit / Repair Unit Tests

```powershell
py -3.11 -m unittest tests.test_generation_audit tests.test_repair_loop tests.test_capabilities -v
```

Expected:

- basic ruby generation writes texture PNGs and texture manifest
- audit fails when a generated item texture is missing
- repair-loop regenerates a missing managed texture
- capability matrix includes `procedural_textures` and `texture_audit`
