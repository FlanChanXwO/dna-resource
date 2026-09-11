# Changelog

## Resource sync 2026-09-11

### Added

- `wiki/role/伊薇.webp`、`wiki/role/法露茜.webp`、`wiki/weapon/无声的嘶吼.webp`，改从**皎皎角官方 Wiki**
  （`dnabbs.yingxiong.com`）详情页抓取，宽度沿用既有 2460 基线。
- `images/role_avatar/3104.png`，以及 `images/weapon/10405.png`（无声的嘶吼）、`images/weapon/20298.png`
  （血染织羽），来自游戏服 `role/defaultRoleForTool` 接口下发的 CDN 地址。
- `alias/char_alias.json` 增加 `伊薇`、`法露茜`，并把主角系列补全为
  `女主光`/`主角女`/`主角（女）`/`光·狩月人（女）` 等写法。
- `alias/weapon_alias.json` 增加 `无声的嘶吼`、`血染织羽`。

### Changed

- `docs/sync.md`、`README.md`、`AGENTS.md` 更新 B-wiki 的权威上游与抓取步骤；DNAUID 不再作为图鉴基线。
- `resource_version` 更新为 `resource-sync-2026-09-11-jjj-wiki-ivy-faluxi`。

### Notes

- 裸词 `主角`/`光主`/`暗主` **不入库**：与 `主角男`/`主角（男）` 存在包含关系，会被别名歧义校验拒绝。
  这三个称呼由插件侧按玩家实际拥有的性别动态解析。
- 男女主角同名但立绘、头像与模型不同，别名保持在各自规范键下，不合并。

### Known gaps

- `血染织羽`（武器 id `20298`）暂缺图鉴图：皎皎角目前只在 `物品大全/灾厄` 下收录“血染织羽的原型”，
  武器词条尚未建立，属上游如此。


## Goal 3 resource contract (2026-08-29)

### Added

- `data/redeem_codes.json` as the public redeem-code source of truth.
- `schemas/redeem-codes.v1.schema.json` for the versioned redeem-code shape.
- `data` and `schemas` in `resource_manifest.json`.
- README guidance for typed submissions, main-only release, legacy `end_at` migration, mirror
  trust, and Git revert rollback.

### Security and licensing

- The repository remains pure public resources. It must not contain editor code, build output,
  tokens, cookies, databases, or bot configuration.
- No blanket licence is granted for third-party assets; upstream terms and attribution remain the
  responsibility of each contributor and maintainer.

### Verification boundary

- The current contract is on the Goal 3 working branch until its pull request is merged to `main`.
- The editor's `resource-contract` Check and the plugin's generation validator are the semantic
  gates for duplicate codes, time ordering, file paths, headers, and complete layout.
