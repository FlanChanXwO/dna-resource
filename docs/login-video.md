# 登录背景视频更新

登录页动态背景固定使用：

```text
videos/login/background.mp4
```

不要把新拿到的原始 MP4 直接覆盖后提交。用于 Web progressive playback 的 MP4 应确保 `moov` atom 位于 `mdat` 之前，否则浏览器可能先请求文件尾部才能拿到索引，导致首屏动态背景明显延迟。

## 前置要求

本仓库提供维护脚本：

```text
scripts/prepare_login_video.py
```

运行环境需要：

- Python 3.10+
- `ffmpeg`
- `ffprobe`

脚本只接受 **H.264** 视频流，并且不会自动转码。登录背景在插件中始终静音，因此脚本只保留第一路视频流并移除音轨。

## 更新流程

### 1. 准备源视频

先确认素材来源和使用权限。官方或上游提供的原始文件可以放在仓库外任意临时目录，不需要先覆盖正式文件。

例如：

```text
/tmp/Video_Login_Chapter00.mp4
```

### 2. 运行无损 Web 优化脚本

在仓库根目录执行：

```bash
python3 scripts/prepare_login_video.py /tmp/Video_Login_Chapter00.mp4
```

默认输出到：

```text
videos/login/background.mp4
```

如果源文件本身已经放在目标路径，也可以原地处理：

```bash
python3 scripts/prepare_login_video.py videos/login/background.mp4
```

脚本会先写临时文件，通过全部校验后才原子替换正式文件。

需要输出到其他位置进行预检时：

```bash
python3 scripts/prepare_login_video.py /tmp/source.mp4 --output /tmp/background.faststart.mp4
```

### 3. 检查脚本输出

成功时会打印：

- 输出文件大小；
- H.264 elementary stream 的 SHA-256；
- `moov` offset；
- `mdat` offset。

必须满足：

```text
moov offset < mdat offset
```

脚本还会分别导出处理前后的 H.264 elementary stream 并计算 SHA-256。两边哈希必须完全一致，否则脚本直接失败，不会覆盖目标文件。

这意味着 `-c:v copy` 过程中没有重新编码视频帧，也没有因为 Web 优化降低画质。

### 4. 更新资源版本

视频替换后同步修改 `resource_manifest.json` 中的 `resource_version`，让插件资源状态和快照语义能够明确区分新旧素材。

例如：

```json
"resource_version": "login-media-v6-2026-09-12"
```

版本名只需要保持可读、唯一，并能体现登录媒体发生了变化；不要复用旧版本号。

### 5. 提交前确认 diff

至少检查：

```bash
git status --short
git diff --stat
```

正常的视频更新通常只应包含：

```text
videos/login/background.mp4
resource_manifest.json
```

如果这次同时调整维护脚本或说明文档，再额外出现对应的 `scripts/` / `docs/` 文件即可。

不要提交源视频副本、ffmpeg 临时文件、导出的 `.h264` 文件或其他分析产物。

### 6. PR 说明

PR 中至少写明：

- 视频素材来源；
- 权利状态；
- 原文件与处理后文件大小；
- 编码、分辨率、帧率；
- `moov` / `mdat` offset；
- H.264 SHA-256 无损校验结果。

## 脚本会拒绝的情况

以下情况会直接失败：

- 系统没有 `ffmpeg` 或 `ffprobe`；
- 找不到输入文件；
- 第一视频流不是 H.264；
- remux 前后视频流哈希不同；
- 分辨率、帧率或编码信息发生变化；
- 输出文件仍然不是 Fast Start 布局。

脚本故意**不提供自动有损压缩/转码**。如果未来的视频处理后仍接近或超过 GitHub 单文件限制，应该单独评估编码、分辨率、码率和 GOP 策略，而不是在资源更新脚本里静默降低画质。

## 为什么不能直接上传原始 MP4

MP4 的总大小不是首屏播放速度的唯一因素。对于登录背景，更关键的是浏览器能否在文件开头快速拿到容器索引和首个可解码 GOP。

当前维护流程只解决不会损伤画面的容器层问题：

```text
原始 MP4
  -> H.264 bitstream 保持不变
  -> 移除无用音轨
  -> moov 前移（Fast Start）
  -> 校验视频流 SHA-256
  -> 写入 videos/login/background.mp4
```

如果 Fast Start 后首屏仍慢，应继续排查首个 IDR/keyframe 位置、GOP 长度、服务器 TTFB、HTTP Range 支持和浏览器请求瀑布图，而不是优先牺牲画质。
