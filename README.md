# dna-resource

[`astrbot_plugin_dna`](https://github.com/FlanChanXwO/astrbot_plugin_dna) 的公共运行期资源仓库。

这里存放插件渲染和资料查询所需的**公开资源**，例如角色/武器图片、图鉴、攻略、活动素材、别名、兑换码、字体以及登录媒体等。仓库不包含插件代码，也不应存放 Cookie、Token、账号数据库、Bot 配置、`.env` 或其他私有运行时数据。

插件会把本仓库内容作为候选资源获取到 AstrBot 分配的插件数据目录，完成 manifest、路径和资源可用性校验后再切换为当前可用快照；同步失败时不应破坏已有的已验证资源。

## 目录说明

实际运行期布局以 [`resource_manifest.json`](./resource_manifest.json) 为准。目前主要目录如下：

| 路径 | 内容 |
| --- | --- |
| `fonts/` | 卡片渲染使用的字体资源 |
| `images/` | 角色头像、角色立绘、武器图片等基础素材 |
| `videos/` | 登录页面背景视频等视频资源 |
| `audios/` | 登录页面背景音乐等音频资源 |
| `panel/` | 角色面板等卡片使用的通用背景素材 |
| `alias/` | 角色与武器别名表 |
| `data/` | 结构化公共数据，目前包含兑换码清单 |
| `schemas/` | 公共数据对应的 JSON Schema |
| `wiki/role/` | 角色图鉴图片 |
| `wiki/weapon/` | 武器图鉴图片 |
| `wiki/spirit/` | 魔灵图鉴图片 |
| `guide/` | 按攻略作者整理的攻略图片 |
| `weekly_item/` | 周报等功能使用的物品图标 |
| `calendar/` | 活动日历相关图片 |
| `textures/` | 角色卡、签到、体力、公告、帮助等共享渲染纹理 |

`textures/` 与 `calendar/`、`wiki/`、`guide/` 分开维护：前者是 renderer 共用的背景、frame 和装饰素材，后几类则分别承载活动或按内容索引的图片。

不要自行创建新的资源路径约定。新增资源类型前，应先确认插件端已经有对应的读取/渲染逻辑，再同步修改 manifest 与相关校验。

## 插件如何使用这些资源

插件端当前提供的资源管理命令包括：

- `dna资源状态`：查看当前资源快照和最近同步状态；
- `dna同步资源`：从本仓库获取候选内容，校验通过后更新当前资源。

精确命令和权限以插件仓库的 [`commands.json`](https://github.com/FlanChanXwO/astrbot_plugin_dna/blob/main/commands.json) 为准。

资源同步遵循“**候选 → 校验 → 发布**”的流程。`resource_manifest.json`、必要目录、JSON 数据和可解码图片等检查未通过时，候选版本不应成为当前资源。

## 资源来源与维护方式

不同目录的来源并不相同，也不应假设所有资源都能通过同一个上游自动生成。

### 可从游戏服务同步的资源

角色/武器基础图片、部分周报物品和活动素材主要来自《二重螺旋》公开游戏服务接口及其 CDN。维护时应优先按接口实际返回结果增量同步，避免因为某个账号暂时没有返回某项数据而误删仓库中已有资源。

### 静态图鉴、攻略与渲染纹理

- `wiki/`：图鉴静态图，权威上游是**皎皎角（`dnabbs.yingxiong.com`）官方 Wiki 详情页**。新角色、武器或魔灵缺图时，先在该站确认词条（`/forum/wiki/condition` + `/forum/wiki/list` 拿 `wikiId`），再抓取整页长图归一到既有 2460 宽 webp；具体坐标与步骤见 [`docs/sync.md`](./docs/sync.md) 的 B-wiki。
- `guide/`：主要整理公开发布的攻略图片，并按作者分目录保存。提交时应保留来源信息并尊重原作者的使用要求。
- `panel/`：通用卡片背景等人工维护素材，不属于角色接口自动同步内容。
- `textures/`：插件多个 renderer 共用的背景、banner、frame 和装饰素材；文件名与插件资源映射保持一致，不应作为任意缓存目录使用。

### 别名与兑换码

- `alias/`：人工维护，新增别名时要避免同名或包含关系造成解析歧义。
- [`data/redeem_codes.json`](./data/redeem_codes.json)：插件当前读取的兑换码事实源。
- [`schemas/redeem-codes.v1.schema.json`](./schemas/redeem-codes.v1.schema.json)：兑换码数据结构约束。

兑换码条目的 `code` 为必填字段；`reward`、`valid_from`、`expires_at`、`platforms`、`servers` 为可选字段。时间必须带时区，区服当前使用 `cn` / `global`，平台当前使用 `pc` / `android` / `ios`。

未注明区服或平台时，应保持字段缺省，不要自行推断为“全服”或“全平台”。对有效期不确定的兑换码，也不要凭猜测填写截止时间。

## 更新与贡献

本仓库是资源仓库，不是通用文件投放区。建议所有改动通过独立分支和 Pull Request 进入 `main`，不要直接向 `main` 写入未经校验的内容。

提交前至少确认：

1. 文件位于现有资源契约允许的目录；
2. JSON 文件可解析，并满足对应 Schema 和语义约束；
3. 图片文件可以正常解码；
4. 没有符号链接、绝对路径或 `..` 路径逃逸；
5. 没有提交 Cookie、Token、数据库、配置文件或其他敏感数据；
6. 第三方图片/攻略等素材已经注明来源，且没有把“来源公开”误写成“可任意再分发”。

## 权利说明

本仓库中的素材可能来自游戏官方、上游开源项目或社区作者，各自的授权和使用条件可能不同。

仓库根目录没有统一许可证，并不代表所有第三方素材被统一授权。插件源码本身的许可证也不会自动覆盖本仓库中的图片、字体、攻略等外部资源。转载或在本项目之外重新分发前，请确认对应素材的原始来源和使用条款。

## 相关项目

- 插件：[`FlanChanXwO/astrbot_plugin_dna`](https://github.com/FlanChanXwO/astrbot_plugin_dna)
