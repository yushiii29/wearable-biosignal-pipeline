# 第一次上传 GitHub

## 私有与公开

本项目先用 **Private（私有）**。确认代码、说明和展示内容后，可以由仓库
所有者在 GitHub 的仓库设置中改成公开；上传程序不会自动改变可见性。

原始波形、Jupyter 登录信息、个人运行环境和历史界面缓存不进入提交。
训练使用的去除身份信息的特征表和模型参数已经包含在仓库中。

## 注册被限制时

如果注册页显示 **Access is temporarily restricted**，表示 GitHub 暂时
限制了当前设备或网络的访问，尚未进入注册表单。可以先暂停反复刷新，
检查浏览器 JavaScript、扩展、代理或 VPN，再用另一设备或网络测试。
持续受限时通过页面的 Submit feedback 反馈。

[GitHub 官方浏览器排查](https://docs.github.com/en/get-started/using-github/supported-browsers)

注册、密码、邮箱验证和人工验证需要你在 GitHub 官方页面完成。
不要把密码、验证码或个人访问令牌写进项目文件或聊天。

## 注册完成后

1. 登录 GitHub。
2. 使用 GitHub 官方授权页面给上传工具授权；你不需要把密码发给助手。
3. 上传时创建 `wearable-biosignal-pipeline`，可见性设为 **Private**。
4. 上传结束后核对仓库页面的 **Private** 标记。

如果自行使用 GitHub CLI，先登录，然后在项目根目录运行：

```bash
gh auth login --hostname github.com --git-protocol https --web
python tools/publish_private.py
```

脚本会先检查已登录的账号，创建本地 Git 提交，再创建私有仓库并上传。
若本地已有 remote 或同名仓库，会停止并提示检查，不覆盖已有远程内容。
GitHub CLI 与登录凭据不打包进这个仓库。

本地 ZIP 和 Git 提交只能说明上传内容已准备好；只有 GitHub 返回成功并
核对私有状态后，才能认为已完成上传。
