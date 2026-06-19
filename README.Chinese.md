# visacheck — 本地美签状态监控

一个**本地运行(macOS)** 的小工具,定时查询美国**非移民签证(NIV)** 在
[CEAC](https://ceac.state.gov/CEACStatTracker/Status.aspx) 上的状态,并邮件通知你。
基于 [Andision/CEACStatusBot](https://github.com/Andision/CEACStatusBot) 改造为**纯本地**
运行(不依赖云端、不使用付费打码服务)。

## 为什么只在本地跑

CEAC 有反爬 WAF 会拦截机房 IP,所以本工具设计为**在你自己的电脑、用家庭 IP** 运行。
**不要**放到 CI / GitHub Actions 上跑。验证码由自带的 `captcha.onnx` 模型离线识别(免费)。

## 安装

```bash
python3 -m venv .venv
./.venv/bin/python -m pip install -U pip beautifulsoup4 lxml numpy onnxruntime pillow python-dotenv requests
cp .env.example .env      # 然后填入下面的值
```

`.env`(已在 .gitignore 中,**切勿提交**):

| 字段 | 含义 |
|------|------|
| `LOCATION` | 领区文字,如 `CHINA, BEIJING`(见 `LOCATION.md`) |
| `NUMBER` | DS-160 申请号(`AA...`) |
| `PASSPORT_NUMBER` | 护照号 |
| `SURNAME` | 姓的前 5 个字母 |
| `FROM` / `TO` | 发件 / 收件邮箱(用同一个 Gmail = 自己发给自己) |
| `PASSWORD` | Gmail **应用专用密码**(不是登录密码) |
| `SMTP` | `smtp.gmail.com:465` |

## 使用

```bash
./.venv/bin/python run_check.py              # 轮询:仅在状态变化时发邮件
./.venv/bin/python run_check.py --summary    # 总是发邮件(每晚汇总)
./.venv/bin/python run_check.py --print      # 同时把结果打印到终端
```

变化判断:把 `(状态, 最后更新日期)` 跟 `status_record.json` 里上一条比,**任一不同**即为变化
(日期变了也算)。状态会在**邮件发送成功之后**才写入记录,所以发信临时失败下次会自动重发。

## 定时(launchd)

```bash
bash scheduling/install.sh     # 轮询 00/03/09/12/15/18 + 每晚 21:00 汇总
bash scheduling/uninstall.sh   # 停止所有定时检查
```

- 在你**登录状态下**运行;重启后(登录后)自动恢复。
- 睡眠时不会唤醒电脑;**醒来后会补跑一次**。
- 日志:`logs/visacheck.log`。

## 测试

```bash
./.venv/bin/python -m pip install pytest
./.venv/bin/python -m pytest -q
```
