# 资源同步流程

本目录说明 `astrbot_plugin_dna_resources` 各类资源如何同步更新。仓库里每一类素材的来源与更新机制都不同，按下面分类处理，不要混用。

## 资源分类速览

| 目录 | 内容 | 来源 | 更新方式 |
|---|---|---|---|
| `images/role_avatar` | 角色头像 31 | 游戏服 API + CDN | **脚本自动**（A） |
| `images/role_paint` | 角色立绘 29 | 游戏服 API + CDN | **脚本自动**（A） |
| `images/weapon` | 武器图标 64 | 游戏服 API + CDN | **脚本自动**（A） |
| `weekly_item` | 周报物品图标 | 周报 API（需有效登录态） | **脚本半自动**（A，凭证受限） |
| `calendar` | 活动图 | 活动 API `spur/calendar/activity/*` | **脚本半自动**（A 或浏览器抓取） |
| `wiki/{role,weapon,spirit}` | 图鉴静态图 | 插件内置/DNAUID 基线 | **人工迁移**（B-wiki） |
| `guide/<作者>` | 攻略静态图 | B站攻略作者合集 | **脚本自动**（B-guide） |
| `panel` | 卡片通用背景图 | 人工收集 | **人工**（C） |
| `alias/` | 角色/武器别名 | 人工维护 | 人工（PR） |
| `data/redeem_codes.json` | 兑换码 | 历史迁移 + 人工 | 人工（PR） |
| `fonts/` | 渲染字体 | 静态 | 不动 |

---

## A. 游戏服 API 资源（images / weekly_item / calendar）

### 前置

- 同步脚本：`DNA-analysis/script/sync_dna_resources.py`（与插件工作区同机，不在本仓库）。
- 运行环境：`astrbot-plugin-dev/.venv`（含 pycryptodome/requests）。
- 凭证：从已登录插件的数据库中读取，格式 `token:dev_code:d_num:refresh_token`（冒号分隔，作为命令行参数传入；脚本不接收数据库路径）。
- 网络：首次拉取若直连超时，可临时走 `http://127.0.0.1:7890` 代理。

### 拉取最新角色/武器/立绘

```bash
# 读取凭证（脱敏使用，用完即删临时文件）
sqlite3 <插件数据>/dnaby.db \
  "SELECT cookie||':'||dev_code||':'||d_num||':'||refresh_token FROM dnauser LIMIT 1" \
  > /tmp/dna_cred.txt
CRED=$(cat /tmp/dna_cred.txt); rm -f /tmp/dna_cred.txt

# dry-run 预览（不落盘）
astrbot-plugin-dev/.venv/bin/python \
  DNA-analysis/script/sync_dna_resources.py \
  --credential "$CRED" \
  --out <本仓库根> \
  --dry-run

# 实际同步
astrbot-plugin-dev/.venv/bin/python \
  DNA-analysis/script/sync_dna_resources.py \
  --credential "$CRED" \
  --out <本仓库根>
```

要点（实测）：

- `/role/defaultRoleForTool` 需签名（sa/tn+RSA），且 body 必须带 `userId`（从 JWT payload 解析）；脚本已自动处理。
- 服务端响应偶发空（角色列表 0），脚本内置 3 次重试；仍空时等 10~20 秒重跑。
- 凭证的 `d_num` 若过期，`/user/refreshToken` 会失败（222）；**只要现有 token 未失效仍可拉 defaultRoleForTool/getCharDetail**。
- 角色覆盖：31 头像全有；29 立绘（男主 `120101`/`160101` 服务端不返回立绘，正常）；64 武器全有。
- `weekly_item` / `calendar` 需要更严格的登录态（`/role/getItemWeeklyReport` 等接口会校验 d_num），当前多数凭证拉不到；周报图缺失时插件会运行时下载，不影响功能。

### 归档活动日历图（calendar/）

活动 API（`/encourage/calendar/Activity/list`）在浏览器上下文可匿名访问，返回活动含 `icon` 字段：

- 16 个活动中仅约 6 个有 `icon`，其余无图（上游如此，非缺漏）。
- 有图的 URL 形如 `https://herobox-img.yingxiong.com/spur/calendar/activity/<雪花ID>.png`。
- 插件 `calendar_asset(pic)` 按 URL basename 匹配本地文件；仓库里放 `calendar/<basename>` 即免运行时下载。

---

## B-wiki. 图鉴（wiki/）静态素材

- 图鉴 webp **没有生成 API**，是静态图；当前内容来自插件内置纹理（源自 DNAUID 基线，2026-08）。
- 覆盖：wiki role 31 / weapon 64 / spirit 26。
- 新角色/新武器图鉴目前无自动渠道——需要时从 DNAUID 上游（`github.com/tyql688/DNAUID`，`dna_wiki/texture2d/`）或游戏社区产出迁移：

```bash
git clone --depth 1 https://github.com/tyql688/DNAUID.git /tmp/dnauid_upstream
diff -rq /tmp/dnauid_upstream/DNAUID/dna_wiki/texture2d/role <本仓库>/wiki/role
cp -n /tmp/dnauid_upstream/DNAUID/dna_wiki/texture2d/role/*.webp <本仓库>/wiki/role/
```

- `wiki/` 文件名必须等于角色/武器/魔灵**规范名**（与 `alias/*.json` 的键一致），否则图鉴命令 `wiki_asset()` 解析不到。

---

## B-guide. 攻略（guide/）静态素材 —— 来自 B 站攻略作者（持续更新）

### 作者与图源（2026-09 实测验证）

