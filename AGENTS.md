# AGENTS.md — astrbot_plugin_dna_resources

本文件约束在本仓库工作的智能体（agent/模型）。内容按「仓库性质 → 目录契约 → 素材来源与同步 → 提交流程 → 验证 → 禁令」组织；所有规则服务于一个目标：**让本仓库始终是「可被 `astrbot_plugin_dnaby` 插件安全消费的纯公开资源」**。

## 0. 仓库性质（一切判断的出发点）

- 本仓库是 **`astrbot_plugin_dnaby` 的公共运行期资源**，主要放公开资源素材与布局标记；`scripts/` 仅允许存放维护这些公开资源所需的轻量工具，不属于插件运行时依赖。
- 仓库**不是**：插件业务代码仓库、编辑器仓库、运行时数据目录、个人文件备份。
- 参照实现（只读）：插件源码在 `astrbot-plugin-dev/data/plugins/astrbot_plugin_dnaby`；编辑器在 `dna-resource-editor`。需要弄清"某目录被怎么消费"时，去插件 `src/infrastructure/resources/`、`src/infrastructure/rendering/` 查 `EncyclopediaResourceStore` / `ResourceMap` / `generation.py` 的实际读取路径，不要靠猜。

## 1. 语言

- 默认简体中文；代码标识符/文件名保持英文或游戏原名（中文角色名文件按现有命名沿用）。
- 注释/文档默认中文；仓库对外 README 目前为英文，新增 docs 可中文，保持一致即可。

## 2. 目录契约（manifest 约束）

`resource_manifest.json` 的 `required_dirs` 声明运行期布局，**新增运行期资源必须落在这些目录或其既有子结构内**：

```
fonts/            # 渲染字体（dna_fonts.ttf 等）
images/           # 角色头像 role_avatar/{charId}.png、立绘 role_paint/{charId}.png、武器 weapon/{weaponId}.png
videos/           # 登录背景视频等视频资源；当前固定 videos/login/background.mp4
panel/            # 卡片通用背景图（如 panel_1.png…，横版大图；非角色专属）
alias/            # char_alias.json / weapon_alias.json（别名）
data/             # redeem_codes.json（兑换码 v1，唯一权威源）+ schemas/ 校验
schemas/          # redeem-codes.v1.schema.json
wiki/{role,weapon,spirit}/   # 图鉴静态图，文件名=角色/武器/魔灵名（如 贝蕾妮卡.webp）
guide/<作者>/     # 攻略静态图，按作者目录组织（狩月庭攻略组、猫冬…）
weekly_item/      # 周报物品图标 item_{itemId}.png
calendar/         # 活动图（文件名=URL basename）
textures/{ann,common,detail,help,mh,role,sign,stamina}/
                  # 角色卡、签到、体力、公告、帮助等公共卡片纹理
```

- 命名规则由插件消费方决定（见上括号），**不得自创路径模式**；不确定先查插件读取代码。
- `resource_manifest.json` 不含 `images/weapon` 等二级声明属正常——校验只要求列出的目录存在；images 下子目录由渲染器约定。
- 删除/移动文件同理：只能在上述类型化路径内做，且必须评估插件 `EncyclopediaResourceStore`/`ResourceMap` 索引是否随之失效。
- `docs/`、`scripts/`、`AGENTS.md`、`README.md` 等仓库维护文件不属于运行期资源目录；不要把它们加入 `required_dirs`。

## 3. 素材来源与同步（重要）

素材分为自动同步素材和人工维护静态素材，更新方式不能混用。

### 3.1 游戏服 API 可自动同步的（images/ weekly_item/ calendar/ 等）

来源：`dnabbs-api.yingxiong.com`（游戏服）+ `herobox-img.yingxiong.com`（CDN `role/config/...`）。
同步脚本：`DNA-analysis/script/sync_dna_resources.py`（不在本仓库）。要点：

- 凭证经**命令行字符串**传入（`token:dev_code:d_num:refresh_token`），脚本不接收数据库路径。
- 需签名接口（`/role/defaultRoleForTool` 等）走 sa/tn + RSA；`/role/getCharDetail` 等明文。
- body 需带 `userId`（从 JWT token payload 解析）。
- 角色/武器/立绘：`role/defaultRoleForTool` → `role/getCharDetail.paint` 得 URL → 下载改名。
- 覆盖情况：role_avatar 32、role_paint 29（男主 `120101`/`160101` 服务端无立绘）、weapon 66。
- 武器覆盖还包含 3 把**灾厄武器**（`权火将熄`/`无止无休`/`棘刺绝响`），它们只存在于皎皎角 Wiki 的 `武器/灾厄武器`，**不在** `defaultRoleForTool` 的武器列表里，以 wiki 为准。
- 新角色/武器出现：**重跑脚本即可**，接口自动下发新 ID 与 URL。

### 3.2 静态素材（wiki/ guide/ panel/ 一部分）

- **guide 攻略图**：持续来源是 **B 站攻略作者合集**（狩月庭攻略组 mid 3546915226519877 合集 6985158 → 评论区"一图流"长图；猫冬MT mid 91489061 合集 7015403 → 视频封面 2560×1440）。用 `DNA-analysis/script/sync_bili_guide.py` 同步（拉合集→识别角色→下载→存 `guide/<作者>/<角色>.webp`），作者发新视频即可跟更。
- **wiki 图鉴图**：权威上游是**皎皎角（`dnabbs`）官方 Wiki 详情页**，用 `POST /forum/wiki/condition` + `/forum/wiki/list` 拿 `wikiId`，再用 Playwright 抓 `.pec-right` 整页长图。具体坐标与步骤见 `docs/sync.md` 的 B-wiki。不要再用 DNAUID（已弃用，其素材本身就是从皎皎角搬的）。
- **panel**：卡片通用背景图（`panel_N.png` 横版），非角色专属；无官方 API 源，人工补充。

