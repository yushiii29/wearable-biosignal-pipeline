# 穿戴装置传感器与气囊控制代码

这里整理的是作品集中 **Frame 5：Sensor Test / System Flow** 对应的软件：
三路采集、降噪与特征提取、模型训练和验证、候选判断、电脑向 Arduino
发送指令，以及 Arduino 的气囊定时控制。

主项目的原界面和算法保留。本仓库单独整理，便于复现和上传 GitHub。

## 先运行哪一个

想重新算出 Frame 5 图中的结果：

```bash
python tools/reproduce_frame5.py
```

想在没有设备时跑完整的数据处理演示：

```bash
python tools/demo_pipeline.py
```

想打开之前的测试控制界面：

```bash
python launch_jupyter.py
```

第一次使用，先按 [英文首页](README.md#run-without-hardware) 创建 Python
环境并安装依赖。电脑上原来的 `sensor_demos` 测试环境仍可继续使用。

## 和图上的 A/B/C/D 怎样对应

| 图中板块 | 去哪里看 |
|---|---|
| A 采集、传输、保存 | `lab_suite.py`、`wifi_transport.py`、`combined_panel.py`、ESP32 的 `08_sensor_sync` |
| B 降噪、找峰、提取心率/压力节律/运动特征 | `ecg_analysis.py`、`candidate_rules.py` |
| C 模型、系数、留一验证 | `modeling.py`、`frame5_analysis.py`、`models/` |
| D 判断、串口指令、充放气 | `candidate_rules.py`、`airbag_bridge.py`、Uno 的 `09_airbag_command_bench` |

需要注意版本区别：**图上的静息模型和当前实时运行规则是两套参数**。
图中约 `R ≥ 34.1`、`S ≥ 5.10` 来自离线静息重算；实时脚本保留的是
`R ≥ 34.7853`、旧运动评分 `Q ≥ 9.1508`。S 和 Q 的公式也不同，不能只替换数字。
本次整理没有把尚未验证的离线模型自动接入气囊控制。

所有公式和具体处理参数见 [算法说明](docs/ALGORITHMS.md)。

## 数据在哪里

仓库带有去除姓名、采集时间、设备编号和自由备注的特征表，可以直接重现
模型训练。原始波形仍保留在本机；如果需要在这个仓库里回看，可运行：

```bash
python tools/import_recordings.py /原项目位置/sensor_demos/data/runs
```

再打开 `06_历史波形回看.ipynb`，选择 Python 3，按 Shift+Enter。
导入的数据放在 `data/runs/`，已设置为不进入 Git 提交。

## 已检查的内容

压力零点 `34.068226`、运动界线 `5.103498`、心率拟合零点 `79.514854`
与此前保存的分析结果一致。原模型留一验证结果也已核对。

软件测试共 41 项：40 项通过，1 项因为未导入本机原始波形而跳过。
这些检查没有连接或驱动真实气泵。代码状态和硬件实测范围分别说明在
[Frame 5 对照](docs/FRAME5.md) 和 [硬件说明](docs/HARDWARE.md)。

## GitHub

按你的选择，先上传为 **Private（私有）**。确认后是否改成 Public（公开），
由你决定。注册和上传步骤见 [GitHub 入门说明](docs/GITHUB_START.zh-CN.md)。
