# astrbot_plugin_dna_resources

Public runtime resources for [`astrbot_plugin_dnaby`](https://github.com/FlanChanXwO/astrbot_plugin_dnaby).

The plugin's `下载全部资源` command clones this repository into its runtime data directory and
validates `resource_manifest.json` before using the files. The repository intentionally contains
only public resource assets and layout markers; it must not contain cookies, tokens, databases,
bot configuration, or other private runtime data.

The assets may have different upstream sources and licensing terms. No blanket license is implied
for third-party assets; retain or consult their upstream attribution and usage terms before
redistributing them outside this repository.

The `textures/` tree contains shared renderer backgrounds and card decorations. It is intentionally
kept separate from `calendar/`, which contains activity assets, and from `wiki/`/`guide/`, which
are indexed content collections.

## Resource contract

`resource_manifest.json` is format version `1` and declares the complete runtime layout, including
`data` and `schemas`. Every declared directory must exist. The editor and the plugin accept only
type-specific paths; this repository must not become a general file drop or an editor source tree.

The redeem-code source of truth is `data/redeem_codes.json`, validated against
`schemas/redeem-codes.v1.schema.json`:

```json
{
  "format_version": 1,
  "data": [
    {
      "code": "JACKDAW",
      "reward": "委托密函×3",
      "valid_from": "2026-08-01T00:00:00+08:00",
      "expires_at": "2026-09-01T00:00:00+08:00",
      "platforms": ["pc", "android", "ios"],
      "servers": ["cn", "global"]
    }
  ]
}
```

`code` is the only required field. Trim outer whitespace only and do not force uppercase. The
optional fields are `reward`, timezone-aware `valid_from`/`expires_at`, `platforms` (`pc`,
`android`, `ios`) and `servers` (`cn`, `global`). Missing platform or server means that the source
did not state it; it does not mean “all”. Keep planned, current, and expired entries, but do not
write the legacy `end_at` field or unknown fields. Cross-entry code uniqueness and the ordering of
the two time fields are semantic checks performed by the editor Worker Check and plugin validator;
JSON Schema alone cannot express both rules.

## Contribution and release

Use the [DNA resource editor](https://github.com/FlanChanXwO/dna-resource-editor) for changes. A
submission creates one contribution branch, one commit, and one pull request; it never writes
`main` directly. The GitHub App webhook checks the complete tree and publishes a Check named exactly
`resource-contract`. Maintainers merge only after that Check is successful and the upstream asset
rights are understood. The editor repository is separate from this pure-resource repository.

The release order is:

1. merge and record the resource commit SHA and `resource_version` on `main`;
2. verify the raw data/schema and the plugin generation validator against that SHA;
3. release or configure the plugin to fetch only `main`.

Do not ask a plugin to consume a contribution branch, a mirror-only ref, or a commit that has not
reached `main`. A mirror or proxy is only a transport path; it is not a release authority.

## Legacy redeem-code migration

The historical feed used `https://raw.gitcode.com/m0_69204072/dna/raw/main/dna_codes.json` and
called the Unix-seconds expiry field `end_at`. The one-way migration converts each `end_at` to an
offset-aware ISO 8601 `expires_at` (the initial migration uses `Asia/Shanghai`) and keeps only
trustworthy known fields. If reward, platform, server, or start time was not present in the old
feed, leave the corresponding new field absent; do not infer it. Preserve the old JSON outside the
repository as an audit fixture, validate the new schema/semantic rules, and record the migration in
`resource_version` before opening the PR. After the plugin release, the resource file is the only
source; there is no silent GitCode fallback.

## Rollback and trust boundary

If a published resource is wrong, create a normal revert PR against `main`, wait for the
`resource-contract` Check, merge it, and record the new main SHA. Never force-push or delete the
original commit. The plugin's candidate generation validation should keep serving its previous
verified snapshot when a candidate fails; a data rollback is still completed by a Git revert.

The editor Worker and plugin are rolled back independently. For a Worker incident, use the
Cloudflare deployment rollback documented in the editor repository. For a plugin incident, keep
the plugin runtime data directory and switch its resource acceleration to `off`; never promote
unverified mirror content. The full procedure is in the editor's
[`docs/operations.md`](https://github.com/FlanChanXwO/dna-resource-editor/blob/main/docs/operations.md)
and the plugin's resource operations guide.

No root `LICENSE` in this repository should be read as a unified licence grant. The plugin's own
GPL-3.0 licence applies to plugin code, while each third-party asset remains subject to its own
source terms and attribution requirements.