### 3.3 登录背景视频

- 固定目标路径：`videos/login/background.mp4`。
- 新视频属于人工维护素材，确认来源与权利状态后再替换。
- **不要直接提交原始 MP4**。先执行：

```bash
python3 scripts/prepare_login_video.py /path/to/source.mp4
```

- 维护脚本要求输入第一视频流为 H.264，使用 `-c:v copy -movflags +faststart` 做无损 remux；登录背景始终静音，因此只保留第一视频流并移除音轨。
- 脚本会比较 remux 前后的 H.264 elementary stream SHA-256，并检查 `moov` 在 `mdat` 之前；任一校验失败都不得覆盖正式视频。
- 视频更新后必须同步修改 `resource_manifest.json` 的 `resource_version`，不要复用旧版本号。
- 完整流程见 `docs/login-video.md`。

### 3.4 素材权利

- wiki/guide/panel/视频等第三方静态素材权利未在上游确认前，不得宣称"已清权可公开分发"。
- 提交信息与 PR 中应标注素材来源与权利状态。

## 4. 提交流程（发布纪律）

- **不直写 `main`**。改动一律：建独立分支 → 单 commit → PR → 合并。
- 编辑器的 `resource-contract` Check 依赖 GitHub App webhook，**并非所有 PR 都触发**；没有 Check 不代表可绕过自检——提交前本地必须跑通第 5 节验证。
- PR 描述写明：改动内容、素材来源、权利状态、验证结果。
- 涉及兑换码（data/redeem_codes.json）语义变化、manifest 目录变化、alias 变化的，属于高影响改动，需额外谨慎并在 PR 中明确说明。

## 5. 提交前本地验证（必须做）

新增/改动图片后，用插件 venv（`astrbot-plugin-dev/.venv`）实测，不能只看文件存在：

```bash
# 1) 图片可解码性 + 无符号链接（对应插件 generation 校验）
python3 -c "
from PIL import Image
import os
bad = []
for root,_,files in os.walk('wiki'): 
    for f in files:
        if f.endswith(('.webp','.png','.jpg')):
            try: Image.open(os.path.join(root,f)).load()
            except Exception as e: bad.append((root,f,str(e)))
print('bad:', bad)
"
find . -type l   # 必须无输出

# 2) 资源索引可解析（模拟插件 EncyclopediaResourceStore 加载）
PYTHONPATH=astrbot-plugin-dev/data/plugins/astrbot_plugin_dnaby/src \
  astrbot-plugin-dev/.venv/bin/python -c "
from infrastructure.resources.encyclopedia import EncyclopediaResourceStore
s = EncyclopediaResourceStore.from_root('.')
print(len(s.wiki_assets), s.wiki_asset('贝蕾妮卡'))
"
```

- 新增 alias 键时，确认它不在 `alias/*.json` 造成歧义（与现有键冲突）。
- 修改兑换码后，用编辑器 schema + 语义规则（code 唯一、时间有序）校验。
- 修改 `videos/login/background.mp4` 时必须通过 `scripts/prepare_login_video.py` 的 Fast Start 与 H.264 SHA-256 校验，并更新 `resource_version`。

## 6. 禁令（红线）

- 禁止加入：token、cookie、数据库、bot 配置、`.env`、密钥、`cmd_config.json` 类平台配置、编辑器代码/依赖、构建产物。
- 禁止把仓库变成任意文件投放处——运行期内容只放类型化资源路径能解释的文件。
- `scripts/` 只用于资源维护，不得引入插件业务逻辑、运行时依赖、凭证读取、网络账号状态或生成产物。
- 禁止符号链接、绝对路径、`..` 逃逸、非 manifest 目录的新增运行期资源（除非同步改 manifest 且走 PR）。
- 禁止静默把运行时下载缓存（如插件 `resource/` 运行目录内容）当作公共资源提交。
- 禁止在未确认第三方素材权利时声称可公开再分发。
- 图片同步不得覆盖/删除"接口未返回但仓库已有"的文件（某角色可能只是账号未拥有，不是不存在）。

## 7. 常见任务速查

| 任务 | 做法 |
|---|---|
| 新角色头像/立绘/武器图 | 跑 sync_dna_resources.py（3.1），PR 提交新增文件 |
| 攻略缺某角色 | 跑 sync_bili_guide.py（B站作者合集）→ 第 5 节验证 → PR |
| 图鉴缺某角色/武器 | 先用 `/forum/wiki/condition` 找 categorize id → `/forum/wiki/list` 找 `wikiId` → 抓 `.pec-right` 长图归一到 2460 宽 webp（docs/sync.md B-wiki） → 第 5 节验证 → PR |
| 更新登录背景视频 | 跑 `scripts/prepare_login_video.py <源MP4>` → 更新 `resource_version` → 按 `docs/login-video.md` 验证 → PR |
| 兑换码更新 | 只改 data/redeem_codes.json，遵守 schema/语义，走 PR |
| 角色别名/武器别名 | 改 alias/*.json，避免歧义，走 PR |
| 想加新资源类型 | 先查插件消费方是否支持该路径，否则不做 |
| 弄清某目录被谁读 | 查插件 `EncyclopediaResourceStore`/`ResourceMap`/渲染器，不臆测 |
