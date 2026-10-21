# Changelog

## 公开资料刷新 — 2026-10-21

### Updated

- 对照官方 Wiki 全部 132 个条目的详情修订时间，刷新已修订图鉴，并补齐水主男女、圣血·鞭刃、血染织羽及三把灾厄武器的图鉴。伊薇的图鉴同时更新到既有 `艾达（？？）` 路径，保留旧名、新名查询。
- 新增猫冬MT [法露茜攻略](https://www.bilibili.com/video/BV1CCbV6HEXp/)，使用作者 [伊薇攻略](https://www.bilibili.com/video/BV1dV3e6DEto/) 更新 `艾达（？？）` 攻略图片。黎瑟与黎瑟·浴火仍独立。
- 新增国服码 `螺友的酒`，来源为皎皎角社区的[1.7 前瞻直播总结](https://dnabbs.yingxiong.com/pc/detail/891904553652324430)及其中的直播奖励截图；新增国际服码 `TOWARDSTHEDAWN`，来源为[官方繁中账号的前瞻直播文章](https://x.com/DNAbyss_TC/status/2111036124105982375)。
- 资源版本统一提升为 `16`；manifest 由合并后 workflow 生成。

### Sources and limits

- Wiki 来自皎皎角匿名 `/forum/wiki/list`、`/forum/wiki/getDetail` 及详情页；按官方修订时间与本地提交日期筛选，未因接口未返回删除旧资源。少数超长图受 WebP 的 16383 像素边长限制等比缩小，保留完整正文。
- 两个新兑换码均未找到明确截止时间，不填虚构期限；国际服码的官方文章未列奖励，暂不填奖励。收录代表有公开发布依据，不代表已通过账号试兑。既有码保留已有明确失效时间；汇总站有效性互相冲突的旧码未据此增删。
- 狩月庭合集本次未找到可补入的新版正式角色长图，保留已有攻略。后续开放武器「帽匠的宴会」「无解谜题」仍无公开 Wiki 条目，不伪造图鉴。
- Wiki 内容、游戏图片及攻略图的权利属于官方与各贡献者／作者；公开可访问不代表取得任意再分发授权。

## 行于破晓 — 2026-10-20

### Added

- 新增「黎瑟·浴火」独立规范名、头像和立绘（游戏 ID `4103`），不覆盖原「黎瑟」。
- 新增「活着的重量」（`20306`）、「帽匠的宴会」（`20605`）图片，以及三把新武器的规范名。
- 新增「黎瑟·浴火」「活着的重量」图鉴，取自皎皎角官方 Wiki 详情页：
  [黎瑟·浴火](https://dnabbs.yingxiong.com/pc/wiki/wikidetail/891154407784187761)、
  [活着的重量](https://dnabbs.yingxiong.com/pc/wiki/wikidetail/892824858444957009)。
- 新增[猫冬MT 的黎瑟·浴火攻略](https://www.bilibili.com/video/BV1T3nw6KEF4/)，沿用该作者的视频封面图来源。

### Sources and availability

- 基础图片来自官方匿名 `role/build/config` 返回的真实游戏 ID 与公开 CDN 地址。
- 「帽匠的宴会」「无解谜题」按[官方版本公告](https://www.taptap.cn/moment/860116162199948925)收录名称，获取于 11 月 10 日开放；不表示当前已可获取。
- 官方 Wiki 尚无这两把后续武器的词条；`buildConfig` 尚未提供「无解谜题」的 ID 和图片，因此未伪造图鉴或资源 ID。
- 狩月庭攻略组既有合集中尚未检出本角色的新攻略。日历活动接口本次匿名请求未成功，未据此删除旧活动图片。
- 游戏官方及攻略作者保留各自素材权利；公开可访问不代表已取得任意再分发授权。

### Login video

- 已从官方 1.7 安卓包按 HTTP Range 提取实际登录 MP4，并核对后续 Media 补丁没有覆盖该路径。
- 无损 Fast Start 处理后，H.264 视频流与已有 `videos/login/background.mp4` 完全一致，因此保留现有视频，避免仅为容器差异重复替换。
- 原始包、解包工具、索引与临时视频不进入资源仓库。资源版本递增到 `15`，manifest 由合并后 workflow 生成。

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
