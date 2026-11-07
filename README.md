# DongXiang

用于在 **Codex Cloud** 中验证数字动享服务连通性、读取场馆定位配置，并可选检查自己账号的登录会话。

当前工具只有只读 GET 请求。它不会改变设备 GPS，也没有图片上传或打卡提交功能。公开接口成功，不代表账号鉴权、坐标提交或打卡业务已经通过。

## 创建 Codex Cloud 环境

1. 在 Codex 新任务中选择 **Work in → Cloud → Create environment**。
2. 选择此仓库 `sistreeee/DongXiang`，让 Codex准备默认环境。
3. 要求提供 **Python 3.9 或更新版本**；没有第三方 Python 依赖。
4. 如需填写安装／准备脚本，填写：

   ```sh
   sh scripts/setup.sh
   ```

5. 在网络配置的 **Additional allowed domains** 中添加：

   ```text
   www.dongxiangsz.cn
   ```

   仅启用软件包下载域名，不会自动允许访问此服务。请求应沿用云环境配置的 HTTPS 代理。
6. 初次验证时，环境变量和 HTTP secrets 均可留空。环境可见性选择 **Only me**。
7. 检查准备结果，点击 **Publish**，再从发布后的环境开始一个 Cloud 任务。

环境的安装／准备脚本会检查 Python 并运行离线测试，不访问数字动享服务，不需要账号。

参考：[官方 Cloud 环境创建与网络配置](https://learn.chatgpt.com/docs/environments/cloud-environments)。不同界面版本的选项名称可能略有不同。

## 第一次运行：公开接口检查

```sh
python3 cloud-location-check.py
```

默认仅访问：

```text
GET https://www.dongxiangsz.cn/api/fitness/venues
```

输出包括 HTTP 状态、业务状态和公开场馆信息。两项状态均为 `200` 时，`public_service.success` 为 `true`。

2026-11-06 已核对的“动享”场馆配置：

| 参数 | 值 |
| --- | --- |
| 场馆 ID | 1 |
| 纬度 | 36.1704810 |
| 经度 | 116.7546120 |
| 配置半径 | 600 米 |

小程序打卡页请求 WGS84 坐标。脚本输出中的 `reference_location_wgs84` 只是本次研究的参考点；`venues` 才是服务当次返回的配置。工具不会把该参考点设置成当前位置。

## 可选：检查自己的账号会话

先通过自己账号的正常授权流程获得有效会话，再配置 `DONGXIANG_TOKEN`。此仓库不提供从本机微信中提取会话的工具。

推荐在 Codex Cloud 的 **HTTP secret／Network secret** 中设置：

| 字段 | 填写内容 |
| --- | --- |
| Key | `DONGXIANG_TOKEN` |
| Value | 自己账号的原始会话字符串，不含 `Bearer ` 前缀 |
| Allowed domains | `www.dongxiangsz.cn` |

云环境须请求并提供该 Key。程序可接收由 Cloud 代理替换的占位值；不要把秘密值写入仓库、脚本、命令参数或聊天文本。

配置好后运行：

```sh
python3 cloud-location-check.py --check-session
```

这会额外访问 `GET /api/user`，使用客户端对应的 `Authori-zation` 请求头。只输出鉴权状态，不输出用户资料、会话或服务端原始消息。未提供有效会话时，报告 `missing_or_invalid_DONGXIANG_TOKEN` 并退出，不发送账号查询。

已见客户端把业务状态 `110002`、`110003`、`110004` 视为登录失效。会话到期后需要正常重新登录；目前未验证自动续期或 Cloud 登录流程。

## 检查与返回码

```sh
python3 -m unittest discover -s tests -v
```

测试使用本机临时 HTTP 服务和虚构凭据，覆盖响应判断、敏感字段过滤、显式会话检查与重定向保护，不调用线上账号或打卡接口。

- `0`：本次请求的检查均成功。
- `1`：连接、响应或可选会话检查未通过。
- `2`：命令参数不正确。

本机运行通过与 Cloud 中运行通过是两个不同的结果，记录结果时应注明执行环境。

## 给 Cloud 任务的第一条指令

> 请先阅读 README.md 和 AGENTS.md，运行离线测试，然后运行 `python3 cloud-location-check.py`。报告实际执行环境、HTTP 状态、业务状态、场馆坐标和半径；先只验证公开服务的连通性。
