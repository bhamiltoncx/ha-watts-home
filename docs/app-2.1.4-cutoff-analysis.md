# Watts Home app 2.1.4 cutoff (Nov 4, 2026)

Watts emailed customers that on Nov 4, 2026, app versions 2.1.4 and earlier
"will no longer be supported and will no longer work". This note records
whether that affects this integration.

**Conclusion:** No change needed. The only API-relevant difference between
2.1.4 and newer apps is the REST API host. Old apps used an Azure hostname;
2.1.5+ use `home.watts.com`, which this integration already uses.

Analysis date: 2026-11-02. Static analysis only; no live API calls were made.

## What was compared

Android package `com.watts.home`, versions 2.1.4 (last unsupported), 2.1.5
(first supported) and 2.2.0 (latest), downloaded as XAPKs from APKPure. All
base and native-split APKs verify with the same signing certificate
(SHA-256 `899002959743072779951b5a28cdffb3364673de50bef7c9a86363a2b8f2898a`).

## Findings

### API base URL changed at 2.1.5

From `AppSettings::InitProdSettings`:

| App version  | API base                                            |
| ------------ | --------------------------------------------------- |
| ≤ 2.1.4      | `https://wattsresiiotapiawp02.azurewebsites.net/api` |
| 2.1.5, 2.2.0 | `https://home.watts.com/api`                        |

The cutoff lines up with this switch, so the Nov 4 change is most likely the
retirement of the Azure hostname. `API_BASE_URL` in `const.py` is already
`https://home.watts.com/api`.

### Unchanged from 2.1.4 through 2.2.0

- B2C client ID `4b3a6465-94dd-47c2-976c-18bc29c53c2f` (Android), tenant
  `wattsb2cap02`, policy `B2C_1A_Residential_UnifiedSignUpOrSignIn`, scope
  resource `wattsapiresi`, authority `https://login.watts.io/tfp/`.
- Request handler (`SendAsync`) sets `Authorization: Bearer <token>` and
  `Api-Version: 2.0`. No app-version header is sent. The only other headers are
  Application Insights telemetry (W3C trace, `Request-Id`,
  `Correlation-Context`), which the integration has never sent.
- Path segments and payload keys used by `api.py` (`Location`, `Devices`,
  `Device`, `Refresh`, `State`, `Mode`, `Heat`/`HeatHold`, `Cool`/`CoolHold`,
  `Schedule`, `Floor`) are all still present.

### New in 2.2.0, no integration impact

- Force-update dialog. `VersionTrackingService.GetMinimumRequiredVersion`
  fetches `https://watts-home-version.web.app/` and compares it to the app
  version locally; nothing is enforced server-side.
- Alexa and Google voice-assistant account linking.
- App moved from .NET 8 to .NET 9 with a namespace reorganization.

## Residual risk

A server-side change not visible in the app, such as stricter User-Agent
checks, can't be ruled out. If the integration fails after Nov 4, check the
HTTP status codes in the Home Assistant logs first.

## Reproducing

The app is .NET MAUI, so the logic lives in managed assemblies
(`WattsHome.MAUI.dll`, `WattsHome.MAUI.Data.dll`), not Java bytecode. Tools like
jadx don't help.

1. Fetch versions: `apkeep -d apk-pure -o acknowledge_dangers=true -a com.watts.home@<version> <dir>`,
   then unzip the `.xapk`.
2. Extract the assembly store:
   - ≤ 2.1.4: `assemblies/assemblies*.blob` in the base APK (XABA v1: 20-byte
     header, 24-byte descriptors `[offset, size, …]`).
   - ≥ 2.1.5: `lib/<abi>/libassemblies.<abi>.blob.so` in the ABI split (XABA
     v2, version `0x20002`: the 5th header field is the index size, and
     28-byte descriptors `[mapping_index, offset, size, …]` start after it).
   - Entries prefixed `XALZ` are LZ4 blocks: a 12-byte header, with the
     uncompressed size at offset 8.
3. Read user strings, type and method names, and per-method `ldstr`/`call`
   references with [`dnfile`](https://github.com/malwarefrank/dnfile).
   Endpoint config is in `AppSettings::InitProdSettings`; request headers are
   in the HTTP `DelegatingHandler`'s `SendAsync`.