| 作者 | B站 | 合集 | 攻略图位置 | 图特征 |
|---|---|---|---|---|
| **狩月庭攻略组** | mid 3546915226519877 | 合集 6985158 | 角色视频**评论区**"XX养成一图流"回复 | 1080 宽竖长图 |
| **猫冬MT** | mid 91489061 | 合集 7015403「两个陀螺」 | 角色视频**封面** | 2560×1440 |

- 两处图已抽样验证与仓库 `guide/` 中现有文件尺寸/内容对应（如莉兹贝尔 1080×9500、妮弗尔夫人 1080×7300、扶疏 2560×1440）。
- 作者会持续发布新角色攻略视频；**新角色出现时用脚本同步即可**，无需等插件仓库更新。

### 同步脚本（推荐）

```bash
# 脚本：DNA-analysis/script/sync_bili_guide.py（与资源仓库同机）

# dry-run 预览
astrbot-plugin-dev/.venv/bin/python \
  DNA-analysis/script/sync_bili_guide.py --out <本仓库> --dry-run

# 实际同步（只补缺失角色，不覆盖已有）
astrbot-plugin-dev/.venv/bin/python \
  DNA-analysis/script/sync_bili_guide.py --out <本仓库>

# 只同步某作者 / 强制覆盖
... --author 狩月庭攻略组
... --force   # 覆盖已存在同名图（会重拉全量，慎用）
```

行为：
- 拉两合集全部视频 → 按标题关键词识别角色 → 狩月庭翻评论找竖长图、猫冬取封面 → 存 `guide/<作者>/<角色>.webp`。
- 已存在角色跳过（保留本地/修订版）；评论只有横版图时跳过（宁缺毋滥，等作者发正式一图流）。
- 狩月庭评论图 URL 含作者 mid 片段，可用于人工核对。

### 手工对比（备选，不用脚本时）

```bash
git clone --depth 1 https://github.com/tyql688/DNAUID.git /tmp/dnauid_upstream
diff -rq /tmp/dnauid_upstream/DNAUID/dna_guide/texture2d <本仓库>/guide
cp -n /tmp/dnauid_upstream/DNAUID/dna_guide/texture2d/<作者>/*.webp <本仓库>/guide/<作者>/
```

- 上游 DNAUID 仓库仍保有 guide 素材基线，但**作者本人已在 B 站持续更新**，应以 B 站为准。
- `guide/` 文件名需**包含角色名**（`resources.guides_for` 按文件名 casefold 包含匹配），并按作者子目录组织（`guide/狩月庭攻略组/`、`guide/猫冬/`）。

### 覆盖范围说明

- 当前 guide 仅覆盖部分角色（如狩月庭 15、猫冬 11）；无攻略角色是作者尚未发布对应视频，不是搬运遗漏。
- 作者已发布但评论无正式长图的角色（如个别新角色只有横版配置图），脚本会跳过——需作者补发一图流后再同步。

---

## C. panel（卡片通用背景图）

- `panel/` 放卡片**通用背景图**（横版大图，如 `panel_1.png`、`panel_2.png`…）。
- **非角色专属**：不再按 `panel/{charId}.png` 角色命名；用途由插件渲染层决定（作为 hero/卡片背景）。
- 无官方 API 源，人工收集/制作后放入即可；generation 校验（`_ASSET_ROOTS` 含 panel）只要求图片可解码。

---

## D. 共享卡片纹理（textures/）

`textures/` 保存 renderer 共用的背景、banner、frame 和装饰素材，当前按用途分为：

- `common/`、`detail/`、`role/`：角色/武器卡片公共装饰；
- `stamina/`、`sign/`：体力和签到卡片；
- `mh/`、`ann/`、`help/`：密函、公告和帮助卡片；

文件名与插件 resolver 的资源映射保持一致。新增纹理前先核对插件 renderer 的逻辑 key，
不要把 `textures/` 当作任意缓存目录。提交前应对新增图片执行完整 PIL 解码和 SHA-256
manifest 校验。

---

## 提交流程（所有同步后的发布都走 PR）

1. 建独立分支：`git checkout -b sync/<描述>`
2. 只暂存本类资源改动（勿夹带 .DS_Store、运行数据、编辑器文件）
3. 提交：标注来源与权利状态（例：`images 来自游戏服 API；wiki 来自 DNAUID 上游`）
4. PR → 合并。仓库无 branch protection、编辑器 `resource-contract` Check 不一定触发，**合并前本地先过 AGENTS.md 第 5 节验证**。

## 验证清单（同步后必做）

```bash
# 图片可解码 + 无符号链接
find . -type l   # 空
# PIL 解码全部新增图（wiki/guide/webp、images/png）
# 资源索引解析（用插件 venv）
PYTHONPATH=astrbot-plugin-dev/data/plugins/astrbot_plugin_dnaby/src \
  astrbot-plugin-dev/.venv/bin/python -c "
from infrastructure.resources.encyclopedia import EncyclopediaResourceStore
s = EncyclopediaResourceStore.from_root('<本仓库根>')
print(len(s.wiki_assets), len(s.guide_assets))
assert s.wiki_asset('贝蕾妮卡'), '角色图鉴索引失败'
"
```

## 已知边界（如实记录，避免误判）

- 男主（`120101`/`160101`）无官方立绘，`role_paint` 只有 29 张属正常。
- guide 只覆盖 15 角色；其余 17 角色无攻略是攻略组未产出。
- 活动图约 6/16 有 icon；calendar 图少是上游如此。
- 素材权利：wiki/guide/panel 的第三方静态图，公开分发前需确认上游权利（DNAUID 为 GPL-3.0，其携带素材另有归属）。
