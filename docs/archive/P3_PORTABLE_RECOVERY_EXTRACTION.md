# P3-184 Portable Recovery Evidence Extraction

The local portable package was unpacked into the previously absent workspace directory `artifacts/recovery-drill/p3-184-extracted`. From that directory, Python loaded `src/wps_ai_agent_cli/recovery_drill_evidence.py` inside the extracted package, not the original checkout. `verify_recovery_drill_artifacts(".")` returned `passed` for both Writer and Spreadsheet with no component errors.

The extracted Writer current/backup SHA-256 values were `0E17658CE1E56FE27795FBD0F232B452E7D0B9BDEE6E4A14242A7FE3D832AD71` and `B0FD9330BC8D5C003EABCF8DE288DCF52F9957A6C134F18716979AEAC820FB63`; Spreadsheet values were `C3B4B021472468A4215ED97F761DC44D967DF2C53BFB5BA299E002841F01C516` and `1FB75B94990D9EA8B9EEEC89EFDBD06842AC09301ACA2BE7D763FA451E52DE67`. They match the source manifests. An automated test also extracts generated evidence under a different temporary root and verifies it there.

The manifests use workspace-relative paths, so they remain valid when the archive is extracted with its directory layout intact. The check does not prove that an arbitrary external transfer preserves archive bytes; the receiver should verify the ZIP hash and rerun the extracted verifier. No WPS launch, original-document edit, or remote Git was used for this extraction. The full default suite ran 354 tests (29 skipped, no failures).
